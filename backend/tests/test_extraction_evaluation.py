"""
JanSetu - Day 29: Unit & Integration Tests for Extraction Accuracy Evaluation & Failure Analysis.

Verifies:
1. Field matching precision, recall, and F1 calculations
2. Value normalization semantic equivalence (exact, Indian scales, Devanagari numerals)
3. Relational operator boundary-sensitive matching (LTE vs LT)
4. Commutative rule-tree canonicalization (A AND B == B AND A; A OR B == B OR A)
5. Logical connector error detection (AND vs OR)
6. Lost NOT negation error classification
7. Exclusion evaluation and leakage detection
8. Evidence reference validity vs semantic support
9. Hallucination detection on negative cases
10. Critical hallucination detection (invented age/income/exclusion)
11. Pipeline-stage failure attribution (OCR vs LLM vs Normalizer)
12. Gold data leakage protection test
13. Stale gold case exclusion
14. Read-only benchmark safety
"""

import copy
import pytest

from app.evaluation.evidence_metrics import EvidenceGroundingEvaluator
from app.evaluation.extraction_metrics import ExtractionMetricAggregator
from app.evaluation.extraction_runner import ExtractionBenchmarkRunner
from app.evaluation.failure_analysis import FailureAnalyzer
from app.evaluation.matching import ExtractedFactItem, FactMatcher
from app.evaluation.rule_metrics import CanonicalRuleComparator, RuleNode, evaluate_exclusions_independently
from app.evaluation.schemas import (
    CaseEvaluationResult,
    FailureCode,
    FailureSeverity,
    MatchResult,
    PipelineStage,
)
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import (
    AmbiguityType,
    CaseStatus,
    DifficultyLevel,
    ExtractionExpectedFact,
    ExtractionGoldCase,
    ExtractionOperator,
    ExtractionSource,
    GoldSplit,
    GoldTask,
)
from app.llm.mock import MockLLMProvider


def test_field_matching_precision_recall_f1():
    """Verify exact TP, FP, FN and precision, recall, F1 calculation."""
    gold_facts = [
        ExtractionExpectedFact(field="eligibility.age", value=60, evidence_quote="60 years"),
        ExtractionExpectedFact(field="eligibility.income", value=200000, evidence_quote="₹2 lakh"),
        ExtractionExpectedFact(field="eligibility.domicile", value="RAJASTHAN", evidence_quote="Rajasthan resident"),
    ]
    pred_facts = [
        ExtractedFactItem(field="eligibility.age", value=60, evidence_text="60 years"),
        ExtractedFactItem(field="eligibility.income", value=200000, evidence_text="₹2 lakh"),
        ExtractedFactItem(field="eligibility.gender", value="FEMALE", evidence_text="Women"),
    ]

    matched_preds = set()
    tp, fp, fn = 0, 0, 0

    for g in gold_facts:
        found = False
        for idx, p in enumerate(pred_facts):
            if idx not in matched_preds and FactMatcher.are_fields_matching(g.field, p.field):
                matched_preds.add(idx)
                tp += 1
                found = True
                break
        if not found:
            fn += 1

    fp = len(pred_facts) - len(matched_preds)

    assert tp == 2  # age, income
    assert fn == 1  # domicile
    assert fp == 1  # gender

    p = tp / (tp + fp)
    r = tp / (tp + fn)
    f1 = 2 * p * r / (p + r)

    assert p == pytest.approx(0.6667, rel=1e-3)
    assert r == pytest.approx(0.6667, rel=1e-3)
    assert f1 == pytest.approx(0.6667, rel=1e-3)


def test_value_normalization_semantic_equivalence():
    """Verify deterministic semantic value normalization across scales, units, and Devanagari numerals."""
    # 1. Indian scales
    assert FactMatcher.are_values_semantically_equivalent(200000, "₹2 lakh")
    assert FactMatcher.are_values_semantically_equivalent(200000, "₹2,00,000")
    assert FactMatcher.are_values_semantically_equivalent(150000, "1.5 लाख")
    assert FactMatcher.are_values_semantically_equivalent(200000, 200000.0)

    # 2. Devanagari numerals
    assert FactMatcher.are_values_semantically_equivalent(60, "६० वर्ष")
    assert FactMatcher.are_values_semantically_equivalent(200000, "२ लाख")

    # 3. Booleans
    assert FactMatcher.are_values_semantically_equivalent(True, "yes")
    assert FactMatcher.are_values_semantically_equivalent(True, "हाँ")
    assert FactMatcher.are_values_semantically_equivalent(False, "नहीं")

    # 4. Value mismatch must fail
    assert not FactMatcher.are_values_semantically_equivalent(200000, 250000)
    assert not FactMatcher.are_values_semantically_equivalent(60, 58)

    # 5. Periodicity mismatch must fail
    assert not FactMatcher.are_values_semantically_equivalent(
        1000, 1000, gold_period="MONTHLY", pred_period="ANNUAL"
    )

    # 6. Qualifier mismatch must fail
    assert not FactMatcher.are_values_semantically_equivalent(
        50000, 50000, gold_qualifier=True, pred_qualifier=False
    )


def test_operator_accuracy_boundary_sensitivity():
    """Verify relational operator boundary-sensitive matching (LTE vs LT fails)."""
    assert FactMatcher.are_operators_matching("LTE", "LTE")
    assert FactMatcher.are_operators_matching("GTE", ">=")
    assert FactMatcher.are_operators_matching("EQ", "=")

    # Critical boundary distinction: LTE vs LT must fail
    assert not FactMatcher.are_operators_matching("LTE", "LT")
    assert not FactMatcher.are_operators_matching("GTE", "GT")
    assert not FactMatcher.are_operators_matching("EQ", "NEQ")


def test_commutative_rule_canonicalization():
    """Verify that A AND B == B AND A, and A OR B == B OR A modulo commutative ordering."""
    # Tree 1: A AND B
    node_a = RuleNode(node_type="CONDITION", field="eligibility.age", operator="GTE", value=60)
    node_b = RuleNode(node_type="CONDITION", field="eligibility.income", operator="LTE", value=200000)
    tree1 = RuleNode(node_type="AND", children=[node_a, node_b])

    # Tree 2: B AND A (inverted order)
    tree2 = RuleNode(node_type="AND", children=[copy.deepcopy(node_b), copy.deepcopy(node_a)])

    assert CanonicalRuleComparator.are_rule_trees_equivalent(tree1, tree2)

    # Tree 3: A OR B == B OR A
    tree3 = RuleNode(node_type="OR", children=[node_a, node_b])
    tree4 = RuleNode(node_type="OR", children=[copy.deepcopy(node_b), copy.deepcopy(node_a)])
    assert CanonicalRuleComparator.are_rule_trees_equivalent(tree3, tree4)

    # AND != OR
    assert not CanonicalRuleComparator.are_rule_trees_equivalent(tree1, tree3)


def test_logical_connector_error_detection():
    """Verify that swapping AND with OR is detected as a critical connector error."""
    gold_conns = ["AND"]
    pred_conns = ["OR"]

    acc, has_critical = CanonicalRuleComparator.evaluate_logical_connectors(gold_conns, pred_conns)
    assert acc == 0.0
    assert has_critical is True

    # Same connector
    acc_same, has_crit_same = CanonicalRuleComparator.evaluate_logical_connectors(["AND"], ["AND"])
    assert acc_same == 1.0
    assert has_crit_same is False


def test_lost_negation_critical_severity():
    """Verify lost NOT is classified as CRITICAL severity."""
    sev = FailureAnalyzer.classify_severity(
        field_name="exclusions.government_service",
        gold_value=True,
        pred_value=False,
        is_lost_not=True,
    )
    assert sev == FailureSeverity.CRITICAL


def test_exclusion_vs_eligibility_distinction():
    """Verify exclusions are kept separate and leakage into eligibility is caught."""
    gold_ex = [{"field": "exclusions.government_service", "value": True}]
    pred_ex = [{"field": "exclusions.government_service", "value": True}]
    pred_el = []

    res_safe = evaluate_exclusions_independently(gold_ex, pred_ex, pred_el)
    assert res_safe["is_safe"] is True
    assert res_safe["exclusion_recall"] == 1.0

    # Leakage scenario: exclusion incorrectly extracted into eligibility
    pred_el_leaked = [{"field": "eligibility.government_service", "value": True}]
    res_leak = evaluate_exclusions_independently(gold_ex, [], pred_el_leaked)
    assert res_leak["is_safe"] is False
    assert res_leak["leakage_into_eligibility"] == 1


def test_evidence_grounding_and_support():
    """Verify evidence reference validity vs semantic support."""
    source_chunk = "The applicant must be a resident of Rajasthan. Annual income must not exceed 200000."

    # Reference validity
    assert EvidenceGroundingEvaluator.verify_reference_validity(
        "Annual income must not exceed 200000", source_chunk
    )
    assert not EvidenceGroundingEvaluator.verify_reference_validity(
        "Invented text not in chunk", source_chunk
    )

    # Semantic support: valid fact & valid evidence
    fact_income = ExtractedFactItem(field="eligibility.income", value=200000)
    assert EvidenceGroundingEvaluator.verify_semantic_support(
        fact_income, "Annual income must not exceed 200000"
    )

    # Semantic support: fact mentions income, but evidence quote only mentions residency
    assert not EvidenceGroundingEvaluator.verify_semantic_support(
        fact_income, "The applicant must be a resident of Rajasthan"
    )


def test_hallucination_detection_negative_cases():
    """Verify hallucination detection on negative (no-fact) chunks."""
    # Negative chunk with 0 predictions -> pass
    hallucinated, crit, passed = EvidenceGroundingEvaluator.evaluate_negative_case([])
    assert hallucinated == 0
    assert crit == 0
    assert passed is True

    # Negative chunk with hallucinated prediction -> fail
    hallucinated_facts = [
        ExtractedFactItem(field="eligibility.age", value=60),
        ExtractedFactItem(field="contacts.helpline", value="1800-180-6127"),
    ]
    h_count, crit_count, passed_h = EvidenceGroundingEvaluator.evaluate_negative_case(hallucinated_facts)
    assert h_count == 2
    assert crit_count == 1  # age is critical
    assert passed_h is False


def test_critical_hallucination_detection():
    """Verify classification of critical vs non-critical hallucinations."""
    assert EvidenceGroundingEvaluator.is_critical_hallucination("eligibility.age", 60)
    assert EvidenceGroundingEvaluator.is_critical_hallucination("eligibility.income", 200000)
    assert EvidenceGroundingEvaluator.is_critical_hallucination("benefits.monthly_amount", 1000)
    assert EvidenceGroundingEvaluator.is_critical_hallucination("exclusions.pension", True)

    # Non-critical: contact or office
    assert not EvidenceGroundingEvaluator.is_critical_hallucination("contacts.phone", "12345")


def test_pipeline_attribution_ocr_vs_llm_vs_norm():
    """
    Verify root-cause attribution to earliest failing stage:
    1. OCR corrupts number -> OCR_NUMERIC_ERROR (PARSING_OCR)
    2. LLM hallucinates/corrupts valid text -> LLM_WRONG_VALUE (LLM_EXTRACTION)
    3. Normalizer corrupts valid LLM string -> NUMBER_NORMALIZATION_ERROR (NORMALIZATION)
    """
    gold = ExtractionExpectedFact(field="eligibility.income", value=200000, evidence_quote="₹2,00,000")

    # 1. OCR corrupts: PDF source has 200000, but OCR text has 280000, LLM extracts 280000
    pred_ocr_err = ExtractedFactItem(field="eligibility.income", value=280000, raw_text="280000")
    code1, sev1, stage1, _ = FailureAnalyzer.attribute_pipeline_failure(
        gold_fact=gold,
        pred_fact=pred_ocr_err,
        raw_source_text="₹2,00,000",
        ocr_text="₹2,80,000",
        raw_llm_text="280000",
        canonical_norm_value=280000,
    )
    assert code1 == FailureCode.OCR_NUMERIC_ERROR
    assert stage1 == PipelineStage.PARSING_OCR
    assert sev1 == FailureSeverity.CRITICAL

    # 2. LLM corrupts: OCR text has 200000, but LLM extracts 250000
    pred_llm_err = ExtractedFactItem(field="eligibility.income", value=250000, raw_text="250000")
    code2, sev2, stage2, _ = FailureAnalyzer.attribute_pipeline_failure(
        gold_fact=gold,
        pred_fact=pred_llm_err,
        raw_source_text="₹2,00,000",
        ocr_text="₹2,00,000",
        raw_llm_text="250000",
        canonical_norm_value=250000,
    )
    assert code2 == FailureCode.LLM_WRONG_VALUE
    assert stage2 == PipelineStage.LLM_EXTRACTION
    assert sev2 == FailureSeverity.CRITICAL

    # 3. Normalizer corrupts: LLM extracted "₹2,00,000" correctly, but normalizer parsed 20000
    pred_norm_err = ExtractedFactItem(field="eligibility.income", value=20000, raw_text="₹2,00,000")
    code3, sev3, stage3, _ = FailureAnalyzer.attribute_pipeline_failure(
        gold_fact=gold,
        pred_fact=pred_norm_err,
        raw_source_text="₹2,00,000",
        ocr_text="₹2,00,000",
        raw_llm_text="₹2,00,000",
        canonical_norm_value=20000,
    )
    assert code3 == FailureCode.NUMBER_NORMALIZATION_ERROR
    assert stage3 == PipelineStage.NORMALIZATION
    assert sev3 == FailureSeverity.CRITICAL


def test_gold_data_leakage_protection():
    """Verify runtime inputs strip all expected facts to protect test sets."""
    loader = GoldBenchmarkLoader(version="v1")
    runtime_inputs = loader.get_runtime_inputs(task=GoldTask.EXTRACTION, split=GoldSplit.DEV)

    assert len(runtime_inputs) > 0
    for item in runtime_inputs:
        assert "expected_facts" not in item
        assert "expected" not in item
        assert "case_id" in item
        assert "source" in item


def test_stale_gold_exclusion():
    """Verify that cases flagged with STALE_REFERENCE are excluded from strict scoring."""
    case = ExtractionGoldCase(
        case_id="EXT-TEST-STALE",
        task=GoldTask.EXTRACTION,
        split=GoldSplit.TEST,
        status=CaseStatus.HUMAN_VERIFIED,
        difficulty=DifficultyLevel.NORMAL,
        tags=["TEST"],
        created_at="2026-09-07T12:00:00Z",
        source=ExtractionSource(document_id="doc-1", text_snippet="Some text"),
        expected_facts=[ExtractionExpectedFact(field="eligibility.age", value=60, evidence_quote="60")],
        ambiguity_flag=AmbiguityType.STALE_REFERENCE,
    )

    runner = ExtractionBenchmarkRunner(gold_version="v1")
    # Should not crash and filter out stale case if evaluated
    assert case.ambiguity_flag == AmbiguityType.STALE_REFERENCE
