from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKER = "BLOCKER"


class ValidationRunStatus(str, Enum):
    VALIDATING = "VALIDATING"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_REVIEW_REQUIRED = "VALIDATION_REVIEW_REQUIRED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    STALE = "STALE"


class ValidationIssueStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    IGNORED_WITH_REASON = "IGNORED_WITH_REASON"


class ValidationIssueDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, description="Issue UUID string if persisted")
    rule_code: str = Field(..., description="Stable rule identifier, e.g. AGE_RANGE_INVALID")
    severity: ValidationSeverity = Field(..., description="INFO, WARNING, ERROR, BLOCKER")
    field_path: Optional[str] = Field(default=None, description="Dot notation path to target canonical field")
    message: str = Field(..., description="Deterministic explanation of the validation failure")
    actual_value: Optional[Any] = Field(default=None, description="Extracted value that triggered the issue")
    evidence_refs: List[str] = Field(default_factory=list, description="Evidence reference IDs associated with the field")
    status: ValidationIssueStatus = Field(default=ValidationIssueStatus.OPEN)
    resolution_notes: Optional[str] = Field(default=None)


class ValidationSummaryDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    blockers: int = Field(default=0)
    errors: int = Field(default=0)
    warnings: int = Field(default=0)
    info: int = Field(default=0)
    total_issues: int = Field(default=0)
    rules_checked: int = Field(default=0)


class ValidationReportDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0", description="VALIDATION_SCHEMA_VERSION=1.0")
    validator_version: str = Field(default="1.0", description="VALIDATOR_VERSION=1.0")
    scheme_draft_id: str = Field(..., description="UUID of the validated scheme draft")
    canonical_artifact_hash: str = Field(..., description="SHA-256 hex digest of the canonical JSON draft")
    status: ValidationRunStatus = Field(..., description="Overall validation status")
    summary: ValidationSummaryDTO = Field(default_factory=ValidationSummaryDTO)
    issues: List[ValidationIssueDTO] = Field(default_factory=list)
    duration_ms: Optional[int] = Field(default=None)
    created_at: str = Field(..., description="ISO timestamp")


class ValidationIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    validation_run_id: uuid.UUID
    scheme_draft_id: uuid.UUID
    rule_code: str
    severity: str
    field_path: Optional[str] = None
    message: str
    actual_value: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    status: str
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheme_draft_id: uuid.UUID
    validator_version: str
    schema_version: str
    canonical_artifact_hash: str
    status: str
    blocker_count: int
    error_count: int
    warning_count: int
    info_count: int
    rules_checked_count: int
    artifact_path: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    created_at: datetime
