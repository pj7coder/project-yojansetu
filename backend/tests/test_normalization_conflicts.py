import pytest

from app.normalization.conflicts import detect_conflicts, merge_identical_conditions
from app.normalization.schemas import EligibilityCondition, NormalizationStatus, OperatorEnum


def test_true_conflict_detection_under_same_context():
    # Two chunks assert conflicting income limits under the same context
    c1 = EligibilityCondition(
        condition_id="COND-001",
        field="family_income",
        operator=OperatorEnum.LTE,
        value=200000,
        raw_text="वार्षिक पारिवारिक आय ₹2 लाख से अधिक नहीं",
        evidence_refs=["EVID-001"],
    )
    c2 = EligibilityCondition(
        condition_id="COND-002",
        field="family_income",
        operator=OperatorEnum.LTE,
        value=300000,
        raw_text="वार्षिक पारिवारिक आय ₹3 लाख से अधिक नहीं",
        evidence_refs=["EVID-002"],
    )

    processed, conflicts = detect_conflicts([c1, c2])

    assert len(conflicts) == 1
    assert conflicts[0].field == "family_income"
    assert conflicts[0].status == "REVIEW_REQUIRED"
    assert len(conflicts[0].values) == 2
    assert conflicts[0].values[0].value == 200000
    assert conflicts[0].values[0].evidence_refs == ["EVID-001"]
    assert conflicts[0].values[1].value == 300000
    assert conflicts[0].values[1].evidence_refs == ["EVID-002"]

    # Both conditions marked CONFLICT
    for c in processed:
        assert c.normalization_status == NormalizationStatus.CONFLICT


def test_contextual_difference_is_not_a_conflict():
    # Different categories (e.g. General vs SC/ST) have different income limits
    c_gen = EligibilityCondition(
        condition_id="COND-001",
        field="family_income",
        operator=OperatorEnum.LTE,
        value=200000,
        raw_text="सामान्य वर्ग: आय ₹2 लाख तक",
        context_qualifier="General",
        evidence_refs=["EVID-001"],
    )
    c_sc = EligibilityCondition(
        condition_id="COND-002",
        field="family_income",
        operator=OperatorEnum.LTE,
        value=300000,
        raw_text="अनुसूचित जाति: आय ₹3 लाख तक",
        context_qualifier="SC",
        evidence_refs=["EVID-002"],
    )

    processed, conflicts = detect_conflicts([c_gen, c_sc])

    # No conflict should be raised because contexts are different!
    assert len(conflicts) == 0
    assert len(processed) == 2


def test_duplicate_identical_fact_merging():
    # Chunks 1 and 3 both state "age >= 60"
    c1 = EligibilityCondition(
        condition_id="COND-001",
        field="age",
        operator=OperatorEnum.GTE,
        value=60,
        unit="years",
        raw_text="आयु 60 वर्ष या अधिक",
        evidence_refs=["EVID-001"],
    )
    c2 = EligibilityCondition(
        condition_id="COND-002",
        field="age",
        operator=OperatorEnum.GTE,
        value=60,
        unit="years",
        raw_text="आयु 60 वर्ष या अधिक",
        evidence_refs=["EVID-005"],
    )

    merged = merge_identical_conditions([c1, c2])

    assert len(merged) == 1
    assert merged[0].value == 60
    # Both evidence references merged without duplicate conditions
    assert set(merged[0].evidence_refs) == {"EVID-001", "EVID-005"}
