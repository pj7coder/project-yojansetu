"""
JanSetu - Day 31: Unified Search & Scheme Discovery Evaluation Schemas.

Defines typed data models for search benchmark case results,
aggregated metrics summaries, index health status, and strict pass criteria.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.evaluation.bucket_metrics import BucketMetrics
from app.evaluation.candidate_metrics import CandidateMetrics
from app.evaluation.multilingual_analysis import MultilingualMetrics
from app.evaluation.ranking_metrics import RankingMetrics
from app.evaluation.search_failure_analysis import SearchFailureDiagnosis


class IndexHealthMetrics(BaseModel):
    """Health and coverage status of verified scheme search index and embeddings."""
    verified_scheme_count: int = 0
    indexed_current_scheme_count: int = 0
    missing_embedding_count: int = 0
    stale_embedding_count: int = 0
    failed_embedding_count: int = 0
    index_coverage_pct: float = 0.0

    embedding_provider: str = "fastembed"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimension: int = 384
    pgvector_available: bool = False
    index_type: str = "EXACT_COSINE"  # HNSW, IVFFlat, or EXACT_COSINE


class DegradedModeMetrics(BaseModel):
    """Performance and safety when vector search/pgvector is unavailable."""
    fallback_functional: bool = True
    fallback_candidate_recall: float = 0.0
    fallback_top_set_recall: float = 0.0
    fallback_avg_duration_ms: float = 0.0
    notes: Optional[str] = None


class SearchCaseResult(BaseModel):
    """Detailed evaluation result for an individual search gold case."""
    case_id: str
    split: str
    language: str
    query_type: str
    query: Optional[str] = None
    profile_summary: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    # Gold expectations
    gold_relevant_scheme_ids: List[str] = Field(default_factory=list)
    acceptable_top_set: List[str] = Field(default_factory=list)
    must_appear_top_5: List[str] = Field(default_factory=list)
    must_not_appear_top_k: List[str] = Field(default_factory=list)
    expected_empty: bool = False

    # Pipeline stage outputs
    sql_candidate_count: int = 0
    sql_candidate_ids: List[str] = Field(default_factory=list)
    evaluated_count: int = 0
    eligible_count: int = 0
    more_info_count: int = 0
    not_eligible_count: int = 0

    ranked_eligible_ids: List[str] = Field(default_factory=list)
    ranked_more_info_ids: List[str] = Field(default_factory=list)

    # Similarities and ranks
    target_semantic_similarity: Optional[float] = None
    target_rank: Optional[int] = None

    # Ranking evaluation
    recalls: Dict[int, float] = Field(default_factory=dict)
    precisions: Dict[int, float] = Field(default_factory=dict)
    reciprocal_rank: float = 0.0
    ndcg_at_5: float = 0.0

    # Pass flags
    strict_case_pass: bool = True
    ranking_only_pass: bool = True

    # Failures diagnosed
    diagnoses: List[SearchFailureDiagnosis] = Field(default_factory=list)
    duration_ms: float = 0.0


class SearchBenchmarkSummary(BaseModel):
    """Master benchmark summary container for search and discovery evaluation."""
    run_id: str
    gold_version: str = "v1"
    split: str = "TEST"
    timestamp: str
    duration_seconds: float = 0.0

    total_cases: int = 0
    strict_pass_count: int = 0
    strict_case_pass_rate: float = 0.0
    ranking_only_pass_rate: float = 0.0

    # Component metric summaries
    candidate_metrics: CandidateMetrics = Field(default_factory=CandidateMetrics)
    ranking_metrics: RankingMetrics = Field(default_factory=RankingMetrics)
    bucket_metrics: BucketMetrics = Field(default_factory=BucketMetrics)
    multilingual_metrics: MultilingualMetrics = Field(default_factory=MultilingualMetrics)
    index_health: IndexHealthMetrics = Field(default_factory=IndexHealthMetrics)
    degraded_mode: DegradedModeMetrics = Field(default_factory=DegradedModeMetrics)

    # Latencies
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0

    # Critical failures counter
    critical_failures_count: int = 0
