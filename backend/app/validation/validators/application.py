import re
from urllib.parse import urlparse
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApplicationValidator(BaseValidator):
    """
    Validates application submission portal URL safety (strictly http/https),
    application channels, and contact email/phone syntaxes.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft

        # 1. Application URL Safety
        if draft.application and draft.application.portal_url:
            context.increment_rules_checked(1)
            raw_url = draft.application.portal_url.strip()
            field_path = "application.portal_url"

            try:
                parsed = urlparse(raw_url)
                scheme = (parsed.scheme or "").lower()
                if scheme not in ("http", "https") or not parsed.netloc:
                    context.add_issue(
                        rule_code="APPLICATION_URL_UNSAFE",
                        message=f"Application portal URL '{raw_url}' uses disallowed scheme '{scheme}'. Only http/https permitted.",
                        field_path=field_path,
                        actual_value=raw_url,
                        evidence_refs=draft.application.evidence_refs,
                        severity=ValidationSeverity.BLOCKER,
                    )
            except Exception as ex:
                context.add_issue(
                    rule_code="APPLICATION_URL_UNSAFE",
                    message=f"Application portal URL '{raw_url}' could not be safely parsed: {str(ex)}",
                    field_path=field_path,
                    actual_value=raw_url,
                    evidence_refs=draft.application.evidence_refs,
                    severity=ValidationSeverity.BLOCKER,
                )

        # 2. Contact details validation
        for idx, contact in enumerate(draft.contacts):
            context.increment_rules_checked(1)
            c_type = contact.contact_type.lower()
            val = contact.value.strip()
            field_path = f"contacts[{idx}].value"

            if c_type == "email":
                if not EMAIL_REGEX.match(val):
                    context.add_issue(
                        rule_code="CONTACT_INVALID",
                        message=f"Contact email address '{val}' has invalid email format.",
                        field_path=field_path,
                        actual_value=val,
                        evidence_refs=contact.evidence_refs,
                        severity=ValidationSeverity.WARNING,
                    )
            elif c_type in ("phone", "helpline"):
                digits = re.sub(r"\D", "", val)
                if len(digits) < 4:
                    context.add_issue(
                        rule_code="CONTACT_INVALID",
                        message=f"Contact phone/helpline '{val}' contains insufficient digits.",
                        field_path=field_path,
                        actual_value=val,
                        evidence_refs=contact.evidence_refs,
                        severity=ValidationSeverity.WARNING,
                    )
