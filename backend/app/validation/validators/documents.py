from collections import Counter
from app.normalization.schemas import DocumentTypeEnum
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class DocumentsValidator(BaseValidator):
    """
    Validates required document enums and identifies duplicate or redundant requirements.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        doc_types = []
        for idx, doc in enumerate(context.draft.required_documents):
            context.increment_rules_checked(1)
            field_path = f"required_documents[{idx}]"

            if not isinstance(doc.document_type, DocumentTypeEnum):
                context.add_issue(
                    rule_code="DOCUMENT_TYPE_INVALID",
                    message=f"Document '{doc.name_raw}' uses invalid document type '{doc.document_type}'.",
                    field_path=f"{field_path}.document_type",
                    actual_value=str(doc.document_type),
                    evidence_refs=doc.evidence_refs,
                    severity=ValidationSeverity.ERROR,
                )
            else:
                doc_types.append(doc.document_type)

        # Check for duplicates (excluding OTHER)
        counts = Counter(doc_types)
        for d_type, count in counts.items():
            if count > 1 and d_type != DocumentTypeEnum.OTHER:
                context.add_issue(
                    rule_code="DUPLICATE_DOCUMENT_REQUIREMENT",
                    message=f"Document requirement type '{d_type}' appears {count} times across checklist items.",
                    field_path="required_documents",
                    actual_value=d_type,
                    severity=ValidationSeverity.INFO,
                )
