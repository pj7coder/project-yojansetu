from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.human_review_session import HumanReviewSession
    from app.database.models.scheme_draft import SchemeDraft


class ReviewAuditEvent(Base, UUIDPrimaryKeyMixin):
    """
    Immutable, append-only audit record tracking every human review action:
    field approval, edit with before/after snapshots, rejection, conflict resolution,
    override reasons, and review completion.
    """

    __tablename__ = "review_audit_events"

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated review session",
    )
    scheme_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated canonical scheme draft",
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Identity of the reviewing officer",
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="REVIEW_STARTED, FIELD_APPROVED, FIELD_EDITED, FIELD_REJECTED, CONFLICT_RESOLVED, VALIDATION_OVERRIDE, VERIFICATION_OVERRIDE, SCHEME_APPROVED, SCHEME_REJECTED, REVIEW_REOPENED",
    )
    field_path: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Target canonical field path, if action applies to a field",
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Optional ID of associated HumanReviewItem",
    )
    before_value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot of value prior to action",
    )
    after_value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot of value after action",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Mandatory reason or commentary explaining the decision",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Timestamp when audit event occurred",
    )

    # Relationships
    review_session: Mapped["HumanReviewSession"] = relationship(
        "HumanReviewSession",
        back_populates="audit_events",
    )
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
    )

    __table_args__ = (
        Index("ix_review_audit_draft_action", "scheme_draft_id", "action_type"),
    )
