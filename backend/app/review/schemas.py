from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ReviewSessionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class ReviewDecision(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewActionType(str, Enum):
    REVIEW_STARTED = "REVIEW_STARTED"
    FIELD_APPROVED = "FIELD_APPROVED"
    FIELD_EDITED = "FIELD_EDITED"
    FIELD_REJECTED = "FIELD_REJECTED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"
    VALIDATION_OVERRIDE = "VALIDATION_OVERRIDE"
    VERIFICATION_OVERRIDE = "VERIFICATION_OVERRIDE"
    SCHEME_APPROVED = "SCHEME_APPROVED"
    SCHEME_REJECTED = "SCHEME_REJECTED"
    REVIEW_REOPENED = "REVIEW_REOPENED"


class ConflictResolutionChoice(str, Enum):
    SELECT_VALUE = "SELECT_VALUE"
    KEEP_CONDITIONAL = "KEEP_CONDITIONAL"
    REJECT_FIELD = "REJECT_FIELD"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# API Request Models
# ---------------------------------------------------------------------------

class ItemDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    edit_value: Optional[Dict[str, Any]] = Field(default=None, description="New canonical value if edited")
    reviewer_comment: Optional[str] = Field(default=None, description="Optional commentary")
    edit_reason: Optional[str] = Field(default=None, description="Mandatory explanation when editing")
    override_reason: Optional[str] = Field(default=None, description="Mandatory reason if overriding CONTRADICTED or NOT_ENOUGH_EVIDENCE")


class ConflictResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: ConflictResolutionChoice
    selected_value: Optional[Any] = Field(default=None, description="Chosen candidate value if SELECT_VALUE")
    reason: str = Field(..., description="Mandatory audit explanation for conflict resolution")


class CompleteReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(default=None, description="Final signoff remarks")
    review_version: int = Field(..., description="Optimistic locking review version")


class RejectSchemeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., description="Mandatory explanation for scheme rejection")


class ReopenReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., description="Mandatory explanation for reopening verified scheme")


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class ReviewQueueItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    draft_id: uuid.UUID
    internal_scheme_code: str
    scheme_name: str
    department_name: Optional[str] = None
    source_filename: str
    document_id: uuid.UUID
    draft_status: str
    review_status: str
    critical_issues: int = 0
    contradicted_facts: int = 0
    insufficient_facts: int = 0
    ocr_risks: int = 0
    conflicts: int = 0
    total_facts: int = 0
    resolved_facts: int = 0
    last_updated: datetime


class ReviewQueueResponse(BaseModel):
    items: List[ReviewQueueItemDTO]
    total: int
    page: int
    page_size: int


class HumanReviewItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_session_id: uuid.UUID
    scheme_draft_id: uuid.UUID
    fact_id: str
    field_path: str
    item_type: str
    risk_level: str
    statement: str
    original_value_json: Optional[Dict[str, Any]] = None
    current_value_json: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    evidence_text: Optional[str] = None
    page_number: Optional[int] = None
    block_id: Optional[str] = None
    decision: str
    reviewer_comment: Optional[str] = None
    edit_reason: Optional[str] = None
    override_reason: Optional[str] = None
    validation_issues_summary: Optional[List[Dict[str, Any]]] = None
    verification_result: Optional[str] = None
    verification_reason_code: Optional[str] = None
    ocr_risk: bool
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None


class ReviewAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_session_id: uuid.UUID
    scheme_draft_id: uuid.UUID
    reviewer_id: str
    action_type: str
    field_path: Optional[str] = None
    item_id: Optional[uuid.UUID] = None
    before_value_json: Optional[Dict[str, Any]] = None
    after_value_json: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    created_at: datetime


class ConflictItemDTO(BaseModel):
    conflict_id: str
    field: str
    status: str
    explanation: Optional[str] = None
    values: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewSessionDetailResponse(BaseModel):
    session_id: uuid.UUID
    scheme_draft_id: uuid.UUID
    document_id: uuid.UUID
    internal_scheme_code: str
    scheme_name: str
    department_name: Optional[str] = None
    reviewer_id: str
    session_status: str
    draft_status: str
    review_version: int
    canonical_artifact_sha256: str
    is_stale: bool = False
    notes: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    items: List[HumanReviewItemResponse] = Field(default_factory=list)
    conflicts: List[ConflictItemDTO] = Field(default_factory=list)
    validation_summary: Optional[Dict[str, Any]] = None
    verification_summary: Optional[Dict[str, Any]] = None
    audit_events: List[ReviewAuditEventResponse] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None
