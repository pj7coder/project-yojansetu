from datetime import date, datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.cache.verified_rule_cache import get_rule_cache
from app.discovery.schemas import (
    SessionDiscoveryMeta,
    SessionDiscoveryResponse,
    SessionEligibleSchemeItem,
    SessionMoreInfoSchemeItem,
)
from app.eligibility.engine import EligibilityEngine
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus
from app.embeddings.interface import EmbeddingProvider
from app.embeddings.local_provider import LocalFastEmbedProvider
from app.questioning.schemas import (
    CandidateSchemeMissingInfo,
    NextQuestionResult,
    QuestionReasonCode,
)
from app.questioning.selector import NextQuestionSelector
from app.search.candidate_filter import CandidateFilterService
from app.search.semantic_ranker import SemanticSchemeRanker
from app.sessions.manager import get_session_manager
from app.sessions.schemas import SessionSummary

logger = logging.getLogger("jansetu.discovery.session")


class SessionDiscoveryService:
    """
    Coordinates multi-turn citizen discovery:
    1. Retrieves ephemeral session state from process RAM.
    2. Runs fast SQL candidate filtering.
    3. Fetches compiled AST rules from RAM rule cache (with DB fallback).
    4. Deterministically evaluates candidate eligibility (Day 14).
    5. Optionally computes dense vector semantic ranking for citizen need (Day 15).
    6. Identifies missing information and executes NextQuestionSelector (Day 16).
    7. Updates session candidate tracking and recommends the optimal next question.
    """

    @classmethod
    def discover_with_session(
        cls,
        session_id: str,
        db_session: Session,
        need_text: Optional[str] = None,
        evaluation_date: Optional[date] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> SessionDiscoveryResponse:
        start_time = time.perf_counter()
        session_mgr = get_session_manager()
        rule_cache = get_rule_cache()
        citizen_session = session_mgr.require_session(session_id)

        # 1. Update need_text if newly provided
        active_need = need_text.strip() if need_text else citizen_session.need_text
        if need_text and need_text.strip() != citizen_session.need_text:
            session_mgr.set_need_text(session_id, need_text)

        # 2. Build normalized profile for candidate filter
        profile_obj = CitizenProfile(**citizen_session.profile)
        eval_date = evaluation_date or date.today()

        # 3. Fast SQL Candidate Filtering (High Recall)
        candidate_ids, total_verified_count = CandidateFilterService.filter_candidates(
            session=db_session,
            profile=profile_obj,
            evaluation_date=eval_date,
        )

        initial_cache_hits = rule_cache.metrics.hits
        initial_cache_misses = rule_cache.metrics.misses

        # 4. Fetch compiled rule trees from RAM cache
        compiled_schemes_map = rule_cache.get_many(candidate_ids, session=db_session)

        # 5. Deterministic Evaluation on Candidates
        eligible_raw = []
        more_info_raw = []
        not_eligible_count = 0

        for cid in candidate_ids:
            compiled = compiled_schemes_map.get(cid)
            if not compiled:
                continue

            res = EligibilityEngine.evaluate_scheme(
                scheme=compiled,
                profile=profile_obj,
                evaluation_date=eval_date,
            )

            if res.eligibility_status == EligibilityStatus.ELIGIBLE:
                eligible_raw.append(res)
            elif res.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
                more_info_raw.append(res)
            else:
                not_eligible_count += 1

        # 6. Dense Vector Semantic Ranking (if need_text provided)
        semantic_scores: Dict[str, float] = {}
        semantic_ranking_used = False

        if active_need and (eligible_raw or more_info_raw):
            try:
                provider = embedding_provider or LocalFastEmbedProvider()
                all_active_ids = [r.scheme_id for r in eligible_raw] + [r.scheme_id for r in more_info_raw]
                raw_scores = SemanticSchemeRanker.rank_candidates(
                    session=db_session,
                    need_text=active_need,
                    candidate_scheme_ids=all_active_ids,
                    embedding_provider=provider,
                )
                for sid, sim in raw_scores.items():
                    semantic_scores[sid] = round(sim, 4)
                if raw_scores:
                    semantic_ranking_used = True
            except Exception as e:
                logger.warning(f"Semantic ranking skipped or unavailable: {e}")

        # 7. Convert and sort Candidate Lists
        eligible_items: List[SessionEligibleSchemeItem] = []
        for r in eligible_raw:
            score = semantic_scores.get(r.scheme_id)
            eligible_items.append(
                SessionEligibleSchemeItem(
                    scheme_id=r.scheme_id,
                    scheme_name=r.scheme_name,
                    scheme_name_hi=r.scheme_name_hi,
                    semantic_score=score,
                    passed_conditions=[c.condition_id for c in r.passed_conditions],
                )
            )

        more_info_items: List[SessionMoreInfoSchemeItem] = []
        selector_candidates: List[CandidateSchemeMissingInfo] = []

        for r in more_info_raw:
            score = semantic_scores.get(r.scheme_id)
            missing = [m.field for m in r.missing_fields]
            more_info_items.append(
                SessionMoreInfoSchemeItem(
                    scheme_id=r.scheme_id,
                    scheme_name=r.scheme_name,
                    scheme_name_hi=r.scheme_name_hi,
                    semantic_score=score,
                    missing_fields=missing,
                )
            )
            selector_candidates.append(
                CandidateSchemeMissingInfo(
                    scheme_id=r.scheme_id,
                    scheme_name=r.scheme_name,
                    missing_fields=missing,
                    semantic_score=score,
                )
            )

        # Sort lists by semantic score descending if ranking was used
        if semantic_ranking_used:
            eligible_items.sort(key=lambda x: x.semantic_score or 0.0, reverse=True)
            more_info_items.sort(key=lambda x: x.semantic_score or 0.0, reverse=True)
            selector_candidates.sort(key=lambda x: x.semantic_score or 0.0, reverse=True)

        # 8. Deterministic Next Question Selection
        question_selector = NextQuestionSelector()
        next_question = question_selector.select_next_question(
            eligible_schemes_count=len(eligible_items),
            more_info_schemes=selector_candidates,
            known_profile_fields=set(citizen_session.get_known_field_names()),
            declined_fields=set(citizen_session.get_declined_field_names()),
            field_ask_counts=citizen_session.field_ask_counts,
        )

        # If a question field was selected, track that it has been presented
        if next_question.field:
            session_mgr.record_asked_field(session_id, next_question.field)

        # 9. Update temporary session discovery tracking
        citizen_session.candidate_scheme_ids = candidate_ids
        citizen_session.eligible_scheme_ids = [e.scheme_id for e in eligible_items]
        citizen_session.more_info_scheme_ids = [m.scheme_id for m in more_info_items]
        citizen_session.discovery_version = citizen_session.profile_version

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Calculate cache hit rate for this request
        delta_hits = rule_cache.metrics.hits - initial_cache_hits
        delta_misses = rule_cache.metrics.misses - initial_cache_misses
        total_lookups = delta_hits + delta_misses
        hit_rate = round(delta_hits / total_lookups, 4) if total_lookups > 0 else 1.0

        summary = SessionSummary(
            session_id=citizen_session.session_id,
            known_fields=citizen_session.get_known_field_names(),
            declined_fields=citizen_session.get_declined_field_names(),
            asked_fields=list(citizen_session.asked_fields),
            need_text=citizen_session.need_text,
            expires_at=citizen_session.expires_at,
            created_at=citizen_session.created_at,
            updated_at=citizen_session.updated_at,
            profile_version=citizen_session.profile_version,
        )

        return SessionDiscoveryResponse(
            session_id=citizen_session.session_id,
            eligible=eligible_items,
            more_information_required=more_info_items,
            next_question=next_question,
            session_summary=summary,
            meta=SessionDiscoveryMeta(
                total_candidates=len(candidate_ids),
                eligible_count=len(eligible_items),
                more_info_count=len(more_info_items),
                duration_ms=round(duration_ms, 2),
                semantic_ranking_used=semantic_ranking_used,
                rule_cache_hit_rate=hit_rate,
            ),
        )
