from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.eligibility.truth import TruthState


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    MORE_INFORMATION_REQUIRED = "MORE_INFORMATION_REQUIRED"


class SchemeAvailability(str, Enum):
    ACTIVE = "ACTIVE"
    SCHEME_NOT_ACTIVE = "SCHEME_NOT_ACTIVE"
    NOT_YET_ACTIVE = "NOT_YET_ACTIVE"
    EXPIRED = "EXPIRED"


class ReasonCode(str, Enum):
    CONDITION_SATISFIED = "CONDITION_SATISFIED"
    CONDITION_NOT_SATISFIED = "CONDITION_NOT_SATISFIED"
    VALUE_NOT_PROVIDED = "VALUE_NOT_PROVIDED"
    VALUE_INVALID = "VALUE_INVALID"
    UNSUPPORTED_FIELD = "UNSUPPORTED_FIELD"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    RULE_INVALID = "RULE_INVALID"
    RULE_UNSUPPORTED = "RULE_UNSUPPORTED"
    EXCLUSION_TRIGGERED = "EXCLUSION_TRIGGERED"
    SCHEME_INACTIVE = "SCHEME_INACTIVE"


class ConditionEvaluationResult(BaseModel):
    """Structured result of evaluating a single rule condition."""
    model_config = ConfigDict(extra="ignore")

    condition_id: str
    field: str
    result: TruthState
    operator: str
    required_value: Any = None
    citizen_value: Any = None
    reason_code: ReasonCode
    evidence_refs: List[str] = Field(default_factory=list)
    message: str = ""


class MissingFieldInfo(BaseModel):
    """Details of a missing citizen field needed to reach an eligibility decision."""
    model_config = ConfigDict(extra="ignore")

    field: str
    reason: str = "REQUIRED_FOR_RULE"
    condition_id: Optional[str] = None
    display_name_en: Optional[str] = None
    display_name_hi: Optional[str] = None


class EligibilityResult(BaseModel):
    """Top-level deterministic evaluation outcome for a scheme."""
    model_config = ConfigDict(extra="ignore")

    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    availability: SchemeAvailability = SchemeAvailability.ACTIVE
    eligibility_status: EligibilityStatus
    missing_fields: List[MissingFieldInfo] = Field(default_factory=list)
    failed_conditions: List[ConditionEvaluationResult] = Field(default_factory=list)
    passed_conditions: List[ConditionEvaluationResult] = Field(default_factory=list)
    exclusions_triggered: List[ConditionEvaluationResult] = Field(default_factory=list)
    preferences_matched: List[ConditionEvaluationResult] = Field(default_factory=list)
    evaluation_trace: Optional[Dict[str, Any]] = None
    engine_version: str = "1.0"
    evaluation_duration_ms: float = 0.0
