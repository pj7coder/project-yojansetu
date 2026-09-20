from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.search.search_text import SchemeSearchTextBuilder, compute_search_text_hash

logger = logging.getLogger("jansetu.search.metadata_builder")


class SearchMetadataBuilder:
    """
    Constructs normalized SchemeSearchMetadata records from human-verified scheme artifacts.
    Derives standardized beneficiary and occupation tags for indexed SQL filtering.
    """

    @classmethod
    def build_metadata(
        cls,
        canonical_scheme: Dict[str, Any],
        scheme_draft_id: Optional[uuid.UUID] = None,
    ) -> SchemeSearchMetadata:
        scheme = canonical_scheme.get("canonical_scheme") or canonical_scheme.get("scheme") or canonical_scheme

        # 1. Identity
        identity = scheme.get("scheme_identity") or scheme.get("identity") or {}
        scheme_id = str(
            identity.get("scheme_id")
            or scheme.get("scheme_id")
            or scheme.get("internal_scheme_code")
            or canonical_scheme.get("scheme_id")
            or canonical_scheme.get("scheme_draft_id")
            or f"SCHEME-{uuid.uuid4().hex[:8]}"
        )

        name_obj = identity.get("name") or identity.get("official_name") or {}
        if isinstance(name_obj, dict):
            name_en = (
                name_obj.get("en")
                or name_obj.get("english")
                or name_obj.get("raw")
                or identity.get("official_name_raw")
                or "Unknown Scheme"
            )
            name_hi = name_obj.get("hi") or name_obj.get("hindi")
        else:
            name_en = str(name_obj or identity.get("official_name_raw") or "Unknown Scheme")
            name_hi = identity.get("official_name_hi")

        category = identity.get("category")
        origin = identity.get("scheme_origin") or "RAJASTHAN_STATE"
        dept_id = identity.get("department_id")

        # 2. Scope
        scope = scheme.get("scope", {})
        state = scope.get("state") or identity.get("jurisdiction") or "Rajasthan"
        if isinstance(state, list):
            state = state[0] if state else "Rajasthan"
        districts = scope.get("districts", [])
        if not isinstance(districts, list):
            districts = [str(districts)]

        rural_urban = scope.get("rural_urban", "BOTH")
        if rural_urban not in ("RURAL", "URBAN", "BOTH"):
            rural_urban = "BOTH"

        # 3. Controlled Tags Extraction
        beneficiary_tags = cls._extract_beneficiary_tags(scheme)
        occupation_tags = cls._extract_occupation_tags(scheme)

        # 4. Dates
        valid_from, valid_until = cls._extract_validity_dates(scheme)

        # 5. Search Text & Hash
        search_text = SchemeSearchTextBuilder.build_search_text(scheme)
        text_hash = compute_search_text_hash(search_text)

        # Draft ID
        draft_uuid: Optional[uuid.UUID] = None
        raw_draft_id = canonical_scheme.get("scheme_draft_id") or scheme_draft_id
        if raw_draft_id:
            try:
                draft_uuid = uuid.UUID(str(raw_draft_id))
            except ValueError:
                draft_uuid = None

        return SchemeSearchMetadata(
            scheme_id=scheme_id,
            scheme_name=name_en,
            scheme_name_hi=name_hi,
            scheme_draft_id=draft_uuid,
            state=state,
            districts=districts,
            rural_urban=rural_urban,
            scheme_origin=str(origin),
            category=category,
            department_id=uuid.UUID(str(dept_id)) if dept_id else None,
            beneficiary_tags=beneficiary_tags,
            occupation_tags=occupation_tags,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True,
            is_verified=True,
            search_text=search_text,
            search_text_hash=text_hash,
        )

    @classmethod
    def _extract_beneficiary_tags(cls, scheme: Dict[str, Any]) -> List[str]:
        tags = set()
        text_corpus = (
            str(scheme.get("scheme_identity", {}))
            + " "
            + str(scheme.get("identity", {}))
            + " "
            + str(scheme.get("scope", {}))
            + " "
            + str(scheme.get("eligibility", {}))
        ).lower()

        if "farmer" in text_corpus or "किसान" in text_corpus or "कृषक" in text_corpus:
            tags.add("FARMER")
        if "student" in text_corpus or "छात्र" in text_corpus or "विद्यार्थी" in text_corpus:
            tags.add("STUDENT")
        if "senior" in text_corpus or "वृद्ध" in text_corpus or "old age" in text_corpus or "पेंशन" in text_corpus:
            tags.add("SENIOR_CITIZEN")
        if "woman" in text_corpus or "women" in text_corpus or "महिला" in text_corpus or "widow" in text_corpus or "विधवा" in text_corpus:
            tags.add("WOMEN")
        if "disab" in text_corpus or "दिव्यांग" in text_corpus or "handicap" in text_corpus:
            tags.add("PERSON_WITH_DISABILITY")
        if "bpl" in text_corpus or "बीपीएल" in text_corpus or "गरीबी" in text_corpus:
            tags.add("BPL")
        if "labour" in text_corpus or "labor" in text_corpus or "श्रमिक" in text_corpus or "मजदूर" in text_corpus:
            tags.add("LABOURER")

        if not tags:
            tags.add("GENERAL_PUBLIC")

        return sorted(list(tags))

    @classmethod
    def _extract_occupation_tags(cls, scheme: Dict[str, Any]) -> List[str]:
        tags = set()
        text_corpus = (
            str(scheme.get("scheme_identity", {}))
            + " "
            + str(scheme.get("eligibility", {}))
        ).lower()

        if "farmer" in text_corpus or "किसान" in text_corpus or "कृषक" in text_corpus or "खेती" in text_corpus:
            tags.add("FARMER")
        if "artisan" in text_corpus or "कारीगर" in text_corpus or "शिल्पकार" in text_corpus:
            tags.add("ARTISAN")
        if "labour" in text_corpus or "labor" in text_corpus or "श्रमिक" in text_corpus:
            tags.add("LABOURER")
        if "teacher" in text_corpus or "शिक्षक" in text_corpus:
            tags.add("TEACHER")

        return sorted(list(tags))

    @classmethod
    def _extract_validity_dates(cls, scheme: Dict[str, Any]) -> tuple[Optional[date], Optional[date]]:
        valid_from: Optional[date] = None
        valid_until: Optional[date] = None

        for item in scheme.get("important_dates", []):
            event = str(item.get("event_name", "")).lower()
            date_str = item.get("normalized_date")
            if date_str:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if "start" in event or "effective" in event or "valid_from" in event or "launch" in event:
                        valid_from = d
                    elif "end" in event or "expiry" in event or "valid_until" in event or "deadline" in event:
                        valid_until = d
                except Exception:
                    pass

        return valid_from, valid_until
