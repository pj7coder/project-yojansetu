import hashlib
import json
import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from app.database.models.scheme_change_item import SchemeChangeItem
from app.database.models.scheme_change_set import SchemeChangeSet
from app.versioning.schemas import ChangeItemSchema, ChangeRiskLevel, ChangeType

logger = logging.getLogger("yojansetu.versioning.change_set_builder")


class SchemeChangeSetBuilder:
    """
    Constructs persistent SchemeChangeSet and SchemeChangeItem records from structured diffs,
    classifies risks, detects temporal and precedence conflicts, and hashes for idempotency.
    """

    def build_change_set(
        self,
        scheme_id: uuid.UUID,
        base_version_id: uuid.UUID,
        source_document_id: uuid.UUID,
        change_items: List[ChangeItemSchema],
        relationship_id: Optional[uuid.UUID] = None,
        effective_date: Optional[date] = None,
        publication_date: Optional[date] = None,
        conflict_reason: Optional[str] = None,
        base_version_hash: Optional[str] = None,
    ) -> SchemeChangeSet:
        """
        Build a SchemeChangeSet with child SchemeChangeItem instances.
        """
        critical_count = sum(1 for item in change_items if item.risk_level == ChangeRiskLevel.CRITICAL)
        total_count = len(change_items)

        # Detect temporal conflict flags
        detected_conflicts: List[str] = []
        if conflict_reason:
            detected_conflicts.append(conflict_reason)

        today = date.today()
        if effective_date:
            if publication_date and effective_date < publication_date:
                detected_conflicts.append("RETROACTIVE_EFFECTIVE_DATE")
            elif effective_date < today:
                detected_conflicts.append("RETROACTIVE_EFFECTIVE_DATE")
        else:
            detected_conflicts.append("EFFECTIVE_DATE_REVIEW_REQUIRED")

        final_conflict = "; ".join(detected_conflicts) if detected_conflicts else None

        # Build summary
        summary = self._generate_summary(change_items, effective_date)

        # Compute deterministic hash
        change_set_hash = self._compute_hash(
            scheme_id=str(scheme_id),
            base_version_id=str(base_version_id),
            source_document_id=str(source_document_id),
            items=change_items,
            effective_date=effective_date.isoformat() if effective_date else "",
        )

        change_set = SchemeChangeSet(
            id=uuid.uuid4(),
            scheme_id=scheme_id,
            base_version_id=base_version_id,
            source_document_id=source_document_id,
            relationship_id=relationship_id,
            status="REVIEW_REQUIRED" if total_count > 0 else "DETECTED",
            effective_date=effective_date,
            publication_date=publication_date,
            changes_count=total_count,
            critical_changes_count=critical_count,
            change_summary=summary,
            conflict_reason=final_conflict,
            change_set_hash=change_set_hash,
        )

        # Build items
        for item in change_items:
            change_item_model = SchemeChangeItem(
                id=uuid.uuid4(),
                change_set_id=change_set.id,
                field_path=item.field_path,
                change_type=item.change_type.value if hasattr(item.change_type, "value") else str(item.change_type),
                old_value_json=self._sanitize_value(item.old_value),
                new_value_json=self._sanitize_value(item.new_value),
                risk_level=item.risk_level.value if hasattr(item.risk_level, "value") else str(item.risk_level),
                evidence_refs=item.evidence_refs,
                clause_reference=item.clause_reference,
                status="PENDING",
            )
            change_set.items.append(change_item_model)

        return change_set

    def _generate_summary(self, items: List[ChangeItemSchema], eff_date: Optional[date]) -> str:
        if not items:
            return "No rule changes detected."

        elig_count = sum(1 for i in items if i.field_path.startswith("eligibility"))
        benefit_count = sum(1 for i in items if i.field_path.startswith("benefits"))
        excl_count = sum(1 for i in items if i.field_path.startswith("exclusions"))
        doc_count = sum(1 for i in items if i.field_path.startswith("documents"))

        parts = []
        if elig_count > 0:
            parts.append(f"{elig_count} eligibility condition(s) modified/added")
        if benefit_count > 0:
            parts.append(f"{benefit_count} benefit provision(s) updated")
        if excl_count > 0:
            parts.append(f"{excl_count} exclusion(s) added")
        if doc_count > 0:
            parts.append(f"{doc_count} document requirement(s) changed")

        if eff_date:
            parts.append(f"Effective date: {eff_date.isoformat()}")

        return "; ".join(parts) if parts else f"{len(items)} change(s) proposed"

    def _compute_hash(
        self,
        scheme_id: str,
        base_version_id: str,
        source_document_id: str,
        items: List[ChangeItemSchema],
        effective_date: str,
    ) -> str:
        payload = {
            "scheme_id": scheme_id,
            "base_version_id": base_version_id,
            "source_document_id": source_document_id,
            "effective_date": effective_date,
            "items": sorted(
                [
                    {
                        "path": i.field_path,
                        "type": str(i.change_type),
                        "val": str(i.new_value),
                    }
                    for i in items
                ],
                key=lambda x: x["path"],
            ),
        }
        raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    def _sanitize_value(self, val: Any) -> Optional[Any]:
        if val is None:
            return None
        if isinstance(val, (dict, list, str, int, float, bool)):
            return val
        return str(val)
