from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class VerificationResult(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"


class VerificationReasonCode(str, Enum):
    # Support reason codes
    DIRECT_MATCH = "DIRECT_MATCH"
    NUMERIC_MATCH = "NUMERIC_MATCH"
    NORMALIZED_EQUIVALENCE = "NORMALIZED_EQUIVALENCE"

    # Contradiction reason codes
    VALUE_CONFLICT = "VALUE_CONFLICT"
    OPERATOR_CONFLICT = "OPERATOR_CONFLICT"
    NEGATION_CONFLICT = "NEGATION_CONFLICT"
    UNIT_CONFLICT = "UNIT_CONFLICT"
    PERIOD_CONFLICT = "PERIOD_CONFLICT"
    LOGICAL_CONNECTOR_CONFLICT = "LOGICAL_CONNECTOR_CONFLICT"
    SUBJECT_MISMATCH = "SUBJECT_MISMATCH"

    # Insufficient/Error reason codes
    FACT_NOT_PRESENT = "FACT_NOT_PRESENT"
    PARTIAL_SUPPORT = "PARTIAL_SUPPORT"
    AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    SOURCE_EVIDENCE_CONFLICT = "SOURCE_EVIDENCE_CONFLICT"
    MODEL_ERROR = "MODEL_ERROR"
    BROKEN_LINEAGE = "BROKEN_LINEAGE"


class VerificationMethod(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    COMBINED = "COMBINED"


class FactRiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class FactType(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    LOGICAL_CONNECTOR = "LOGICAL_CONNECTOR"
    EXCLUSION = "EXCLUSION"
    BENEFIT = "BENEFIT"
    DOCUMENT = "DOCUMENT"
    APPLICATION = "APPLICATION"
    DATE = "DATE"
    DEFINITION = "DEFINITION"
    IDENTITY = "IDENTITY"


class VerificationRunStatus(str, Enum):
    EVIDENCE_VERIFYING = "EVIDENCE_VERIFYING"
    VERIFYING = "VERIFYING"
    EVIDENCE_VERIFIED = "EVIDENCE_VERIFIED"
    EVIDENCE_REVIEW_REQUIRED = "EVIDENCE_REVIEW_REQUIRED"
    EVIDENCE_VERIFICATION_FAILED = "EVIDENCE_VERIFICATION_FAILED"
    STALE = "STALE"


# ---------------------------------------------------------------------------
# Verifiable Fact DTOs
# ---------------------------------------------------------------------------

class VerifiableFact(BaseModel):
    """Atomic factual statement extracted from canonical scheme draft."""
    model_config = ConfigDict(extra="ignore")

    fact_id: str = Field(..., description="Stable fact identifier, e.g. FACT-001")
    field_path: str = Field(..., description="Target canonical field dot-notation path")
    fact_type: FactType = Field(..., description="Classification category of the fact")
    risk_level: FactRiskLevel = Field(default=FactRiskLevel.NORMAL, description="Risk criticality")
    statement: str = Field(..., description="Clear human-readable claim being tested")
    canonical_value: Optional[Dict[str, Any]] = Field(default=None, description="Structured parsed canonical payload")
    evidence_refs: List[str] = Field(default_factory=list, description="IDs of supporting evidence records")
    table_context: Optional[str] = Field(default=None, description="Table column/row context if table-derived")


class LLMVerificationResponse(BaseModel):
    """Structured response schema returned by Llama 3.2 3B."""
    model_config = ConfigDict(extra="ignore")

    result: VerificationResult = Field(..., description="Strictly SUPPORTED, CONTRADICTED, or NOT_ENOUGH_EVIDENCE")
    reason_code: VerificationReasonCode = Field(..., description="Standardized classification reason code")
    explanation: Optional[str] = Field(default=None, description="Brief 1-sentence diagnostic rationale")


class FactVerificationDTO(BaseModel):
    """Evaluation result for one atomic claim."""
    model_config = ConfigDict(extra="ignore")

    fact_id: str
    field_path: str
    fact_type: FactType
    risk_level: FactRiskLevel
    statement: str
    canonical_value: Optional[Dict[str, Any]] = None
    evidence_text: Optional[str] = None
    result: VerificationResult
    reason_code: VerificationReasonCode
    explanation: Optional[str] = None
    verification_method: VerificationMethod = VerificationMethod.DETERMINISTIC
    evidence_refs: List[str] = Field(default_factory=list)
    ocr_risk: bool = False
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    duration_ms: Optional[int] = None


class EvidenceVerificationSummaryDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    facts_total: int = 0
    facts_supported: int = 0
    facts_contradicted: int = 0
    facts_insufficient: int = 0
    facts_failed: int = 0
    critical_issues_count: int = 0
    deterministic_count: int = 0
    llm_count: int = 0
    ocr_risk_count: int = 0


class EvidenceVerificationReportDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0"
    verifier_version: str = "1.0"
    prompt_version: str = "1.0"
    scheme_draft_id: str
    canonical_artifact_sha256: str
    status: VerificationRunStatus
    summary: EvidenceVerificationSummaryDTO
    facts: List[FactVerificationDTO] = Field(default_factory=list)
    duration_ms: Optional[int] = None
    created_at: str


# ---------------------------------------------------------------------------
# API Responses
# ---------------------------------------------------------------------------

class FactVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    verification_run_id: uuid.UUID
    scheme_draft_id: uuid.UUID
    fact_id: str
    field_path: str
    fact_type: str
    risk_level: str
    statement: str
    canonical_value: Optional[Dict[str, Any]] = None
    evidence_text: Optional[str] = None
    result: str
    reason_code: str
    explanation: Optional[str] = None
    verification_method: str
    evidence_refs: List[str] = Field(default_factory=list)
    ocr_risk: bool
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime


class EvidenceVerificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheme_draft_id: uuid.UUID
    canonical_artifact_sha256: str
    status: str
    facts_total: int
    facts_supported: int
    facts_contradicted: int
    facts_insufficient: int
    facts_failed: int
    critical_issues_count: int
    verifier_version: str
    prompt_version: str
    schema_version: str
    artifact_path: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    created_at: datetime
