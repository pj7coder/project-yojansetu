"""
YojanSetu - Day 31: Search Failure Taxonomy & Stage-Level Root Cause Attributor.

Diagnoses search and discovery failures:
- Identifies the exact pipeline stage where a scheme was dropped or misclassified
- Maps failure symptoms to precise taxonomy codes
- Distinguishes candidate filter false negatives from vector ranking failures
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class SearchPipelineStage(str, Enum):
    """Discovery pipeline stages for failure localization."""
    CORPUS_INDEXING = "CORPUS_INDEXING"
    SQL_CANDIDATE_FILTER = "SQL_CANDIDATE_FILTER"
    ELIGIBILITY_BUCKETING = "ELIGIBILITY_BUCKETING"
    SEMANTIC_RANKING = "SEMANTIC_RANKING"
    OUTPUT_FORMATTING = "OUTPUT_FORMATTING"


class SearchFailureCode(str, Enum):
    """Standardized failure taxonomy codes for search benchmarking."""
    GOLD_RELEVANT_SCHEME_NOT_INDEXED = "GOLD_RELEVANT_SCHEME_NOT_INDEXED"
    STALE_EMBEDDING = "STALE_EMBEDDING"
    CANDIDATE_FILTER_FALSE_NEGATIVE = "CANDIDATE_FILTER_FALSE_NEGATIVE"
    CANDIDATE_FILTER_OVERBROAD = "CANDIDATE_FILTER_OVERBROAD"
    ELIGIBILITY_BUCKET_ERROR = "ELIGIBILITY_BUCKET_ERROR"
    INELIGIBLE_SCHEME_LEAKED = "INELIGIBLE_SCHEME_LEAKED"
    RELEVANT_SCHEME_LOW_RANK = "RELEVANT_SCHEME_LOW_RANK"
    IRRELEVANT_SCHEME_HIGH_RANK = "IRRELEVANT_SCHEME_HIGH_RANK"
    MULTILINGUAL_EMBEDDING_FAILURE = "MULTILINGUAL_EMBEDDING_FAILURE"
    QUERY_NORMALIZATION_ERROR = "QUERY_NORMALIZATION_ERROR"
    DUPLICATE_RESULT = "DUPLICATE_RESULT"
    WRONG_SCHEME_VERSION = "WRONG_SCHEME_VERSION"
    NO_RESULT_FALSE_POSITIVE = "NO_RESULT_FALSE_POSITIVE"
    PGVECTOR_FAILURE = "PGVECTOR_FAILURE"
    EMBEDDING_PROVIDER_FAILURE = "EMBEDDING_PROVIDER_FAILURE"
    UNKNOWN_ROOT_CAUSE = "UNKNOWN_ROOT_CAUSE"


class SearchFailureDiagnosis(BaseModel):
    """Diagnostic details for a failed search case or missed target scheme."""
    case_id: str
    scheme_id: Optional[str] = None
    stage: SearchPipelineStage
    code: SearchFailureCode
    severity: str = "MAJOR"  # CRITICAL, MAJOR, MINOR
    description: str
    stage_evidence: Dict[str, Any] = Field(default_factory=dict)


class SearchFailureAttributor:
    """Attributes failures to their root-cause pipeline stage."""

    @classmethod
    def diagnose_case(
        cls,
        case_id: str,
        gold_relevant_ids: List[str],
        expected_empty: bool,
        sql_candidate_ids: List[str],
        eligible_result_ids: List[str],
        more_info_result_ids: List[str],
        not_eligible_ids: List[str],
        ranked_eligible_ids: List[str],
        ranked_more_info_ids: List[str],
        indexed_scheme_ids: Set[str],
        stale_scheme_ids: Set[str],
        ineligible_leakage_ids: List[str],
        duplicate_ids: List[str],
        top_k: int = 5,
        language: str = "hi",
    ) -> List[SearchFailureDiagnosis]:
        """Diagnoses any failures in a single search case execution."""
        diagnoses: List[SearchFailureDiagnosis] = []

        all_recommendations = ranked_eligible_ids + ranked_more_info_ids
        top_k_recommendations = all_recommendations[:top_k]

        # 1. Safety Invariant: Ineligible Leakage (CRITICAL)
        if ineligible_leakage_ids:
            for sid in ineligible_leakage_ids:
                diagnoses.append(
                    SearchFailureDiagnosis(
                        case_id=case_id,
                        scheme_id=sid,
                        stage=SearchPipelineStage.OUTPUT_FORMATTING,
                        code=SearchFailureCode.INELIGIBLE_SCHEME_LEAKED,
                        severity="CRITICAL",
                        description=f"Definitely ineligible scheme '{sid}' leaked into eligible recommendations",
                        stage_evidence={"leaked_id": sid},
                    )
                )

        # 2. Safety Invariant: Duplicate Results
        if duplicate_ids:
            diagnoses.append(
                SearchFailureDiagnosis(
                    case_id=case_id,
                    stage=SearchPipelineStage.OUTPUT_FORMATTING,
                    code=SearchFailureCode.DUPLICATE_RESULT,
                    severity="MAJOR",
                    description=f"Duplicate scheme results detected: {duplicate_ids}",
                    stage_evidence={"duplicates": duplicate_ids},
                )
            )

        # 3. Safety Invariant: No-Result False Positive
        if expected_empty and all_recommendations:
            diagnoses.append(
                SearchFailureDiagnosis(
                    case_id=case_id,
                    stage=SearchPipelineStage.OUTPUT_FORMATTING,
                    code=SearchFailureCode.NO_RESULT_FALSE_POSITIVE,
                    severity="MAJOR",
                    description=f"Case expected zero results but returned {len(all_recommendations)} recommendations",
                    stage_evidence={"returned_recommendations": all_recommendations},
                )
            )
            return diagnoses

        # 4. Attribution for each missed relevant scheme
        for target_id in gold_relevant_ids:
            # Check Stage A: Corpus & Indexing
            if target_id not in indexed_scheme_ids:
                diagnoses.append(
                    SearchFailureDiagnosis(
                        case_id=case_id,
                        scheme_id=target_id,
                        stage=SearchPipelineStage.CORPUS_INDEXING,
                        code=SearchFailureCode.GOLD_RELEVANT_SCHEME_NOT_INDEXED,
                        severity="MAJOR",
                        description=f"Gold target scheme '{target_id}' is not indexed in search metadata",
                        stage_evidence={"target_id": target_id},
                    )
                )
                continue

            if target_id in stale_scheme_ids:
                diagnoses.append(
                    SearchFailureDiagnosis(
                        case_id=case_id,
                        scheme_id=target_id,
                        stage=SearchPipelineStage.CORPUS_INDEXING,
                        code=SearchFailureCode.STALE_EMBEDDING,
                        severity="MAJOR",
                        description=f"Scheme '{target_id}' has a stale vector embedding",
                        stage_evidence={"target_id": target_id},
                    )
                )

            # Check Stage B: SQL Candidate Filter
            if target_id not in sql_candidate_ids:
                diagnoses.append(
                    SearchFailureDiagnosis(
                        case_id=case_id,
                        scheme_id=target_id,
                        stage=SearchPipelineStage.SQL_CANDIDATE_FILTER,
                        code=SearchFailureCode.CANDIDATE_FILTER_FALSE_NEGATIVE,
                        severity="MAJOR",
                        description=f"Target scheme '{target_id}' was prematurely dropped by SQL candidate filtering",
                        stage_evidence={"total_candidates": len(sql_candidate_ids)},
                    )
                )
                continue

            # Check Stage C: Deterministic Eligibility Classification
            in_eligible = target_id in eligible_result_ids
            in_more_info = target_id in more_info_result_ids
            is_disqualified = target_id in not_eligible_ids

            if is_disqualified:
                diagnoses.append(
                    SearchFailureDiagnosis(
                        case_id=case_id,
                        scheme_id=target_id,
                        stage=SearchPipelineStage.ELIGIBILITY_BUCKETING,
                        code=SearchFailureCode.ELIGIBILITY_BUCKET_ERROR,
                        severity="MAJOR",
                        description=f"Relevant target scheme '{target_id}' was evaluated as NOT_ELIGIBLE and suppressed",
                        stage_evidence={"target_id": target_id},
                    )
                )
                continue

            # Check Stage D & E: Semantic Vector Ranking
            if target_id not in top_k_recommendations:
                # Survived SQL filter and eligibility, but ranked below top-K
                failure_code = SearchFailureCode.RELEVANT_SCHEME_LOW_RANK
                if language in ("hi-Latn", "hinglish"):
                    failure_code = SearchFailureCode.MULTILINGUAL_EMBEDDING_FAILURE

                diagnoses.append(
                    SearchFailureDiagnosis(
                        case_id=case_id,
                        scheme_id=target_id,
                        stage=SearchPipelineStage.SEMANTIC_RANKING,
                        code=failure_code,
                        severity="MINOR" if target_id in all_recommendations else "MAJOR",
                        description=f"Target scheme '{target_id}' ranked below top {top_k} recommendations",
                        stage_evidence={
                            "top_k": top_k,
                            "top_k_recommendations": top_k_recommendations,
                            "overall_recommendations_count": len(all_recommendations),
                        },
                    )
                )

        return diagnoses
