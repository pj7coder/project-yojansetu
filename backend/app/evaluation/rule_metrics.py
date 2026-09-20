"""
YojanSetu - Day 29: Logical Rule Tree Canonicalization & Operator Evaluation.

Implements:
- Canonical AST rule comparison for eligibility logic
- Commutative canonicalization for AND / OR clause groupings (A AND B == B AND A)
- Order-sensitive preservation for NOT and hierarchical sub-clauses
- Operator accuracy and logical connector accuracy tracking
- Exclusion separation from eligibility criteria
"""

from dataclasses import dataclass, field as dc_field
import json
from typing import Any, Dict, List, Optional, Tuple, Union

from app.evaluation.matching import FactMatcher
from app.normalization.schemas import LogicalGroupType, OperatorEnum, RuleGroup


@dataclass
class RuleNode:
    """Canonical representation of an eligibility rule AST node."""
    node_type: str  # "CONDITION", "AND", "OR", "NOT"
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[Any] = None
    children: List["RuleNode"] = dc_field(default_factory=list)

    def signature(self) -> str:
        """Deterministic serialization signature used for commutative child sorting."""
        if self.node_type == "CONDITION":
            norm_val = FactMatcher.normalize_value(self.value)
            can_op = FactMatcher.canonicalize_operator(self.operator) or "EQ"
            can_field = FactMatcher.canonicalize_field_name(self.field or "")
            return f"COND:{can_field}:{can_op}:{str(norm_val)}"
        elif self.node_type in ("AND", "OR"):
            sorted_child_sigs = sorted(c.signature() for c in self.children)
            return f"{self.node_type}:[" + ",".join(sorted_child_sigs) + "]"
        elif self.node_type == "NOT":
            child_sig = self.children[0].signature() if self.children else "EMPTY"
            return f"NOT:[{child_sig}]"
        return "UNKNOWN"

    def canonicalize(self) -> "RuleNode":
        """
        Recursively sorts children of commutative operators (AND, OR).
        Preserves non-commutative order (NOT and strict sequential clauses).
        """
        can_children = [c.canonicalize() for c in self.children]
        if self.node_type in ("AND", "OR"):
            # Commutative: sort children by canonical signature
            can_children.sort(key=lambda x: x.signature())
        return RuleNode(
            node_type=self.node_type,
            field=self.field,
            operator=FactMatcher.canonicalize_operator(self.operator),
            value=FactMatcher.normalize_value(self.value),
            children=can_children,
        )


class CanonicalRuleComparator:
    """
    Compares two rule trees for exact semantic equivalence under commutative boolean logic.
    """

    @classmethod
    def are_rule_trees_equivalent(cls, tree_a: RuleNode, tree_b: RuleNode) -> bool:
        """Compare two rule trees modulo commutative child ordering."""
        can_a = tree_a.canonicalize()
        can_b = tree_b.canonicalize()
        return can_a.signature() == can_b.signature()

    @classmethod
    def build_tree_from_conditions(
        cls,
        conditions: List[Dict[str, Any]],
        default_connector: str = "AND",
    ) -> RuleNode:
        """
        Construct a RuleNode tree from an enumerated list of extracted conditions.
        Handles intra-condition logical_connector annotations.
        """
        if not conditions:
            return RuleNode(node_type="AND", children=[])

        if len(conditions) == 1:
            c = conditions[0]
            return RuleNode(
                node_type="CONDITION",
                field=c.get("field"),
                operator=c.get("operator"),
                value=c.get("value"),
            )

        # Check if connectors are mixed
        connectors = set()
        child_nodes = []
        for c in conditions:
            child_nodes.append(
                RuleNode(
                    node_type="CONDITION",
                    field=c.get("field"),
                    operator=c.get("operator"),
                    value=c.get("value"),
                )
            )
            conn = c.get("logical_connector")
            if conn:
                connectors.add(conn.strip().upper())

        group_type = "OR" if "OR" in connectors and "AND" not in connectors else default_connector.upper()
        return RuleNode(node_type=group_type, children=child_nodes)

    @classmethod
    def evaluate_logical_connectors(
        cls,
        gold_connectors: List[str],
        pred_connectors: List[str],
    ) -> Tuple[float, bool]:
        """
        Calculates connector accuracy and detects critical AND <-> OR swaps.
        Returns (connector_accuracy, has_critical_connector_error).
        """
        if not gold_connectors and not pred_connectors:
            return 1.0, False
        if not gold_connectors or not pred_connectors:
            return 0.0, True

        matches = 0
        total = max(len(gold_connectors), len(pred_connectors))
        has_critical = False

        for g, p in zip(gold_connectors, pred_connectors):
            g_c = (g or "AND").strip().upper()
            p_c = (p or "AND").strip().upper()
            if g_c == p_c:
                matches += 1
            else:
                if (g_c == "AND" and p_c == "OR") or (g_c == "OR" and p_c == "AND"):
                    has_critical = True

        acc = matches / total if total > 0 else 1.0
        return acc, has_critical


def evaluate_exclusions_independently(
    gold_exclusions: List[Dict[str, Any]],
    predicted_exclusions: List[Dict[str, Any]],
    predicted_eligibility: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates exclusions separately from eligibility rules (Phase 9).
    Verifies:
    1. Exclusion detection recall and value accuracy.
    2. Zero exclusion leakage into eligibility requirements.
    """
    tp = 0
    fn = 0
    fp = len(predicted_exclusions)
    leakage_into_eligibility = 0

    matched_pred_indices = set()

    for g_ex in gold_exclusions:
        g_field = g_ex.get("field", "")
        g_val = g_ex.get("value")
        found = False

        for idx, p_ex in enumerate(predicted_exclusions):
            if idx in matched_pred_indices:
                continue
            p_field = p_ex.get("field", "")
            p_val = p_ex.get("value")

            if FactMatcher.are_fields_matching(g_field, p_field):
                if FactMatcher.are_values_semantically_equivalent(g_val, p_val):
                    tp += 1
                    fp -= 1
                    matched_pred_indices.add(idx)
                    found = True
                    break

        if not found:
            fn += 1

    # Check if any gold exclusion was mistakenly extracted as an eligibility requirement
    for g_ex in gold_exclusions:
        g_sub = g_ex.get("field", "").split(".")[-1].lower()
        for p_el in predicted_eligibility:
            p_sub = p_el.get("field", "").split(".")[-1].lower()
            if g_sub and g_sub == p_sub:
                leakage_into_eligibility += 1
                break

    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "exclusion_tp": tp,
        "exclusion_fp": fp,
        "exclusion_fn": fn,
        "exclusion_recall": recall,
        "exclusion_precision": precision,
        "exclusion_f1": f1,
        "leakage_into_eligibility": leakage_into_eligibility,
        "is_safe": leakage_into_eligibility == 0,
    }
