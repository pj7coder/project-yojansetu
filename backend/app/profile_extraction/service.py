"""
CitizenProfileExtractionService — Core Day 24 Service.
Orchestrates language normalization, deterministic fast path, LLM fallback,
type and range validation, conflict detection, and critical-value confirmation.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.eligibility.profile import CitizenProfile
from app.profile_extraction.boolean_parser import BooleanAndStatusParser
from app.profile_extraction.config import get_profile_extraction_settings
from app.profile_extraction.confirmation import ProfileConfirmationPolicy
from app.profile_extraction.conflicts import ProfileConflictDetector
from app.profile_extraction.deterministic import DeterministicProfileExtractor
from app.profile_extraction.dialects import DialectNormalizationService
from app.profile_extraction.llm_extractor import LocalLLMProfileExtractor
from app.profile_extraction.normalizer import CitizenTextNormalizer
from app.profile_extraction.schemas import (
    CandidateProfileUpdate,
    CandidateStatus,
    ConfirmationRequest,
    InputSource,
    IntentType,
    ProfileExtractionResult,
)

logger = logging.getLogger("jansetu.profile_extraction.service")


class CitizenProfileExtractionService:
    """
    Safely bridges natural language speech transcripts and text inputs
    to validated, structured citizen profile facts.
    """

    def __init__(
        self,
        normalizer: Optional[CitizenTextNormalizer] = None,
        dialect_service: Optional[DialectNormalizationService] = None,
        deterministic_extractor: Optional[DeterministicProfileExtractor] = None,
        llm_extractor: Optional[LocalLLMProfileExtractor] = None,
        confirmation_policy: Optional[ProfileConfirmationPolicy] = None,
    ):
        self.settings = get_profile_extraction_settings()
        self.normalizer = normalizer or CitizenTextNormalizer()
        self.dialect_service = dialect_service or DialectNormalizationService()
        self.deterministic = deterministic_extractor or DeterministicProfileExtractor()
        self.llm_extractor = llm_extractor or LocalLLMProfileExtractor()
        self.confirmation_policy = confirmation_policy or ProfileConfirmationPolicy()

    def process_citizen_input(
        self,
        text: str,
        input_source: InputSource = InputSource.TEXT_INPUT,
        expected_field: Optional[str] = None,
        existing_profile: Optional[Dict[str, Any]] = None,
    ) -> ProfileExtractionResult:
        """
        Main end-to-end processing pipeline for citizen speech/text input:
        1. Length & format validation.
        2. Unicode surface normalization.
        3. Vernacular dialect lexicon mapping.
        4. Intent classification (Query, Decline, Unknown, Correction, Profile).
        5. Deterministic fast path extraction.
        6. LLM fallback for open complex natural language.
        7. Range and type validation.
        8. Conflict detection against existing session profile.
        9. Confirmation policy evaluation.
        """
        start_time = time.perf_counter()
        timings: Dict[str, float] = {}
        existing = existing_profile or {}

        # Validation: Reject overly long payloads
        if len(text) > self.settings.profile_extraction_max_input_chars:
            return ProfileExtractionResult(
                input_text=text[:100] + "...",
                normalized_text="",
                intent=IntentType.OTHER,
                status="PAYLOAD_TOO_LARGE",
            )

        # Step 1: Surface Normalization
        t_norm_start = time.perf_counter()
        normalized_surface = self.normalizer.normalize(text)
        timings["surface_normalization_ms"] = round((time.perf_counter() - t_norm_start) * 1000, 3)

        if not normalized_surface:
            return ProfileExtractionResult(
                input_text=text,
                normalized_text="",
                intent=IntentType.OTHER,
                status="EMPTY_INPUT",
            )

        # Step 2: Vernacular Dialect Normalization
        t_dialect_start = time.perf_counter()
        if self.settings.dialect_normalization_enabled:
            normalized_text = self.dialect_service.normalize_dialect(normalized_surface)
        else:
            normalized_text = normalized_surface
        timings["dialect_normalization_ms"] = round((time.perf_counter() - t_dialect_start) * 1000, 3)

        # Step 3: Intent Classification
        intent = BooleanAndStatusParser.detect_intent(normalized_text)

        # Handle explicit User Queries (e.g. 'इस योजना में कितना पैसा मिलता है?')
        if intent == IntentType.USER_QUERY:
            timings["total_ms"] = round((time.perf_counter() - start_time) * 1000, 3)
            return ProfileExtractionResult(
                input_text=text,
                normalized_text=normalized_text,
                intent=IntentType.USER_QUERY,
                need_text=normalized_text,
                candidates=[],
                timings_ms=timings,
                status="USER_QUERY_IDENTIFIED",
            )

        # Handle explicit Decline (e.g. 'मैं नहीं बताना चाहता')
        if intent == IntentType.DECLINE:
            candidates = []
            if expected_field:
                candidates.append(
                    CandidateProfileUpdate(
                        field=expected_field,
                        value=None,
                        source_text=text,
                        input_source=input_source,
                        status=CandidateStatus.ACCEPTED,
                        confirmation_reason="CITIZEN_DECLINED_FIELD",
                    )
                )
            timings["total_ms"] = round((time.perf_counter() - start_time) * 1000, 3)
            return ProfileExtractionResult(
                input_text=text,
                normalized_text=normalized_text,
                intent=IntentType.DECLINE,
                candidates=candidates,
                timings_ms=timings,
                status="DECLINED",
            )

        # Handle explicit Unknown (e.g. 'पता नहीं')
        if intent == IntentType.UNKNOWN_RESPONSE:
            candidates = []
            if expected_field:
                candidates.append(
                    CandidateProfileUpdate(
                        field=expected_field,
                        value=None,
                        source_text=text,
                        input_source=input_source,
                        status=CandidateStatus.ACCEPTED,
                        confirmation_reason="CITIZEN_UNKNOWN_FIELD",
                    )
                )
            timings["total_ms"] = round((time.perf_counter() - start_time) * 1000, 3)
            return ProfileExtractionResult(
                input_text=text,
                normalized_text=normalized_text,
                intent=IntentType.UNKNOWN_RESPONSE,
                candidates=candidates,
                timings_ms=timings,
                status="UNKNOWN_RESPONSE",
            )

        # Step 4: Extraction Engine (Deterministic First)
        candidates: List[CandidateProfileUpdate] = []
        need_text: Optional[str] = None
        t_det_start = time.perf_counter()

        if expected_field:
            candidates = self.deterministic.extract_expected_field(
                normalized_text,
                expected_field=expected_field,
                input_source=input_source,
            )

        if not candidates:
            # Try open utterance deterministic extraction
            candidates, need_text = self.deterministic.extract_open_utterance(
                normalized_text,
                input_source=input_source,
            )

        timings["deterministic_ms"] = round((time.perf_counter() - t_det_start) * 1000, 3)

        # Step 5: LLM Fallback (only for open complex utterances where deterministic found nothing)
        if not candidates and self.settings.profile_llm_extraction_enabled:
            t_llm_start = time.perf_counter()
            llm_candidates = self.llm_extractor.extract_candidates(
                normalized_text,
                input_source=input_source,
                expected_field=expected_field,
            )
            candidates.extend(llm_candidates)
            timings["llm_extraction_ms"] = round((time.perf_counter() - t_llm_start) * 1000, 3)

        # Enforce max facts limit
        if len(candidates) > self.settings.profile_max_facts_per_utterance:
            candidates = candidates[: self.settings.profile_max_facts_per_utterance]

        # Step 6: Validation, Conflict Detection & Confirmation Policy
        validated_candidates: List[CandidateProfileUpdate] = []
        active_confirmation: Optional[ConfirmationRequest] = None

        for cand in candidates:
            # A. Range and type sanity check using CitizenProfile validators
            is_valid = self._validate_field_value(cand.field, cand.value)
            if not is_valid:
                cand.status = CandidateStatus.REJECTED
                cand.confirmation_reason = "INVALID_FIELD_VALUE_RANGE"
                validated_candidates.append(cand)
                continue

            # B. Conflict and correction check against active session
            cand = ProfileConflictDetector.evaluate_conflict(cand, existing, text)

            # C. Confirmation policy evaluation
            cand = self.confirmation_policy.evaluate_confirmation_requirement(cand)
            validated_candidates.append(cand)

            # Queue single active confirmation (prioritize first critical/uncertain fact)
            if cand.requires_confirmation and active_confirmation is None:
                active_confirmation = self.confirmation_policy.create_confirmation_request(cand)

        timings["total_ms"] = round((time.perf_counter() - start_time) * 1000, 3)

        return ProfileExtractionResult(
            input_text=text,
            normalized_text=normalized_text,
            intent=intent,
            need_text=need_text,
            candidates=validated_candidates,
            pending_confirmation=active_confirmation,
            timings_ms=timings,
            status="OK" if validated_candidates else "NO_PROFILE_FACT_EXTRACTED",
        )

    def _validate_field_value(self, field: str, value: Any) -> bool:
        """Validates that candidate values respect CitizenProfile domain bounds."""
        if value is None:
            return True

        if field == "age":
            try:
                v = int(value)
                return 0 <= v <= 125
            except (ValueError, TypeError):
                return False

        if field in ("family_income", "annual_income"):
            try:
                v = float(value)
                return 0 <= v <= 100_000_000
            except (ValueError, TypeError):
                return False

        if field == "disability_percentage":
            try:
                v = float(value)
                return 0 <= v <= 100
            except (ValueError, TypeError):
                return False

        if field == "family_size":
            try:
                v = int(value)
                return 1 <= v <= 50
            except (ValueError, TypeError):
                return False

        if field == "land_holding":
            try:
                v = float(value)
                return 0 <= v <= 10_000
            except (ValueError, TypeError):
                return False

        return True


_GLOBAL_EXTRACTION_SERVICE: Optional[CitizenProfileExtractionService] = None


def get_profile_extraction_service() -> CitizenProfileExtractionService:
    """Returns singleton instance of CitizenProfileExtractionService."""
    global _GLOBAL_EXTRACTION_SERVICE
    if _GLOBAL_EXTRACTION_SERVICE is None:
        _GLOBAL_EXTRACTION_SERVICE = CitizenProfileExtractionService()
    return _GLOBAL_EXTRACTION_SERVICE
