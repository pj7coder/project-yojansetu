from typing import Any, List, Set
from app.normalization.schemas import EligibilityCondition, RuleGroup
from app.validation.schemas import ValidationSeverity
from app.validation.validators.base import BaseValidator, ValidationContext


class EvidenceValidator(BaseValidator):
    """
    Validates evidence presence across all canonical factual fields and ensures
    every referenced evidence ID exists in the draft's immutable evidence registry.
    """

    def validate(self, context: ValidationContext) -> None:
        if not context.draft:
            return

        draft = context.draft
        evidence_registry = draft.evidence_registry or {}
        referenced_evidence_ids: Set[str] = set()

        def collect_condition_evidence(rule_group: RuleGroup, path: str = "eligibility.root_rule") -> None:
            context.increment_rules_checked(1)
            for idx, child in enumerate(rule_group.children):
                child_path = f"{path}.children[{idx}]"
                if isinstance(child, RuleGroup):
                    collect_condition_evidence(child, child_path)
                elif isinstance(child, EligibilityCondition):
                    context.increment_rules_checked(1)
                    if not child.evidence_refs:
                        context.add_issue(
                            rule_code="EVIDENCE_REF_MISSING",
                            message=f"Eligibility condition '{child.field}' has no supporting evidence reference.",
                            field_path=f"{child_path}.evidence_refs",
                            actual_value=child.field,
                            severity=ValidationSeverity.ERROR,
                        )
                    else:
                        referenced_evidence_ids.update(child.evidence_refs)

        # 1. Eligibility rule tree conditions
        if draft.eligibility and draft.eligibility.root_rule:
            collect_condition_evidence(draft.eligibility.root_rule)

        # 2. Exclusions
        for idx, excl in enumerate(draft.exclusions):
            context.increment_rules_checked(1)
            if not excl.evidence_refs:
                context.add_issue(
                    rule_code="EVIDENCE_REF_MISSING",
                    message=f"Exclusion '{excl.exclusion_id}' has no supporting evidence reference.",
                    field_path=f"exclusions[{idx}].evidence_refs",
                    actual_value=excl.raw_text[:60] if excl.raw_text else None,
                    severity=ValidationSeverity.ERROR,
                )
            else:
                referenced_evidence_ids.update(excl.evidence_refs)

        # 3. Benefits
        for idx, ben in enumerate(draft.benefits):
            context.increment_rules_checked(1)
            if not ben.evidence_refs:
                context.add_issue(
                    rule_code="EVIDENCE_REF_MISSING",
                    message=f"Benefit '{ben.benefit_id}' ({ben.type}) has no supporting evidence reference.",
                    field_path=f"benefits[{idx}].evidence_refs",
                    actual_value=ben.type,
                    severity=ValidationSeverity.ERROR,
                )
            else:
                referenced_evidence_ids.update(ben.evidence_refs)

        # 4. Required documents
        for idx, doc in enumerate(draft.required_documents):
            context.increment_rules_checked(1)
            if not doc.evidence_refs:
                context.add_issue(
                    rule_code="EVIDENCE_REF_MISSING",
                    message=f"Required document '{doc.document_id}' ({doc.document_type}) has no supporting evidence reference.",
                    field_path=f"required_documents[{idx}].evidence_refs",
                    actual_value=doc.name_raw,
                    severity=ValidationSeverity.WARNING,
                )
            else:
                referenced_evidence_ids.update(doc.evidence_refs)

        # 5. Application
        if draft.application and draft.application.evidence_refs:
            referenced_evidence_ids.update(draft.application.evidence_refs)

        # 6. Important dates
        for idx, dt in enumerate(draft.important_dates):
            context.increment_rules_checked(1)
            if not dt.evidence_refs:
                context.add_issue(
                    rule_code="EVIDENCE_REF_MISSING",
                    message=f"Important date '{dt.event_name}' has no supporting evidence reference.",
                    field_path=f"important_dates[{idx}].evidence_refs",
                    actual_value=dt.raw_date_text,
                    severity=ValidationSeverity.WARNING,
                )
            else:
                referenced_evidence_ids.update(dt.evidence_refs)

        # 7. Verify all referenced evidence IDs exist in registry
        for evid_id in sorted(referenced_evidence_ids):
            context.increment_rules_checked(1)
            if evid_id not in evidence_registry:
                context.add_issue(
                    rule_code="EVIDENCE_REGISTRY_MISSING",
                    message=f"Referenced evidence ID '{evid_id}' does not exist in the draft evidence registry.",
                    field_path="evidence_registry",
                    actual_value=evid_id,
                    evidence_refs=[evid_id],
                    severity=ValidationSeverity.BLOCKER,
                )
