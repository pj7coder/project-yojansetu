"""
JanSetu - Day 29: Evaluation Subsystem Pydantic Schemas.

Defines deterministic, typed schemas for extraction benchmark evaluation:
- Field match classifications (TP, FP, FN)
- Failure severity levels (CRITICAL, HIGH, MEDIUM, LOW)
- Standardized failure taxonomy codes (Phase 21)
- Pipeline-stage attribution tags (Phase 22)
- Fact-level & case-level evaluation results
- Benchmark run manifest and summary structures
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from app.gold.schemas import DifficultyLevel, GoldSplit


class MatchResult(str, Enum):
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"


class FailureSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FailureCode(str, Enum):
    # Parsing / OCR
    PARSING_TEXT_LOSS = "PARSING_TEXT_LOSS"
    OCR_CHARACTER_ERROR = "OCR_CHARACTER_ERROR"
    OCR_NUMERIC_ERROR = "OCR_NUMERIC_ERROR"
    OCR_TABLE_STRUCTURE_ERROR = "OCR_TABLE_STRUCTURE_ERROR"

    # Chunking / Context
    CHUNK_BOUNDARY_ERROR = "CHUNK_BOUNDARY_ERROR"
    SECTION_CLASSIFICATION_ERROR = "SECTION_CLASSIFICATION_ERROR"
    CONTEXT_LOSS = "CONTEXT_LOSS"

    # LLM Extraction
    LLM_FIELD_OMISSION = "LLM_FIELD_OMISSION"
    LLM_HALLUCINATION = "LLM_HALLUCINATION"
    LLM_WRONG_VALUE = "LLM_WRONG_VALUE"
    LLM_WRONG_OPERATOR = "LLM_WRONG_OPERATOR"
    LLM_WRONG_LOGICAL_CONNECTOR = "LLM_WRONG_LOGICAL_CONNECTOR"
    LLM_NEGATION_ERROR = "LLM_NEGATION_ERROR"

    # Normalization
    NORMALIZATION_ERROR = "NORMALIZATION_ERROR"
    UNIT_NORMALIZATION_ERROR = "UNIT_NORMALIZATION_ERROR"
    NUMBER_NORMALIZATION_ERROR = "NUMBER_NORMALIZATION_ERROR"

    # Evidence & Validation
    EVIDENCE_LINK_ERROR = "EVIDENCE_LINK_ERROR"
    VALIDATION_GAP = "VALIDATION_GAP"

    # Fallback
    UNKNOWN_ROOT_CAUSE = "UNKNOWN_ROOT_CAUSE"


class PipelineStage(str, Enum):
    PARSING_OCR = "PARSING_OCR"
    CHUNKING = "CHUNKING"
    LLM_EXTRACTION = "LLM_EXTRACTION"
    NORMALIZATION = "NORMALIZATION"
    EVIDENCE_VERIFICATION = "EVIDENCE_VERIFICATION"
    VALIDATION = "VALIDATION"


class FactEvaluation(BaseModel):
    """Evaluation result for an individual fact comparison."""
    model_config = ConfigDict(extra="ignore")

    field: str
    match_result: MatchResult
    gold_value: Optional[Any] = None
    predicted_value: Optional[Any] = None
    gold_operator: Optional[str] = None
    predicted_operator: Optional[str] = None
    gold_unit: Optional[str] = None
    predicted_unit: Optional[str] = None
    gold_period: Optional[str] = None
    predicted_period: Optional[str] = None

    value_exact_match: bool = False
    value_normalized_match: bool = False
    operator_match: Optional[bool] = None

    evidence_reference_valid: bool = False
    evidence_supported: bool = False
    is_hallucination: bool = False
    is_critical_hallucination: bool = False

    failure_code: Optional[FailureCode] = None
    severity: Optional[FailureSeverity] = None
    attribution_stage: Optional[PipelineStage] = None
    reason: Optional[str] = None

    evidence_quote: Optional[str] = None
    source_snippet: Optional[str] = None


class CaseEvaluationResult(BaseModel):
    """Detailed benchmark result for a single extraction case."""
    model_config = ConfigDict(extra="ignore")

    case_id: str
    split: GoldSplit
    status: str = "HUMAN_VERIFIED"
    difficulty: DifficultyLevel = DifficultyLevel.NORMAL
    tags: List[str] = Field(default_factory=list)

    is_negative: bool = False
    is_security_test: bool = False
    prompt_injection_resisted: Optional[bool] = None

    source_format: str = "DIGITAL"  # DIGITAL or OCR
    layout_type: str = "PROSE"      # PROSE or TABLE
    language: str = "hi"            # hi, en, mixed

    document_id: Optional[str] = None
    chunk_id: Optional[str] = None

    gold_fact_count: int = 0
    predicted_fact_count: int = 0
    tp_count: int = 0
    fp_count: int = 0
    fn_count: int = 0

    field_precision: float = 0.0
    field_recall: float = 0.0
    field_f1: float = 0.0

    value_exact_accuracy: float = 0.0
    value_normalized_accuracy: float = 0.0
    operator_accuracy: float = 0.0
    rule_tree_exact_match: bool = False

    evidence_reference_validity: float = 1.0
    evidence_grounding_rate: float = 1.0

    hallucinated_fact_count: int = 0
    critical_hallucination_count: int = 0

    strict_case_pass: bool = False
    critical_fact_pass: bool = False

    critical_errors: List[Dict[str, Any]] = Field(default_factory=list)
    failure_codes: List[FailureCode] = Field(default_factory=list)
    fact_evaluations: List[FactEvaluation] = Field(default_factory=list)

    execution_time_ms: float = 0.0


class BenchmarkRunManifest(BaseModel):
    """Comprehensive environment and execution manifest for reproducibility."""
    model_config = ConfigDict(extra="ignore")

    run_id: str
    benchmark_version: str = "1.0"
    gold_dataset_version: str = "1.0"
    gold_manifest_sha256: str
    git_commit: Optional[str] = None
    split: GoldSplit
    case_count: int
    llm_model: str
    llm_configuration: Dict[str, Any] = Field(default_factory=dict)
    mineru_version: str = "0.1.0-sim"
    paddleocr_version: str = "2.7.0-sim"
    normalizer_version: str = "1.0"
    validator_version: str = "1.0"
    device: str = "cpu"
    timestamp: str


class BenchmarkSummary(BaseModel):
    """Aggregated benchmark statistics across an evaluation run."""
    model_config = ConfigDict(extra="ignore")

    run_id: str
    split: str
    timestamp: str
    total_cases: int

    strict_case_pass_count: int
    strict_case_pass_rate: float
    critical_fact_pass_count: int
    critical_fact_pass_rate: float

    total_gold_facts: int
    total_predicted_facts: int
    total_tp: int
    total_fp: int
    total_fn: int

    field_precision: float
    field_recall: float
    field_f1: float

    value_exact_accuracy: float
    value_normalized_accuracy: float
    operator_accuracy: float
    logical_connector_accuracy: float
    rule_tree_exact_match_rate: float

    evidence_reference_validity: float
    evidence_grounding_rate: float
    hallucination_rate: float
    critical_hallucination_count: int

    critical_safety_errors: Dict[str, int] = Field(default_factory=dict)
    failure_taxonomy_counts: Dict[str, int] = Field(default_factory=dict)
    pipeline_attribution_counts: Dict[str, int] = Field(default_factory=dict)

    category_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    format_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    layout_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    language_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    difficulty_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    prompt_injection_resistance: Dict[str, Any] = Field(default_factory=dict)
    performance: Dict[str, float] = Field(default_factory=dict)
