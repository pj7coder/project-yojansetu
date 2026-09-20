"""
YojanSetu - Day 30: Trace Comparator & Decisive Condition Verification.

Validates that:
1. Final eligibility status strictly agrees with the reasoning trace.
2. Decisive conditions match gold expectations (order-independent across commutative branches).
3. Evidence references from verified scheme rules are preserved in trace.
4. Short-circuited / skipped branches do not falsely claim to have decided the outcome.
"""

import re
from typing import Any, Dict, List, Optional, Set
from app.eligibility.result import EligibilityResult, EligibilityStatus
from app.evaluation.eligibility_schemas import TraceEvaluation


class TraceComparator:
    """
    Compares the engine's structured audit trace against gold decisive rules.
    """

    @classmethod
    def compare_trace(
        cls,
        result: EligibilityResult,
        gold_decisive_rules: List[str],
        gold_status: EligibilityStatus,
    ) -> TraceEvaluation:
        """
        Performs comprehensive trace validation.
        """
        trace = result.evaluation_trace or {}
        pos_state = trace.get("positive_state")
        excl_state = trace.get("exclusion_state")

        # 1. Status vs Trace Consistency
        status_trace_consistent = True
        explanation_parts: List[str] = []

        if result.eligibility_status == EligibilityStatus.ELIGIBLE:
            if pos_state != "TRUE" or excl_state not in ("FALSE", None):
                status_trace_consistent = False
                explanation_parts.append(
                    f"ELIGIBLE status inconsistent with trace: positive={pos_state}, exclusion={excl_state}"
                )
        elif result.eligibility_status == EligibilityStatus.NOT_ELIGIBLE:
            if pos_state != "FALSE" and excl_state != "TRUE":
                # Must have either failed positive conditions, or triggered an exclusion, or been inactive
                if trace.get("availability") not in ("EXPIRED", "NOT_YET_ACTIVE"):
                    status_trace_consistent = False
                    explanation_parts.append(
                        f"NOT_ELIGIBLE status inconsistent with trace: positive={pos_state}, exclusion={excl_state}"
                    )
        elif result.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
            if pos_state not in ("UNKNOWN",) and excl_state not in ("UNKNOWN",):
                status_trace_consistent = False
                explanation_parts.append(
                    f"MORE_INFORMATION_REQUIRED status inconsistent with trace: positive={pos_state}, exclusion={excl_state}"
                )

        # 2. Extract actual decisive conditions from passed/failed/exclusion results
        actual_decisive_summaries: List[str] = []

        # If eligible, all passed conditions contributed
        if result.eligibility_status == EligibilityStatus.ELIGIBLE:
            for cond in result.passed_conditions:
                op_symbol = cls._operator_to_symbol(cond.operator)
                actual_decisive_summaries.append(f"{cond.field} {op_symbol} {cond.required_value}")

        # If not eligible due to failed condition
        elif result.eligibility_status == EligibilityStatus.NOT_ELIGIBLE:
            for cond in result.failed_conditions:
                inverted_op = cls._invert_operator_to_symbol(cond.operator)
                actual_decisive_summaries.append(f"{cond.field} {inverted_op} {cond.required_value}")
            for cond in result.exclusions_triggered:
                actual_decisive_summaries.append(f"{cond.field} == True")

        # If more information required, include passed conditions and missing fields
        elif result.eligibility_status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
            for cond in result.passed_conditions:
                op_symbol = cls._operator_to_symbol(cond.operator)
                actual_decisive_summaries.append(f"{cond.field} {op_symbol} {cond.required_value}")
            for m in result.missing_fields:
                actual_decisive_summaries.append(f"{m.field} is missing")

        # 3. Decisive Rule Match Accuracy (Order-independent and fuzzy semantic matching)
        matched_decisive_count = 0
        gold_normalized = [cls._normalize_rule_str(r) for r in gold_decisive_rules if r]
        actual_normalized = [cls._normalize_rule_str(r) for r in actual_decisive_summaries if r]

        if not gold_normalized:
            decisive_rule_accuracy = 1.0
        else:
            for g_norm in gold_normalized:
                if any(cls._rules_semantically_match(g_norm, a_norm) for a_norm in actual_normalized):
                    matched_decisive_count += 1
            decisive_rule_accuracy = round(matched_decisive_count / len(gold_normalized), 4)

        # 4. Check evidence references
        evidence_valid = True
        for cond in result.passed_conditions + result.failed_conditions + result.exclusions_triggered:
            # Evidence refs should be a list and not None
            if cond.evidence_refs is None:
                evidence_valid = False

        # 5. Check short-circuit cleanliness: skipped nodes shouldn't be in passed/failed conditions
        short_circuit_clean = True
        failed_fields = {c.field for c in result.failed_conditions}
        passed_fields = {c.field for c in result.passed_conditions}
        # If a field was skipped via short-circuit in trace, it should not appear in passed or failed
        for skipped_node in cls._collect_skipped_nodes(trace.get("root_rule", {})):
            node_field = skipped_node.get("field")
            if node_field and (node_field in failed_fields or node_field in passed_fields):
                short_circuit_clean = False
                explanation_parts.append(f"Skipped field '{node_field}' incorrectly recorded in evaluated conditions")

        return TraceEvaluation(
            status_trace_consistent=status_trace_consistent,
            expected_decisive_rules=gold_decisive_rules,
            actual_decisive_rules=actual_decisive_summaries,
            decisive_rule_accuracy=decisive_rule_accuracy,
            evidence_references_valid=evidence_valid,
            short_circuit_clean=short_circuit_clean,
            reasoning_explanation="; ".join(explanation_parts) if explanation_parts else None,
        )

    @classmethod
    def _operator_to_symbol(cls, op: str) -> str:
        mapping = {
            "GTE": ">=",
            "GT": ">",
            "LTE": "<=",
            "LT": "<",
            "EQ": "==",
            "NE": "!=",
            "IN": "IN",
            "NOT_IN": "NOT IN",
        }
        return mapping.get(str(op).upper(), str(op))

    @classmethod
    def _invert_operator_to_symbol(cls, op: str) -> str:
        mapping = {
            "GTE": "<",
            "GT": "<=",
            "LTE": ">",
            "LT": ">=",
            "EQ": "!=",
            "NE": "==",
        }
        return mapping.get(str(op).upper(), "!=")

    @classmethod
    def _normalize_rule_str(cls, rule: str) -> str:
        s = rule.lower().strip()
        s = re.sub(r"\s+", " ", s)
        s = s.replace("==", "=").replace("===", "=")
        return s

    @classmethod
    def _rules_semantically_match(cls, gold: str, actual: str) -> bool:
        if gold == actual:
            return True
        # Check field name and boundary tokens
        g_tokens = set(gold.replace(">", " > ").replace("<", " < ").replace("=", " = ").split())
        a_tokens = set(actual.replace(">", " > ").replace("<", " < ").replace("=", " = ").split())
        # Check if primary field is shared
        common = g_tokens.intersection(a_tokens)
        if any(f in common for f in ("age", "income", "family_income", "domicile", "district", "bpl_status")):
            # If both have same comparison operator or boundary
            if any(op in common for op in (">", "<", ">=", "<=", "=")):
                return True
        return False

    @classmethod
    def _collect_skipped_nodes(cls, root_trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        skipped = []
        if root_trace.get("result") == "SKIPPED_SHORT_CIRCUIT":
            skipped.append(root_trace)
        for child in root_trace.get("children", []):
            skipped.extend(cls._collect_skipped_nodes(child))
        return skipped
