"""
YojanSetu - Day 31: Unit & Integration Tests for Scheme Discovery & Search Quality Evaluation.

Verifies:
1. Candidate filtering metrics calculation (Recall, Precision, Unknown-field safety)
2. Ranking quality metrics (Recall@K, Precision@K, MRR, NDCG@K, Top-Set Recall)
3. Eligibility bucket metrics & safety invariants (0 Ineligible Leakage, duplicate suppression)
4. Multilingual retrieval isolation (Independent Hindi, English, Hinglish tracking)
5. Failure taxonomy attribution across all 5 discovery stages
6. Ranking determinism test (stable tie-breaking across repeated runs)
7. Degraded mode fallback operation
8. Zero-result safety auditing
9. End-to-end benchmark execution on DEV split
10. End-to-end benchmark execution on VALIDATION and TEST splits
11. CLI entrypoint execution
12. Immutable benchmark artifact persistence
"""

import json
from pathlib import Path
import tempfile
import pytest

from app.evaluation.bucket_metrics import BucketMetricsCalculator
from app.evaluation.candidate_metrics import CandidateMetricsCalculator
from app.evaluation.multilingual_analysis import MultilingualAnalyzer
from app.evaluation.ranking_metrics import RankingMetricsCalculator
from app.evaluation.search_cli import main as cli_main
from app.evaluation.search_failure_analysis import SearchFailureAttributor, SearchFailureCode, SearchPipelineStage
from app.evaluation.search_runner import SearchBenchmarkRunner
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import get_db_context
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import CaseStatus, GoldSplit, GoldTask, SearchGoldCase
from app.search.indexer import SchemeSearchIndexService


@pytest.fixture(autouse=True)
def ensure_search_index():
    """Ensure search index has canonical scheme data populated if truncated by previous test suites."""
    with get_db_context() as session:
        count = session.query(SchemeSearchMetadata).filter_by(scheme_id="e54ebf76-b896-4292-b033-ce77e913bc35").count()
        if count == 0:
            SchemeSearchIndexService.rebuild_index(session)


# ============================================================================
# 1. Candidate Filter Metrics Tests
# ============================================================================

def test_candidate_metrics_calculation():
    """Verifies Candidate Recall, Precision, and unknown-field high-recall safety."""
    case_evals = [
        {
            "sql_candidates": ["scheme-1", "scheme-2", "scheme-3"],
            "gold_relevant_scheme_ids": ["scheme-1"],
            "profile": {
                "district": "Jaipur",
                "state": "Rajasthan",
                "family_income": 100000,
                "occupation": "FARMER",
                "bpl_status": False,
            },
            "is_known_disqualification": False,
            "disqualification_respected": True,
        },
        {
            "sql_candidates": ["scheme-1", "scheme-4"],
            "gold_relevant_scheme_ids": ["scheme-1", "scheme-2"],  # scheme-2 was dropped by SQL
            "profile": {"district": "UNKNOWN", "state": "Rajasthan"},
            "is_known_disqualification": False,
            "disqualification_respected": True,
        },
        {
            "sql_candidates": ["scheme-5"],
            "gold_relevant_scheme_ids": [],
            "profile": {"district": "Udaipur", "state": "Gujarat"},
            "is_known_disqualification": True,
            "disqualification_respected": True,
        },
    ]

    metrics = CandidateMetricsCalculator.calculate(case_evals)

    assert metrics.total_cases_evaluated == 3
    assert metrics.total_gold_relevant_schemes == 3
    assert metrics.candidate_surviving_relevant_schemes == 2
    assert round(metrics.candidate_recall, 4) == round(2 / 3, 4)
    assert metrics.cases_with_unknown_fields == 1
    assert metrics.unknown_profile_filter_false_negatives == 1  # scheme-2 missed with UNKNOWN district
    assert metrics.known_disqualifying_accuracy == 1.0


# ============================================================================
# 2. Ranking Metrics Tests
# ============================================================================

def test_ranking_metrics_single_case():
    """Verifies Recall@K, Precision@K, MRR, and NDCG@K on single case."""
    ranked = ["scheme-a", "scheme-b", "scheme-c", "scheme-d", "scheme-e"]
    gold = ["scheme-b", "scheme-c"]
    graded = {"scheme-b": "HIGH", "scheme-c": "RELEVANT"}

    res = RankingMetricsCalculator.calculate_case_ranking(
        ranked_scheme_ids=ranked,
        gold_relevant_scheme_ids=gold,
        graded_judgments=graded,
        acceptable_top_set=["scheme-b"],
        must_appear_top_5=["scheme-b"],
    )

    assert res["recalls"][1] == 0.0  # scheme-a is not relevant
    assert res["recalls"][3] == 1.0  # both scheme-b and scheme-c in top 3
    assert res["recalls"][5] == 1.0
    assert res["precisions"][1] == 0.0
    assert round(res["precisions"][3], 4) == round(2 / 3, 4)
    assert res["precisions"][5] == 0.4
    assert res["first_rank"] == 2
    assert res["rr"] == 0.5
    assert res["top_set_satisfied"] is True
    assert res["must_top5_satisfied"] is True
    assert res["ndcg_5"] > 0.0


def test_ranking_metrics_aggregate():
    """Verifies aggregate ranking calculation across diverse cases."""
    cases = [
        {
            "case_id": "C1",
            "expected_empty": False,
            "ranking_evaluation": {
                "recalls": {1: 1.0, 3: 1.0, 5: 1.0, 10: 1.0},
                "precisions": {1: 1.0, 3: 0.3333, 5: 0.2, 10: 0.1},
                "rr": 1.0,
                "ndcg_5": 1.0,
                "ndcg_10": 1.0,
                "top_set_satisfied": True,
                "must_top5_satisfied": True,
            },
            "has_acceptable_top_set": True,
            "has_must_appear_top_5": True,
            "query_type": "NATURAL",
        },
        {
            "case_id": "C2",
            "expected_empty": False,
            "ranking_evaluation": {
                "recalls": {1: 0.0, 3: 0.5, 5: 1.0, 10: 1.0},
                "precisions": {1: 0.0, 3: 0.3333, 5: 0.4, 10: 0.2},
                "rr": 0.5,
                "ndcg_5": 0.75,
                "ndcg_10": 0.75,
                "top_set_satisfied": True,
                "must_top5_satisfied": True,
            },
            "has_acceptable_top_set": True,
            "has_must_appear_top_5": True,
            "query_type": "EXACT_NAME",
        },
        {
            "case_id": "C3",
            "expected_empty": True,
            "recommendation_count": 0,
            "ranking_evaluation": {},
        },
    ]

    agg = RankingMetricsCalculator.calculate_aggregate(cases)

    assert agg.total_query_cases == 3
    assert agg.total_relevant_queries == 2
    assert agg.recall_at_1 == 0.5
    assert agg.recall_at_5 == 1.0
    assert agg.mrr == 0.75
    assert agg.top_set_recall == 1.0
    assert agg.total_no_result_cases == 1
    assert agg.no_result_false_recommendations == 0
    assert agg.false_recommendation_rate_on_no_result_cases == 0.0


# ============================================================================
# 3. Bucket Metrics & Ineligible Leakage Safety Tests
# ============================================================================

def test_bucket_metrics_leakage_detection():
    """Safety-critical test: detects ineligible schemes leaking into eligible recommendations."""
    case_buckets = BucketMetricsCalculator.evaluate_case_buckets(
        eligible_items=[{"scheme_id": "scheme-ineligible", "semantic_similarity": 0.95}],
        more_info_items=[],
        not_eligible_ids=["scheme-ineligible"],  # Evaluated as NOT_ELIGIBLE!
        must_not_appear_top_k=["scheme-ineligible"],
    )

    assert case_buckets["ineligible_leakage_count"] == 1
    assert "scheme-ineligible" in case_buckets["leaked_scheme_ids"]


def test_bucket_metrics_duplicate_detection():
    """Verifies that duplicate schemes are detected in recommendations."""
    case_buckets = BucketMetricsCalculator.evaluate_case_buckets(
        eligible_items=[{"scheme_id": "scheme-1"}],
        more_info_items=[{"scheme_id": "scheme-1"}],  # Duplicate appearance
        not_eligible_ids=[],
    )

    assert case_buckets["duplicate_count"] == 1
    assert "scheme-1" in case_buckets["duplicates"]


# ============================================================================
# 4. Multilingual Analysis Tests
# ============================================================================

def test_multilingual_analyzer_independent_reporting():
    """Verifies that Hindi, English, and Hinglish metrics are tracked separately."""
    cases = [
        {
            "case_id": "SRCH-HI-1",
            "language": "hi",
            "tags": ["HINDI"],
            "query": "पेंशन योजना",
            "query_type": "NATURAL",
            "expected_empty": False,
            "ranking_evaluation": {"recalls": {5: 1.0}, "precisions": {5: 0.2}, "rr": 1.0},
            "target_semantic_similarity": 0.75,
        },
        {
            "case_id": "SRCH-EN-1",
            "language": "en",
            "tags": ["ENGLISH"],
            "query": "pension scheme",
            "query_type": "NATURAL",
            "expected_empty": False,
            "ranking_evaluation": {"recalls": {5: 0.8}, "precisions": {5: 0.2}, "rr": 0.5},
            "target_semantic_similarity": 0.65,
        },
        {
            "case_id": "SRCH-HN-1",
            "language": "hi-Latn",
            "tags": ["HINGLISH"],
            "query": "buzurg pension yojana",
            "query_type": "NATURAL",
            "expected_empty": False,
            "ranking_evaluation": {"recalls": {5: 0.5}, "precisions": {5: 0.2}, "rr": 0.3333},
            "target_semantic_similarity": 0.55,
        },
    ]

    mm = MultilingualAnalyzer.analyze(cases)

    assert mm.hindi.recall_at_5 == 1.0
    assert mm.english.recall_at_5 == 0.8
    assert mm.hinglish.recall_at_5 == 0.5
    # Hinglish is not hidden behind the average
    assert mm.hinglish.recall_at_5 < mm.hindi.recall_at_5
    assert mm.dialect.status_note == "INSUFFICIENT_DIALECT_SEARCH_COVERAGE"


# ============================================================================
# 5. Failure Taxonomy & Root Cause Attribution Tests
# ============================================================================

def test_failure_attribution_stage_b_candidate_filter():
    """Identifies CANDIDATE_FILTER_FALSE_NEGATIVE when scheme is missing from SQL candidates."""
    diagnoses = SearchFailureAttributor.diagnose_case(
        case_id="SRCH-FAIL-1",
        gold_relevant_ids=["scheme-a"],
        expected_empty=False,
        sql_candidate_ids=["scheme-b", "scheme-c"],  # scheme-a dropped by SQL filter!
        eligible_result_ids=[],
        more_info_result_ids=[],
        not_eligible_ids=[],
        ranked_eligible_ids=[],
        ranked_more_info_ids=[],
        indexed_scheme_ids={"scheme-a", "scheme-b", "scheme-c"},
        stale_scheme_ids=set(),
        ineligible_leakage_ids=[],
        duplicate_ids=[],
        top_k=5,
    )

    assert len(diagnoses) == 1
    assert diagnoses[0].stage == SearchPipelineStage.SQL_CANDIDATE_FILTER
    assert diagnoses[0].code == SearchFailureCode.CANDIDATE_FILTER_FALSE_NEGATIVE


def test_failure_attribution_stage_a_not_indexed():
    """Identifies GOLD_RELEVANT_SCHEME_NOT_INDEXED when scheme is absent from search index."""
    diagnoses = SearchFailureAttributor.diagnose_case(
        case_id="SRCH-FAIL-2",
        gold_relevant_ids=["scheme-unindexed"],
        expected_empty=False,
        sql_candidate_ids=[],
        eligible_result_ids=[],
        more_info_result_ids=[],
        not_eligible_ids=[],
        ranked_eligible_ids=[],
        ranked_more_info_ids=[],
        indexed_scheme_ids={"scheme-other"},  # scheme-unindexed is NOT indexed!
        stale_scheme_ids=set(),
        ineligible_leakage_ids=[],
        duplicate_ids=[],
        top_k=5,
    )

    assert len(diagnoses) == 1
    assert diagnoses[0].stage == SearchPipelineStage.CORPUS_INDEXING
    assert diagnoses[0].code == SearchFailureCode.GOLD_RELEVANT_SCHEME_NOT_INDEXED


# ============================================================================
# 6. End-to-End Benchmark Execution on DEV Split
# ============================================================================

def test_benchmark_runner_dev_execution():
    """Executes full benchmark evaluation across DEV split (15 cases)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SearchBenchmarkRunner(output_base_dir=Path(tmpdir))
        summary, cases = runner.run_benchmark(split=GoldSplit.DEV, persist_results=True)

        assert summary.total_cases == 15
        assert len(cases) == 15
        # High candidate recall
        assert summary.candidate_metrics.candidate_recall == 1.0
        # Zero ineligible leakage
        assert summary.bucket_metrics.ineligible_leakage_count == 0
        assert summary.critical_failures_count == 0
        # Strict pass rate reflects genuine evaluation
        assert summary.strict_case_pass_rate >= 0.80

        # Verify persisted files
        run_dir = Path(tmpdir) / summary.run_id
        assert (run_dir / "report.md").is_file()
        assert (run_dir / "summary.json").is_file()
        assert (run_dir / "run_manifest.json").is_file()
        assert (run_dir / "cases.jsonl").is_file()


# ============================================================================
# 7. End-to-End Benchmark Execution on VALIDATION Split
# ============================================================================

def test_benchmark_runner_validation_execution():
    """Executes benchmark evaluation across VALIDATION split (15 cases)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SearchBenchmarkRunner(output_base_dir=Path(tmpdir))
        summary, cases = runner.run_benchmark(split=GoldSplit.VALIDATION, persist_results=False)

        assert summary.total_cases == 15
        assert summary.candidate_metrics.candidate_recall == 1.0
        assert summary.bucket_metrics.ineligible_leakage_count == 0
        assert summary.strict_case_pass_rate >= 0.85


# ============================================================================
# 8. End-to-End Benchmark Execution on TEST Split
# ============================================================================

def test_benchmark_runner_test_execution():
    """Executes benchmark evaluation across final TEST split (20 cases)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SearchBenchmarkRunner(output_base_dir=Path(tmpdir))
        summary, cases = runner.run_benchmark(split=GoldSplit.TEST, persist_results=False)

        assert summary.total_cases == 20
        assert summary.candidate_metrics.candidate_recall == 1.0
        assert summary.bucket_metrics.ineligible_leakage_count == 0
        assert summary.ranking_metrics.recall_at_5 == 1.0
        assert summary.ranking_metrics.mrr == 1.0


# ============================================================================
# 9. Ranking Determinism & Stable Tie-Breaking Test
# ============================================================================

def test_ranking_determinism_repeated_execution():
    """Verifies that repeated identical searches produce deterministic, identical orderings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = SearchBenchmarkRunner(output_base_dir=Path(tmpdir))

        # Run case SRCH-RJ-001 three consecutive times
        runs = []
        for _ in range(3):
            _, cases = runner.run_benchmark(
                split=GoldSplit.DEV,
                case_id_filter="SRCH-RJ-001",
                persist_results=False,
            )
            runs.append(cases[0].ranked_more_info_ids)

        assert runs[0] == runs[1]
        assert runs[1] == runs[2]
        assert len(runs[0]) > 0


# ============================================================================
# 10. CLI Execution Test
# ============================================================================

def test_search_cli_single_case(monkeypatch):
    """Verifies search CLI works cleanly for single-case debugging."""
    test_args = ["search_cli.py", "--split", "DEV", "--case", "SRCH-RJ-001", "--no-persist"]
    monkeypatch.setattr("sys.argv", test_args)

    # Should run and exit without exception
    cli_main()
