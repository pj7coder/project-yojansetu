"""
YojanSetu - Day 30: Eligibility Evaluation Subsystem Schemas.

Defines typed dataclasses and Pydantic models for deterministic eligibility evaluation:
- Tri-state decisions (ELIGIBLE, NOT_ELIGIBLE, MORE_INFORMATION_REQUIRED)
- 3x3 decision confusion matrix with deterministic severity counts
- Minimal missing information metrics (Precision, Recall, F1, Unnecessary Questions)
- Reasoning trace and decisive condition comparison structures
- Boundary and temporal versioning validation structures
- Benchmark run manifest and aggregate evaluation summary
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, ConfigDict, Field

from app.gold.schemas import CaseStatus, DifficultyLevel, EligibilityStatus, GoldSplit


class EligibilitySeverity(str, Enum):
    """Deterministic severity ranking for eligibility evaluation errors."""
    CRITICAL = "CRITICAL"  # Inverted entitlement (e.g. NOT_ELIGIBLE -> ELIGIBLE), ignored exclusion, boundary operator inverted
    HIGH = "HIGH"          # Premature decision with missing information (MORE_INFO -> ELIGIBLE/NOT_ELIGIBLE)
    MEDIUM = "MEDIUM"      # Unnecessary question asked (ELIGIBLE -> MORE_INFO)
    LOW = "LOW"            # Trace formatting or non-decisive discrepancy


class EligibilityFailureCode(str, Enum):
    """Stable taxonomy of eligibility evaluation failure codes."""
    WRONG_FINAL_STATUS = "WRONG_FINAL_STATUS"
    TRISTATE_LOGIC_ERROR = "TRISTATE_LOGIC_ERROR"
    AND_SHORT_CIRCUIT_ERROR = "AND_SHORT_CIRCUIT_ERROR"
    OR_SHORT_CIRCUIT_ERROR = "OR_SHORT_CIRCUIT_ERROR"
    NOT_LOGIC_ERROR = "NOT_LOGIC_ERROR"
    WRONG_OPERATOR_BEHAVIOR = "WRONG_OPERATOR_BEHAVIOR"
    BOUNDARY_ERROR = "BOUNDARY_ERROR"
    UNKNOWN_FALSE_CONFUSION = "UNKNOWN_FALSE_CONFUSION"
    DECLINED_STATE_ERROR = "DECLINED_STATE_ERROR"
    WRONG_PROFILE_FIELD_USED = "WRONG_PROFILE_FIELD_USED"
    UNIT_MISMATCH_ERROR = "UNIT_MISMATCH_ERROR"
    EXCLUSION_IGNORED = "EXCLUSION_IGNORED"
    EXCLUSION_FALSE_POSITIVE = "EXCLUSION_FALSE_POSITIVE"
    EXCLUSION_UNKNOWN_ERROR = "EXCLUSION_UNKNOWN_ERROR"
    WRONG_SCHEME_VERSION = "WRONG_SCHEME_VERSION"
    FUTURE_VERSION_USED_EARLY = "FUTURE_VERSION_USED_EARLY"
    HISTORICAL_VERSION_ERROR = "HISTORICAL_VERSION_ERROR"
    MISSING_FIELD_FALSE_POSITIVE = "MISSING_FIELD_FALSE_POSITIVE"
    MISSING_FIELD_FALSE_NEGATIVE = "MISSING_FIELD_FALSE_NEGATIVE"
    TRACE_ERROR = "TRACE_ERROR"
    TRACE_EVIDENCE_ERROR = "TRACE_EVIDENCE_ERROR"
    CUSTOM_EVALUATOR_ERROR = "CUSTOM_EVALUATOR_ERROR"
    RULE_DATA_MISMATCH = "RULE_DATA_MISMATCH"
    UNKNOWN_ROOT_CAUSE = "UNKNOWN_ROOT_CAUSE"


class FailureRootCause(str, Enum):
    """High-level attribution of error root cause."""
    ENGINE_LOGIC = "ENGINE_LOGIC"
    RULE_DATA = "RULE_DATA"
    VERSION_SELECTION = "VERSION_SELECTION"
    PROFILE_FIELD_MAPPING = "PROFILE_FIELD_MAPPING"
    TRACE_ONLY = "TRACE_ONLY"
    UNKNOWN = "UNKNOWN"


class DecisionConfusionMatrix(BaseModel):
    """
    3x3 Confusion Matrix for deterministic eligibility decisions:
    Rows = Gold (Ground Truth), Columns = Predicted (Actual Engine Output).
    """
    model_config = ConfigDict(extra="ignore")

    # Counts: gold_predicted
    eligible_eligible: int = 0
    eligible_not_eligible: int = 0
    eligible_more_info: int = 0

    not_eligible_eligible: int = 0
    not_eligible_not_eligible: int = 0
    not_eligible_more_info: int = 0

    more_info_eligible: int = 0
    more_info_not_eligible: int = 0
    more_info_more_info: int = 0

    # Safety-critical and high severity error tallies
    critical_false_eligibility_count: int = 0       # NOT_ELIGIBLE -> ELIGIBLE
    critical_false_ineligibility_count: int = 0     # ELIGIBLE -> NOT_ELIGIBLE
    high_premature_eligibility_count: int = 0       # MORE_INFO -> ELIGIBLE
    high_premature_ineligibility_count: int = 0     # MORE_INFO -> NOT_ELIGIBLE
    medium_unnecessary_question_count: int = 0      # ELIGIBLE -> MORE_INFO

    # Overall Metrics
    total_cases: int = 0
    status_accuracy: float = 0.0

    # Per-class F1 / Precision / Recall
    eligible_precision: float = 0.0
    eligible_recall: float = 0.0
    eligible_f1: float = 0.0

    not_eligible_precision: float = 0.0
    not_eligible_recall: float = 0.0
    not_eligible_f1: float = 0.0

    more_info_precision: float = 0.0
    more_info_recall: float = 0.0
    more_info_f1: float = 0.0


class MissingFieldEvaluation(BaseModel):
    """Evaluation of missing fields for MORE_INFORMATION_REQUIRED cases."""
    gold_missing: List[str] = Field(default_factory=list)
    actual_missing: List[str] = Field(default_factory=list)
    matched_missing: List[str] = Field(default_factory=list)
    false_positive_missing: List[str] = Field(default_factory=list)
    false_negative_missing: List[str] = Field(default_factory=list)
    precision: float = 1.0
    recall: float = 1.0
    f1: float = 1.0
    unnecessary_question_count: int = 0


class TraceEvaluation(BaseModel):
    """Evaluation of the structured decision reasoning trace."""
    status_trace_consistent: bool = True
    expected_decisive_rules: List[str] = Field(default_factory=list)
    actual_decisive_rules: List[str] = Field(default_factory=list)
    decisive_rule_accuracy: float = 1.0
    evidence_references_valid: bool = True
    short_circuit_clean: bool = True
    reasoning_explanation: Optional[str] = None


class EligibilityCaseResult(BaseModel):
    """Full evaluation record for an individual benchmark eligibility case."""
    model_config = ConfigDict(extra="ignore")

    case_id: str
    split: GoldSplit
    difficulty: DifficultyLevel
    tags: List[str] = Field(default_factory=list)
    scheme_version_id: str
    evaluation_date: str

    gold_status: EligibilityStatus
    actual_status: EligibilityStatus

    gold_missing_fields: List[str] = Field(default_factory=list)
    actual_missing_fields: List[str] = Field(default_factory=list)

    gold_decisive_rules: List[str] = Field(default_factory=list)
    actual_decisive_rules: List[str] = Field(default_factory=list)

    status_match: bool
    strict_case_pass: bool  # status match + missing fields exact match + decisive rules consistent + version correct

    missing_field_eval: Optional[MissingFieldEvaluation] = None
    trace_eval: Optional[TraceEvaluation] = None

    failure_code: Optional[EligibilityFailureCode] = None
    severity: Optional[EligibilitySeverity] = None
    root_cause: Optional[FailureRootCause] = None
    failure_reason: Optional[str] = None

    evaluation_duration_ms: float = 0.0
    evaluation_trace: Dict[str, Any] = Field(default_factory=dict)


class TriStateMetrics(BaseModel):
    """Kleene three-valued logic accuracy metrics."""
    and_pass_rate: float = 1.0
    or_pass_rate: float = 1.0
    not_pass_rate: float = 1.0
    unknown_false_distinction_pass_rate: float = 1.0
    short_circuit_accuracy: float = 1.0


class BoundaryMetrics(BaseModel):
    """Numeric and relational boundary metrics."""
    total_boundary_cases: int = 0
    boundary_accuracy: float = 1.0
    age_boundary_accuracy: float = 1.0
    income_boundary_accuracy: float = 1.0
    percentage_boundary_accuracy: float = 1.0


class VersionMetrics(BaseModel):
    """Temporal scheme versioning metrics."""
    total_version_cases: int = 0
    version_selection_accuracy: float = 1.0
    future_version_rejection_accuracy: float = 1.0
    historical_version_accuracy: float = 1.0


class FieldBreakdownMetric(BaseModel):
    """Accuracy metrics for rules concerning a specific citizen profile field."""
    field_name: str
    case_count: int
    correct_count: int
    accuracy: float


class OperatorBreakdownMetric(BaseModel):
    """Accuracy metrics for rules evaluated by a specific relational operator."""
    operator: str
    case_count: int
    correct_count: int
    accuracy: float


class EligibilityBenchmarkSummary(BaseModel):
    """Comprehensive summary of an eligibility benchmark execution run."""
    run_id: str
    benchmark_mode: str  # "ENGINE-ONLY" or "END-TO-END VERIFIED-RULE"
    gold_version: str
    gold_sha256: str
    split: str
    case_count: int

    engine_version: str
    rule_schema_version: str = "1.0"
    evaluated_at: str

    status_accuracy: float
    strict_case_pass_rate: float

    confusion_matrix: DecisionConfusionMatrix
    tri_state_metrics: TriStateMetrics
    missing_field_precision: float
    missing_field_recall: float
    missing_field_f1: float
    total_unnecessary_questions: int

    boundary_metrics: BoundaryMetrics
    version_metrics: VersionMetrics
    exclusion_accuracy: float
    negation_accuracy: float

    trace_decisive_accuracy: float
    trace_evidence_accuracy: float

    critical_failure_count: int
    high_failure_count: int
    medium_failure_count: int
    low_failure_count: int

    field_metrics: List[FieldBreakdownMetric] = Field(default_factory=list)
    operator_metrics: List[OperatorBreakdownMetric] = Field(default_factory=list)

    duration_mean_ms: float = 0.0
    duration_p50_ms: float = 0.0
    duration_p95_ms: float = 0.0
