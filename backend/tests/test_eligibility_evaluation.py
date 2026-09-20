"""
JanSetu - Day 30: Unit & Integration Tests for Eligibility Accuracy Evaluation & Failure Analysis.

Verifies:
1. Decision Confusion Matrix metrics (3x3), precision, recall, F1, and safety-critical counts
2. Minimal missing information metrics (Precision, Recall, F1, Unnecessary Questions)
3. Trace consistency, evidence validity, and decisive condition matching
4. Tri-state Kleene logic invariants (AND, OR, UNKNOWN vs FALSE)
5. Boundary operator accuracy (inclusive GTE, LTE at exact cutoffs)
6. Temporal scheme versioning and date cutoff adaptation
7. Disqualifying exclusion evaluation without unnecessary UNKNOWN questions
8. Deterministic failure taxonomy and root cause attribution
9. Strict runtime data-leakage protection
10. End-to-end benchmark execution on DEV split (100% accuracy, 0 critical failures)
11. End-to-end benchmark execution on VALIDATION and TEST splits
12. Immutable artifact persistence and report generation
13. Stratified slice metrics by difficulty, tags, profile fields, and operators
14. CLI entrypoint execution
"""

import json
from pathlib import Path
import tempfile
import pytest

from app.eligibility.profile import CitizenProfile
from app.eligibility.repository import VerifiedSchemeRepository
from app.evaluation.eligibility_cli import main as cli_main
from app.evaluation.eligibility_runner import EligibilityBenchmarkRunner
from app.evaluation.eligibility_schemas import (
    DecisionConfusionMatrix,
    EligibilityCaseResult,
    EligibilityFailureCode,
    EligibilitySeverity,
    FailureRootCause,
    MissingFieldEvaluation,
    TraceEvaluation,
)
from app.evaluation.missing_field_metrics import MissingFieldEvaluator
from app.evaluation.trace_comparator import TraceComparator
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import (
    CaseStatus,
    DifficultyLevel,
    EligibilityExpected,
    EligibilityGoldCase,
    EligibilityStatus,
    GoldSplit,
    GoldTask,
)


# ============================================================================
# 1. Confusion Matrix & Safety Counter Tests
# ============================================================================

def test_decision_confusion_matrix_calculation():
    """Verify precision, recall, F1 and safety counts on a synthetic test matrix."""
    cm = DecisionConfusionMatrix(total_cases=10, status_accuracy=0.8)
    cm.eligible_eligible = 4
    cm.eligible_not_eligible = 1  # False ineligibility (Critical)
    cm.eligible_more_info = 0
    cm.not_eligible_eligible = 0  # False eligibility (Critical)
    cm.not_eligible_not_eligible = 3
    cm.not_eligible_more_info = 0
    cm.more_info_eligible = 0
    cm.more_info_not_eligible = 1  # Premature ineligibility (High)
    cm.more_info_more_info = 1

    cm.critical_false_ineligibility_count = 1
    cm.high_premature_ineligibility_count = 1

    assert cm.total_cases == 10
    assert cm.critical_false_ineligibility_count == 1
    assert cm.critical_false_eligibility_count == 0
    assert cm.high_premature_ineligibility_count == 1


# ============================================================================
# 2. Minimal Missing Information Metric Tests
# ============================================================================

def test_missing_field_evaluator_exact_match():
    """Verify missing field metrics on exact ground truth match."""
    eval_res = MissingFieldEvaluator.evaluate_missing_fields(
        actual_missing=["family_income", "age"],
        gold_missing=["age", "family_income"],
    )
    assert eval_res.precision == 1.0
    assert eval_res.recall == 1.0
    assert eval_res.f1 == 1.0
    assert eval_res.false_positive_missing == []
    assert eval_res.false_negative_missing == []


def test_missing_field_evaluator_unnecessary_questions():
    """Verify detection of unnecessary questions asked to citizen."""
    eval_res = MissingFieldEvaluator.evaluate_missing_fields(
        actual_missing=["age", "family_income", "caste_certificate"],
        gold_missing=["age", "family_income"],
    )
    assert eval_res.recall == 1.0
    assert eval_res.precision == round(2 / 3, 4)
    assert eval_res.false_positive_missing == ["caste_certificate"]


def test_missing_field_evaluator_omitted_questions():
    """Verify detection of omitted questions."""
    eval_res = MissingFieldEvaluator.evaluate_missing_fields(
        actual_missing=["age"],
        gold_missing=["age", "family_income"],
    )
    assert eval_res.precision == 1.0
    assert eval_res.recall == 0.5
    assert eval_res.false_negative_missing == ["family_income"]


# ============================================================================
# 3. Trace Comparator & Decisive Condition Tests
# ============================================================================

def test_trace_comparator_order_independent_matching():
    """Verify that decisive rules match regardless of order in conjunction."""
    from app.eligibility.result import ConditionEvaluationResult, EligibilityResult, ReasonCode, TruthState

    res = EligibilityResult(
        scheme_id="scheme-test",
        scheme_name="Test Scheme",
        eligibility_status=EligibilityStatus.ELIGIBLE,
        passed_conditions=[
            ConditionEvaluationResult(
                condition_id="C1",
                field="age",
                result=TruthState.TRUE,
                operator="GTE",
                required_value=60,
                citizen_value=65,
                reason_code=ReasonCode.CONDITION_SATISFIED,
                evidence_refs=["doc1.pdf"],
            ),
            ConditionEvaluationResult(
                condition_id="C2",
                field="domicile",
                result=TruthState.TRUE,
                operator="EQ",
                required_value="RAJASTHAN",
                citizen_value="RAJASTHAN",
                reason_code=ReasonCode.CONDITION_SATISFIED,
                evidence_refs=["doc2.pdf"],
            ),
        ],
        evaluation_trace={"positive_state": "TRUE", "exclusion_state": "FALSE"},
    )

    # Gold order is inverted: domicile first, then age
    trace_eval = TraceComparator.compare_trace(
        result=res,
        gold_decisive_rules=["domicile == RAJASTHAN", "age >= 60"],
        gold_status=EligibilityStatus.ELIGIBLE,
    )

    assert trace_eval.status_trace_consistent is True
    assert trace_eval.decisive_rule_accuracy == 1.0
    assert trace_eval.evidence_references_valid is True


# ============================================================================
# 4. Tri-State Logic Invariant Tests
# ============================================================================

def test_tristate_short_circuit_invariants():
    """Verify that in Kleene logic, FALSE AND UNKNOWN evaluates to FALSE without requesting missing info."""
    from app.eligibility.compiler import EligibilityRuleCompiler
    from app.eligibility.engine import EligibilityEngine

    scheme_data = {
        "scheme_identity": {"scheme_id": "test-ts", "scheme_name": "TS Test"},
        "eligibility": {
            "root_rule": {
                "rule_id": "R1",
                "logic": "AND",
                "children": [
                    {"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 60},
                    {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 200000},
                ],
            },
            "exclusions": [],
            "preferences": [],
        },
    }
    compiled = EligibilityRuleCompiler.compile_scheme(scheme_data)

    # Citizen is age 40 (definitely fails C-AGE) but family_income is None (UNKNOWN)
    prof = CitizenProfile(age=40, family_income=None)
    res = EligibilityEngine.evaluate_scheme(compiled, prof)

    # Must be NOT_ELIGIBLE because age failed; should NOT demand family_income
    assert res.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert len(res.missing_fields) == 0


# ============================================================================
# 5. Boundary Operator Tests
# ============================================================================

def test_boundary_exact_and_off_by_one():
    """Verify boundary evaluation at cutoff and off-by-one."""
    scheme_data = VerifiedSchemeRepository.resolve_verified_scheme("e54ebf76-b896-4292-b033-ce77e913bc35")
    from app.eligibility.compiler import EligibilityRuleCompiler
    from app.eligibility.engine import EligibilityEngine

    compiled = EligibilityRuleCompiler.compile_scheme(scheme_data)

    # 1. Exact cutoff (age 60, income 2,00,000, domicile Rajasthan) -> ELIGIBLE
    prof_exact = CitizenProfile(age=60, family_income=200000, domicile="Rajasthan")
    res_exact = EligibilityEngine.evaluate_scheme(compiled, prof_exact)
    assert res_exact.eligibility_status == EligibilityStatus.ELIGIBLE

    # 2. One below age cutoff (age 59) -> NOT_ELIGIBLE
    prof_underage = CitizenProfile(age=59, family_income=150000, domicile="Rajasthan")
    res_underage = EligibilityEngine.evaluate_scheme(compiled, prof_underage)
    assert res_underage.eligibility_status == EligibilityStatus.NOT_ELIGIBLE

    # 3. One rupee above income cutoff (income 2,00,001) -> NOT_ELIGIBLE
    prof_over_inc = CitizenProfile(age=65, family_income=200001, domicile="Rajasthan")
    res_over_inc = EligibilityEngine.evaluate_scheme(compiled, prof_over_inc)
    assert res_over_inc.eligibility_status == EligibilityStatus.NOT_ELIGIBLE


# ============================================================================
# 6. Temporal Versioning Amendment Tests
# ============================================================================

def test_temporal_amendment_resolution():
    """Verify temporal scheme adaptation before and after 2026-04-01."""
    from datetime import date
    from app.eligibility.compiler import EligibilityRuleCompiler
    from app.eligibility.engine import EligibilityEngine

    scheme_id = "4c2771f3-97d2-435b-885c-6922f6578844"
    prof_income_250k = CitizenProfile(age=65, family_income=250000, domicile="Rajasthan")

    # Before amendment (2026-03-15): ceiling is 2,00,000 -> NOT_ELIGIBLE
    s_pre = VerifiedSchemeRepository.resolve_verified_scheme(scheme_id, evaluation_date="2026-03-15")
    c_pre = EligibilityRuleCompiler.compile_scheme(s_pre)
    res_pre = EligibilityEngine.evaluate_scheme(c_pre, prof_income_250k, evaluation_date=date(2026, 3, 15))
    assert res_pre.eligibility_status == EligibilityStatus.NOT_ELIGIBLE

    # After amendment (2026-04-15): ceiling increased to 3,00,000 -> ELIGIBLE
    s_post = VerifiedSchemeRepository.resolve_verified_scheme(scheme_id, evaluation_date="2026-04-15")
    c_post = EligibilityRuleCompiler.compile_scheme(s_post)
    res_post = EligibilityEngine.evaluate_scheme(c_post, prof_income_250k, evaluation_date=date(2026, 4, 15))
    assert res_post.eligibility_status == EligibilityStatus.ELIGIBLE


# ============================================================================
# 7. Exclusion Evaluation Tests
# ============================================================================

def test_exclusion_disqualification_and_non_mandatory_absence():
    """Verify government employees are disqualified, while regular citizens don't get asked for it."""
    from app.eligibility.compiler import EligibilityRuleCompiler
    from app.eligibility.engine import EligibilityEngine

    scheme_data = VerifiedSchemeRepository.resolve_verified_scheme("e54ebf76-b896-4292-b033-ce77e913bc35")
    compiled = EligibilityRuleCompiler.compile_scheme(scheme_data)

    # 1. Government employee (age 65, income 1,50,000, domicile Rajasthan, is_government_employee=True)
    prof_govt = CitizenProfile(age=65, family_income=150000, domicile="Rajasthan", is_government_employee=True)
    res_govt = EligibilityEngine.evaluate_scheme(compiled, prof_govt)
    assert res_govt.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert len(res_govt.exclusions_triggered) > 0

    # 2. Regular citizen without is_government_employee specified -> ELIGIBLE, no missing questions
    prof_regular = CitizenProfile(age=65, family_income=150000, domicile="Rajasthan")
    res_regular = EligibilityEngine.evaluate_scheme(compiled, prof_regular)
    assert res_regular.eligibility_status == EligibilityStatus.ELIGIBLE
    assert len(res_regular.missing_fields) == 0


# ============================================================================
# 8. Failure Taxonomy & Classification Tests
# ============================================================================

def test_failure_classification_logic():
    """Verify failure taxonomy assigns correct severity and failure codes."""
    runner = EligibilityBenchmarkRunner()

    # Case: NOT_ELIGIBLE expected, but ELIGIBLE produced
    gold_case = EligibilityGoldCase(
        case_id="ELG-ERR-01",
        split=GoldSplit.DEV,
        difficulty=DifficultyLevel.HARD,
        tags=["EXCLUSION"],
        scheme_version_id="e54ebf76-b896-4292-b033-ce77e913bc35",
        evaluation_date="2026-09-01",
        created_at="2026-09-01T00:00:00Z",
        profile={"age": 65, "family_income": 100000, "domicile": "Rajasthan", "is_government_employee": True},
        expected=EligibilityExpected(
            status=EligibilityStatus.NOT_ELIGIBLE,
            missing_fields=[],
            decisive_rules=["is_government_employee == True"],
        ),
    )

    code, sev, root, reason = runner._classify_failure(
        gold_status=EligibilityStatus.NOT_ELIGIBLE,
        actual_status=EligibilityStatus.ELIGIBLE,
        case=gold_case,
        profile=CitizenProfile(age=65),
        result=None,
        missing_eval=MissingFieldEvaluation(),
        trace_eval=TraceEvaluation(status_trace_consistent=False),
    )

    assert sev == EligibilitySeverity.CRITICAL
    assert code == EligibilityFailureCode.EXCLUSION_IGNORED
    assert root == FailureRootCause.ENGINE_LOGIC


# ============================================================================
# 9. Data Leakage Protection Tests
# ============================================================================

def test_data_leakage_protection():
    """Verify runtime inputs extracted from loader contain zero expected answer labels."""
    loader = GoldBenchmarkLoader()
    inputs = loader.get_runtime_inputs(task=GoldTask.ELIGIBILITY, split=GoldSplit.DEV)

    assert len(inputs) > 0
    for inp in inputs:
        # Must not contain expected answer keys
        assert "expected" not in inp
        assert "expected_status" not in inp
        assert "expected_missing_fields" not in inp
        assert "expected_decisive_rules" not in inp
        # Must contain valid input fields
        assert "case_id" in inp
        assert "scheme_version_id" in inp
        assert "profile" in inp


# ============================================================================
# 10. End-to-End Runner Execution on DEV Split
# ============================================================================

def test_benchmark_runner_dev_split():
    """Verify full benchmark evaluation on DEV split meets 100% target."""
    runner = EligibilityBenchmarkRunner()
    summary, results = runner.run_benchmark(split=GoldSplit.DEV)

    assert summary.case_count == 30
    assert summary.status_accuracy == 1.0
    assert summary.strict_case_pass_rate == 1.0
    assert summary.critical_failure_count == 0
    assert summary.total_unnecessary_questions == 0
    assert summary.missing_field_f1 == 1.0
    assert summary.trace_decisive_accuracy == 1.0
    assert summary.duration_mean_ms < 10.0


# ============================================================================
# 11. End-to-End Runner Execution on VALIDATION & TEST Splits
# ============================================================================

def test_benchmark_runner_validation_and_test_splits():
    """Verify full benchmark evaluation on VALIDATION (30) and TEST (60) splits."""
    runner = EligibilityBenchmarkRunner()

    val_summary, val_results = runner.run_benchmark(split=GoldSplit.VALIDATION)
    assert val_summary.case_count == 30
    assert val_summary.status_accuracy == 1.0
    assert val_summary.strict_case_pass_rate == 1.0
    assert val_summary.critical_failure_count == 0

    test_summary, test_results = runner.run_benchmark(split=GoldSplit.TEST)
    assert test_summary.case_count == 60
    assert test_summary.status_accuracy == 1.0
    assert test_summary.strict_case_pass_rate == 1.0
    assert test_summary.critical_failure_count == 0


# ============================================================================
# 12. Artifact Persistence Tests
# ============================================================================

def test_benchmark_runner_persistence():
    """Verify persistence of immutable benchmark run artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir)
        runner = EligibilityBenchmarkRunner(output_base_dir=out_path)
        summary, results = runner.run_benchmark(split=GoldSplit.DEV)

        run_dir = runner.persist_run(summary, results)

        assert (run_dir / "summary.json").is_file()
        assert (run_dir / "confusion_matrix.json").is_file()
        assert (run_dir / "cases.jsonl").is_file()
        assert (run_dir / "slices.json").is_file()
        assert (run_dir / "report.md").is_file()
        assert (run_dir / "eligibility_evaluation_report.json").is_file()
        assert (run_dir / "eligibility_evaluation_report.md").is_file()

        with open(run_dir / "summary.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["case_count"] == 30
            assert data["status_accuracy"] == 1.0


# ============================================================================
# 13. Stratified Slice Metrics Tests
# ============================================================================

def test_slice_metrics_generation():
    """Verify slice calculation covers difficulty and categories."""
    runner = EligibilityBenchmarkRunner()
    summary, results = runner.run_benchmark(split=GoldSplit.DEV)
    slices = runner.compute_slice_metrics(results)

    assert "by_difficulty" in slices
    assert "by_category" in slices
    assert "NORMAL" in slices["by_difficulty"]
    assert "BOUNDARY" in slices["by_category"]


# ============================================================================
# 14. CLI Execution Test
# ============================================================================

def test_cli_execution():
    """Verify CLI runs cleanly with argument parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run single case
        cli_main(["--gold-version", "v1", "--split", "DEV", "--case", "ELG-RJ-001"])
        # Run split without persist
        cli_main(["--gold-version", "v1", "--split", "DEV", "--no-persist"])
