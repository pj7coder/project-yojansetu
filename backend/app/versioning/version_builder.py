import copy
import hashlib
import json
import logging
import os
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.core.config import settings
from app.database.base import utc_now
from app.database.models.scheme import SchemeVersion
from app.database.models.scheme_change_set import SchemeChangeSet

logger = logging.getLogger("jansetu.versioning.version_builder")


class SchemeVersionBuilder:
    """
    Constructs an immutable new SchemeVersion by applying approved ChangeSet patches
    to the base verified version canonical data, saving disk artifacts, and attaching provenance.
    """

    def __init__(self, storage_root: Optional[str] = None):
        self.storage_root = Path(storage_root or getattr(settings, "STORAGE_ROOT", "storage"))

    def create_new_version(
        self,
        base_version: SchemeVersion,
        change_set: SchemeChangeSet,
        approved_items_only: bool = True,
    ) -> SchemeVersion:
        """
        Build a new SchemeVersion from base_version + change_set.
        Base version remains 100% immutable.
        """
        base_canonical = base_version.canonical_data or {}
        new_canonical = copy.deepcopy(base_canonical)

        # Determine which items to apply
        items_to_apply = change_set.items
        if approved_items_only:
            items_to_apply = [i for i in change_set.items if i.status == "APPROVED"]
            # If no items were specifically marked APPROVED yet (e.g. bulk approval of whole changeset),
            # apply all items if change_set.status == 'HUMAN_APPROVED'
            if not items_to_apply and change_set.status == "HUMAN_APPROVED":
                items_to_apply = change_set.items

        # Apply patches with provenance
        source_doc_str = str(change_set.source_document_id)
        base_ver_num = base_version.version_number

        field_provenance: Dict[str, Dict[str, Any]] = new_canonical.get("_field_provenance", {})

        for item in items_to_apply:
            fpath = item.field_path
            new_val = item.new_value_json
            ch_type = item.change_type

            # Case 1: eligibility rules
            if fpath.startswith("eligibility.rules."):
                field_name = fpath.replace("eligibility.rules.", "").strip().lower()
                self._patch_eligibility_condition(
                    canonical=new_canonical,
                    field_name=field_name,
                    new_value_dict=new_val,
                    change_type=ch_type,
                    source_doc_id=source_doc_str,
                    evidence_refs=item.evidence_refs,
                )
                field_provenance[fpath] = {
                    "origin": "AMENDMENT",
                    "document_id": source_doc_str,
                    "evidence_refs": item.evidence_refs,
                    "updated_at": utc_now().isoformat(),
                }

            # Case 2: benefits
            elif fpath.startswith("benefits.financial."):
                prop = fpath.replace("benefits.financial.", "")
                benefits = new_canonical.setdefault("benefits", {})
                financial = benefits.setdefault("financial", {})
                financial[prop] = new_val
                field_provenance[fpath] = {
                    "origin": "AMENDMENT",
                    "document_id": source_doc_str,
                    "evidence_refs": item.evidence_refs,
                    "updated_at": utc_now().isoformat(),
                }

            # Case 3: exclusions
            elif fpath.startswith("exclusions."):
                excl_key = fpath.replace("exclusions.", "")
                exclusions = new_canonical.setdefault("exclusions", [])
                if ch_type == "ADD" and new_val:
                    exclusions.append(new_val)
                field_provenance[fpath] = {
                    "origin": "AMENDMENT",
                    "document_id": source_doc_str,
                    "evidence_refs": item.evidence_refs,
                    "updated_at": utc_now().isoformat(),
                }

            # Case 4: documents
            elif fpath.startswith("documents."):
                doc_key = fpath.replace("documents.", "")
                docs = new_canonical.setdefault("documents_required", [])
                if ch_type == "ADD" and new_val:
                    docs.append(new_val)
                field_provenance[fpath] = {
                    "origin": "AMENDMENT",
                    "document_id": source_doc_str,
                    "evidence_refs": item.evidence_refs,
                    "updated_at": utc_now().isoformat(),
                }

            # Case 5: validity / deadline
            elif fpath.startswith("validity."):
                prop = fpath.replace("validity.", "")
                val_sec = new_canonical.setdefault("validity", {})
                val_sec[prop] = new_val
                field_provenance[fpath] = {
                    "origin": "AMENDMENT",
                    "document_id": source_doc_str,
                    "evidence_refs": item.evidence_refs,
                    "updated_at": utc_now().isoformat(),
                }

        new_canonical["_field_provenance"] = field_provenance

        # Next version number
        new_version_number = base_version.version_number + 1
        scheme_id_str = str(base_version.scheme_id)

        # Artifact path & directory
        version_dir = self.storage_root / "schemes" / scheme_id_str / "versions" / f"v{new_version_number}"
        version_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = version_dir / "scheme.json"

        # Serialize JSON and compute SHA-256
        json_bytes = json.dumps(new_canonical, indent=2, ensure_ascii=False).encode("utf-8")
        artifact_sha256 = hashlib.sha256(json_bytes).hexdigest()

        with open(artifact_file, "wb") as f:
            f.write(json_bytes)

        # Write version manifest
        manifest = {
            "version_number": new_version_number,
            "base_version_number": base_ver_num,
            "scheme_id": scheme_id_str,
            "source_document_id": source_doc_str,
            "change_set_id": str(change_set.id),
            "artifact_sha256": artifact_sha256,
            "effective_date": change_set.effective_date.isoformat() if change_set.effective_date else None,
            "publication_date": change_set.publication_date.isoformat() if change_set.publication_date else None,
            "applied_changes_count": len(items_to_apply),
            "created_at": utc_now().isoformat(),
        }
        manifest_file = version_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Create new SchemeVersion record
        new_version = SchemeVersion(
            id=uuid.uuid4(),
            scheme_id=base_version.scheme_id,
            version_number=new_version_number,
            version_label=f"v{new_version_number}.0 (Amended)",
            status="HUMAN_VERIFIED",
            valid_from=change_set.effective_date or base_version.valid_from,
            valid_until=None,
            effective_date=change_set.effective_date,
            source_document_id=change_set.source_document_id,
            supersedes_version_id=base_version.id,
            created_from_relationship_id=change_set.relationship_id,
            canonical_data=new_canonical,
            artifact_path=str(artifact_file),
            artifact_sha256=artifact_sha256,
            source_summary=f"Created from amendment document {source_doc_str}",
            change_summary=change_set.change_summary,
            is_current=False,  # Becomes current only upon explicit activation
        )

        return new_version

    def _patch_eligibility_condition(
        self,
        canonical: Dict[str, Any],
        field_name: str,
        new_value_dict: Any,
        change_type: str,
        source_doc_id: str,
        evidence_refs: List[Dict[str, Any]],
    ) -> None:
        elig = canonical.setdefault("eligibility", {})
        simple = elig.setdefault("simple_fields", {})
        root_rule = elig.setdefault("root_rule", {"type": "AND", "children": []})

        val = new_value_dict.get("value") if isinstance(new_value_dict, dict) else new_value_dict
        op = new_value_dict.get("operator", "LTE") if isinstance(new_value_dict, dict) else "LTE"

        # Update simple fields
        simple[field_name] = val

        # Update or add in root_rule tree
        found = self._update_condition_node(root_rule, field_name, op, val)
        if not found:
            # Append new condition to root rule children
            new_cond = {
                "condition_id": f"COND-AMEND-{uuid.uuid4().hex[:6]}",
                "field": field_name,
                "operator": op,
                "value": val,
                "raw_text": f"{field_name} {op} {val}",
                "evidence_refs": [str(e.get("evidence_id", e)) for e in evidence_refs],
            }
            root_rule.setdefault("children", []).append(new_cond)

    def _update_condition_node(
        self,
        node: Dict[str, Any],
        field_name: str,
        new_op: str,
        new_val: Any,
    ) -> bool:
        if not isinstance(node, dict):
            return False

        if str(node.get("field", "")).lower() == field_name:
            node["operator"] = new_op
            node["value"] = new_val
            return True

        children = node.get("children") or []
        for child in children:
            if isinstance(child, dict):
                if self._update_condition_node(child, field_name, new_op, new_val):
                    return True

        return False
