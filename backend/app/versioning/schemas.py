from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RelationshipType(str, Enum):
    AMENDS = "AMENDS"
    SUPERSEDES = "SUPERSEDES"
    CORRIGENDUM_TO = "CORRIGENDUM_TO"
    ADDENDUM_TO = "ADDENDUM_TO"
    REPLACES = "REPLACES"
    EXTENDS = "EXTENDS"
    CLARIFIES = "CLARIFIES"
    IMPLEMENTS = "IMPLEMENTS"
    REFERENCES = "REFERENCES"
    RELATED_TO = "RELATED_TO"
    POSSIBLE_VERSION_OF = "POSSIBLE_VERSION_OF"
    UNKNOWN_RELATIONSHIP = "UNKNOWN_RELATIONSHIP"


class RelationshipStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    AUTO_SUPPORTED = "AUTO_SUPPORTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


class DetectionMethod(str, Enum):
    EXPLICIT_REFERENCE = "EXPLICIT_REFERENCE"
    DETERMINISTIC_METADATA = "DETERMINISTIC_METADATA"
    TEXTUAL_SIGNAL = "TEXTUAL_SIGNAL"
    LLM_ASSISTED = "LLM_ASSISTED"
    HUMAN = "HUMAN"


class ChangeRiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    NORMAL = "NORMAL"
    LOW = "LOW"


class ChangeType(str, Enum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    MODIFY = "MODIFY"
    EXTEND_VALIDITY = "EXTEND_VALIDITY"
    NO_RULE_CHANGE = "NO_RULE_CHANGE"
    UNKNOWN_CHANGE = "UNKNOWN_CHANGE"


class VersionStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class ChangeSetStatus(str, Enum):
    DETECTED = "DETECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    APPLIED_TO_VERSION = "APPLIED_TO_VERSION"


class SchemeDocumentLinkType(str, Enum):
    PRIMARY_GUIDELINE = "PRIMARY_GUIDELINE"
    NOTIFICATION = "NOTIFICATION"
    AMENDMENT = "AMENDMENT"
    CORRIGENDUM = "CORRIGENDUM"
    APPLICATION_GUIDE = "APPLICATION_GUIDE"
    CLARIFICATION = "CLARIFICATION"
    OTHER = "OTHER"


class GovernmentReference(BaseModel):
    reference_type: str = Field(description="NOTIFICATION, ORDER, CIRCULAR, GUIDELINE, CLAUSE, etc.")
    reference_number: Optional[str] = None
    date: Optional[str] = None
    department: Optional[str] = None
    scheme_name: Optional[str] = None
    clause_reference: Optional[str] = None
    raw_text: str
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    block_id: Optional[str] = None


class DetectedRelationshipResult(BaseModel):
    relationship_type: RelationshipType
    relationship_status: RelationshipStatus
    detection_method: DetectionMethod
    signal_strength: str = Field(default="EXPLICIT", description="EXPLICIT, STRONG, WEAK")
    target_document_id: Optional[UUID] = None
    target_scheme_id: Optional[UUID] = None
    effective_date: Optional[date] = None
    publication_date: Optional[date] = None
    evidence_text: Optional[str] = None
    evidence_page: Optional[int] = None
    evidence_block_ids: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    conflict_reason: Optional[str] = None


class ChangeItemSchema(BaseModel):
    field_path: str
    change_type: ChangeType
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    risk_level: ChangeRiskLevel
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    clause_reference: Optional[str] = None
    reason: Optional[str] = None


class ChangeSetCreate(BaseModel):
    scheme_id: UUID
    base_version_id: UUID
    source_document_id: UUID
    relationship_id: Optional[UUID] = None
    effective_date: Optional[date] = None
    publication_date: Optional[date] = None
    items: List[ChangeItemSchema] = Field(default_factory=list)
    change_summary: Optional[str] = None
    conflict_reason: Optional[str] = None


class ChangeSetResponse(BaseModel):
    id: UUID
    scheme_id: UUID
    base_version_id: UUID
    source_document_id: UUID
    relationship_id: Optional[UUID] = None
    status: str
    effective_date: Optional[date] = None
    publication_date: Optional[date] = None
    changes_count: int
    critical_changes_count: int
    change_summary: Optional[str] = None
    conflict_reason: Optional[str] = None
    change_set_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SchemeVersionResponse(BaseModel):
    id: UUID
    scheme_id: UUID
    version_number: int
    version_label: Optional[str] = None
    status: str
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    effective_date: Optional[date] = None
    source_document_id: Optional[UUID] = None
    supersedes_version_id: Optional[UUID] = None
    created_from_relationship_id: Optional[UUID] = None
    canonical_data: Optional[Dict[str, Any]] = None
    artifact_path: Optional[str] = None
    artifact_sha256: Optional[str] = None
    source_summary: Optional[str] = None
    change_summary: Optional[str] = None
    is_current: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VersionTimelineItem(BaseModel):
    version_id: UUID
    version_number: int
    version_label: Optional[str] = None
    status: str
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    effective_date: Optional[date] = None
    is_current: bool
    source_document_id: Optional[UUID] = None
    change_summary: Optional[str] = None
    changes_count: int = 0
    critical_changes_count: int = 0


class SchemeTimelineResponse(BaseModel):
    scheme_id: UUID
    scheme_name: str
    versions: List[VersionTimelineItem]
    anomalies: List[str] = Field(default_factory=list)
