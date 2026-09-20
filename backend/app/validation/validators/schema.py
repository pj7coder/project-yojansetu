from typing import Any, Dict
from pydantic import ValidationError

from app.normalization.schemas import CanonicalSchemeDraft
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class SchemaValidator(BaseValidator):
    """
    Validates canonical scheme draft against Day 10 Pydantic models.
    Malformed canonical JSON or missing essential structural schemas are BLOCKERs.
    """

    def validate(self, context: ValidationContext) -> None:
        context.increment_rules_checked(2)

        if not isinstance(context.raw_canonical_data, dict):
            context.add_issue(
                rule_code="SCHEMA_INVALID",
                message="Canonical artifact is not a valid JSON object dictionary.",
                field_path="",
                actual_value=type(context.raw_canonical_data).__name__,
                severity=ValidationSeverity.BLOCKER,
            )
            return

        # Check essential top-level keys before detailed model parse
        required_keys = ["scheme_identity", "eligibility", "document_id"]
        for key in required_keys:
            if key not in context.raw_canonical_data or context.raw_canonical_data[key] is None:
                context.add_issue(
                    rule_code="REQUIRED_FIELD_MISSING",
                    message=f"Essential canonical top-level field '{key}' is missing.",
                    field_path=key,
                    severity=ValidationSeverity.BLOCKER,
                )

        # Parse against Pydantic CanonicalSchemeDraft model
        try:
            draft = CanonicalSchemeDraft.model_validate(context.raw_canonical_data)
            context.draft = draft
        except ValidationError as ve:
            for err in ve.errors():
                loc_path = ".".join(str(p) for p in err.get("loc", []))
                context.add_issue(
                    rule_code="SCHEMA_INVALID",
                    message=f"Canonical schema validation error at '{loc_path}': {err.get('msg')}",
                    field_path=loc_path,
                    actual_value=err.get("input"),
                    severity=ValidationSeverity.BLOCKER,
                )
        except Exception as ex:
            context.add_issue(
                rule_code="SCHEMA_INVALID",
                message=f"Unexpected schema parse failure: {str(ex)}",
                field_path="",
                severity=ValidationSeverity.BLOCKER,
            )
