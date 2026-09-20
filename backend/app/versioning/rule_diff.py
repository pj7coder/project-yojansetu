import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from app.versioning.schemas import ChangeItemSchema, ChangeRiskLevel, ChangeType

logger = logging.getLogger("yojansetu.versioning.rule_diff")


class RuleDiffService:
    """
    Deterministic rule-tree diffing engine.
    Compares eligibility rule trees, detects threshold modifications, added conditions,
    and logical connector changes, while strictly preventing accidental omission-based removals.
    """

    CRITICAL_FIELDS = {
        "age",
        "min_age",
        "max_age",
        "family_income",
        "annual_income",
        "income",
        "caste",
        "category",
        "gender",
        "domicile",
        "residency",
        "disability_percentage",
        "land_holding_acres",
    }

    def diff_rule_trees(
        self,
        base_eligibility: Dict[str, Any],
        candidate_eligibility: Dict[str, Any],
        is_partial_amendment: bool = True,
        evidence_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ChangeItemSchema]:
        """
        Compare base and candidate canonical eligibility models.
        """
        changes: List[ChangeItemSchema] = []
        ev_refs = evidence_refs or []

        # 1. Compare root rule logical connector (AND vs OR)
        base_root = base_eligibility.get("root_rule") or {}
        cand_root = candidate_eligibility.get("root_rule") or {}

        base_type = base_root.get("type")
        cand_type = cand_root.get("type")

        if base_type and cand_type and base_type != cand_type:
            changes.append(
                ChangeItemSchema(
                    field_path="eligibility.root_rule.type",
                    change_type=ChangeType.MODIFY,
                    old_value=base_type,
                    new_value=cand_type,
                    risk_level=ChangeRiskLevel.CRITICAL,
                    evidence_refs=ev_refs,
                    reason="LOGICAL_CONNECTOR_CHANGED",
                )
            )

        # 2. Extract atomic conditions
        base_conditions = self._extract_conditions(base_root)
        cand_conditions = self._extract_conditions(cand_root)

        # Also inspect simple_fields if available
        base_simple = base_eligibility.get("simple_fields") or {}
        cand_simple = candidate_eligibility.get("simple_fields") or {}

        # Merge simple fields into conditions map if missing
        for k, v in cand_simple.items():
            if k not in cand_conditions and v is not None:
                cand_conditions[k] = {"field": k, "operator": "EQ", "value": v, "raw_text": str(v)}
        for k, v in base_simple.items():
            if k not in base_conditions and v is not None:
                base_conditions[k] = {"field": k, "operator": "EQ", "value": v, "raw_text": str(v)}

        # 3. Compare matched conditions
        all_fields = set(base_conditions.keys()).union(set(cand_conditions.keys()))

        for field in sorted(all_fields):
            base_cond = base_conditions.get(field)
            cand_cond = cand_conditions.get(field)

            # Case A: Field present in both -> check for modification
            if base_cond and cand_cond:
                b_val = base_cond.get("value")
                c_val = cand_cond.get("value")
                b_op = str(base_cond.get("operator", "")).upper()
                c_op = str(cand_cond.get("operator", "")).upper()

                if b_val != c_val or b_op != c_op:
                    risk = ChangeRiskLevel.CRITICAL if field in self.CRITICAL_FIELDS else ChangeRiskLevel.NORMAL
                    changes.append(
                        ChangeItemSchema(
                            field_path=f"eligibility.rules.{field}",
                            change_type=ChangeType.REPLACE,
                            old_value={"operator": b_op, "value": b_val},
                            new_value={"operator": c_op, "value": c_val},
                            risk_level=risk,
                            evidence_refs=ev_refs,
                            reason=f"Modified condition for '{field}'",
                        )
                    )

            # Case B: Field present in candidate only -> condition added
            elif not base_cond and cand_cond:
                risk = ChangeRiskLevel.CRITICAL if field in self.CRITICAL_FIELDS else ChangeRiskLevel.NORMAL
                c_val = cand_cond.get("value")
                c_op = str(cand_cond.get("operator", "EQ")).upper()
                changes.append(
                    ChangeItemSchema(
                        field_path=f"eligibility.rules.{field}",
                        change_type=ChangeType.ADD,
                        old_value=None,
                        new_value={"operator": c_op, "value": c_val},
                        risk_level=risk,
                        evidence_refs=ev_refs,
                        reason=f"New eligibility condition added for '{field}'",
                    )
                )

            # Case C: Field present in base only
            elif base_cond and not cand_cond:
                # Critical guard: in partial amendments, omissions are NEVER automatic removals!
                if not is_partial_amendment:
                    changes.append(
                        ChangeItemSchema(
                            field_path=f"eligibility.rules.{field}",
                            change_type=ChangeType.REMOVE,
                            old_value={"operator": base_cond.get("operator"), "value": base_cond.get("value")},
                            new_value=None,
                            risk_level=ChangeRiskLevel.CRITICAL,
                            evidence_refs=ev_refs,
                            reason=f"Condition '{field}' omitted in full superseding document",
                        )
                    )
                else:
                    logger.info(
                        f"Preserving base condition '{field}' because document is partial amendment (omission != removal)"
                    )

        return changes

    def _extract_conditions(self, node: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Recursively extract atomic conditions from a RuleGroup dictionary,
        mapping field_name -> condition_dict.
        """
        result: Dict[str, Dict[str, Any]] = {}
        if not isinstance(node, dict):
            return result

        # Check if node is itself a condition
        if "field" in node:
            field = str(node.get("field")).lower().strip()
            if field:
                result[field] = node
                return result

        # If it has children, recurse
        children = node.get("children") or []
        for child in children:
            if isinstance(child, dict):
                child_conds = self._extract_conditions(child)
                result.update(child_conds)

        return result
