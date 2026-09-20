from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.config import settings
from app.normalization.schemas import (
    EligibilityCondition,
    LogicalGroupType,
    OperatorEnum,
    RuleGroup,
)
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext

# Categorical fields that cannot use numeric boundary operators (GT, GTE, LT, LTE, BETWEEN)
CATEGORICAL_FIELDS = {
    "gender",
    "social_category",
    "caste",
    "residency",
    "residency_type",
    "marital_status",
    "religion",
    "occupation",
    "employment_status",
    "state",
    "district",
}

BOOLEAN_FIELDS = {
    "is_student",
    "is_bpl",
    "bpl_status",
    "disability_status",
    "is_employed",
    "is_widow",
    "is_orphan",
}


class EligibilityValidator(BaseValidator):
    """
    Validates eligibility rule tree structure, operator-field compatibility,
    missing values, BETWEEN boundaries, AND/OR/NOT structure, depth limits,
    numeric contradictions within AND groups, and eligibility vs exclusion conflicts.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft or not context.draft.eligibility:
            return

        draft = context.draft
        max_depth = settings.max_rule_depth
        inclusion_conditions: List[EligibilityCondition] = []

        def check_condition(cond: EligibilityCondition, path: str) -> None:
            context.increment_rules_checked(1)
            field_name = cond.field.lower().strip()
            op = cond.operator

            # 1. Custom / Unsupported condition detection
            if field_name == "custom" or cond.custom_field_name:
                context.add_issue(
                    rule_code="CUSTOM_FIELD_REQUIRED",
                    message=f"Custom eligibility condition '{cond.custom_field_name or cond.raw_text}' requires citizen input.",
                    field_path=f"{path}.custom_field_name",
                    actual_value=cond.custom_field_name or cond.raw_text,
                    evidence_refs=cond.evidence_refs,
                    severity=ValidationSeverity.INFO,
                )
                context.add_issue(
                    rule_code="UNSUPPORTED_FOR_AUTOMATIC_ELIGIBILITY",
                    message=f"Condition '{cond.custom_field_name or cond.raw_text}' cannot be evaluated automatically without human review.",
                    field_path=f"{path}.field",
                    actual_value=cond.field,
                    evidence_refs=cond.evidence_refs,
                    severity=ValidationSeverity.WARNING,
                )

            # 2. Missing rule value check
            if op not in (OperatorEnum.EXISTS, OperatorEnum.NOT_EXISTS):
                if cond.value is None:
                    context.add_issue(
                        rule_code="RULE_VALUE_MISSING",
                        message=f"Operator '{op}' on field '{cond.field}' requires an explicit value, but value is null.",
                        field_path=f"{path}.value",
                        actual_value=None,
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )

            # 3. Operator compatibility
            if field_name in CATEGORICAL_FIELDS:
                if op in (OperatorEnum.GT, OperatorEnum.GTE, OperatorEnum.LT, OperatorEnum.LTE, OperatorEnum.BETWEEN):
                    context.add_issue(
                        rule_code="OPERATOR_INCOMPATIBLE",
                        message=f"Categorical field '{cond.field}' cannot use numeric operator '{op}'.",
                        field_path=f"{path}.operator",
                        actual_value=op,
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )
            elif field_name in BOOLEAN_FIELDS:
                if op not in (OperatorEnum.EQ, OperatorEnum.NE, OperatorEnum.EXISTS, OperatorEnum.NOT_EXISTS):
                    context.add_issue(
                        rule_code="OPERATOR_INCOMPATIBLE",
                        message=f"Boolean field '{cond.field}' cannot use operator '{op}'.",
                        field_path=f"{path}.operator",
                        actual_value=op,
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )

            # 4. BETWEEN operator check
            if op == OperatorEnum.BETWEEN:
                if not isinstance(cond.value, (list, tuple)) or len(cond.value) != 2:
                    context.add_issue(
                        rule_code="RULE_OPERATOR_INVALID",
                        message=f"BETWEEN operator requires exactly two boundary values [lower, upper], got {cond.value}.",
                        field_path=f"{path}.value",
                        actual_value=cond.value,
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )
                else:
                    v1, v2 = cond.value[0], cond.value[1]
                    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                        if v1 > v2:
                            context.add_issue(
                                rule_code="RULE_OPERATOR_INVALID",
                                message=f"BETWEEN lower bound ({v1}) cannot be greater than upper bound ({v2}).",
                                field_path=f"{path}.value",
                                actual_value=cond.value,
                                evidence_refs=cond.evidence_refs,
                                severity=ValidationSeverity.ERROR,
                            )

            # 5. IN / NOT_IN operator check
            if op in (OperatorEnum.IN, OperatorEnum.NOT_IN):
                if not isinstance(cond.value, (list, tuple, set)) or len(cond.value) == 0:
                    context.add_issue(
                        rule_code="RULE_VALUE_EMPTY",
                        message=f"Operator '{op}' requires a non-empty collection of values.",
                        field_path=f"{path}.value",
                        actual_value=cond.value,
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )

            inclusion_conditions.append(cond)

        def check_and_group_contradictions(conditions: List[EligibilityCondition], group_path: str) -> None:
            """Detect mutually exclusive numeric intervals in the same AND node."""
            # Group conditions by field
            field_conds: Dict[str, List[EligibilityCondition]] = {}
            for c in conditions:
                field_conds.setdefault(c.field.lower().strip(), []).append(c)

            for field, cond_list in field_conds.items():
                if len(cond_list) < 2:
                    continue

                min_val = float("-inf")
                max_val = float("inf")
                min_inclusive = True
                max_inclusive = True

                for c in cond_list:
                    op = c.operator
                    val = c.value

                    if isinstance(val, (int, float)):
                        if op == OperatorEnum.GT:
                            if val >= min_val:
                                min_val = val
                                min_inclusive = False
                        elif op == OperatorEnum.GTE:
                            if val > min_val or (val == min_val and not min_inclusive):
                                min_val = val
                                min_inclusive = True
                        elif op == OperatorEnum.LT:
                            if val <= max_val:
                                max_val = val
                                max_inclusive = False
                        elif op == OperatorEnum.LTE:
                            if val < max_val or (val == max_val and not max_inclusive):
                                max_val = val
                                max_inclusive = True

                # Check if interval is empty: e.g. min_val > max_val or (min_val == max_val and (!min_inclusive or !max_inclusive))
                is_contradiction = False
                if min_val > max_val:
                    is_contradiction = True
                elif min_val == max_val and (not min_inclusive or not max_inclusive):
                    is_contradiction = True

                if is_contradiction:
                    refs = [r for c in cond_list for r in c.evidence_refs]
                    context.add_issue(
                        rule_code="CONTRADICTORY_RULES",
                        message=f"Contradictory conditions detected for field '{field}' in same AND branch: min ({min_val}) exceeds max ({max_val}).",
                        field_path=group_path,
                        actual_value=[f"{c.operator} {c.value}" for c in cond_list],
                        evidence_refs=refs,
                        severity=ValidationSeverity.ERROR,
                    )

        def walk_tree(node: RuleGroup, path: str, current_depth: int) -> None:
            context.increment_rules_checked(1)

            # Depth limit check
            if current_depth > max_depth:
                context.add_issue(
                    rule_code="RULE_DEPTH_EXCEEDED",
                    message=f"Rule tree nesting depth ({current_depth}) exceeds maximum allowable depth ({max_depth}).",
                    field_path=path,
                    actual_value=current_depth,
                    severity=ValidationSeverity.BLOCKER,
                )
                return

            # Group structure checks
            if node.type in (LogicalGroupType.AND, LogicalGroupType.OR):
                if not node.children:
                    context.add_issue(
                        rule_code="RULE_GROUP_EMPTY",
                        message=f"{node.type} logical group has no child conditions or groups.",
                        field_path=path,
                        severity=ValidationSeverity.ERROR,
                    )

            elif node.type == LogicalGroupType.NOT:
                if len(node.children) != 1:
                    context.add_issue(
                        rule_code="RULE_NOT_INVALID",
                        message=f"NOT logical group must have exactly 1 child, got {len(node.children)}.",
                        field_path=path,
                        actual_value=len(node.children),
                        severity=ValidationSeverity.ERROR,
                    )
                else:
                    child = node.children[0]
                    # Double negation check
                    if isinstance(child, RuleGroup) and child.type == LogicalGroupType.NOT:
                        context.add_issue(
                            rule_code="DOUBLE_NEGATION_SUSPICIOUS",
                            message="Double negation NOT(NOT(...)) detected in rule group.",
                            field_path=path,
                            severity=ValidationSeverity.WARNING,
                        )

            # If this is an AND group, check for internal numeric contradictions
            if node.type == LogicalGroupType.AND:
                direct_conditions = [c for c in node.children if isinstance(c, EligibilityCondition)]
                if len(direct_conditions) >= 2:
                    check_and_group_contradictions(direct_conditions, path)

            # Recurse children
            for idx, child in enumerate(node.children):
                child_path = f"{path}.children[{idx}]"
                if isinstance(child, RuleGroup):
                    walk_tree(child, child_path, current_depth + 1)
                elif isinstance(child, EligibilityCondition):
                    check_condition(child, child_path)

        # Walk the root rule
        if draft.eligibility.root_rule:
            walk_tree(draft.eligibility.root_rule, "eligibility.root_rule", 1)

        # Cross-check exclusions vs inclusions
        for idx, excl in enumerate(draft.exclusions):
            context.increment_rules_checked(1)
            if excl.field and excl.value is not None:
                excl_field = excl.field.lower().strip()
                for inc in inclusion_conditions:
                    inc_field = inc.field.lower().strip()
                    if inc_field == excl_field and inc.value == excl.value and inc.operator == excl.operator:
                        context.add_issue(
                            rule_code="ELIGIBILITY_EXCLUSION_CONFLICT",
                            message=f"Direct conflict: Condition '{inc.field} {inc.operator} {inc.value}' appears in both eligibility inclusion and exclusion rules.",
                            field_path=f"exclusions[{idx}]",
                            actual_value=f"{excl.field} == {excl.value}",
                            evidence_refs=list(set(inc.evidence_refs + excl.evidence_refs)),
                            severity=ValidationSeverity.ERROR,
                        )
