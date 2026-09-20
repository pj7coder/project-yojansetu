from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext

CRITICAL_CONFLICT_FIELDS = {
    "age",
    "min_age",
    "max_age",
    "income",
    "family_income",
    "annual_income",
    "benefit",
    "benefit_amount",
    "exclusion",
    "eligibility",
    "disability_percentage",
}


class ConflictsValidator(BaseValidator):
    """
    Validates unresolved normalization conflicts and identity/department integrity.
    Critical unresolved conflicts block progression and are flagged with ERROR severity.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft

        # 1. Unresolved normalization conflicts
        for idx, conf in enumerate(draft.conflicts):
            context.increment_rules_checked(1)
            field_name = conf.field.lower().strip()
            field_path = f"conflicts[{idx}]"
            all_refs = [ref for v in conf.values for ref in v.evidence_refs]

            is_critical = any(crit in field_name for crit in CRITICAL_CONFLICT_FIELDS)

            if is_critical:
                context.add_issue(
                    rule_code="UNRESOLVED_CRITICAL_CONFLICT",
                    message=f"Critical unresolved contradiction for field '{conf.field}': conflicting values across chunks require human review.",
                    field_path=field_path,
                    actual_value=[v.raw_text for v in conf.values],
                    evidence_refs=all_refs,
                    severity=ValidationSeverity.ERROR,
                )
            else:
                context.add_issue(
                    rule_code="UNRESOLVED_CONFLICT",
                    message=f"Unresolved contradiction detected for field '{conf.field}'.",
                    field_path=field_path,
                    actual_value=[v.raw_text for v in conf.values],
                    evidence_refs=all_refs,
                    severity=ValidationSeverity.WARNING,
                )

        # 2. Scheme Name Check
        context.increment_rules_checked(1)
        ident = draft.scheme_identity
        if not ident.name or (not ident.name.raw and not ident.name.en and not ident.name.hi):
            context.add_issue(
                rule_code="SCHEME_NAME_MISSING",
                message="Scheme draft has no detected official title or name.",
                field_path="scheme_identity.name",
                severity=ValidationSeverity.WARNING,
            )

        # 3. Department Resolution Check
        if ident.department and not ident.department_id:
            context.increment_rules_checked(1)
            context.add_issue(
                rule_code="DEPARTMENT_UNRESOLVED",
                message=f"Extracted department '{ident.department}' is not linked to an official registry department ID.",
                field_path="scheme_identity.department",
                actual_value=ident.department,
                severity=ValidationSeverity.INFO,
            )
