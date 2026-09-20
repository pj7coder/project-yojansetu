"""
Citizen Discovery Facade for JanSetu.
Orchestrates multi-turn session discovery, active version lookup (Day 19),
rule evaluation (Day 14), question generation (Day 16), and presentation formatting (Day 20).
"""

from datetime import date
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache.verified_rule_cache import get_rule_cache
from app.citizen.presentation import CitizenExplanationService
from app.citizen.questions import CitizenQuestionBuilder
from app.citizen.schemas import (
    CitizenDiscoveryResponse,
    CitizenQuestionDisplay,
    CitizenSchemeCard,
    CitizenSchemeDetailResponse,
    RajasthanDistrictItem,
)
from app.database.models.document import Document
from app.database.models.scheme import Scheme, SchemeVersion
from app.discovery.session_discovery_service import SessionDiscoveryService
from app.questioning.schemas import QuestionReasonCode
from app.sessions.manager import SessionNotFoundError, get_session_manager
from app.versioning.timeline import SchemeTimelineService

logger = logging.getLogger("jansetu.citizen.service")

_DISTRICTS_CACHE: Optional[List[RajasthanDistrictItem]] = None


def load_rajasthan_districts() -> List[RajasthanDistrictItem]:
    """Loads and caches curated Rajasthan districts from reference data."""
    global _DISTRICTS_CACHE
    if _DISTRICTS_CACHE is not None:
        return _DISTRICTS_CACHE

    reg_path = Path(__file__).resolve().parent.parent / "reference_data" / "rajasthan_districts.json"
    items: List[RajasthanDistrictItem] = []
    if reg_path.exists():
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for d in data.get("districts", []):
                    items.append(
                        RajasthanDistrictItem(
                            code=d["code"],
                            name_en=d["name"],
                            name_hi=d.get("name_hi", d["name"]),
                            aliases=d.get("aliases", []),
                            status=d.get("status", "ACTIVE"),
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed loading rajasthan_districts.json: {e}")

    # Sort alphabetically by English name
    items.sort(key=lambda x: x.name_en)
    _DISTRICTS_CACHE = items
    return items


class CitizenDiscoveryFacade:
    """
    Unified citizen orchestration facade.
    Connects ephemeral session profile, candidate filtering, rule evaluation,
    intelligent question selection, and citizen-safe presentation.
    """

    @classmethod
    def discover_for_citizen(
        cls,
        session_id: str,
        db_session: Session,
        need_text: Optional[str] = None,
        evaluation_date: Optional[date] = None,
    ) -> CitizenDiscoveryResponse:
        """
        Executes end-to-end citizen scheme discovery and returns presentation DTOs.
        """
        eval_dt = evaluation_date or date.today()

        # 1. Execute core session discovery
        raw_res = SessionDiscoveryService.discover_with_session(
            session_id=session_id,
            db_session=db_session,
            need_text=need_text,
            evaluation_date=eval_dt,
        )

        # 2. Build CitizenSchemeCards for Eligible Schemes
        eligible_cards: List[CitizenSchemeCard] = []
        for item in raw_res.eligible:
            card = cls._resolve_scheme_card(
                scheme_id=item.scheme_id,
                db_session=db_session,
                evaluation_date=eval_dt,
                status_label="ELIGIBLE",
                passed_ids=item.passed_conditions,
            )
            if card:
                eligible_cards.append(card)

        # 3. Build CitizenSchemeCards for More Info Required
        more_info_cards: List[CitizenSchemeCard] = []
        for item in raw_res.more_information_required:
            card = cls._resolve_scheme_card(
                scheme_id=item.scheme_id,
                db_session=db_session,
                evaluation_date=eval_dt,
                status_label="MORE_INFORMATION_REQUIRED",
                missing_fields=item.missing_fields,
            )
            if card:
                more_info_cards.append(card)

        # 4. Determine Citizen Flow State and Friendly Messages
        state = "COLLECTING_INFORMATION"
        msg_hi = ""
        msg_en = ""

        reason_code = raw_res.next_question.reason_code if raw_res.next_question else None

        if reason_code == QuestionReasonCode.NO_RELEVANT_CANDIDATES:
            state = "NO_CANDIDATES"
            msg_hi = "अभी दी गई जानकारी के आधार पर कोई उपयुक्त सत्यापित योजना नहीं मिली। आप अपनी आवश्यकता बदलकर फिर से खोज सकते हैं।"
            msg_en = "No verified schemes matching your criteria were found. You can try adjusting your need or information."
        elif reason_code == QuestionReasonCode.CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION:
            state = "CANNOT_RESOLVE"
            msg_hi = "कुछ योजनाओं की पात्रता जाँचने के लिए अतिरिक्त जानकारी आवश्यक है जो बताने में असुविधा के कारण उपलब्ध नहीं है।"
            msg_en = "Additional information is required to evaluate remaining schemes."
        elif reason_code == QuestionReasonCode.ENOUGH_CONFIRMED_RESULTS or (
            len(eligible_cards) >= 3 and not (raw_res.next_question and raw_res.next_question.field)
        ):
            state = "RESULTS_READY"
            msg_hi = f"दी गई जानकारी के आधार पर आपके लिए {len(eligible_cards)} योजनाएँ उपयुक्त मिली हैं।"
            msg_en = f"Found {len(eligible_cards)} schemes matching your profile."
        elif raw_res.next_question and raw_res.next_question.field:
            state = "COLLECTING_INFORMATION"
            msg_hi = "आपकी जानकारी के आधार पर सबसे उपयुक्त योजनाएं खोजी जा रही हैं…"
            msg_en = "Finding the most relevant schemes based on your information…"
        elif eligible_cards:
            state = "RESULTS_READY"
            msg_hi = f"दी गई जानकारी के आधार पर आपके लिए {len(eligible_cards)} योजनाएँ उपयुक्त मिली हैं।"
            msg_en = f"Found {len(eligible_cards)} schemes matching your profile."
        else:
            state = "NO_CANDIDATES"
            msg_hi = "अभी दी गई जानकारी के आधार पर कोई उपयुक्त सत्यापित योजना नहीं मिली।"
            msg_en = "No matching schemes found."

        # 5. Format next question display if a question field was chosen
        next_q_display: Optional[CitizenQuestionDisplay] = None
        if raw_res.next_question and raw_res.next_question.field and state == "COLLECTING_INFORMATION":
            next_q_display = CitizenQuestionBuilder.build_question_display(raw_res.next_question)

        return CitizenDiscoveryResponse(
            session_id=session_id,
            state=state,
            message_hi=msg_hi,
            message_en=msg_en,
            eligible=eligible_cards,
            more_information_required=more_info_cards,
            next_question=next_q_display,
            session_summary=raw_res.session_summary,
            total_eligible_count=len(eligible_cards),
            total_more_info_count=len(more_info_cards),
            meta=raw_res.meta.model_dump(),
        )

    @classmethod
    def _resolve_scheme_card(
        cls,
        scheme_id: str,
        db_session: Session,
        evaluation_date: date,
        status_label: str,
        passed_ids: Optional[List[str]] = None,
        missing_fields: Optional[List[str]] = None,
    ) -> Optional[CitizenSchemeCard]:
        """Resolves active scheme metadata to construct a presentation card."""
        rule_cache = get_rule_cache()
        cached_entry = rule_cache.get(scheme_id)

        canonical: Dict[str, Any] = {}
        scheme_name = scheme_id
        scheme_name_hi = None
        scheme_code = scheme_id

        # 1. Try DB lookup for active version first
        timeline = SchemeTimelineService()
        try:
            s_uuid = uuid.UUID(scheme_id)
            scheme_obj = db_session.get(Scheme, s_uuid)
            if scheme_obj:
                scheme_code = scheme_obj.scheme_code
                scheme_name = scheme_obj.name_en
                scheme_name_hi = scheme_obj.name_hi
                active_ver = timeline.get_active_scheme_version(db_session, s_uuid, evaluation_date)
                if active_ver and active_ver.canonical_data:
                    canonical = active_ver.canonical_data
        except (ValueError, TypeError):
            pass

        # 2. Fallback to cached scheme if DB query did not yield canonical
        if not canonical and cached_entry:
            scheme_name = cached_entry.scheme_name or scheme_name
            scheme_name_hi = cached_entry.scheme_name_hi or scheme_name_hi
            canonical = getattr(cached_entry, "raw_canonical", {}) or {}

        # 3. Create card via presentation service
        return CitizenExplanationService.build_scheme_card(
            scheme_id=scheme_id,
            scheme_code=scheme_code,
            name_en=scheme_name,
            name_hi=scheme_name_hi,
            canonical=canonical,
            eligibility_status=status_label,
            missing_fields=missing_fields,
        )

    @classmethod
    def get_citizen_scheme_detail(
        cls,
        scheme_id: str,
        db_session: Session,
        evaluation_date: Optional[date] = None,
    ) -> CitizenSchemeDetailResponse:
        """
        Retrieves citizen-safe detail for the active, human-verified scheme version.
        Guarantees superseded, future, or unverified rules are never presented.
        """
        eval_dt = evaluation_date or date.today()

        # Find Scheme by UUID or scheme_code
        scheme_obj: Optional[Scheme] = None
        try:
            s_uuid = uuid.UUID(scheme_id)
            scheme_obj = db_session.get(Scheme, s_uuid)
        except ValueError:
            stmt = select(Scheme).where(Scheme.scheme_code == scheme_id)
            scheme_obj = db_session.execute(stmt).scalars().first()

        if not scheme_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme '{scheme_id}' was not found in the verified registry.",
            )

        # Get legally active version for eval_dt
        timeline = SchemeTimelineService()
        active_ver = timeline.get_active_scheme_version(db_session, scheme_obj.id, eval_dt)

        if not active_ver:
            # Check if an expired or future version exists to give accurate citizen guidance
            all_versions = (
                db_session.execute(
                    select(SchemeVersion)
                    .where(SchemeVersion.scheme_id == scheme_obj.id)
                    .order_by(SchemeVersion.version_number.desc())
                )
                .scalars()
                .all()
            )
            if not all_versions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="This scheme has no verified versions.",
                )

            latest_v = all_versions[0]
            is_future = latest_v.valid_from and latest_v.valid_from > eval_dt
            is_expired = latest_v.valid_until and latest_v.valid_until < eval_dt

            status_str = "NOT_YET_ACTIVE" if is_future else ("EXPIRED" if is_expired else "NOT_ACTIVE")
            raise HTTPException(
                status_code=status.HTTP_410_GONE if is_expired else status.HTTP_404_NOT_FOUND,
                detail=f"This scheme version is {status_str} for evaluation date {eval_dt}.",
            )

        # Load primary source document if attached
        doc_obj: Optional[Document] = None
        if active_ver.source_document_id:
            doc_obj = db_session.get(Document, active_ver.source_document_id)

        return CitizenExplanationService.build_scheme_detail(
            scheme=scheme_obj,
            version=active_ver,
            doc=doc_obj,
            evaluation_result=None,
        )
