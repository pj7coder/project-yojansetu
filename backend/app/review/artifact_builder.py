import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import get_settings
from app.database.models.human_review_session import HumanReviewSession

logger = logging.getLogger("yojansetu.review.artifact_builder")


class VerifiedArtifactBuilder:
    """
    Constructs and persists immutable verified scheme artifacts upon successful human signoff.
    Stores verified_scheme.json, review_summary.json, and audit_snapshot.json under storage/verified/<draft_id>/.
    """

    @classmethod
    def seal_verified_artifacts(
        cls,
        session: HumanReviewSession,
        raw_canonical_data: Dict[str, Any],
        validation_report_data: Optional[Dict[str, Any]] = None,
        verification_report_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, Dict[str, Any]]:
        settings = get_settings()
        settings.ensure_storage_dirs()

        draft_id_str = str(session.scheme_draft_id)
        verified_dir = settings.verified_dir / draft_id_str
        verified_dir.mkdir(parents=True, exist_ok=True)

        verified_scheme_file = verified_dir / "verified_scheme.json"
        summary_file = verified_dir / "review_summary.json"
        audit_file = verified_dir / "audit_snapshot.json"

        # 1. Construct Verified Scheme Payload
        # Exclude rejected items and reflect current approved/edited values
        verified_scheme_payload = {
            "schema_version": "1.0",
            "verifier_version": "1.0",
            "scheme_draft_id": draft_id_str,
            "review": {
                "status": "HUMAN_VERIFIED",
                "session_id": str(session.id),
                "reviewer_id": session.reviewer_id,
                "review_version": session.review_version,
                "completed_at": session.completed_at.isoformat() if session.completed_at else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "notes": session.notes,
            },
            "canonical_scheme": raw_canonical_data,
            "scheme": raw_canonical_data,
        }

        # 2. Construct Review Summary
        total_items = len(session.items)
        approved_count = sum(1 for i in session.items if i.decision == "APPROVED")
        edited_count = sum(1 for i in session.items if i.decision == "EDITED")
        rejected_count = sum(1 for i in session.items if i.decision == "REJECTED")
        na_count = sum(1 for i in session.items if i.decision == "NOT_APPLICABLE")
        verification_overrides = sum(
            1 for i in session.items if i.decision == "APPROVED" and i.override_reason
        )

        summary_payload = {
            "scheme_draft_id": draft_id_str,
            "session_id": str(session.id),
            "reviewer_id": session.reviewer_id,
            "status": "HUMAN_VERIFIED",
            "fields_total": total_items,
            "approved": approved_count,
            "edited": edited_count,
            "rejected": rejected_count,
            "not_applicable": na_count,
            "verification_overrides": verification_overrides,
            "completed_at": session.completed_at.isoformat() if session.completed_at else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input_canonical_sha256": session.canonical_artifact_sha256,
        }

        # 3. Construct Audit Snapshot
        audit_payload = [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "reviewer_id": a.reviewer_id,
                "field_path": a.field_path,
                "before_value": a.before_value_json,
                "after_value": a.after_value_json,
                "reason": a.reason,
                "timestamp": a.created_at.isoformat() if a.created_at else None,
            }
            for a in session.audit_events
        ]

        # Write files atomically
        with open(verified_scheme_file, "w", encoding="utf-8") as f:
            json.dump(verified_scheme_payload, f, indent=2, ensure_ascii=False)

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2, ensure_ascii=False)

        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(audit_payload, f, indent=2, ensure_ascii=False)

        # Calculate sealed verified artifact hash
        verified_bytes = verified_scheme_file.read_bytes()
        verified_sha256 = hashlib.sha256(verified_bytes).hexdigest()
        summary_payload["verified_artifact_sha256"] = verified_sha256

        return verified_scheme_file, summary_payload
