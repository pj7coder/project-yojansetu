from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.document import Document
from app.database.models.human_review_item import HumanReviewItem
from app.database.models.human_review_session import HumanReviewSession
from app.database.models.review_audit_event import ReviewAuditEvent
from app.database.models.scheme_draft import SchemeDraft
from app.review.schemas import ReviewActionType, ReviewSessionStatus


class ReviewRepository:
    """Repository for managing human review sessions, review items, and immutable audit logs."""

    @staticmethod
    def create_session(
        db: Session,
        scheme_draft_id: uuid.UUID,
        reviewer_id: str,
        canonical_artifact_sha256: str,
        validation_run_id: Optional[uuid.UUID] = None,
        evidence_verification_run_id: Optional[uuid.UUID] = None,
        status: str = ReviewSessionStatus.IN_PROGRESS.value,
        review_version: int = 1,
    ) -> HumanReviewSession:
        session = HumanReviewSession(
            scheme_draft_id=scheme_draft_id,
            reviewer_id=reviewer_id,
            status=status,
            canonical_artifact_sha256=canonical_artifact_sha256,
            validation_run_id=validation_run_id,
            evidence_verification_run_id=evidence_verification_run_id,
            review_version=review_version,
            started_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def get_latest_session_by_draft_id(
        db: Session, draft_id: uuid.UUID
    ) -> Optional[HumanReviewSession]:
        stmt = (
            select(HumanReviewSession)
            .where(HumanReviewSession.scheme_draft_id == draft_id)
            .order_by(desc(HumanReviewSession.created_at))
            .limit(1)
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_session_by_id(
        db: Session, session_id: uuid.UUID
    ) -> Optional[HumanReviewSession]:
        stmt = (
            select(HumanReviewSession)
            .where(HumanReviewSession.id == session_id)
            .options(
                joinedload(HumanReviewSession.items),
                joinedload(HumanReviewSession.audit_events),
            )
        )
        return db.scalars(stmt).first()

    @staticmethod
    def add_review_items(
        db: Session, items: List[HumanReviewItem]
    ) -> List[HumanReviewItem]:
        for item in items:
            db.add(item)
        db.flush()
        return items

    @staticmethod
    def get_item_by_id(db: Session, item_id: uuid.UUID) -> Optional[HumanReviewItem]:
        return db.get(HumanReviewItem, item_id)

    @staticmethod
    def add_audit_event(
        db: Session,
        session_id: uuid.UUID,
        scheme_draft_id: uuid.UUID,
        reviewer_id: str,
        action_type: ReviewActionType,
        field_path: Optional[str] = None,
        item_id: Optional[uuid.UUID] = None,
        before_value: Optional[Dict[str, Any]] = None,
        after_value: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> ReviewAuditEvent:
        event = ReviewAuditEvent(
            review_session_id=session_id,
            scheme_draft_id=scheme_draft_id,
            reviewer_id=reviewer_id,
            action_type=action_type.value if hasattr(action_type, "value") else str(action_type),
            field_path=field_path,
            item_id=item_id,
            before_value_json=before_value,
            after_value_json=after_value,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def get_audit_events_by_draft(
        db: Session, draft_id: uuid.UUID
    ) -> List[ReviewAuditEvent]:
        stmt = (
            select(ReviewAuditEvent)
            .where(ReviewAuditEvent.scheme_draft_id == draft_id)
            .order_by(desc(ReviewAuditEvent.created_at))
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def query_queue_drafts(
        db: Session,
        status_filter: Optional[str] = None,
        department_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[SchemeDraft], int]:
        """
        Queries review-eligible drafts with prioritization and pagination.
        Priority orders drafts with critical issues, contradictions, and OCR risk first.
        """
        stmt = select(SchemeDraft).join(Document, SchemeDraft.document_id == Document.id)

        if status_filter:
            stmt = stmt.where(SchemeDraft.status == status_filter.upper())
        else:
            # Default queue shows drafts ready for or in human review
            stmt = stmt.where(
                or_(
                    SchemeDraft.status == "READY_FOR_HUMAN_REVIEW",
                    SchemeDraft.status == "IN_HUMAN_REVIEW",
                    SchemeDraft.status == "EVIDENCE_REVIEW_REQUIRED",
                )
            )

        if department_id:
            stmt = stmt.where(SchemeDraft.department_id == department_id)

        # Count total matching
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Prioritize drafts with conflicts or issues, then latest updated
        stmt = stmt.order_by(
            desc(SchemeDraft.conflict_count),
            desc(SchemeDraft.unresolved_field_count),
            desc(SchemeDraft.updated_at),
        )
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        drafts = list(db.scalars(stmt).all())
        return drafts, total
