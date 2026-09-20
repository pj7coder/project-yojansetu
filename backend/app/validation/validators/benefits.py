from app.normalization.schemas import BenefitTypeEnum
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class BenefitsValidator(BaseValidator):
    """
    Validates entitlement benefits: non-negative amounts, currency specifications,
    and type consistency (e.g. CASH with missing amount, IN_KIND with currency).
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        for idx, ben in enumerate(context.draft.benefits):
            context.increment_rules_checked(1)
            field_path = f"benefits[{idx}]"

            # Check negative amount
            if ben.amount is not None and ben.amount < 0:
                context.add_issue(
                    rule_code="BENEFIT_NEGATIVE_AMOUNT",
                    message=f"Benefit amount cannot be negative: {ben.amount}.",
                    field_path=f"{field_path}.amount",
                    actual_value=ben.amount,
                    evidence_refs=ben.evidence_refs,
                    severity=ValidationSeverity.ERROR,
                )

            # Check CASH type with missing amount
            if ben.type == BenefitTypeEnum.CASH and ben.amount is None:
                context.add_issue(
                    rule_code="BENEFIT_TYPE_INCONSISTENT",
                    message=f"Benefit '{ben.benefit_id}' is CASH type but has no specified monetary amount.",
                    field_path=f"{field_path}.amount",
                    actual_value=None,
                    evidence_refs=ben.evidence_refs,
                    severity=ValidationSeverity.WARNING,
                )

            # Check IN_KIND with monetary currency
            if ben.type == BenefitTypeEnum.IN_KIND and ben.amount is not None and ben.currency:
                context.add_issue(
                    rule_code="BENEFIT_TYPE_INCONSISTENT",
                    message=f"Benefit '{ben.benefit_id}' is marked IN_KIND but specifies a monetary currency amount ({ben.currency} {ben.amount}).",
                    field_path=f"{field_path}.type",
                    actual_value={"type": ben.type, "amount": ben.amount, "currency": ben.currency},
                    evidence_refs=ben.evidence_refs,
                    severity=ValidationSeverity.WARNING,
                )
