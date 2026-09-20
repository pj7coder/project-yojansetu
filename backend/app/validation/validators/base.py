from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple
from app.normalization.schemas import CanonicalSchemeDraft
from app.validation.registry import get_severity
from app.validation.schemas import ValidationIssueDTO, ValidationSeverity


class ValidationContext:
    """
    Context passed to all deterministic validators during a validation run.
    Contains canonical scheme draft, provenance metadata, document metadata, and issues list.
    """

    def __init__(
        self,
        scheme_draft_id: str,
        document_id: str,
        raw_canonical_data: Dict[str, Any],
        canonical_draft: Optional[CanonicalSchemeDraft] = None,
        doc_page_count: Optional[int] = None,
        chunk_ids: Optional[Set[str]] = None,
        block_ids: Optional[Set[str]] = None,
        chunk_page_ranges: Optional[Dict[str, Tuple[int, int]]] = None,
        chunk_block_ids: Optional[Dict[str, Set[str]]] = None,
        ocr_low_confidence_blocks: Optional[Set[str]] = None,
        registered_department_ids: Optional[Set[str]] = None,
    ):
        self.scheme_draft_id = scheme_draft_id
        self.document_id = document_id
        self.raw_canonical_data = raw_canonical_data
        self.draft = canonical_draft
        self.doc_page_count = doc_page_count
        self.chunk_ids = chunk_ids or set()
        self.block_ids = block_ids or set()
        self.chunk_page_ranges = chunk_page_ranges or {}
        self.chunk_block_ids = chunk_block_ids or {}
        self.ocr_low_confidence_blocks = ocr_low_confidence_blocks or set()
        self.registered_department_ids = registered_department_ids or set()
        self.issues: List[ValidationIssueDTO] = []
        self.rules_checked: int = 0

    def add_issue(
        self,
        rule_code: str,
        message: str,
        field_path: Optional[str] = None,
        actual_value: Optional[Any] = None,
        evidence_refs: Optional[List[str]] = None,
        severity: Optional[ValidationSeverity] = None,
    ) -> None:
        """Record a validation issue."""
        resolved_severity = get_severity(rule_code, severity)
        self.issues.append(
            ValidationIssueDTO(
                rule_code=rule_code,
                severity=resolved_severity,
                field_path=field_path,
                message=message,
                actual_value=str(actual_value) if actual_value is not None else None,
                evidence_refs=list(evidence_refs) if evidence_refs else [],
            )
        )

    def increment_rules_checked(self, count: int = 1) -> None:
        self.rules_checked += count


class BaseValidator(ABC):
    """Abstract base class for all modular deterministic validators."""

    @abstractmethod
    def validate(self, context: ValidationContext) -> None:
        """Run validation rules against context and append any issues."""
        pass
