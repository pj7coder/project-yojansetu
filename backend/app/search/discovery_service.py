from datetime import date
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus
from app.eligibility.service import EligibilityService
from app.embeddings.interface import EmbeddingProvider
from app.embeddings.local_provider import LocalFastEmbedProvider
from app.search.candidate_filter import CandidateFilterService
from app.search.schemas import (
    DiscoveryMeta,
    EligibleSchemeItem,
    MoreInfoSchemeItem,
    SchemeDiscoveryRequest,
    SchemeDiscoveryResponse,
)
from app.search.semantic_ranker import SemanticSchemeRanker, is_pgvector_available

logger = logging.getLogger("yojansetu.search.discovery")


class SchemeDiscoveryService:
    """
    Orchestrates the Day 15 scheme discovery pipeline:
    1. Safe high-recall SQL candidate filtering.
    2. Authoritative Day 14 deterministic eligibility evaluation.
    3. Partitioning into ELIGIBLE, MORE_INFO, and NOT_ELIGIBLE (pruned).
    4. Dense vector semantic ranking over eligible/more-info candidates.
    5. Privacy-safe response construction.
    """

    @classmethod
    def discover_schemes(
        cls,
        session: Session,
        request: SchemeDiscoveryRequest,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> SchemeDiscoveryResponse:
        start_time = time.perf_counter()
        settings = get_settings()
        provider = embedding_provider or LocalFastEmbedProvider()

        # 1. Normalize citizen profile
        profile = CitizenProfile(**request.profile)
        eval_date = request.evaluation_date or date.today()

        # 2. Fast SQL Candidate Filtering (High Recall)
        candidate_ids, total_verified_count = CandidateFilterService.filter_candidates(
            session=session,
            profile=profile,
            evaluation_date=eval_date,
        )

        if not candidate_ids:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return SchemeDiscoveryResponse(
                eligible=[],
                more_information_required=[],
                meta=DiscoveryMeta(
                    candidates_before_filter=total_verified_count,
                    sql_candidates=0,
                    evaluated_count=0,
                    eligible_count=0,
                    more_information_required_count=0,
                    not_eligible_count=0,
                    semantic_ranking_used=False,
                    semantic_ranking_available=provider.is_available(),
                    evaluation_duration_ms=round(duration_ms, 2),
                ),
            )

        # 3. Deterministic Eligibility Evaluation on Candidates
        eval_results = EligibilityService.evaluate_multiple_schemes(
            session=session,
            scheme_ids=candidate_ids,
            profile_data=request.profile,
            evaluation_date=eval_date,
        )

        # 4. Bucket Candidates into Outcomes
        eligible_raw = []
        more_info_raw = []
        not_eligible_count = 0

        for res in eval_results:
            if res.eligibility_status == EligibilityStatus.ELIGIBLE:
                eligible_raw.append(res)
            elif res.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
                more_info_raw.append(res)
            else:
                not_eligible_count += 1  # Excluded from recommendations

        # 5. Semantic Vector Ranking (if citizen provided need_text)
        semantic_ranking_used = False
        relevance_scores: Dict[str, float] = {}

        if request.need_text and request.need_text.strip():
            candidate_pool_for_ranking = [r.scheme_id for r in eligible_raw] + [r.scheme_id for r in more_info_raw]
            if candidate_pool_for_ranking and provider.is_available() and settings.semantic_ranking_enabled:
                relevance_scores = SemanticSchemeRanker.rank_candidates(
                    session=session,
                    need_text=request.need_text,
                    candidate_scheme_ids=candidate_pool_for_ranking,
                    embedding_provider=provider,
                )
                if relevance_scores:
                    semantic_ranking_used = True

        # 6. Assemble Output Items
        limit = min(request.limit, settings.discovery_max_limit)

        eligible_items: List[EligibleSchemeItem] = []
        for r in eligible_raw:
            sim = relevance_scores.get(r.scheme_id)
            eligible_items.append(
                EligibleSchemeItem(
                    scheme_id=r.scheme_id,
                    scheme_name=r.scheme_name,
                    scheme_name_hi=r.scheme_name_hi,
                    eligibility_status=r.eligibility_status,
                    semantic_similarity=sim,
                    passed_conditions=r.passed_conditions if request.include_debug else [],
                )
            )

        more_info_items: List[MoreInfoSchemeItem] = []
        for r in more_info_raw:
            sim = relevance_scores.get(r.scheme_id)
            more_info_items.append(
                MoreInfoSchemeItem(
                    scheme_id=r.scheme_id,
                    scheme_name=r.scheme_name,
                    scheme_name_hi=r.scheme_name_hi,
                    eligibility_status=r.eligibility_status,
                    missing_fields=[m.field for m in r.missing_fields],
                    missing_field_details=r.missing_fields if request.include_debug else [],
                    semantic_similarity=sim,
                )
            )

        # 7. Sorting:
        # If semantic ranking used: sort by similarity descending, then scheme_id ascending
        # Else: sort by scheme_id ascending (deterministic stable ordering)
        if semantic_ranking_used:
            eligible_items.sort(
                key=lambda x: (-(x.semantic_similarity if x.semantic_similarity is not None else -1.0), x.scheme_id)
            )
            more_info_items.sort(
                key=lambda x: (-(x.semantic_similarity if x.semantic_similarity is not None else -1.0), x.scheme_id)
            )
        else:
            eligible_items.sort(key=lambda x: x.scheme_id)
            more_info_items.sort(key=lambda x: x.scheme_id)

        # Apply limits
        eligible_items = eligible_items[:limit]
        more_info_items = more_info_items[:limit]

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 8. Privacy-Preserving Audit Log (NO citizen personal values logged!)
        logger.info(
            f"Scheme discovery executed: candidates={len(candidate_ids)}, "
            f"evaluated={len(eval_results)}, eligible={len(eligible_raw)}, "
            f"more_info={len(more_info_raw)}, semantic_ranking={semantic_ranking_used}, "
            f"duration_ms={round(duration_ms, 2)}"
        )

        return SchemeDiscoveryResponse(
            eligible=eligible_items,
            more_information_required=more_info_items,
            meta=DiscoveryMeta(
                candidates_before_filter=total_verified_count,
                sql_candidates=len(candidate_ids),
                evaluated_count=len(eval_results),
                eligible_count=len(eligible_raw),
                more_information_required_count=len(more_info_raw),
                not_eligible_count=not_eligible_count,
                semantic_ranking_used=semantic_ranking_used,
                semantic_ranking_available=provider.is_available(),
                evaluation_duration_ms=round(duration_ms, 2),
            ),
        )
