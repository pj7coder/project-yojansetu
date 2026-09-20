from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.admin.schemas import AdminActivityItem, AdminActivityResponse
from app.database.models.admin_operation_event import AdminOperationEvent
from app.database.models.document import Document
from app.database.models.review_audit_event import ReviewAuditEvent
from app.database.models.scheme import SchemeVersion
from app.database.models.source_change_event import SourceChangeEvent

logger = logging.getLogger("jansetu.admin.activity")


class AdminActivityService:
    """Operational activity aggregator providing unified event stream with strict privacy protection."""

    def get_recent_activity(self, db: Session, limit: int = 40) -> AdminActivityResponse:
        events: List[AdminActivityItem] = []

        # 1. Admin Operation Events (Privileged retries, cache refreshes, etc.)
        admin_ops = db.execute(
            select(AdminOperationEvent).order_by(desc(AdminOperationEvent.created_at)).limit(limit)
        ).scalars().all()
        for op in admin_ops:
            events.append(
                AdminActivityItem(
                    id=str(op.id),
                    event_type="ADMIN_OPERATION",
                    actor=op.actor_id,
                    title=f"{op.action_type.replace('_', ' ').title()}",
                    description=f"Action on {op.target_type}: {op.target_id or ''}",
                    target_id=op.target_id,
                    target_link="/admin/documents" if op.target_type == "DOCUMENT" else None,
                    timestamp=op.created_at.isoformat(),
                    severity="SUCCESS" if "COMPLETED" in op.action_type else "INFO",
                )
            )

        # 2. Source Change Events
        source_evs = db.execute(
            select(SourceChangeEvent).order_by(desc(SourceChangeEvent.created_at)).limit(limit)
        ).scalars().all()
        for sc in source_evs:
            events.append(
                AdminActivityItem(
                    id=str(sc.id),
                    event_type="SOURCE_CHANGE",
                    actor="Monitoring Daemon",
                    title="Source Change Detected",
                    description=f"Change type: {sc.change_type} | Status: {sc.processing_status}",
                    target_id=str(sc.source_url_id),
                    target_link="/admin/sources",
                    timestamp=sc.created_at.isoformat(),
                    severity="WARNING" if sc.change_type == "CONTENT_CHANGED" else "INFO",
                )
            )

        # 3. Document Ingestion / Status Updates
        docs = db.execute(
            select(Document).order_by(desc(Document.created_at)).limit(limit)
        ).scalars().all()
        for d in docs:
            is_failed = "FAILED" in d.processing_status or d.processing_status == "INVALID"
            events.append(
                AdminActivityItem(
                    id=str(d.id),
                    event_type="DOCUMENT",
                    actor=d.ingestion_method,
                    title=f"Document: {d.document_code}",
                    description=f"{d.original_filename} (Status: {d.processing_status})",
                    target_id=str(d.id),
                    target_link=f"/admin/documents",
                    timestamp=(d.updated_at or d.created_at).isoformat(),
                    severity="ERROR" if is_failed else ("SUCCESS" if d.processing_status == "HUMAN_VERIFIED" else "INFO"),
                )
            )

        # 4. Review Audit Events
        reviews = db.execute(
            select(ReviewAuditEvent).order_by(desc(ReviewAuditEvent.created_at)).limit(limit)
        ).scalars().all()
        for r in reviews:
            events.append(
                AdminActivityItem(
                    id=str(r.id),
                    event_type="REVIEW",
                    actor=r.reviewer_id,
                    title=f"Review: {r.action_type}",
                    description=f"Draft {r.scheme_draft_id} updated",
                    target_id=str(r.scheme_draft_id),
                    target_link=f"/admin/review/{r.scheme_draft_id}",
                    timestamp=r.created_at.isoformat(),
                    severity="SUCCESS" if r.action_type == "REVIEW_COMPLETED" else "INFO",
                )
            )

        # 5. Scheme Version Events
        versions = db.execute(
            select(SchemeVersion).order_by(desc(SchemeVersion.created_at)).limit(limit)
        ).scalars().all()
        for v in versions:
            events.append(
                AdminActivityItem(
                    id=str(v.id),
                    event_type="VERSIONING",
                    actor="System / Reviewer",
                    title=f"Scheme Version v{v.version_number}",
                    description=f"Status: {v.status} | Label: {v.version_label or 'Official'}",
                    target_id=str(v.scheme_id),
                    target_link="/admin/versions",
                    timestamp=v.created_at.isoformat(),
                    severity="SUCCESS" if v.status == "ACTIVE" else "INFO",
                )
            )

        # Sort all aggregated activities chronologically descending
        events.sort(key=lambda x: x.timestamp, reverse=True)
        trimmed = events[:limit]

        return AdminActivityResponse(items=trimmed, total=len(trimmed))
