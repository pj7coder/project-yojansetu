from typing import Any, List, Optional
from app.core.config import settings
from app.normalization.schemas import EligibilityCondition, OperatorEnum, PeriodicityEnum, RuleGroup
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class NumbersValidator(BaseValidator):
    """
    Validates numeric ranges, boundaries, currencies, percentages, and measurement units.
    Ensures negative numbers, inverted intervals, and out-of-bound percentages are flagged.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft
        max_age_limit = settings.max_reasonable_age

        def validate_numeric_condition(cond: EligibilityCondition, path: str) -> None:
            context.increment_rules_checked(1)
            field_lower = cond.field.lower()

            # --- Age Checks ---
            if "age" in field_lower:
                # Single numeric value
                if isinstance(cond.value, (int, float)):
                    if cond.value < 0:
                        context.add_issue(
                            rule_code="AGE_NEGATIVE",
                            message=f"Age condition '{cond.field}' cannot be negative ({cond.value}).",
                            field_path=f"{path}.value",
                            actual_value=cond.value,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.ERROR,
                        )
                    elif cond.value > max_age_limit:
                        context.add_issue(
                            rule_code="AGE_SUSPICIOUS",
                            message=f"Age condition value {cond.value} exceeds reasonable maximum of {max_age_limit}.",
                            field_path=f"{path}.value",
                            actual_value=cond.value,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.WARNING,
                        )
                # Range list for BETWEEN
                elif isinstance(cond.value, (list, tuple)) and len(cond.value) >= 2:
                    val1, val2 = cond.value[0], cond.value[1]
                    if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                        if val1 < 0 or val2 < 0:
                            context.add_issue(
                                rule_code="AGE_NEGATIVE",
                                message=f"Age range contains negative boundary: [{val1}, {val2}].",
                                field_path=f"{path}.value",
                                actual_value=cond.value,
                                evidence_refs=cond.evidence_refs,
                                severity=ValidationSeverity.ERROR,
                            )
                        if val1 > val2:
                            context.add_issue(
                                rule_code="AGE_RANGE_INVALID",
                                message=f"Minimum age ({val1}) cannot exceed maximum age ({val2}).",
                                field_path=f"{path}.value",
                                actual_value=cond.value,
                                evidence_refs=cond.evidence_refs,
                                severity=ValidationSeverity.ERROR,
                            )

            # --- Income Checks ---
            elif "income" in field_lower:
                if isinstance(cond.value, (int, float)):
                    if cond.value < 0:
                        context.add_issue(
                            rule_code="INCOME_NEGATIVE",
                            message=f"Income condition '{cond.field}' cannot be negative ({cond.value}).",
                            field_path=f"{path}.value",
                            actual_value=cond.value,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.ERROR,
                        )
                    elif cond.value > 100_000_000:  # > 10 Crore
                        context.add_issue(
                            rule_code="INCOME_EXTREME_VALUE",
                            message=f"Income value {cond.value} is suspiciously extreme for welfare criteria (> 10 Crore INR).",
                            field_path=f"{path}.value",
                            actual_value=cond.value,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.WARNING,
                        )

                # Periodicity consistency
                if "annual" in field_lower and cond.periodicity == PeriodicityEnum.MONTHLY:
                    context.add_issue(
                        rule_code="INCOME_PERIOD_MISMATCH",
                        message=f"Condition field '{cond.field}' is designated annual but periodicity is MONTHLY.",
                        field_path=f"{path}.periodicity",
                        actual_value="MONTHLY",
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.WARNING,
                    )
                elif "monthly" in field_lower and cond.periodicity == PeriodicityEnum.ANNUAL:
                    context.add_issue(
                        rule_code="INCOME_PERIOD_MISMATCH",
                        message=f"Condition field '{cond.field}' is designated monthly but periodicity is ANNUAL.",
                        field_path=f"{path}.periodicity",
                        actual_value="ANNUAL",
                        evidence_refs=cond.evidence_refs,
                        severity=ValidationSeverity.WARNING,
                    )

            # --- Percentage Checks ---
            if "percent" in field_lower or (cond.unit and cond.unit.upper() in ["PERCENT", "%"]):
                if isinstance(cond.value, (int, float)):
                    if cond.value < 0 or cond.value > 100:
                        context.add_issue(
                            rule_code="PERCENTAGE_OUT_OF_RANGE",
                            message=f"Percentage value {cond.value} must be between 0 and 100.",
                            field_path=f"{path}.value",
                            actual_value=cond.value,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.ERROR,
                        )

            # --- Land Holding Checks ---
            if "land" in field_lower:
                if isinstance(cond.value, (int, float)):
                    if cond.value < 0:
                        context.add_issue(
                            rule_code="LAND_MEASUREMENT_NEGATIVE",
                            message=f"Land measurement value cannot be negative ({cond.value}).",
                            field_path=f"{path}.value",
                            actual_value=cond.value,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.ERROR,
                        )
                if cond.unit:
                    recognized_units = {"HECTARE", "HECTARES", "ACRE", "ACRES", "BIGHA", "BIGHAS", "SQ_FT", "SQ_METERS", "SQM"}
                    if cond.unit.upper() not in recognized_units:
                        context.add_issue(
                            rule_code="LAND_UNIT_UNKNOWN",
                            message=f"Unrecognized land measurement unit '{cond.unit}'.",
                            field_path=f"{path}.unit",
                            actual_value=cond.unit,
                            evidence_refs=cond.evidence_refs,
                            severity=ValidationSeverity.WARNING,
                        )

        def walk_rule_group(rule_group: RuleGroup, path: str = "eligibility.root_rule") -> None:
            for idx, child in enumerate(rule_group.children):
                child_path = f"{path}.children[{idx}]"
                if isinstance(child, RuleGroup):
                    walk_rule_group(child, child_path)
                elif isinstance(child, EligibilityCondition):
                    validate_numeric_condition(child, child_path)

        if draft.eligibility and draft.eligibility.root_rule:
            walk_rule_group(draft.eligibility.root_rule)

        # Cross-check simple fields for age range
        simple = draft.eligibility.simple_fields if draft.eligibility else {}
        min_age = simple.get("min_age")
        max_age = simple.get("max_age")
        if isinstance(min_age, (int, float)) and isinstance(max_age, (int, float)):
            if min_age > max_age:
                context.add_issue(
                    rule_code="AGE_RANGE_INVALID",
                    message=f"Eligibility simple_fields min_age ({min_age}) exceeds max_age ({max_age}).",
                    field_path="eligibility.simple_fields",
                    actual_value={"min_age": min_age, "max_age": max_age},
                    severity=ValidationSeverity.ERROR,
                )

        # Check benefit amounts
        for idx, ben in enumerate(draft.benefits):
            context.increment_rules_checked(1)
            if ben.amount is not None:
                if ben.amount < 0:
                    context.add_issue(
                        rule_code="BENEFIT_NEGATIVE_AMOUNT",
                        message=f"Benefit amount cannot be negative ({ben.amount}).",
                        field_path=f"benefits[{idx}].amount",
                        actual_value=ben.amount,
                        evidence_refs=ben.evidence_refs,
                        severity=ValidationSeverity.ERROR,
                    )
                if not ben.currency:
                    context.add_issue(
                        rule_code="CURRENCY_MISSING",
                        message=f"Benefit '{ben.benefit_id}' specifies numeric amount ({ben.amount}) without currency indication.",
                        field_path=f"benefits[{idx}].currency",
                        evidence_refs=ben.evidence_refs,
                        severity=ValidationSeverity.WARNING,
                    )
