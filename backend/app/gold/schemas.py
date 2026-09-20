"""
YojanSetu - Day 28: Gold Dataset Pydantic Schemas.

Defines deterministic, typed structures for gold-standard cases,
splits, metadata, provenance references, and manifest catalogs.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class GoldTask(str, Enum):
    EXTRACTION = "extraction"
    ELIGIBILITY = "eligibility"
    SEARCH = "search"
    VOICE = "voice"
    CONVERSATION = "conversation"


class GoldSplit(str, Enum):
    DEV = "DEV"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


class CaseStatus(str, Enum):
    DRAFT = "DRAFT"
    ANNOTATED = "ANNOTATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    EXCLUDED = "EXCLUDED"


class DifficultyLevel(str, Enum):
    EASY = "EASY"
    NORMAL = "NORMAL"
    HARD = "HARD"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    MORE_INFORMATION_REQUIRED = "MORE_INFORMATION_REQUIRED"


class RelevanceGrade(str, Enum):
    HIGH = "HIGH"
    RELEVANT = "RELEVANT"
    NOT_RELEVANT = "NOT_RELEVANT"


class ExtractionOperator(str, Enum):
    EQ = "EQ"
    NEQ = "NEQ"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    CONTAINS = "CONTAINS"


class AmbiguityType(str, Enum):
    AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    STALE_REFERENCE = "STALE_REFERENCE"
    UNRESOLVED_DISPUTE = "UNRESOLVED_DISPUTE"


class GoldCaseMeta(BaseModel):
    case_id: str = Field(..., description="Stable unique case ID (e.g. EXT-RJ-001)")
    task: GoldTask
    split: GoldSplit
    status: CaseStatus = CaseStatus.HUMAN_VERIFIED
    difficulty: DifficultyLevel = DifficultyLevel.NORMAL
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    reviewed_at: Optional[str] = Field(None, description="ISO-8601 review timestamp")
    annotated_by: str = Field("HUMAN_ANNOTATOR", description="Anonymized annotator identifier")
    reviewed_by: Optional[str] = Field("HUMAN_REVIEWER", description="Anonymized reviewer identifier")
    source_references: List[str] = Field(default_factory=list, description="Source document or audio references")
    notes: Optional[str] = None
    ambiguity_flag: Optional[AmbiguityType] = None


# ---------------------------------------------------------------------------
# Task A: Extraction Schemas
# ---------------------------------------------------------------------------

class ExtractionExpectedFact(BaseModel):
    field: str = Field(..., description="Canonical field path (e.g. eligibility.age, benefits.monthly_amount)")
    operator: Optional[ExtractionOperator] = None
    value: Any = Field(..., description="Expected extracted value")
    unit: Optional[str] = None
    period: Optional[str] = None
    currency: Optional[str] = None
    is_mandatory: Optional[bool] = None
    evidence_quote: str = Field(..., description="Verbatim quote from source document")
    evidence_page: Optional[int] = Field(None, description="1-based page number")
    evidence_block_ids: List[str] = Field(default_factory=list, description="Source layout block IDs")


class ExtractionSource(BaseModel):
    document_id: str = Field(..., description="UUID of source government document")
    chunk_id: Optional[str] = Field(None, description="Chunk ID in storage/chunks")
    page_number: Optional[int] = Field(None, description="Physical page number")
    source_block_ids: List[str] = Field(default_factory=list)
    text_snippet: Optional[str] = Field(None, description="Input chunk text snippet")
    contains_table: bool = False
    contains_ocr: bool = False
    language: str = "hi"


class ExtractionGoldCase(GoldCaseMeta):
    task: GoldTask = GoldTask.EXTRACTION
    source: ExtractionSource
    expected_facts: List[ExtractionExpectedFact] = Field(default_factory=list)
    is_negative: bool = Field(False, description="True if chunk contains zero scheme facts (measures hallucination)")
    is_security_test: bool = Field(False, description="True for synthetic prompt-injection safety tests")


# ---------------------------------------------------------------------------
# Task B: Eligibility Schemas
# ---------------------------------------------------------------------------

class EligibilityExpected(BaseModel):
    status: EligibilityStatus
    decisive_rules: List[str] = Field(default_factory=list, description="Rules that decided the outcome")
    missing_fields: List[str] = Field(default_factory=list, description="Unresolved fields for MORE_INFORMATION_REQUIRED")
    exclusion_triggered: bool = False
    explanation: Optional[str] = None


class EligibilityGoldCase(GoldCaseMeta):
    task: GoldTask = GoldTask.ELIGIBILITY
    scheme_version_id: str = Field(..., description="Target scheme version ID")
    evaluation_date: str = Field(..., description="YYYY-MM-DD evaluation date (temporal safety)")
    profile: Dict[str, Any] = Field(..., description="Synthetic citizen demographic and economic facts")
    expected: EligibilityExpected


# ---------------------------------------------------------------------------
# Task C: Search Schemas
# ---------------------------------------------------------------------------

class SearchExpectedItem(BaseModel):
    scheme_id: str
    relevance: RelevanceGrade
    reason: Optional[str] = None


class SearchExpected(BaseModel):
    relevance_judgments: List[SearchExpectedItem] = Field(default_factory=list)
    acceptable_top_set: List[str] = Field(default_factory=list, description="Set of schemes acceptable in top-K")
    must_appear_top_5: List[str] = Field(default_factory=list, description="Schemes that must rank in top 5")
    must_not_appear_top_k: List[str] = Field(default_factory=list, description="Ineligible or irrelevant schemes forbidden from top-K")
    expected_empty: bool = Field(False, description="True if no schemes are relevant")


class SearchGoldCase(GoldCaseMeta):
    task: GoldTask = GoldTask.SEARCH
    query: Optional[str] = Field(None, description="Natural language need or keyword query")
    language: str = "hi"
    query_type: str = Field("NATURAL", description="KEYWORD, NATURAL, PROBLEM, BENEFICIARY, NO_QUERY")
    profile: Optional[Dict[str, Any]] = Field(None, description="Optional profile filters applied during search")
    expected: SearchExpected


# ---------------------------------------------------------------------------
# Task D: Voice Schemas
# ---------------------------------------------------------------------------

class VoiceVADTruth(BaseModel):
    contains_speech: bool = True
    speech_start_ms: Optional[int] = None
    speech_end_ms: Optional[int] = None


class VoiceExpectedMeaning(BaseModel):
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    unit: Optional[str] = None
    is_confirmation: Optional[bool] = None


class VoiceContext(BaseModel):
    expected_field: Optional[str] = None
    conversation_state: Optional[str] = None


class VoiceGoldCase(GoldCaseMeta):
    task: GoldTask = GoldTask.VOICE
    audio_file: str = Field(..., description="Relative path to audio file under benchmarks/gold/v1/voice/audio/")
    audio_sha256: str = Field(..., description="SHA-256 hash of audio file")
    duration_seconds: float
    sample_rate: int = 16000
    speaker_id: str = "ANON_SPK"
    speech_category: str = Field("CLEAN", description="CLEAN, NOISY, ACCENT, DIALECT, SILENCE, SHORT_ANSWER")
    noise_condition: str = "NONE"
    reference_transcript: str = Field(..., description="Human-transcribed Devanagari reference")
    context: VoiceContext = Field(default_factory=VoiceContext)
    expected_meaning: VoiceExpectedMeaning = Field(default_factory=VoiceExpectedMeaning)
    vad: VoiceVADTruth = Field(default_factory=VoiceVADTruth)


# ---------------------------------------------------------------------------
# Task E: Multi-Turn Conversation Schemas
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    turn_index: int
    input_type: str = "TEXT"
    user_text: str
    expected_state: str = Field(..., description="Deterministic ConversationState enum name")
    expected_action: str = Field(..., description="Deterministic ConversationAction enum name")
    expected_field: Optional[str] = None
    expected_profile_delta: Dict[str, Any] = Field(default_factory=dict)
    message_key: Optional[str] = None


class ConversationGoldCase(GoldCaseMeta):
    task: GoldTask = GoldTask.CONVERSATION
    conversation_id: str
    language: str = "hi"
    description: str
    turns: List[ConversationTurn] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest Schema
# ---------------------------------------------------------------------------

class GoldManifestCaseEntry(BaseModel):
    case_id: str
    task: GoldTask
    split: GoldSplit
    status: CaseStatus
    difficulty: DifficultyLevel
    tags: List[str] = Field(default_factory=list)
    relative_path: str


class GoldDatasetManifest(BaseModel):
    dataset_version: str = "1.0"
    created_at: str
    dataset_sha256: Optional[str] = None
    task_counts: Dict[str, int] = Field(default_factory=dict)
    split_counts: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    schema_versions: Dict[str, str] = Field(default_factory=dict)
    annotation_guidelines_version: str = "1.0"
    cases: List[GoldManifestCaseEntry] = Field(default_factory=list)
