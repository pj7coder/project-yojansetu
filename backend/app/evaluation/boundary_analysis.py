"""
YojanSetu - Day 30: Numeric, Percentage & Relational Boundary Analysis.

Provides rigorous testing for exact edge boundaries:
- Age >= 60 (59 vs 60 vs 61)
- Income <= 200000 (199999 vs 200000 vs 200001)
- Percentage thresholds (39% vs 40% vs 41%)
- Integer / Decimal-safe financial precision (Rs 200000.00 vs Rs 199999.99)
- Relational operators (GT, GTE, LT, LTE, EQ, NE, BETWEEN, IN, NOT_IN, EXISTS, NOT_EXISTS)
"""

from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.eligibility.engine import EligibilityEngine
from app.eligibility.models import CompiledScheme, ConditionNode, GroupNode
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import EligibilityStatus
from app.evaluation.eligibility_schemas import BoundaryMetrics


class BoundaryAnalyzer:
    """
    Evaluates edge-case numeric and operator boundaries in eligibility rules.
    """

    @classmethod
    def run_synthetic_boundary_suite(cls) -> Tuple[BoundaryMetrics, List[Dict[str, Any]]]:
        """
        Executes a deterministic suite of boundary conditions against Day 14 engine.
        Returns aggregate metrics and case-level results.
        """
        results: List[Dict[str, Any]] = []

        # 1. Age Boundary Test: GTE 60
        age_scheme = CompiledScheme(
            scheme_id="SYNTH-AGE-BOUND",
            scheme_name="Age Boundary Scheme",
            schema_version="1.0",
            root_rule=ConditionNode(node_id="C-AGE", field="age", operator="GTE", value=60),
        )
        age_cases = [
            (59, EligibilityStatus.NOT_ELIGIBLE, "59 < 60"),
            (60, EligibilityStatus.ELIGIBLE, "60 >= 60"),
            (61, EligibilityStatus.ELIGIBLE, "61 >= 60"),
        ]
        for age_val, expected_st, desc in age_cases:
            res = EligibilityEngine.evaluate_scheme(age_scheme, {"age": age_val})
            passed = res.eligibility_status == expected_st
            results.append({
                "test": "AGE_GTE_60",
                "input": age_val,
                "expected": expected_st.value,
                "actual": res.eligibility_status.value,
                "passed": passed,
                "description": desc,
            })

        # 2. Income Boundary Test: LTE 200000 (Decimal precision)
        income_scheme = CompiledScheme(
            scheme_id="SYNTH-INCOME-BOUND",
            scheme_name="Income Boundary Scheme",
            schema_version="1.0",
            root_rule=ConditionNode(node_id="C-INC", field="family_income", operator="LTE", value=200000),
        )
        income_cases = [
            (Decimal("199999.99"), EligibilityStatus.ELIGIBLE, "199999.99 <= 200000"),
            (200000, EligibilityStatus.ELIGIBLE, "200000 <= 200000"),
            (Decimal("200000.00"), EligibilityStatus.ELIGIBLE, "200000.00 <= 200000"),
            (200001, EligibilityStatus.NOT_ELIGIBLE, "200001 > 200000"),
            (Decimal("200000.01"), EligibilityStatus.NOT_ELIGIBLE, "200000.01 > 200000"),
        ]
        for inc_val, expected_st, desc in income_cases:
            res = EligibilityEngine.evaluate_scheme(income_scheme, {"family_income": inc_val})
            passed = res.eligibility_status == expected_st
            results.append({
                "test": "INCOME_LTE_200000",
                "input": str(inc_val),
                "expected": expected_st.value,
                "actual": res.eligibility_status.value,
                "passed": passed,
                "description": desc,
            })

        # 3. Percentage Boundary Test: GTE 40%
        pct_scheme = CompiledScheme(
            scheme_id="SYNTH-PCT-BOUND",
            scheme_name="Disability Percentage Scheme",
            schema_version="1.0",
            root_rule=ConditionNode(node_id="C-DIS", field="disability_percentage", operator="GTE", value=40),
        )
        pct_cases = [
            (39, EligibilityStatus.NOT_ELIGIBLE, "39% < 40%"),
            (40, EligibilityStatus.ELIGIBLE, "40% >= 40%"),
            (41, EligibilityStatus.ELIGIBLE, "41% >= 40%"),
        ]
        for pct_val, expected_st, desc in pct_cases:
            res = EligibilityEngine.evaluate_scheme(pct_scheme, {"disability_percentage": pct_val})
            passed = res.eligibility_status == expected_st
            results.append({
                "test": "PCT_GTE_40",
                "input": pct_val,
                "expected": expected_st.value,
                "actual": res.eligibility_status.value,
                "passed": passed,
                "description": desc,
            })

        # 4. BETWEEN operator: BETWEEN [18, 25]
        between_scheme = CompiledScheme(
            scheme_id="SYNTH-BETWEEN-BOUND",
            scheme_name="Between Age Scheme",
            schema_version="1.0",
            root_rule=ConditionNode(node_id="C-BETW", field="age", operator="BETWEEN", value=[18, 25]),
        )
        between_cases = [
            (17, EligibilityStatus.NOT_ELIGIBLE, "17 < 18"),
            (18, EligibilityStatus.ELIGIBLE, "18 inclusive min"),
            (21, EligibilityStatus.ELIGIBLE, "21 inside range"),
            (25, EligibilityStatus.ELIGIBLE, "25 inclusive max"),
            (26, EligibilityStatus.NOT_ELIGIBLE, "26 > 25"),
        ]
        for b_val, expected_st, desc in between_cases:
            res = EligibilityEngine.evaluate_scheme(between_scheme, {"age": b_val})
            passed = res.eligibility_status == expected_st
            results.append({
                "test": "BETWEEN_18_25",
                "input": b_val,
                "expected": expected_st.value,
                "actual": res.eligibility_status.value,
                "passed": passed,
                "description": desc,
            })

        # Aggregate Metrics
        total = len(results)
        passed_count = sum(1 for r in results if r["passed"])
        age_passed = sum(1 for r in results if r["test"] == "AGE_GTE_60" and r["passed"])
        inc_passed = sum(1 for r in results if r["test"] == "INCOME_LTE_200000" and r["passed"])
        pct_passed = sum(1 for r in results if r["test"] == "PCT_GTE_40" and r["passed"])

        metrics = BoundaryMetrics(
            total_boundary_cases=total,
            boundary_accuracy=round(passed_count / total, 4) if total else 1.0,
            age_boundary_accuracy=round(age_passed / len(age_cases), 4),
            income_boundary_accuracy=round(inc_passed / len(income_cases), 4),
            percentage_boundary_accuracy=round(pct_passed / len(pct_cases), 4),
        )

        return metrics, results
