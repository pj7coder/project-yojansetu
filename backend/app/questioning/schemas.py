from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionReasonCode(str, Enum):
    """Reason code explaining why a particular field or stopping state was selected."""
    RESOLVES_MOST_RELEVANT_SCHEMES = "RESOLVES_MOST_RELEVANT_SCHEMES"
    IMMEDIATE_SCHEME_RESOLUTION = "IMMEDIATE_SCHEME_RESOLUTION"
    ENOUGH_CONFIRMED_RESULTS = "ENOUGH_CONFIRMED_RESULTS"
    NO_RELEVANT_CANDIDATES = "NO_RELEVANT_CANDIDATES"
    CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION = "CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION"


class CandidateSchemeMissingInfo(BaseModel):
    """Representation of an unresolved candidate scheme and its missing fields."""
    scheme_id: str
    scheme_name: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    semantic_score: Optional[float] = Field(default=None, description="Similarity score (0.0 - 1.0) if ranked")


class NextQuestionResult(BaseModel):
    """
    Deterministic next-question recommendation.
    Contains no LLM hallucination; provides exact canonical field and vernacular metadata.
    """
    field: Optional[str] = Field(default=None, description="Canonical name of field to ask next; null if stopping")
    reason_code: str = Field(..., description="Machine-readable justification code for question selection or stopping")
    affected_scheme_count: int = Field(default=0, description="Number of candidate schemes needing this field")
    display_name_en: Optional[str] = None
    display_name_hi: Optional[str] = None
    data_type: Optional[str] = None
    sensitivity_level: Optional[str] = None
    example_question_en: Optional[str] = None
    example_question_hi: Optional[str] = None
