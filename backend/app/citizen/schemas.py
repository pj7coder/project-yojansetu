from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.sessions.schemas import SessionSummary


class QuestionOption(BaseModel):
    """Structured selectable option for single-choice questions."""
    value: str = Field(..., description="Canonical value stored in profile, e.g. MALE, FARMER, OBC")
    label_en: str = Field(..., description="English display label")
    label_hi: str = Field(..., description="Hindi display label")


class CitizenQuestionDisplay(BaseModel):
    """
    Presentation-ready dynamic question model for the citizen UI.
    Contains canonical field, display labels in Hindi and English,
    input type, units, options, and decline configuration.
    """
    field: str = Field(..., description="Canonical profile attribute name (e.g. age, family_income)")
    reason_code: str = Field(..., description="Day 16 question selection justification code")
    affected_scheme_count: int = Field(default=0, description="Number of candidate schemes needing this field")
    data_type: str = Field(..., description="Input UI control: integer, currency, select, boolean, string")
    display_name_en: str = Field(..., description="Attribute name in English")
    display_name_hi: str = Field(..., description="Attribute name in Hindi")
    question_en: str = Field(..., description="Full friendly question sentence in English")
    question_hi: str = Field(..., description="Full friendly question sentence in Hindi")
    options: Optional[List[QuestionOption]] = Field(default=None, description="Selectable choices if applicable")
    unit_en: Optional[str] = Field(default=None, description="Display unit in English (e.g. Years, ₹ per year)")
    unit_hi: Optional[str] = Field(default=None, description="Display unit in Hindi (e.g. वर्ष, ₹ प्रति वर्ष)")
    sensitivity_level: str = Field(default="LOW", description="LOW, MEDIUM, HIGH")
    allow_decline: bool = Field(default=True, description="Whether citizen can decline answering")
    help_text_en: Optional[str] = Field(default=None, description="Optional guidance text in English")
    help_text_hi: Optional[str] = Field(default=None, description="Optional guidance text in Hindi")


class CitizenSchemeCard(BaseModel):
    """
    Safe scheme summary card presented on citizen discovery results.
    Never exposes internal dense vector similarity scores or AST hashes.
    """
    scheme_id: str
    scheme_code: str
    name_en: str
    name_hi: Optional[str] = None
    scheme_name: Optional[str] = None
    scheme_name_hi: Optional[str] = None
    department_en: Optional[str] = None
    department_hi: Optional[str] = None
    purpose_en: Optional[str] = None
    purpose_hi: Optional[str] = None
    primary_benefit_en: Optional[str] = None
    primary_benefit_hi: Optional[str] = None
    eligibility_status: str = Field(..., description="ELIGIBLE or MORE_INFORMATION_REQUIRED")
    why_eligible_summary_hi: List[str] = Field(default_factory=list)
    why_eligible_summary_en: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    missing_fields_display_hi: List[str] = Field(default_factory=list)
    missing_fields_display_en: List[str] = Field(default_factory=list)


class CitizenBenefitItem(BaseModel):
    """Structured citizen benefit presentation."""
    benefit_type: str = Field(..., description="CASH, SUBSIDY, IN_KIND, SERVICE, CONCESSION")
    amount: Optional[float] = None
    currency: str = "INR"
    frequency: Optional[str] = None
    description_en: Optional[str] = None
    description_hi: Optional[str] = None
    display_text_en: Optional[str] = None
    display_text_hi: Optional[str] = None


class CitizenDocumentItem(BaseModel):
    """Structured checklist enclosure requirement."""
    document_name_en: str
    document_name_hi: Optional[str] = None
    is_mandatory: bool = True
    description_en: Optional[str] = None
    description_hi: Optional[str] = None


class CitizenApplicationGuidance(BaseModel):
    """Safe application channels and procedure guidance."""
    channels: List[str] = Field(default_factory=list, description="e.g. e-Mitra, SSO, Department Portal")
    portal_url: Optional[str] = Field(default=None, description="Validated safe HTTP/HTTPS URL")
    is_portal_url_safe: bool = False
    submission_mode: Optional[str] = None
    steps_en: List[str] = Field(default_factory=list)
    steps_hi: List[str] = Field(default_factory=list)
    fee_inr: Optional[float] = None
    guidance_note_en: str = "Apply through designated official government channels. YojanSetu provides guidance and does not directly submit applications."
    guidance_note_hi: str = "नामित आधिकारिक सरकारी माध्यमों से आवेदन करें। योजनसेतु मार्गदर्शन प्रदान करता है और सीधे आवेदन जमा नहीं करता है।"


class CitizenSourceInfo(BaseModel):
    """Citizen-safe official government document reference."""
    department_en: Optional[str] = None
    department_hi: Optional[str] = None
    notification_reference: Optional[str] = None
    source_date: Optional[str] = None
    page_reference: Optional[str] = None
    official_url: Optional[str] = None


class CitizenSchemeDetailResponse(BaseModel):
    """
    Complete citizen-safe detail payload for an active, human-verified scheme version.
    Filters out internal audit records, OCR confidences, reviewer IDs, and rule ASTs.
    """
    scheme_id: str
    scheme_code: str
    name_en: str
    name_hi: Optional[str] = None
    version_number: int
    version_label: Optional[str] = None
    status: str = Field(..., description="ACTIVE, NOT_ACTIVE, NOT_YET_ACTIVE, EXPIRED")
    is_active: bool = True
    effective_date: Optional[date] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    department_en: Optional[str] = None
    department_hi: Optional[str] = None
    category_en: Optional[str] = None
    category_hi: Optional[str] = None
    purpose_en: Optional[str] = None
    purpose_hi: Optional[str] = None
    why_eligible_hi: List[str] = Field(default_factory=list)
    why_eligible_en: List[str] = Field(default_factory=list)
    eligibility_conditions_hi: List[str] = Field(default_factory=list)
    eligibility_conditions_en: List[str] = Field(default_factory=list)
    benefits: List[CitizenBenefitItem] = Field(default_factory=list)
    required_documents: List[CitizenDocumentItem] = Field(default_factory=list)
    application: CitizenApplicationGuidance
    important_dates: List[Dict[str, Any]] = Field(default_factory=list)
    official_source: CitizenSourceInfo


class CitizenDiscoveryResponse(BaseModel):
    """
    Top-level conversational response for citizen multi-turn scheme discovery.
    Provides clear visual separation of confirmed eligible vs more-info schemes,
    next recommended question, and flow state.
    """
    session_id: str
    state: str = Field(
        ...,
        description="START, COLLECTING_INFORMATION, RESULTS_READY, NO_CANDIDATES, CANNOT_RESOLVE",
    )
    message_hi: str = ""
    message_en: str = ""
    eligible: List[CitizenSchemeCard] = Field(default_factory=list)
    more_information_required: List[CitizenSchemeCard] = Field(default_factory=list)
    next_question: Optional[CitizenQuestionDisplay] = None
    session_summary: SessionSummary
    total_eligible_count: int = 0
    total_more_info_count: int = 0
    meta: Optional[Dict[str, Any]] = None


class RajasthanDistrictItem(BaseModel):
    """Curated Rajasthan active district reference for citizen selection."""
    code: str
    name_en: str
    name_hi: str
    aliases: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"
