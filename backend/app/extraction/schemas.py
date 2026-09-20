from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceItem(BaseModel):
    """
    Standardized, verifiable evidence reference supporting an extracted fact.
    Must contain the exact or near-exact short snippet from the source document.
    """
    model_config = ConfigDict(extra="ignore")

    value: Optional[str] = Field(
        default=None,
        description="The specific extracted fact or value (e.g. '₹2,00,000' or 'Above 58 years')",
    )
    evidence_text: str = Field(
        ...,
        description="Exact or near-exact verbatim text snippet from the source chunk supporting this fact",
    )
    page_numbers: List[int] = Field(
        default_factory=list,
        description="Physical 1-based page numbers from which the evidence text was drawn",
    )
    source_block_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="IDs of the source document blocks containing this evidence",
    )
    chunk_id: Optional[str] = Field(
        default=None,
        description="Stable chunk identifier string where this evidence was found",
    )
    extraction_method: str = Field(
        default="LLM",
        description="Method used to extract this fact ('LLM')",
    )
    validation_status: str = Field(
        default="NOT_CHECKED",
        description="Deterministic verification status: MATCHED, EVIDENCE_MATCH_FAILED, PAGE_MISMATCH, BLOCK_MISMATCH",
    )


class EligibilityConditionExtraction(BaseModel):
    """Individual eligibility criteria clause."""
    model_config = ConfigDict(extra="ignore")

    condition: str = Field(..., description="Stated eligibility criterion in verbatim/source terms")
    logical_connector: Optional[str] = Field(
        default=None,
        description="Logical relationship if explicitly joined with another condition ('AND', 'OR', null)",
    )
    definition: Optional[str] = Field(
        default=None,
        description="Associated definition if defined in context (e.g. 'Family means...')",
    )
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this condition")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "condition" not in data:
                data["condition"] = data.get("evidence_text") or data.get("text") or "Condition"
            if "evidence" not in data:
                ev_text = data.get("evidence_text") or data.get("condition", "")
                data["evidence"] = {"evidence_text": ev_text}
        return data


class ExclusionExtraction(BaseModel):
    """Negative condition, disqualification, exception, or proviso."""
    model_config = ConfigDict(extra="ignore")

    exclusion: str = Field(..., description="Stated exclusion, proviso, or disqualification")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this exclusion")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "exclusion" not in data:
                data["exclusion"] = data.get("evidence_text") or data.get("text") or data.get("condition") or "Exclusion"
            if "evidence" not in data:
                ev_text = data.get("evidence_text") or data.get("exclusion", "")
                data["evidence"] = {"evidence_text": ev_text}
        return data


class BenefitExtraction(BaseModel):
    """Entitlement, cash grant, subsidy, allowance, or in-kind assistance."""
    model_config = ConfigDict(extra="ignore")

    benefit_type: str = Field(
        default="financial_assistance",
        description="Type of benefit: financial_assistance, subsidy, pension, allowance, in_kind",
    )
    raw_amount: Optional[str] = Field(
        default=None,
        description="Preserved raw monetary or quantity string (e.g. '₹1,150', '₹1,000 प्रति माह')",
    )
    frequency_text: Optional[str] = Field(
        default=None,
        description="Preserved frequency wording (e.g. 'per month', 'प्रति माह', 'one-time')",
    )
    description: Optional[str] = Field(
        default=None,
        description="Explanatory text describing the entitlement or tiered criteria",
    )
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this benefit")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "evidence" not in data:
                ev_text = data.get("evidence_text") or data.get("raw_amount") or data.get("description", "")
                data["evidence"] = {"evidence_text": ev_text}
        return data


class DocumentRequirementExtraction(BaseModel):
    """Identity card, certificate, or checklist enclosure."""
    model_config = ConfigDict(extra="ignore")

    document_name: str = Field(..., description="Name of required document (e.g. 'Jan Aadhaar Card')")
    mandatory: Optional[bool] = Field(
        default=True,
        description="True if mandatory, False if optional or alternative",
    )
    description: Optional[str] = Field(
        default=None,
        description="Preserved details or issuing authority instructions",
    )
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this document")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "evidence" not in data:
                ev_text = data.get("evidence_text") or data.get("document_name", "")
                data["evidence"] = {"evidence_text": ev_text}
        return data


class ApplicationStepExtraction(BaseModel):
    """Procedure, portal, or submission step."""
    model_config = ConfigDict(extra="ignore")

    step_order: Optional[int] = Field(
        default=None,
        description="Sequential step number if explicitly enumerated in source, else null",
    )
    channel: Optional[str] = Field(
        default=None,
        description="Explicit channel: e-Mitra, SSO, online portal, department office, offline",
    )
    description: str = Field(..., description="Instruction text for this application step")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this step")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict) and "evidence" not in data:
            data["evidence"] = {"evidence_text": data.get("evidence_text") or data.get("description", "")}
        return data


class ImportantDateExtraction(BaseModel):
    """Deadlines, effective dates, or timelines."""
    model_config = ConfigDict(extra="ignore")

    event_name: str = Field(..., description="Event name (e.g. 'application deadline', 'effective date')")
    raw_date_text: str = Field(..., description="Preserved raw date wording (e.g. '31/03/2026', '30 days')")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this date")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict) and "evidence" not in data:
            data["evidence"] = {"evidence_text": data.get("evidence_text") or data.get("raw_date_text", "")}
        return data


class FinancialRuleExtraction(BaseModel):
    """Income ceiling, budgetary limit, or financial restriction."""
    model_config = ConfigDict(extra="ignore")

    rule_type: str = Field(..., description="Type: income_limit, budget_cap, asset_limit")
    raw_amount_text: str = Field(..., description="Preserved raw amount wording (e.g. '₹2,00,000', '₹2.5 लाख')")
    description: Optional[str] = Field(default=None, description="Details or calculation rules")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this financial rule")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict) and "evidence" not in data:
            data["evidence"] = {"evidence_text": data.get("evidence_text") or data.get("raw_amount_text", "")}
        return data


class ContactExtraction(BaseModel):
    """Helpline, nodal office, website, or contact point."""
    model_config = ConfigDict(extra="ignore")

    contact_type: str = Field(default="helpline", description="helpline, website, office, email")
    value: str = Field(..., description="Phone number, URL, or office address")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this contact")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict) and "evidence" not in data:
            data["evidence"] = {"evidence_text": data.get("evidence_text") or data.get("value", "")}
        return data


class ReferenceExtraction(BaseModel):
    """Government order, gazette notification, or circular reference."""
    model_config = ConfigDict(extra="ignore")

    reference_title: str = Field(..., description="Title of referenced circular or rule")
    reference_number: Optional[str] = Field(default=None, description="Reference or dispatch number")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this reference")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict) and "evidence" not in data:
            data["evidence"] = {"evidence_text": data.get("evidence_text") or data.get("reference_title", "")}
        return data


class AmendmentExtraction(BaseModel):
    """Specific amendment or corrigendum details modifying an earlier scheme order."""
    model_config = ConfigDict(extra="ignore")

    amendment_details: str = Field(..., description="Details of the modification or revision")
    evidence: EvidenceItem = Field(..., description="Verifiable evidence snippet for this amendment")

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat(cls, data: Any) -> Any:
        if isinstance(data, dict) and "evidence" not in data:
            data["evidence"] = {"evidence_text": data.get("evidence_text") or data.get("amendment_details", "")}
        return data


class SchemeRawExtraction(BaseModel):
    """
    Extracted facts for an individual scheme identified in a chunk.
    If multiple schemes appear, multiple instances are created.
    If no scheme content appears in chunk, schemes list is empty.
    """
    model_config = ConfigDict(extra="ignore")

    scheme_name: Optional[str] = Field(
        default=None,
        description="Official scheme title explicitly stated in this chunk, else null",
    )
    department: Optional[str] = Field(
        default=None,
        description="Department name explicitly stated in this chunk, else null",
    )
    purpose: List[EvidenceItem] = Field(
        default_factory=list,
        description="Stated scheme objectives, background, or rationale",
    )
    target_beneficiaries: List[EvidenceItem] = Field(
        default_factory=list,
        description="General target group categories (e.g. elderly residents, small farmers)",
    )
    eligibility_conditions: List[EligibilityConditionExtraction] = Field(
        default_factory=list,
        description="Explicit eligibility criteria statements",
    )
    exclusions: List[ExclusionExtraction] = Field(
        default_factory=list,
        description="Explicit disqualifications, exceptions, or provisos",
    )
    benefits: List[BenefitExtraction] = Field(
        default_factory=list,
        description="Cash grants, allowances, subsidies, or entitlements",
    )
    required_documents: List[DocumentRequirementExtraction] = Field(
        default_factory=list,
        description="Required identity documents, certificates, or proofs",
    )
    application_process: List[ApplicationStepExtraction] = Field(
        default_factory=list,
        description="Procedural application steps and submission channels",
    )
    important_dates: List[ImportantDateExtraction] = Field(
        default_factory=list,
        description="Application start/end dates, timelines, or deadlines",
    )
    financial_values: List[FinancialRuleExtraction] = Field(
        default_factory=list,
        description="Income limits, financial thresholds, or family income caps",
    )
    contacts: List[ContactExtraction] = Field(
        default_factory=list,
        description="Helpline numbers, websites, or contact persons",
    )
    references: List[ReferenceExtraction] = Field(
        default_factory=list,
        description="Citations to prior government circulars or acts",
    )
    amendments: List[AmendmentExtraction] = Field(
        default_factory=list,
        description="Corrigenda, amendments, or revision notes",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_none_lists(cls, data: Any) -> Any:
        if isinstance(data, dict):
            list_fields = [
                "purpose", "target_beneficiaries", "eligibility_conditions",
                "exclusions", "benefits", "required_documents",
                "application_process", "important_dates", "financial_values",
                "contacts", "references", "amendments",
            ]
            for field in list_fields:
                if data.get(field) is None:
                    data[field] = []
        return data


class ChunkExtractionResult(BaseModel):
    """
    Top-level payload returned by the LLM extraction pipeline for a single chunk.
    """
    model_config = ConfigDict(extra="ignore")

    document_id: Optional[str] = Field(default=None)
    chunk_id: Optional[str] = Field(default=None)
    section_type: Optional[str] = Field(default=None)

    schemes: List[SchemeRawExtraction] = Field(
        default_factory=list,
        description="List of schemes identified and parsed from this chunk",
    )
    unassociated_eligibility_rules: List[EligibilityConditionExtraction] = Field(
        default_factory=list,
    )
    unassociated_benefits: List[BenefitExtraction] = Field(
        default_factory=list,
    )
    unassociated_exclusions: List[ExclusionExtraction] = Field(
        default_factory=list,
    )
    unassociated_documents: List[DocumentRequirementExtraction] = Field(
        default_factory=list,
    )
    contradictions_detected: List[Dict[str, Any]] = Field(
        default_factory=list,
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_none_lists(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in [
                "schemes", "unassociated_eligibility_rules", "unassociated_benefits",
                "unassociated_exclusions", "unassociated_documents", "contradictions_detected"
            ]:
                if data.get(field) is None:
                    data[field] = []
        return data
