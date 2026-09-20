"""
Pydantic schemas and enums for Citizen Profile Extraction, Normalization & Confirmation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class InputSource(str, Enum):
    """Source channel of the input statement."""
    STT_TRANSCRIPT = "STT_TRANSCRIPT"
    TEXT_INPUT = "TEXT_INPUT"
    STRUCTURED_UI_INPUT = "STRUCTURED_UI_INPUT"


class ExtractionMethod(str, Enum):
    """Method used to extract candidate profile facts."""
    DETERMINISTIC = "DETERMINISTIC"
    LLM_ASSISTED = "LLM_ASSISTED"
    COMBINED = "COMBINED"
    EXPECTED_FIELD_PARSER = "EXPECTED_FIELD_PARSER"


class CandidateStatus(str, Enum):
    """Controlled lifecycle status of an extracted candidate field fact."""
    EXTRACTED = "EXTRACTED"
    VALIDATED = "VALIDATED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICT_WITH_EXISTING_VALUE = "CONFLICT_WITH_EXISTING_VALUE"


class IntentType(str, Enum):
    """High-level communicative intent of the citizen utterance."""
    PROFILE_INFORMATION = "PROFILE_INFORMATION"
    CORRECTION = "CORRECTION"
    UNKNOWN_RESPONSE = "UNKNOWN_RESPONSE"
    DECLINE = "DECLINE"
    USER_QUERY = "USER_QUERY"
    OTHER = "OTHER"


class CandidateProfileUpdate(BaseModel):
    """
    Candidate update for a single citizen profile attribute.
    Encapsulates raw span, canonical value, type safety, and provenance.
    """
    field: str = Field(description="Canonical profile field key, matching CitizenProfile")
    value: Any = Field(description="Normalized typed value (int, Decimal, bool, str)")
    raw_value: Optional[str] = Field(default=None, description="Original unnormalized substring")
    source_text: str = Field(description="Full or clause context string from which fact was extracted")
    input_source: InputSource = Field(default=InputSource.TEXT_INPUT, description="STT or Text origin")
    extraction_method: ExtractionMethod = Field(default=ExtractionMethod.DETERMINISTIC)
    status: CandidateStatus = Field(default=CandidateStatus.EXTRACTED)
    requires_confirmation: bool = Field(default=False)
    confirmation_reason: Optional[str] = Field(default=None)
    normalization_steps: List[str] = Field(default_factory=list)
    is_approximate: bool = Field(default=False, description="True if citizen stated 'लगभग', 'करीब', etc.")
    is_correction: bool = Field(default=False, description="True if statement explicitly corrects previous fact")
    old_value: Optional[Any] = Field(default=None, description="Existing value in session if conflict/correction")
    evidence_text: Optional[str] = Field(default=None)
    unit: Optional[str] = Field(default=None, description="Unit e.g. INR, years, hectares, BIGHA")
    frequency: Optional[str] = Field(default=None, description="ANNUAL or MONTHLY for monetary values")
    range_min: Optional[float] = Field(default=None)
    range_max: Optional[float] = Field(default=None)


class ConfirmationOption(BaseModel):
    """Structured decision option presented to citizen for confirmation."""
    decision: str = Field(description="YES or NO")
    label_hi: str
    label_en: str


class ConfirmationRequest(BaseModel):
    """
    Deterministic confirmation request presented to citizen when candidate fact is uncertain or critical.
    """
    confirmation_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    field: str = Field(description="Profile field under confirmation")
    proposed_value: Any = Field(description="Candidate value awaiting confirmation")
    display_value: str = Field(description="Formatted value for presentation e.g. '₹1,50,000 प्रति वर्ष'")
    display_question_hi: str = Field(description="Localized question in Hindi")
    display_question_en: str = Field(description="Localized question in English")
    options: List[ConfirmationOption] = Field(default_factory=list)
    reason_code: str = Field(description="STT_CRITICAL_VALUE, APPROXIMATE_VALUE, CORRECTION, etc.")
    source: InputSource = Field(default=InputSource.STT_TRANSCRIPT)
    is_correction: bool = Field(default=False)


class ProfileExtractionResult(BaseModel):
    """
    Complete typed output of CitizenProfileExtractionService.
    Does NOT mutate citizen session.
    """
    input_text: str = Field(description="Raw citizen input preserved without alteration")
    normalized_text: str = Field(description="Cleaned, NFC-normalized, Devanagari-digit resolved text")
    intent: IntentType = Field(default=IntentType.PROFILE_INFORMATION)
    need_text: Optional[str] = Field(default=None, description="Natural language assistance need if expressed")
    candidates: List[CandidateProfileUpdate] = Field(default_factory=list)
    pending_confirmation: Optional[ConfirmationRequest] = Field(default=None)
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    status: str = Field(default="OK")
