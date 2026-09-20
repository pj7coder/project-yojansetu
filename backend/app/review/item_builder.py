import logging
from typing import Any, Dict, List, Optional
import uuid

from app.database.models.human_review_item import HumanReviewItem
from app.database.models.fact_verification import FactVerification
from app.database.models.validation_issue import ValidationIssue
from app.verification.fact_builder import CanonicalFactBuilder
from app.verification.schemas import FactRiskLevel, VerifiableFact

logger = logging.getLogger("yojansetu.review.item_builder")


class ReviewItemBuilder:
    """
    Builds atomic HumanReviewItem database models from a canonical draft JSON,
    correlating each fact with Day 11 validation issues, Day 12 verification results,
    and official document evidence provenance.
    """

    @classmethod
    def build_review_items(
        cls,
        review_session_id: uuid.UUID,
        scheme_draft_id: uuid.UUID,
        raw_canonical_data: Dict[str, Any],
        fact_verifications: Optional[List[FactVerification]] = None,
        validation_issues: Optional[List[ValidationIssue]] = None,
    ) -> List[HumanReviewItem]:
        facts_list = CanonicalFactBuilder.build_facts(raw_canonical_data)
        evidence_registry = (
            raw_canonical_data.get("evidence_registry")
            or raw_canonical_data.get("evidence")
            or {}
        )

        # Index fact verifications by fact_id and field_path
        verif_by_fact_id: Dict[str, FactVerification] = {}
        verif_by_field_path: Dict[str, FactVerification] = {}
        if fact_verifications:
            for fv in fact_verifications:
                verif_by_fact_id[fv.fact_id] = fv
                verif_by_field_path[fv.field_path] = fv

        # Index validation issues by field_path
        issues_by_field_path: Dict[str, List[Dict[str, Any]]] = {}
        if validation_issues:
            for vi in validation_issues:
                issue_dict = {
                    "rule_code": vi.rule_code,
                    "severity": vi.severity,
                    "message": vi.message,
                    "field_path": vi.field_path,
                }
                if vi.field_path not in issues_by_field_path:
                    issues_by_field_path[vi.field_path] = []
                issues_by_field_path[vi.field_path].append(issue_dict)

        items: List[HumanReviewItem] = []

        for fact in facts_list:
            # Correlate verification outcome
            matched_verif = verif_by_fact_id.get(fact.fact_id) or verif_by_field_path.get(fact.field_path)
            verif_result = matched_verif.result if matched_verif else None
            verif_reason = matched_verif.reason_code if matched_verif else None
            ocr_risk = matched_verif.ocr_risk if matched_verif else False

            # Correlate validation issues
            matched_issues: List[Dict[str, Any]] = []
            for fp, iss_list in issues_by_field_path.items():
                if fp == fact.field_path or fp.startswith(fact.field_path) or fact.field_path.startswith(fp):
                    matched_issues.extend(iss_list)

            # Resolve primary evidence text and page/block
            primary_evidence_text = None
            page_num = None
            block_id = None
            if fact.evidence_refs:
                for ref in fact.evidence_refs:
                    if ref in evidence_registry:
                        reg_entry = evidence_registry[ref]
                        if isinstance(reg_entry, dict):
                            primary_evidence_text = (
                                reg_entry.get("text")
                                or reg_entry.get("snippet")
                                or reg_entry.get("raw_text")
                                or reg_entry.get("verbatim_text")
                            )
                            p = reg_entry.get("page_number")
                            if p is None and reg_entry.get("page_numbers"):
                                p = reg_entry.get("page_numbers")[0]
                            page_num = p
                            b = reg_entry.get("block_id") or reg_entry.get("source_block_id")
                            if b is None and reg_entry.get("source_block_ids"):
                                b = reg_entry.get("source_block_ids")[0]
                            block_id = b
                            if "OCR" in (reg_entry.get("extraction_method") or "").upper():
                                ocr_risk = True
                            break

            # Calculate risk level
            risk = fact.risk_level.value
            has_blocker_or_error = any(
                i["severity"] in ["BLOCKER", "ERROR"] for i in matched_issues
            )
            if verif_result == "CONTRADICTED" or has_blocker_or_error or ocr_risk:
                risk = FactRiskLevel.CRITICAL.value

            item = HumanReviewItem(
                review_session_id=review_session_id,
                scheme_draft_id=scheme_draft_id,
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                item_type=fact.fact_type.value,
                risk_level=risk,
                statement=fact.statement,
                original_value_json=fact.canonical_value,
                current_value_json=fact.canonical_value,
                raw_text=primary_evidence_text or fact.statement,
                evidence_refs=fact.evidence_refs,
                evidence_text=primary_evidence_text,
                page_number=page_num,
                block_id=block_id,
                decision="PENDING",
                validation_issues_summary=matched_issues if matched_issues else None,
                verification_result=verif_result,
                verification_reason_code=verif_reason,
                ocr_risk=ocr_risk,
            )
            items.append(item)

        return items
