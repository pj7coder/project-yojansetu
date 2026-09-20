import logging
from typing import Any, Dict, List, Optional

from app.versioning.rule_diff import RuleDiffService
from app.versioning.schemas import ChangeItemSchema, ChangeRiskLevel, ChangeType

logger = logging.getLogger("yojansetu.versioning.canonical_diff")


class CanonicalSchemeDiffService:
    """
    Deterministic structured diff engine comparing complete CanonicalScheme models
    across identity, eligibility, exclusions, benefits, documents, and dates.
    """

    def __init__(self, rule_diff_service: Optional[RuleDiffService] = None):
        self.rule_diff = rule_diff_service or RuleDiffService()

    def diff_schemes(
        self,
        base_canonical: Dict[str, Any],
        candidate_canonical: Dict[str, Any],
        is_partial_amendment: bool = True,
        evidence_refs: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ChangeItemSchema]:
        """
        Compare base canonical scheme against candidate canonical scheme.
        Returns ordered list of ChangeItemSchema records.
        """
        changes: List[ChangeItemSchema] = []
        ev_refs = evidence_refs or []

        # 1. Eligibility Diff (delegates to RuleDiffService)
        base_elig = base_canonical.get("eligibility") or {}
        cand_elig = candidate_canonical.get("eligibility") or {}
        if cand_elig:
            elig_changes = self.rule_diff.diff_rule_trees(
                base_eligibility=base_elig,
                candidate_eligibility=cand_elig,
                is_partial_amendment=is_partial_amendment,
                evidence_refs=ev_refs,
            )
            changes.extend(elig_changes)

        # 2. Exclusions Diff
        base_exclusions = self._normalize_named_list(base_canonical.get("exclusions") or [], name_keys=["title", "description", "field", "text"])
        cand_exclusions = self._normalize_named_list(candidate_canonical.get("exclusions") or [], name_keys=["title", "description", "field", "text"])

        # Check added exclusions
        for key, cand_excl in cand_exclusions.items():
            if key not in base_exclusions:
                changes.append(
                    ChangeItemSchema(
                        field_path=f"exclusions.{key}",
                        change_type=ChangeType.ADD,
                        old_value=None,
                        new_value=cand_excl,
                        risk_level=ChangeRiskLevel.CRITICAL,
                        evidence_refs=ev_refs,
                        reason="EXCLUSION_ADDED",
                    )
                )

        # Check removed exclusions only if not partial amendment
        if not is_partial_amendment:
            for key, base_excl in base_exclusions.items():
                if key not in cand_exclusions:
                    changes.append(
                        ChangeItemSchema(
                            field_path=f"exclusions.{key}",
                            change_type=ChangeType.REMOVE,
                            old_value=base_excl,
                            new_value=None,
                            risk_level=ChangeRiskLevel.CRITICAL,
                            evidence_refs=ev_refs,
                            reason="EXCLUSION_REMOVED",
                        )
                    )

        # 3. Benefits Diff
        base_benefits = base_canonical.get("benefits") or {}
        cand_benefits = candidate_canonical.get("benefits") or {}

        # Check financial benefits
        b_fin = base_benefits.get("financial") or base_benefits.get("financial_benefit") or {}
        c_fin = cand_benefits.get("financial") or cand_benefits.get("financial_benefit") or {}

        if c_fin and isinstance(c_fin, dict):
            b_amount = b_fin.get("amount") if isinstance(b_fin, dict) else None
            c_amount = c_fin.get("amount")

            if c_amount is not None and c_amount != b_amount:
                changes.append(
                    ChangeItemSchema(
                        field_path="benefits.financial.amount",
                        change_type=ChangeType.REPLACE if b_amount is not None else ChangeType.ADD,
                        old_value=b_amount,
                        new_value=c_amount,
                        risk_level=ChangeRiskLevel.CRITICAL,
                        evidence_refs=ev_refs,
                        reason="Benefit amount modified",
                    )
                )

            b_period = b_fin.get("periodicity") if isinstance(b_fin, dict) else None
            c_period = c_fin.get("periodicity")
            if c_period is not None and c_period != b_period:
                changes.append(
                    ChangeItemSchema(
                        field_path="benefits.financial.periodicity",
                        change_type=ChangeType.REPLACE if b_period is not None else ChangeType.ADD,
                        old_value=b_period,
                        new_value=c_period,
                        risk_level=ChangeRiskLevel.CRITICAL,
                        evidence_refs=ev_refs,
                        reason="Benefit periodicity modified",
                    )
                )

        # 4. Required Documents Diff (array diff by normalized identity)
        base_docs = self._normalize_named_list(base_canonical.get("documents_required") or base_canonical.get("documents") or [], name_keys=["name", "document_type", "type"])
        cand_docs = self._normalize_named_list(candidate_canonical.get("documents_required") or candidate_canonical.get("documents") or [], name_keys=["name", "document_type", "type"])

        for doc_key, cand_doc in cand_docs.items():
            if doc_key not in base_docs:
                changes.append(
                    ChangeItemSchema(
                        field_path=f"documents.{doc_key}",
                        change_type=ChangeType.ADD,
                        old_value=None,
                        new_value=cand_doc,
                        risk_level=ChangeRiskLevel.NORMAL,
                        evidence_refs=ev_refs,
                        reason=f"New required document '{doc_key}' added",
                    )
                )

        if not is_partial_amendment:
            for doc_key, base_doc in base_docs.items():
                if doc_key not in cand_docs:
                    changes.append(
                        ChangeItemSchema(
                            field_path=f"documents.{doc_key}",
                            change_type=ChangeType.REMOVE,
                            old_value=base_doc,
                            new_value=None,
                            risk_level=ChangeRiskLevel.NORMAL,
                            evidence_refs=ev_refs,
                            reason=f"Required document '{doc_key}' omitted in full replacement",
                        )
                    )

        # 5. Dates & Deadlines Diff (EXTEND_VALIDITY)
        base_validity = base_canonical.get("validity") or {}
        cand_validity = candidate_canonical.get("validity") or {}

        base_deadline = base_validity.get("application_deadline") or base_validity.get("last_date")
        cand_deadline = cand_validity.get("application_deadline") or cand_validity.get("last_date")

        if cand_deadline and cand_deadline != base_deadline:
            changes.append(
                ChangeItemSchema(
                    field_path="validity.application_deadline",
                    change_type=ChangeType.EXTEND_VALIDITY if base_deadline else ChangeType.ADD,
                    old_value=base_deadline,
                    new_value=cand_deadline,
                    risk_level=ChangeRiskLevel.CRITICAL,
                    evidence_refs=ev_refs,
                    reason="Application deadline updated/extended",
                )
            )

        # 6. Identity Diff (contact info, description: LOW risk)
        base_ident = base_canonical.get("identity") or {}
        cand_ident = candidate_canonical.get("identity") or {}

        for low_key in ["contact_number", "helpdesk", "email", "portal_url"]:
            b_val = base_ident.get(low_key)
            c_val = cand_ident.get(low_key)
            if c_val and c_val != b_val:
                changes.append(
                    ChangeItemSchema(
                        field_path=f"identity.{low_key}",
                        change_type=ChangeType.REPLACE if b_val else ChangeType.ADD,
                        old_value=b_val,
                        new_value=c_val,
                        risk_level=ChangeRiskLevel.LOW,
                        evidence_refs=ev_refs,
                        reason=f"Contact info '{low_key}' updated",
                    )
                )

        return changes

    def _normalize_named_list(self, items: Any, name_keys: List[str]) -> Dict[str, Any]:
        """
        Normalize a list of strings or dicts into a key -> object map for index-agnostic diffing.
        """
        result: Dict[str, Any] = {}
        if not isinstance(items, list):
            return result

        for item in items:
            if isinstance(item, str):
                key = item.strip().lower()
                result[key] = item
            elif isinstance(item, dict):
                key = None
                for nk in name_keys:
                    val = item.get(nk)
                    if val and isinstance(val, str):
                        key = val.strip().lower()
                        break
                if not key:
                    key = str(item.get("id", item.get("type", "unknown"))).lower()
                result[key] = item

        return result
