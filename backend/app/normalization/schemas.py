from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OperatorEnum(str, Enum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    BETWEEN = "BETWEEN"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"


class LogicalGroupType(str, Enum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    CONDITION = "CONDITION"


class NormalizationStatus(str, Enum):
    NORMALIZED = "NORMALIZED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"
    UNSUPPORTED = "UNSUPPORTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class NormalizationMethod(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM_ASSISTED = "LLM_ASSISTED"
    MANUAL = "MANUAL"
    UNRESOLVED = "UNRESOLVED"


class PeriodicityEnum(str, Enum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"
    ONE_TIME = "ONE_TIME"
    PER_SEMESTER = "PER_SEMESTER"
    PER_BENEFICIARY = "PER_BENEFICIARY"
    UNKNOWN = "UNKNOWN"


class BenefitTypeEnum(str, Enum):
    CASH = "CASH"
    PENSION = "PENSION"
    SUBSIDY = "SUBSIDY"
    SCHOLARSHIP = "SCHOLARSHIP"
    INSURANCE = "INSURANCE"
    LOAN = "LOAN"
    REIMBURSEMENT = "REIMBURSEMENT"
    SERVICE = "SERVICE"
    IN_KIND = "IN_KIND"
    CONCESSION = "CONCESSION"
    OTHER = "OTHER"


class DocumentTypeEnum(str, Enum):
    AADHAAR = "AADHAAR"
    JAN_AADHAAR = "JAN_AADHAAR"
    INCOME_CERTIFICATE = "INCOME_CERTIFICATE"
    DOMICILE_CERTIFICATE = "DOMICILE_CERTIFICATE"
    CASTE_CERTIFICATE = "CASTE_CERTIFICATE"
    DISABILITY_CERTIFICATE = "DISABILITY_CERTIFICATE"
    BANK_PASSBOOK = "BANK_PASSBOOK"
    PHOTO = "PHOTO"
    RATION_CARD = "RATION_CARD"
    LAND_RECORD = "LAND_RECORD"
    MARKSHEET = "MARKSHEET"
    OTHER = "OTHER"


class ApplicationChannelEnum(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    EMITRA = "EMITRA"
    SSO = "SSO"
    DEPARTMENT_OFFICE = "DEPARTMENT_OFFICE"
    OTHER = "OTHER"


class SchemeOriginEnum(str, Enum):
    RAJASTHAN_STATE = "RAJASTHAN_STATE"
    CENTRAL = "CENTRAL"
    CENTRALLY_SPONSORED = "CENTRALLY_SPONSORED"
    RAJASTHAN_MODIFIED_CSS = "RAJASTHAN_MODIFIED_CSS"
    UNKNOWN = "UNKNOWN"


class GenderEnum(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    ANY = "ANY"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class SocialCategoryEnum(str, Enum):
    SC = "SC"
    ST = "ST"
    OBC = "OBC"
    EWS = "EWS"
    GENERAL = "GENERAL"
    MINORITY = "MINORITY"
    OTHER = "OTHER"
    ANY = "ANY"
    UNKNOWN = "UNKNOWN"


class ResidencyTypeEnum(str, Enum):
    RESIDENT = "RESIDENT"
    PERMANENT_RESIDENT = "PERMANENT_RESIDENT"
    DOMICILE = "DOMICILE"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Layer 1 & 2 Evidence Provenance
# ---------------------------------------------------------------------------

class EvidenceRegistryItem(BaseModel):
    """
    Standardized, auditable evidence item in the Scheme Draft Evidence Registry.
    Links a canonical fact directly to chunk, blocks, page numbers, and original document.
    """
    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(..., description="Unique evidence reference code, e.g. EVID-001")
    document_id: str = Field(..., description="UUID string of the source PDF document")
    chunk_id: Optional[str] = Field(default=None, description="Stable chunk identifier string")
    page_numbers: List[int] = Field(default_factory=list, description="1-based page numbers in source PDF")
    source_block_ids: List[str] = Field(default_factory=list, description="Bounding block IDs from parser")
    text: str = Field(..., description="Verbatim raw text snippet from source PDF")
    raw_value: Optional[str] = Field(default=None, description="Extracted raw value/phrase")
    extraction_method: str = Field(default="LLM", description="Extraction provenance method")


# ---------------------------------------------------------------------------
# Canonical Scheme Components
# ---------------------------------------------------------------------------

class SchemeNameDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    raw: str = Field(..., description="Preserved raw official scheme name as extracted")
    en: Optional[str] = Field(default=None, description="English official scheme name if present")
    hi: Optional[str] = Field(default=None, description="Hindi official scheme name if present")


class CanonicalIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scheme_id: str = Field(..., description="Stable internal code, e.g. RJ-DRAFT-<UUID>")
    name: SchemeNameDetail = Field(..., description="Official names preservation")
    official_name_raw: Optional[str] = Field(default=None, description="Unmodified raw title text")
    normalized_name_for_matching: str = Field(..., description="Unicode/whitespace normalized name")
    short_name: Optional[str] = Field(default=None, description="Colloquial acronym or abbreviation")
    department: Optional[str] = Field(default=None, description="Government department name")
    department_id: Optional[str] = Field(default=None, description="Resolved registry department UUID if matched")
    category: Optional[str] = Field(default=None, description="Scheme functional category")
    category_id: Optional[str] = Field(default=None, description="Resolved category UUID if matched")
    category_source: Optional[str] = Field(default=None, description="OFFICIAL, INFERRED, or null")
    jurisdiction: str = Field(default="RAJASTHAN", description="Government jurisdiction")
    scheme_origin: SchemeOriginEnum = Field(default=SchemeOriginEnum.UNKNOWN, description="Scheme origin")
    description: Optional[str] = Field(default=None, description="Official scheme overview summary")
    target_beneficiaries: List[str] = Field(default_factory=list, description="Stated target groups")


class CanonicalScope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    state: Optional[str] = Field(default=None, description="State (e.g. 'Rajasthan') or null if not stated")
    districts: List[str] = Field(default_factory=list, description="Specific target districts, empty if statewide")
    rural_urban: str = Field(default="BOTH", description="RURAL, URBAN, BOTH, or UNKNOWN")
    beneficiary_group: List[str] = Field(default_factory=list, description="Special beneficiary cohorts")
    geographical_scope: Optional[str] = Field(default=None, description="Additional scope restrictions")


# ---------------------------------------------------------------------------
# Canonical Eligibility Model
# ---------------------------------------------------------------------------

class EligibilityCondition(BaseModel):
    """Atomic machine-evaluable eligibility condition."""
    model_config = ConfigDict(extra="ignore")

    condition_id: str = Field(..., description="Unique condition identifier, e.g. COND-001")
    field: str = Field(..., description="Controlled field name (age, family_income, annual_income, etc.)")
    operator: OperatorEnum = Field(..., description="Canonical operator: EQ, NE, GT, GTE, LT, LTE, BETWEEN, IN, etc.")
    value: Any = Field(..., description="Normalized machine-readable value (int, float, str, list, bool)")
    value_type: str = Field(default="number", description="number, string, boolean, range, list")
    unit: Optional[str] = Field(default=None, description="years, months, INR, PERCENT, etc.")
    periodicity: Optional[PeriodicityEnum] = Field(default=None, description="For income: MONTHLY, ANNUAL, ONE_TIME")
    raw_text: str = Field(..., description="Preserved original source clause/text")
    normalization_status: NormalizationStatus = Field(default=NormalizationStatus.NORMALIZED)
    normalization_method: NormalizationMethod = Field(default=NormalizationMethod.DETERMINISTIC)
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of evidence snippets supporting this condition")
    custom_field_name: Optional[str] = Field(default=None, description="Description if field == CUSTOM")
    context_qualifier: Optional[str] = Field(default=None, description="Category or contextual scope if conditional")


class RuleGroup(BaseModel):
    """
    Composite hierarchical rule group (AND / OR / NOT).
    Preserves boolean logic structure without flattening.
    """
    model_config = ConfigDict(extra="ignore")

    type: LogicalGroupType = Field(..., description="AND, OR, NOT, or CONDITION")
    children: List[Union["RuleGroup", EligibilityCondition]] = Field(
        default_factory=list,
        description="Nested child rule groups or atomic conditions",
    )
    logical_relationship: Optional[str] = Field(
        default=None,
        description="UNKNOWN if ambiguous in raw text, else matching type",
    )
    raw_text: Optional[str] = Field(default=None, description="Composite sentence or phrasing if available")
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalEligibility(BaseModel):
    """Top-level canonical eligibility structure."""
    model_config = ConfigDict(extra="ignore")

    root_rule: RuleGroup = Field(..., description="Root boolean rule group tree")
    simple_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Quick-lookup map of key simple criteria (min_age, max_age, family_income_max, residency, etc.)",
    )
    field_statuses: Dict[str, NormalizationStatus] = Field(
        default_factory=dict,
        description="Normalization status per field (NORMALIZED, AMBIGUOUS, CONFLICT, etc.)",
    )
    missing_fields_behavior: Dict[str, str] = Field(
        default_factory=dict,
        description="Explicit record of fields unmentioned vs unconstrained (NOT_MENTIONED vs NO_RESTRICTION)",
    )


class CanonicalExclusion(BaseModel):
    """Negative condition or disqualification."""
    model_config = ConfigDict(extra="ignore")

    exclusion_id: str = Field(..., description="Unique identifier, e.g. EXCL-001")
    type: str = Field(default="EXCLUSION", description="EXCLUSION")
    field: Optional[str] = Field(default=None, description="Controlled field if applicable")
    operator: Optional[OperatorEnum] = Field(default=None)
    value: Optional[Any] = Field(default=None)
    raw_text: str = Field(..., description="Verbatim raw text of disqualification or proviso")
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalBenefit(BaseModel):
    """Normalized entitlement or benefit structure."""
    model_config = ConfigDict(extra="ignore")

    benefit_id: str = Field(..., description="Unique identifier, e.g. BEN-001")
    type: BenefitTypeEnum = Field(..., description="CASH, PENSION, SUBSIDY, SCHOLARSHIP, etc.")
    amount: Optional[float] = Field(default=None, description="Normalized amount, null if not stated")
    currency: Optional[str] = Field(default="INR", description="Currency symbol or ISO code")
    frequency: PeriodicityEnum = Field(default=PeriodicityEnum.UNKNOWN, description="MONTHLY, ANNUAL, ONE_TIME, etc.")
    quantity: Optional[float] = Field(default=None, description="For in-kind or metric quantities")
    unit: Optional[str] = Field(default=None, description="Unit of measurement if applicable")
    description: Optional[str] = Field(default=None, description="Descriptive benefit explanation")
    raw_amount_text: Optional[str] = Field(default=None, description="Preserved verbatim amount string")
    raw_text: str = Field(..., description="Full source text snippet describing benefit")
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalDocument(BaseModel):
    """Required identity document, certificate, or proof."""
    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(..., description="Unique identifier, e.g. DOC-REQ-001")
    document_type: DocumentTypeEnum = Field(..., description="Controlled document category")
    name_raw: str = Field(..., description="Verbatim original document name in Hindi/English")
    mandatory: Optional[bool] = Field(default=None, description="True if explicitly mandatory, null if unstated")
    notes: Optional[str] = Field(default=None, description="Issuing authority or instructions")
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalApplication(BaseModel):
    """Normalized application submission procedures and channels."""
    model_config = ConfigDict(extra="ignore")

    channels: List[ApplicationChannelEnum] = Field(default_factory=list, description="Explicit application channels")
    portal_url: Optional[str] = Field(default=None, description="Official online submission URL")
    office: Optional[str] = Field(default=None, description="Designated physical office or officer")
    steps: List[str] = Field(default_factory=list, description="Sequential procedural instructions")
    fees: Optional[str] = Field(default=None, description="Application or processing fee statement")
    application_window: Optional[str] = Field(default=None, description="Opening or closing window summary")
    notes: Optional[str] = Field(default=None, description="Additional submission notes")
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalImportantDate(BaseModel):
    """Deadlines, effective dates, or timelines."""
    model_config = ConfigDict(extra="ignore")

    event_name: str = Field(..., description="Event (e.g. 'application deadline', 'effective date')")
    date_type: str = Field(default="EXACT", description="EXACT, RELATIVE_DURATION, or UNKNOWN")
    normalized_date: Optional[str] = Field(default=None, description="ISO YYYY-MM-DD format if exact")
    raw_date_text: str = Field(..., description="Preserved raw date wording")
    relative_duration: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Relative duration details, e.g. {'value': 30, 'unit': 'days'}",
    )
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalContact(BaseModel):
    """Helpline, nodal office, website, or contact point."""
    model_config = ConfigDict(extra="ignore")

    contact_type: str = Field(default="helpline", description="helpline, website, office, email")
    value: str = Field(..., description="Contact details")
    raw_text: Optional[str] = Field(default=None)
    evidence_refs: List[str] = Field(default_factory=list)


class CanonicalDefinition(BaseModel):
    """Key statutory definitions affecting eligibility."""
    model_config = ConfigDict(extra="ignore")

    term: str = Field(..., description="Defined term (e.g. 'Family', 'Small Farmer')")
    definition: str = Field(..., description="Verbatim definition text from government order")
    evidence_refs: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Conflicts and Diagnostics
# ---------------------------------------------------------------------------

class ConflictValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: Any = Field(..., description="Normalized conflicting value")
    raw_text: str = Field(..., description="Raw wording supporting this value")
    context: Optional[str] = Field(default=None, description="Contextual clause or target group")
    evidence_refs: List[str] = Field(default_factory=list)


class ConflictRecord(BaseModel):
    """Contradiction or conflicting factual statement across chunks."""
    model_config = ConfigDict(extra="ignore")

    conflict_id: str = Field(..., description="Unique conflict identifier, e.g. CONF-001")
    field: str = Field(..., description="Field with conflicting interpretations")
    values: List[ConflictValue] = Field(..., description="Contradicting candidate values")
    status: str = Field(default="REVIEW_REQUIRED", description="REVIEW_REQUIRED")
    explanation: Optional[str] = Field(default=None, description="Explanation of contradiction")


class NormalizationSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fields_normalized: int = Field(default=0)
    fields_ambiguous: int = Field(default=0)
    conflicts: int = Field(default=0)
    unresolved: int = Field(default=0)
    evidence_items_registered: int = Field(default=0)


# ---------------------------------------------------------------------------
# Top-Level Canonical Scheme Draft
# ---------------------------------------------------------------------------

class CanonicalSchemeDraft(BaseModel):
    """
    Top-level Layer 3 Canonical Scheme Representation.
    Fully typed, machine-readable, auditable with end-to-end evidence references.
    """
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0", description="CANONICAL_SCHEMA_VERSION=1.0")
    normalizer_version: str = Field(default="1.0", description="NORMALIZER_VERSION=1.0")
    internal_scheme_code: str = Field(..., description="Internal draft code, e.g. RJ-DRAFT-<UUID>")
    document_id: str = Field(..., description="Source document UUID string")
    status: str = Field(default="READY_FOR_VALIDATION", description="Draft lifecycle status")

    scheme_identity: CanonicalIdentity = Field(..., description="Scheme official identification and metadata")
    scope: CanonicalScope = Field(default_factory=CanonicalScope, description="Geographical and demographic scope")
    eligibility: CanonicalEligibility = Field(..., description="Structured machine-readable eligibility rule tree")
    exclusions: List[CanonicalExclusion] = Field(default_factory=list, description="Negative disqualifications")
    benefits: List[CanonicalBenefit] = Field(default_factory=list, description="Entitlements and assistance")
    required_documents: List[CanonicalDocument] = Field(default_factory=list, description="Checklist enclosures")
    application: CanonicalApplication = Field(default_factory=CanonicalApplication, description="Application procedure")
    important_dates: List[CanonicalImportantDate] = Field(default_factory=list, description="Deadlines and dates")
    contacts: List[CanonicalContact] = Field(default_factory=list, description="Helplines and nodal offices")
    definitions: List[CanonicalDefinition] = Field(default_factory=list, description="Statutory definitions")

    evidence_registry: Dict[str, EvidenceRegistryItem] = Field(
        default_factory=dict,
        description="Immutable registry mapping EVID-XXX to chunk, blocks, page numbers, and verbatim text",
    )
    conflicts: List[ConflictRecord] = Field(default_factory=list, description="Flagged factual contradictions")
    normalization_summary: NormalizationSummary = Field(default_factory=NormalizationSummary)
