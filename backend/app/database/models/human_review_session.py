from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.scheme_draft import SchemeDraft
    from app.database.models.human_review_item import HumanReviewItem
    from app.database.models.review_audit_event import ReviewAuditEvent
    from app.database.models.validation_run import ValidationRun
    from app.database.models.evidence_verification_run import EvidenceVerificationRun


class HumanReviewSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Session tracking an authorized human reviewer's evaluation of a canonical scheme draft.
    Ties together validation runs, second-pass evidence verification, individual fact decisions,
    conflict resolutions, and immutable audit history.
    """

    __tablename__ = "human_review_sessions"

    scheme_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated canonical scheme draft under review",
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="DEV_REVIEWER",
        index=True,
        comment="Identity of the reviewing officer/admin",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="NOT_STARTED",
        index=True,
        comment="NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETED, REJECTED, STALE",
    )
    canonical_artifact_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of canonical draft when review began; used for stale detection",
    )
    validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated Day 11 deterministic validation run",
    )
    evidence_verification_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_verification_runs.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated Day 12 evidence verification run",
    )
    review_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Monotonically increasing version counter for optimistic locking",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reviewer notes or high-level observations",
    )
    summary_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Aggregated summary of items: approved, edited, rejected, conflicts resolved",
    )
    verified_artifact_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Relative path to storage/verified/<draft_id>/verified_scheme.json",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when review session began",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when review was finalized",
    )

    # Relationships
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
        back_populates="review_sessions",
    )
    items: Mapped[List["HumanReviewItem"]] = relationship(
        "HumanReviewItem",
        back_populates="review_session",
        cascade="all, delete-orphan",
        order_by="HumanReviewItem.created_at",
    )
    audit_events: Mapped[List["ReviewAuditEvent"]] = relationship(
        "ReviewAuditEvent",
        back_populates="review_session",
        cascade="all, delete-orphan",
        order_by="ReviewAuditEvent.created_at",
    )

    __table_args__ = (
        Index("ix_review_sess_draft_status", "scheme_draft_id", "status"),
    )
