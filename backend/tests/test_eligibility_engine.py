from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.eligibility.availability import check_scheme_availability
from app.eligibility.compiler import CompilationError, EligibilityRuleCompiler
from app.eligibility.engine import EligibilityEngine
from app.eligibility.evaluator import RuleEvaluator
from app.eligibility.models import CompiledScheme, ConditionNode, ExclusionNode, GroupNode
from app.eligibility.operators import (
    evaluate_operator,
    op_between,
    op_eq,
    op_gt,
    op_gte,
    op_in,
    op_lt,
    op_lte,
    op_ne,
    op_not_in,
)
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus, ReasonCode, SchemeAvailability
from app.eligibility.truth import TruthState, evaluate_and, evaluate_not, evaluate_or


# ===========================================================================
# 1. Operators & Boundary Tests
# ===========================================================================

def test_boundary_operators():
    # GTE 60
    assert op_gte(60, 60) == TruthState.TRUE
    assert op_gte(64, 60) == TruthState.TRUE
    assert op_gte(59, 60) == TruthState.FALSE

    # GT 60
    assert op_gt(60, 60) == TruthState.FALSE
    assert op_gt(61, 60) == TruthState.TRUE
    assert op_gt(59, 60) == TruthState.FALSE

    # LTE 60
    assert op_lte(60, 60) == TruthState.TRUE
    assert op_lte(59, 60) == TruthState.TRUE
    assert op_lte(61, 60) == TruthState.FALSE

    # LT 60
    assert op_lt(60, 60) == TruthState.FALSE
    assert op_lt(59, 60) == TruthState.TRUE
    assert op_lt(61, 60) == TruthState.FALSE


def test_between_operator():
    # Between 18 and 40 (inclusive)
    assert op_between(18, [18, 40]) == TruthState.TRUE
    assert op_between(40, [18, 40]) == TruthState.TRUE
    assert op_between(25, [18, 40]) == TruthState.TRUE
    assert op_between(17, [18, 40]) == TruthState.FALSE
    assert op_between(41, [18, 40]) == TruthState.FALSE


def test_membership_operators():
    categories = ["SC", "ST"]
    assert op_in("SC", categories) == TruthState.TRUE
    assert op_in("sc", categories) == TruthState.TRUE
    assert op_in("ST", categories) == TruthState.TRUE
    assert op_in("OBC", categories) == TruthState.FALSE
    assert op_in(None, categories) == TruthState.UNKNOWN

    assert op_not_in("OBC", categories) == TruthState.TRUE
    assert op_not_in("SC", categories) == TruthState.FALSE
    assert op_not_in(None, categories) == TruthState.UNKNOWN


def test_operators_with_missing_values():
    assert evaluate_operator("GTE", None, 60) == TruthState.UNKNOWN
    assert evaluate_operator("EQ", None, "Rajasthan") == TruthState.UNKNOWN
    assert evaluate_operator("EXISTS", None, None) == TruthState.FALSE
    assert evaluate_operator("EXISTS", 0, None) == TruthState.TRUE
    assert evaluate_operator("EXISTS", False, None) == TruthState.TRUE
    assert evaluate_operator("NOT_EXISTS", None, None) == TruthState.TRUE
    assert evaluate_operator("NOT_EXISTS", 42, None) == TruthState.FALSE


# ===========================================================================
# 2. Kleene Three-Valued Logic Truth Tables
# ===========================================================================

def test_and_truth_table():
    # TRUE + TRUE -> TRUE
    assert evaluate_and([TruthState.TRUE, TruthState.TRUE]) == TruthState.TRUE
    # TRUE + FALSE -> FALSE
    assert evaluate_and([TruthState.TRUE, TruthState.FALSE]) == TruthState.FALSE
    # TRUE + UNKNOWN -> UNKNOWN
    assert evaluate_and([TruthState.TRUE, TruthState.UNKNOWN]) == TruthState.UNKNOWN
    # FALSE + UNKNOWN -> FALSE (Short-circuit / definitive rejection)
    assert evaluate_and([TruthState.FALSE, TruthState.UNKNOWN]) == TruthState.FALSE
    assert evaluate_and([TruthState.UNKNOWN, TruthState.FALSE]) == TruthState.FALSE
    # UNKNOWN + UNKNOWN -> UNKNOWN
    assert evaluate_and([TruthState.UNKNOWN, TruthState.UNKNOWN]) == TruthState.UNKNOWN


def test_or_truth_table():
    # TRUE + UNKNOWN -> TRUE (Short-circuit / definitive satisfaction)
    assert evaluate_or([TruthState.TRUE, TruthState.UNKNOWN]) == TruthState.TRUE
    assert evaluate_or([TruthState.UNKNOWN, TruthState.TRUE]) == TruthState.TRUE
    # FALSE + TRUE -> TRUE
    assert evaluate_or([TruthState.FALSE, TruthState.TRUE]) == TruthState.TRUE
    # FALSE + FALSE -> FALSE
    assert evaluate_or([TruthState.FALSE, TruthState.FALSE]) == TruthState.FALSE
    # FALSE + UNKNOWN -> UNKNOWN
    assert evaluate_or([TruthState.FALSE, TruthState.UNKNOWN]) == TruthState.UNKNOWN
    # UNKNOWN + UNKNOWN -> UNKNOWN
    assert evaluate_or([TruthState.UNKNOWN, TruthState.UNKNOWN]) == TruthState.UNKNOWN


def test_not_truth_table():
    assert evaluate_not(TruthState.TRUE) == TruthState.FALSE
    assert evaluate_not(TruthState.FALSE) == TruthState.TRUE
    assert evaluate_not(TruthState.UNKNOWN) == TruthState.UNKNOWN


# ===========================================================================
# 3. Citizen Profile Validation & Normalization
# ===========================================================================

def test_profile_impossible_inputs():
    # Negative age rejected
    with pytest.raises(ValueError):
        CitizenProfile(age=-5)

    # Negative income rejected
    with pytest.raises(ValueError):
        CitizenProfile(family_income=-2000)

    # Disability percentage > 100 rejected
    with pytest.raises(ValueError):
        CitizenProfile(disability_percentage=150)

    # Family size < 1 rejected
    with pytest.raises(ValueError):
        CitizenProfile(family_size=0)


def test_profile_income_monthly_to_annual():
    p = CitizenProfile(
        family_income=15000,
        family_income_frequency="MONTHLY",
    )
    assert p.family_income == Decimal("180000")
    assert p.family_income_frequency == "ANNUAL"


def test_profile_district_alias_resolution():
    # Hindi "उदयपुर" maps to canonical "Udaipur"
    p = CitizenProfile(district="उदयपुर")
    assert p.district == "Udaipur"

    p2 = CitizenProfile(district="ajmer")
    assert p2.district == "Ajmer"


def test_profile_distinctions():
    p = CitizenProfile(
        annual_income=100000,
        state="Rajasthan",
    )
    # Family income must NOT be auto-populated from annual personal income
    assert p.family_income is None
    # Domicile must NOT be auto-populated from current state
    assert p.domicile_status is None
    # Farmer status must NOT be assumed without explicit setting
    assert p.farmer_status is None


# ===========================================================================
# 4. Pure Engine Condition Evaluation
# ===========================================================================

def test_simple_age_evaluations():
    rule_tree = {
        "condition_id": "COND-AGE",
        "field": "age",
        "operator": "GTE",
        "value": 60,
    }
    scheme = {
        "scheme_identity": {"scheme_id": "TEST-SCHEME", "name": {"en": "Old Age Assistance"}},
        "eligibility": {"root_rule": rule_tree},
    }

    # Citizen 1: Age 64 -> ELIGIBLE
    res1 = EligibilityEngine.evaluate_scheme(scheme, {"age": 64})
    assert res1.eligibility_status == EligibilityStatus.ELIGIBLE
    assert len(res1.passed_conditions) == 1

    # Citizen 2: Age 50 -> NOT_ELIGIBLE
    res2 = EligibilityEngine.evaluate_scheme(scheme, {"age": 50})
    assert res2.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert len(res2.failed_conditions) == 1

    # Citizen 3: Age missing -> MORE_INFORMATION_REQUIRED
    res3 = EligibilityEngine.evaluate_scheme(scheme, {})
    assert res3.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert len(res3.missing_fields) == 1
    assert res3.missing_fields[0].field == "age"


def test_minimal_missing_fields_in_or_branch():
    # Rule: BPL = true OR family_income <= 200000
    rule = {
        "type": "OR",
        "children": [
            {"condition_id": "C-BPL", "field": "bpl_status", "operator": "EQ", "value": True},
            {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 200000},
        ],
    }
    scheme = {
        "scheme_identity": {"scheme_id": "TEST-OR", "name": "BPL or Low Income"},
        "eligibility": {"root_rule": rule},
    }

    # Citizen with BPL true, income missing -> ELIGIBLE, NO missing fields required!
    res = EligibilityEngine.evaluate_scheme(scheme, {"bpl_status": True})
    assert res.eligibility_status == EligibilityStatus.ELIGIBLE
    assert res.missing_fields == []


def test_and_short_circuit_definitely_not_eligible():
    # Rule: State = Rajasthan AND age >= 60 AND family_income <= 200000
    rule = {
        "type": "AND",
        "children": [
            {"condition_id": "C-ST", "field": "state", "operator": "EQ", "value": "Rajasthan"},
            {"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 60},
            {"condition_id": "C-INC", "field": "family_income", "operator": "LTE", "value": 200000},
        ],
    }
    scheme = {
        "scheme_identity": {"scheme_id": "TEST-AND", "name": "Rajasthan Senior Low Income"},
        "eligibility": {"root_rule": rule},
    }

    # Citizen is Gujarat resident, age and income missing
    # Result is already NOT_ELIGIBLE, and should NOT ask for age or income!
    res = EligibilityEngine.evaluate_scheme(scheme, {"state": "Gujarat"})
    assert res.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert res.missing_fields == []
    assert res.evaluation_trace["conditions_short_circuited"] >= 1


def test_nested_rule():
    # Rule: State = Rajasthan AND (BPL = true OR (family_income <= 200000 AND age >= 60))
    rule = {
        "type": "AND",
        "children": [
            {"condition_id": "C1", "field": "state", "operator": "EQ", "value": "Rajasthan"},
            {
                "type": "OR",
                "children": [
                    {"condition_id": "C2", "field": "bpl_status", "operator": "EQ", "value": True},
                    {
                        "type": "AND",
                        "children": [
                            {"condition_id": "C3", "field": "family_income", "operator": "LTE", "value": 200000},
                            {"condition_id": "C4", "field": "age", "operator": "GTE", "value": 60},
                        ],
                    },
                ],
            },
        ],
    }
    scheme = {
        "scheme_identity": {"scheme_id": "TEST-NESTED", "name": "Complex Nested Scheme"},
        "eligibility": {"root_rule": rule},
    }

    # Profile 1: Rajasthan, BPL true -> ELIGIBLE
    r1 = EligibilityEngine.evaluate_scheme(scheme, {"state": "Rajasthan", "bpl_status": True})
    assert r1.eligibility_status == EligibilityStatus.ELIGIBLE

    # Profile 2: Rajasthan, BPL false, income 150000, age 65 -> ELIGIBLE
    r2 = EligibilityEngine.evaluate_scheme(
        scheme,
        {"state": "Rajasthan", "bpl_status": False, "family_income": 150000, "age": 65},
    )
    assert r2.eligibility_status == EligibilityStatus.ELIGIBLE

    # Profile 3: Rajasthan, BPL false, income 150000, age missing -> MORE_INFORMATION_REQUIRED
    r3 = EligibilityEngine.evaluate_scheme(
        scheme,
        {"state": "Rajasthan", "bpl_status": False, "family_income": 150000},
    )
    assert r3.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert any(m.field == "age" for m in r3.missing_fields)


# ===========================================================================
# 5. Exclusions & Disqualification Rules
# ===========================================================================

def test_exclusions_evaluation():
    scheme = {
        "scheme_identity": {"scheme_id": "EXCL-SCHEME", "name": "Scheme With Exclusion"},
        "eligibility": {
            "root_rule": {
                "condition_id": "C-AGE",
                "field": "age",
                "operator": "GTE",
                "value": 60,
            }
        },
        "exclusions": [
            {
                "exclusion_id": "EX-001",
                "field": "receiving_pension_x",
                "operator": "EQ",
                "value": True,
                "raw_text": "Not eligible if already receiving Pension X",
            }
        ],
    }

    # Citizen 1: Age 65, receiving_pension_x = True -> NOT_ELIGIBLE (Exclusion triggered)
    res1 = EligibilityEngine.evaluate_scheme(scheme, {"age": 65, "receiving_pension_x": True})
    assert res1.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert len(res1.exclusions_triggered) == 1

    # Citizen 2: Age 65, receiving_pension_x = False -> ELIGIBLE
    res2 = EligibilityEngine.evaluate_scheme(scheme, {"age": 65, "receiving_pension_x": False})
    assert res2.eligibility_status == EligibilityStatus.ELIGIBLE
    assert len(res2.exclusions_triggered) == 0

    # Citizen 3: Age 65, receiving_pension_x unknown -> MORE_INFORMATION_REQUIRED
    res3 = EligibilityEngine.evaluate_scheme(scheme, {"age": 65})
    assert res3.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert any(m.field == "receiving_pension_x" for m in res3.missing_fields)

    # Citizen 4: Age 45 (fails positive), receiving_pension_x unknown -> NOT_ELIGIBLE (Exclusion short-circuited!)
    res4 = EligibilityEngine.evaluate_scheme(scheme, {"age": 45})
    assert res4.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert res4.missing_fields == []


# ===========================================================================
# 6. Preferences (Non-Blocking)
# ===========================================================================

def test_preferences_do_not_block_eligibility():
    scheme = {
        "scheme_identity": {"scheme_id": "PREF-SCHEME", "name": "Widow Preference Scheme"},
        "eligibility": {
            "root_rule": {
                "type": "AND",
                "children": [
                    {"condition_id": "C-AGE", "field": "age", "operator": "GTE", "value": 60},
                    {
                        "condition_id": "C-WIDOW",
                        "field": "widow_status",
                        "operator": "EQ",
                        "value": True,
                        "context_qualifier": "PREFERENCE",
                        "raw_text": "Preference given to widows",
                    },
                ],
            }
        },
    }

    # Citizen aged 65, not a widow: must be ELIGIBLE
    res = EligibilityEngine.evaluate_scheme(scheme, {"age": 65, "widow_status": False})
    assert res.eligibility_status == EligibilityStatus.ELIGIBLE
    assert len(res.preferences_matched) == 0

    # Citizen aged 65, widow: ELIGIBLE + preference matched
    res2 = EligibilityEngine.evaluate_scheme(scheme, {"age": 65, "widow_status": True})
    assert res2.eligibility_status == EligibilityStatus.ELIGIBLE
    assert len(res2.preferences_matched) == 1


# ===========================================================================
# 7. Scheme Availability (Temporal Date Checks)
# ===========================================================================

def test_scheme_temporal_availability():
    scheme_raw = {
        "scheme_identity": {"scheme_id": "DATE-SCHEME", "name": "Dated Scheme"},
        "important_dates": [
            {"event_name": "launch date", "normalized_date": "2026-01-01"},
            {"event_name": "expiry date", "normalized_date": "2026-12-31"},
        ],
        "eligibility": {
            "root_rule": {"condition_id": "C1", "field": "age", "operator": "GTE", "value": 60}
        },
    }
    compiled = EligibilityEngine.compile_scheme(scheme_raw)

    # Active date
    avail_now = check_scheme_availability(compiled, date(2026, 6, 1))
    assert avail_now == SchemeAvailability.ACTIVE

    # Future date (not yet active)
    avail_past = check_scheme_availability(compiled, date(2025, 12, 1))
    assert avail_past == SchemeAvailability.NOT_YET_ACTIVE

    # Expired date
    avail_future = check_scheme_availability(compiled, date(2027, 1, 15))
    assert avail_future == SchemeAvailability.EXPIRED

    # Evaluate against expired date
    res = EligibilityEngine.evaluate_scheme(compiled, {"age": 65}, evaluation_date=date(2027, 1, 15))
    assert res.availability == SchemeAvailability.EXPIRED
    assert res.eligibility_status == EligibilityStatus.NOT_ELIGIBLE


# ===========================================================================
# 8. Defensive Compilation & Cycle Protection
# ===========================================================================

def test_compiler_depth_and_cycle_protection():
    # Build deep nesting > 10
    deep_rule: dict = {"condition_id": "C-LEAF", "field": "age", "operator": "GTE", "value": 60}
    for i in range(12):
        deep_rule = {"type": "AND", "children": [deep_rule]}

    scheme = {
        "scheme_identity": {"scheme_id": "DEEP-SCHEME", "name": "Deep"},
        "eligibility": {"root_rule": deep_rule},
    }
    with pytest.raises(CompilationError, match="Maximum rule depth exceeded"):
        EligibilityEngine.compile_scheme(scheme)


def test_custom_unsupported_rule_does_not_falsely_reject():
    scheme = {
        "scheme_identity": {"scheme_id": "CUSTOM-SCHEME", "name": "Custom"},
        "eligibility": {
            "root_rule": {
                "condition_id": "C-CUSTOM",
                "field": "registered_labour_days",
                "custom_field_name": "registered_labour_days",
                "operator": "GTE",
                "value": 100,
            }
        },
    }
    res = EligibilityEngine.evaluate_scheme(scheme, {"age": 40})
    # Should be MORE_INFORMATION_REQUIRED or UNKNOWN, NEVER NOT_ELIGIBLE
    assert res.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED


# ===========================================================================
# 9. Full Day 14 End-to-End Verified Scheme Test
# ===========================================================================

def test_end_to_end_verified_scheme_evaluation():
    """
    Simulates the verified Day 13 artifact:
    - Age >= 60
    - State = Rajasthan
    - (BPL = true OR family_income <= 200000)
    - Exclusion: receiving_pension_x = true
    """
    verified_scheme = {
        "schema_version": "1.0",
        "verifier_version": "1.0",
        "scheme_identity": {
            "scheme_id": "RJ-VERIFIED-001",
            "name": {"en": "Rajasthan Senior Citizen Pension Scheme", "hi": "राजस्थान वरिष्ठ नागरिक सम्मान पेंशन"},
        },
        "eligibility": {
            "root_rule": {
                "type": "AND",
                "children": [
                    {"condition_id": "COND-01", "field": "age", "operator": "GTE", "value": 60},
                    {"condition_id": "COND-02", "field": "state", "operator": "EQ", "value": "Rajasthan"},
                    {
                        "type": "OR",
                        "children": [
                            {"condition_id": "COND-03A", "field": "bpl_status", "operator": "EQ", "value": True},
                            {"condition_id": "COND-03B", "field": "family_income", "operator": "LTE", "value": 200000},
                        ],
                    },
                ],
            }
        },
        "exclusions": [
            {
                "exclusion_id": "EXCL-01",
                "field": "receiving_pension_x",
                "operator": "EQ",
                "value": True,
                "raw_text": "Applicant must not be in receipt of any other regular social security pension",
            }
        ],
    }

    # Citizen A: Age 64, Rajasthan, BPL true, receiving_pension_x false -> ELIGIBLE
    res_a = EligibilityEngine.evaluate_scheme(
        verified_scheme,
        {
            "age": 64,
            "state": "Rajasthan",
            "bpl_status": True,
            "receiving_pension_x": False,
        },
    )
    assert res_a.eligibility_status == EligibilityStatus.ELIGIBLE
    assert len(res_a.passed_conditions) >= 2
    assert res_a.missing_fields == []

    # Citizen B: Age 55 -> NOT_ELIGIBLE
    res_b = EligibilityEngine.evaluate_scheme(
        verified_scheme,
        {
            "age": 55,
            "state": "Rajasthan",
            "bpl_status": True,
            "receiving_pension_x": False,
        },
    )
    assert res_b.eligibility_status == EligibilityStatus.NOT_ELIGIBLE
    assert any(fc.field == "age" for fc in res_b.failed_conditions)

    # Citizen C: Age 64, Rajasthan, BPL false, income missing, pension_x false -> MORE_INFORMATION_REQUIRED
    res_c = EligibilityEngine.evaluate_scheme(
        verified_scheme,
        {
            "age": 64,
            "state": "Rajasthan",
            "bpl_status": False,
            "receiving_pension_x": False,
        },
    )
    assert res_c.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert len(res_c.missing_fields) == 1
    assert res_c.missing_fields[0].field == "family_income"

    # Citizen D: Age 64, Rajasthan, BPL true, pension_x status missing -> MORE_INFORMATION_REQUIRED (exclusion)
    res_d = EligibilityEngine.evaluate_scheme(
        verified_scheme,
        {
            "age": 64,
            "state": "Rajasthan",
            "bpl_status": True,
        },
    )
    assert res_d.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert len(res_d.missing_fields) == 1
    assert res_d.missing_fields[0].field == "receiving_pension_x"


# ===========================================================================
# 10. Specific Domain Rule Invariants
# ===========================================================================

def test_family_vs_personal_income_invariant():
    """Scheme requires family_income <= 200000. Citizen provides only annual personal income."""
    scheme = {
        "scheme_identity": {"scheme_id": "INC-SCHEME", "name": "Income Specific"},
        "eligibility": {
            "root_rule": {
                "condition_id": "C-INC",
                "field": "family_income",
                "operator": "LTE",
                "value": 200000,
            }
        },
    }
    # Citizen provides personal income = 100000
    res = EligibilityEngine.evaluate_scheme(scheme, {"annual_income": 100000})
    # Must NOT substitute personal income for family income -> MORE_INFORMATION_REQUIRED
    assert res.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert res.missing_fields[0].field == "family_income"


def test_domicile_vs_state_invariant():
    """Scheme requires domicile_status = Rajasthan. Citizen provides only state = Rajasthan."""
    scheme = {
        "scheme_identity": {"scheme_id": "DOM-SCHEME", "name": "Domicile Scheme"},
        "eligibility": {
            "root_rule": {
                "condition_id": "C-DOM",
                "field": "domicile_status",
                "operator": "EQ",
                "value": "Rajasthan",
            }
        },
    }
    res = EligibilityEngine.evaluate_scheme(scheme, {"state": "Rajasthan"})
    # Domicile is legally separate from current residence -> MORE_INFORMATION_REQUIRED
    assert res.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert res.missing_fields[0].field == "domicile_status"


def test_disability_conditions_invariant():
    """Scheme requires disability_status = true AND disability_percentage >= 40."""
    scheme = {
        "scheme_identity": {"scheme_id": "DIS-SCHEME", "name": "Divyangjan Assistance"},
        "eligibility": {
            "root_rule": {
                "type": "AND",
                "children": [
                    {"condition_id": "C-DIS-STAT", "field": "disability_status", "operator": "EQ", "value": True},
                    {"condition_id": "C-DIS-PCT", "field": "disability_percentage", "operator": "GTE", "value": 40},
                ],
            }
        },
    }

    # Partial: disability_status = True, percentage = None -> MORE_INFORMATION_REQUIRED
    res_partial = EligibilityEngine.evaluate_scheme(scheme, {"disability_status": True})
    assert res_partial.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED
    assert res_partial.missing_fields[0].field == "disability_percentage"

    # Fully met: disability_status = True, percentage = 50 -> ELIGIBLE
    res_full = EligibilityEngine.evaluate_scheme(scheme, {"disability_status": True, "disability_percentage": 50})
    assert res_full.eligibility_status == EligibilityStatus.ELIGIBLE

    # Ineligible: percentage = 30 -> NOT_ELIGIBLE
    res_inelig = EligibilityEngine.evaluate_scheme(scheme, {"disability_status": True, "disability_percentage": 30})
    assert res_inelig.eligibility_status == EligibilityStatus.NOT_ELIGIBLE


# ===========================================================================
# 11. API Endpoints & Privacy Invariants
# ===========================================================================

import json
from pathlib import Path
import uuid
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_api_validation_error_on_impossible_input():
    response = client.post(
        "/api/v1/eligibility/evaluate/TEST-ID",
        json={
            "profile": {"age": -10}
        },
    )
    assert response.status_code == 422
    assert "Invalid citizen profile data" in response.json()["detail"]


def test_api_scheme_not_found():
    response = client.post(
        f"/api/v1/eligibility/evaluate/{uuid.uuid4()}",
        json={
            "profile": {"age": 65, "state": "Rajasthan"}
        },
    )
    assert response.status_code == 404
    assert "Verified scheme not found" in response.json()["detail"]


def test_api_verified_scheme_evaluation(tmp_path):
    """Creates a temporary sealed verified scheme artifact and tests API 200 response."""
    settings = get_settings()
    draft_id = str(uuid.uuid4())
    verified_dir = settings.verified_dir / draft_id
    verified_dir.mkdir(parents=True, exist_ok=True)
    verified_file = verified_dir / "verified_scheme.json"

    payload = {
        "schema_version": "1.0",
        "verifier_version": "1.0",
        "scheme_draft_id": draft_id,
        "review": {
            "status": "HUMAN_VERIFIED",
            "reviewer_id": "REV-TEST",
        },
        "canonical_scheme": {
            "schema_version": "1.0",
            "scheme_identity": {
                "scheme_id": draft_id,
                "name": {"en": "API Verified Test Scheme"},
            },
            "eligibility": {
                "root_rule": {
                    "condition_id": "C-API-AGE",
                    "field": "age",
                    "operator": "GTE",
                    "value": 60,
                }
            },
            "exclusions": [],
        },
    }

    with open(verified_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    try:
        # 1. Citizen aged 65 -> ELIGIBLE
        resp = client.post(
            f"/api/v1/eligibility/evaluate/{draft_id}",
            json={"profile": {"age": 65}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility_status"] == "ELIGIBLE"
        assert data["scheme_id"] == draft_id
        assert len(data["passed_conditions"]) == 1

        # 2. Citizen aged 45 -> NOT_ELIGIBLE
        resp2 = client.post(
            f"/api/v1/eligibility/evaluate/{draft_id}",
            json={"profile": {"age": 45}},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["eligibility_status"] == "NOT_ELIGIBLE"

        # 3. Citizen with missing age -> MORE_INFORMATION_REQUIRED
        resp3 = client.post(
            f"/api/v1/eligibility/evaluate/{draft_id}",
            json={"profile": {}},
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["eligibility_status"] == "MORE_INFORMATION_REQUIRED"
        assert len(data3["missing_fields"]) == 1

        # 4. Multi-scheme evaluate endpoint
        multi_resp = client.post(
            "/api/v1/eligibility/evaluate",
            json={
                "scheme_ids": [draft_id],
                "profile": {"age": 65},
            },
        )
        assert multi_resp.status_code == 200
        multi_data = multi_resp.json()
        assert len(multi_data) == 1
        assert multi_data[0]["eligibility_status"] == "ELIGIBLE"

    finally:
        # Cleanup test artifact
        if verified_file.exists():
            verified_file.unlink()
        if verified_dir.exists():
            verified_dir.rmdir()
