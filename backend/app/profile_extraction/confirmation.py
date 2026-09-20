"""
Confirmation policy engine for critical and uncertain citizen profile facts.
Ensures eligibility-altering values (especially from speech/STT) are explicitly verified
by the citizen before mutating active session state.
"""

from decimal import Decimal
from typing import Any, List, Optional
import uuid

from app.profile_extraction.config import get_profile_extraction_settings
from app.profile_extraction.schemas import (
    CandidateProfileUpdate,
    CandidateStatus,
    ConfirmationOption,
    ConfirmationRequest,
    ExtractionMethod,
    InputSource,
)


def format_display_value(field: str, value: Any, unit: Optional[str] = None, frequency: Optional[str] = None) -> str:
    """Formats raw candidate values into clear, human-readable representations."""
    if value is None:
        return "अज्ञात"

    if isinstance(value, bool):
        return "हाँ (Yes)" if value else "नहीं (No)"

    if field in ("annual_income", "family_income"):
        try:
            num = int(value)
            formatted_inr = f"₹{num:,}"
            period_str = "प्रति वर्ष" if frequency == "ANNUAL" else ("प्रति माह" if frequency == "MONTHLY" else "")
            return f"{formatted_inr} {period_str}".strip()
        except (ValueError, TypeError):
            return f"₹{value}"

    if field == "age":
        return f"{value} वर्ष"

    if field == "disability_percentage":
        return f"{value}%"

    if field == "land_holding":
        u = unit or "बीघा"
        return f"{value} {u}"

    return str(value)


def build_confirmation_question(field: str, display_val: str, is_corr: bool = False) -> tuple[str, str]:
    """Builds deterministic Hindi and English confirmation prompts."""
    prefix_hi = "सुधार के अनुसार, " if is_corr else ""
    prefix_en = "As a correction, " if is_corr else ""

    field_labels_hi = {
        "age": "आयु",
        "family_income": "पारिवारिक आय",
        "annual_income": "वार्षिक आय",
        "district": "जिला",
        "bpl_status": "बीपीएल स्थिति",
        "social_category": "सामाजिक श्रेणी (जाति वर्ग)",
        "disability_status": "दिव्यांगता स्थिति",
        "disability_percentage": "दिव्यांगता प्रतिशत",
        "occupation": "व्यवसाय",
        "land_holding": "भूमि स्वामित्व",
        "domicile_status": "मूल निवास स्थिति",
    }

    field_labels_en = {
        "age": "age",
        "family_income": "family income",
        "annual_income": "annual income",
        "district": "district",
        "bpl_status": "BPL status",
        "social_category": "social category",
        "disability_status": "disability status",
        "disability_percentage": "disability percentage",
        "occupation": "occupation",
        "land_holding": "land holding",
        "domicile_status": "domicile status",
    }

    lbl_hi = field_labels_hi.get(field, field)
    lbl_en = field_labels_en.get(field, field)

    q_hi = f"{prefix_hi}आपने अपनी {lbl_hi} {display_val} बताई है। क्या यह सही है?"
    q_en = f"{prefix_en}You stated your {lbl_en} as {display_val}. Is this correct?"
    return (q_hi, q_en)


class ProfileConfirmationPolicy:
    """
    Evaluates whether an extracted candidate update requires confirmation before application.
    """

    def __init__(self):
        self.settings = get_profile_extraction_settings()

    def evaluate_confirmation_requirement(
        self, candidate: CandidateProfileUpdate
    ) -> CandidateProfileUpdate:
        """
        Determines confirmation requirement based on input source, field criticality,
        approximation, and extraction method.
        """
        # If already flagged (e.g. conflict/correction/range ambiguity), keep status
        if candidate.status in (
            CandidateStatus.CONFLICT_WITH_EXISTING_VALUE,
            CandidateStatus.CONFIRMATION_REQUIRED,
            CandidateStatus.AMBIGUOUS,
        ):
            candidate.requires_confirmation = True
            return candidate

        is_critical_field = candidate.field in self.settings.stt_confirm_fields

        # Rule 1: All critical fields from STT transcripts require confirmation
        if candidate.input_source == InputSource.STT_TRANSCRIPT and is_critical_field:
            candidate.requires_confirmation = True
            candidate.status = CandidateStatus.CONFIRMATION_REQUIRED
            candidate.confirmation_reason = "STT_CRITICAL_VALUE"
            return candidate

        # Rule 2: Approximate values always require confirmation
        if candidate.is_approximate:
            candidate.requires_confirmation = True
            candidate.status = CandidateStatus.CONFIRMATION_REQUIRED
            candidate.confirmation_reason = "APPROXIMATE_VALUE"
            return candidate

        # Rule 3: LLM-assisted extractions for critical fields require confirmation
        if (
            candidate.extraction_method == ExtractionMethod.LLM_ASSISTED
            and is_critical_field
            and self.settings.profile_confirm_llm_assisted_values
        ):
            candidate.requires_confirmation = True
            candidate.status = CandidateStatus.CONFIRMATION_REQUIRED
            candidate.confirmation_reason = "LLM_ASSISTED_CRITICAL_VALUE"
            return candidate

        # Rule 4: Direct structured UI input or non-critical text input can be accepted immediately
        candidate.requires_confirmation = False
        candidate.status = CandidateStatus.ACCEPTED
        return candidate

    def create_confirmation_request(
        self, candidate: CandidateProfileUpdate
    ) -> ConfirmationRequest:
        """Creates a localized ConfirmationRequest for an uncertain or critical candidate fact."""
        display_val = format_display_value(
            candidate.field,
            candidate.value,
            unit=candidate.unit,
            frequency=candidate.frequency,
        )
        q_hi, q_en = build_confirmation_question(
            candidate.field, display_val, is_corr=candidate.is_correction
        )

        options = [
            ConfirmationOption(decision="YES", label_hi="हाँ, सही है", label_en="Yes, correct"),
            ConfirmationOption(decision="NO", label_hi="नहीं, सुधारें", label_en="No, change it"),
        ]

        return ConfirmationRequest(
            confirmation_id=uuid.uuid4().hex,
            field=candidate.field,
            proposed_value=candidate.value,
            display_value=display_val,
            display_question_hi=q_hi,
            display_question_en=q_en,
            options=options,
            reason_code=candidate.confirmation_reason or "SAFETY_CHECK",
            source=candidate.input_source,
            is_correction=candidate.is_correction,
        )
