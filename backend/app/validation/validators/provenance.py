from typing import Dict, List, Set
from app.normalization.schemas import EligibilityCondition, RuleGroup
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class ProvenanceValidator(BaseValidator):
    """
    Validates end-to-end evidence lineage:
    Canonical Field -> Evidence -> Chunk -> Source Block -> Page -> Document.
    Verifies page limits, block existence, document ownership, and OCR risk propagation.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft
        registry = draft.evidence_registry or {}

        # Collect which evidence references support sensitive numeric fields
        sensitive_numeric_fields = {
            "age",
            "min_age",
            "max_age",
            "income",
            "family_income",
            "annual_income",
            "disability_percentage",
            "percentage",
            "benefit_amount",
            "land_holding",
        }
        numeric_evidence_map: Dict[str, str] = {}

        def find_numeric_conditions(rule_group: RuleGroup) -> None:
            for child in rule_group.children:
                if isinstance(child, RuleGroup):
                    find_numeric_conditions(child)
                elif isinstance(child, EligibilityCondition):
                    if child.field.lower() in sensitive_numeric_fields:
                        for ref in child.evidence_refs:
                            numeric_evidence_map[ref] = child.field

        if draft.eligibility and draft.eligibility.root_rule:
            find_numeric_conditions(draft.eligibility.root_rule)

        for ben in draft.benefits:
            if ben.amount is not None:
                for ref in ben.evidence_refs:
                    numeric_evidence_map[ref] = f"benefit_{ben.type}"

        # Validate each registered evidence item
        for evid_id, item in registry.items():
            context.increment_rules_checked(1)
            field_path = f"evidence_registry['{evid_id}']"

            # 1. Document ownership
            if item.document_id and context.document_id:
                if str(item.document_id).strip() != str(context.document_id).strip():
                    context.add_issue(
                        rule_code="DOCUMENT_MISMATCH",
                        message=f"Evidence '{evid_id}' references document '{item.document_id}', but draft belongs to '{context.document_id}'.",
                        field_path=f"{field_path}.document_id",
                        actual_value=item.document_id,
                        evidence_refs=[evid_id],
                        severity=ValidationSeverity.BLOCKER,
                    )

            # 2. Page bounds validation
            if not item.page_numbers:
                context.add_issue(
                    rule_code="EVIDENCE_PAGE_INVALID",
                    message=f"Evidence '{evid_id}' has no associated source page numbers.",
                    field_path=f"{field_path}.page_numbers",
                    evidence_refs=[evid_id],
                    severity=ValidationSeverity.ERROR,
                )
            else:
                for pg in item.page_numbers:
                    if pg < 1:
                        context.add_issue(
                            rule_code="EVIDENCE_PAGE_INVALID",
                            message=f"Evidence '{evid_id}' specifies invalid page number {pg} (< 1).",
                            field_path=f"{field_path}.page_numbers",
                            actual_value=pg,
                            evidence_refs=[evid_id],
                            severity=ValidationSeverity.ERROR,
                        )
                    elif context.doc_page_count and pg > context.doc_page_count:
                        context.add_issue(
                            rule_code="EVIDENCE_PAGE_INVALID",
                            message=f"Evidence '{evid_id}' references page {pg}, which exceeds document total pages ({context.doc_page_count}).",
                            field_path=f"{field_path}.page_numbers",
                            actual_value=pg,
                            evidence_refs=[evid_id],
                            severity=ValidationSeverity.ERROR,
                        )

            # 3. Source block validation
            if context.block_ids and item.source_block_ids:
                for b_id in item.source_block_ids:
                    if b_id not in context.block_ids:
                        context.add_issue(
                            rule_code="SOURCE_BLOCK_MISSING",
                            message=f"Evidence '{evid_id}' references block '{b_id}', which does not exist in parsed document structure.",
                            field_path=f"{field_path}.source_block_ids",
                            actual_value=b_id,
                            evidence_refs=[evid_id],
                            severity=ValidationSeverity.ERROR,
                        )

            # 4. Chunk validation
            if item.chunk_id and context.chunk_ids:
                if item.chunk_id not in context.chunk_ids:
                    context.add_issue(
                        rule_code="CHUNK_INVALID",
                        message=f"Evidence '{evid_id}' references chunk '{item.chunk_id}', which does not exist.",
                        field_path=f"{field_path}.chunk_id",
                        actual_value=item.chunk_id,
                        evidence_refs=[evid_id],
                        severity=ValidationSeverity.ERROR,
                    )
                else:
                    # Check page range within chunk
                    if item.chunk_id in context.chunk_page_ranges and item.page_numbers:
                        c_start, c_end = context.chunk_page_ranges[item.chunk_id]
                        for pg in item.page_numbers:
                            if pg < c_start or pg > c_end:
                                context.add_issue(
                                    rule_code="CHUNK_INVALID",
                                    message=f"Evidence '{evid_id}' page {pg} falls outside chunk '{item.chunk_id}' range [{c_start}, {c_end}].",
                                    field_path=f"{field_path}.page_numbers",
                                    actual_value=pg,
                                    evidence_refs=[evid_id],
                                    severity=ValidationSeverity.ERROR,
                                )

            # 5. OCR risk propagation
            is_low_confidence_ocr = False
            if item.extraction_method and "OCR" in item.extraction_method.upper():
                is_low_confidence_ocr = True
            if item.source_block_ids and context.ocr_low_confidence_blocks:
                if any(b in context.ocr_low_confidence_blocks for b in item.source_block_ids):
                    is_low_confidence_ocr = True

            if is_low_confidence_ocr:
                if evid_id in numeric_evidence_map:
                    num_field = numeric_evidence_map[evid_id]
                    context.add_issue(
                        rule_code="LOW_CONFIDENCE_NUMERIC_OCR",
                        message=f"Sensitive numeric fact '{num_field}' is backed by low-confidence OCR evidence '{evid_id}'. Review required.",
                        field_path=field_path,
                        actual_value=item.raw_value or item.text[:50],
                        evidence_refs=[evid_id],
                        severity=ValidationSeverity.ERROR,
                    )
                else:
                    context.add_issue(
                        rule_code="LOW_CONFIDENCE_OCR_EVIDENCE",
                        message=f"Evidence item '{evid_id}' was generated via low-confidence OCR extraction.",
                        field_path=field_path,
                        actual_value=item.text[:50] if item.text else None,
                        evidence_refs=[evid_id],
                        severity=ValidationSeverity.WARNING,
                    )
