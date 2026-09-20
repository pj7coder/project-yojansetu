from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source_change_event import SourceChangeEvent


class SourceChangeAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Analysis record interpreting a source_change_event, diff results, and discovered resources."""

    __tablename__ = "source_change_analyses"

    change_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_change_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Associated source change event being analyzed",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ANALYSIS_CLAIMED",
        nullable=False,
        index=True,
        comment="ANALYSIS_CLAIMED, ANALYZING, ANALYZED, ANALYSIS_FAILED, ANALYSIS_REVIEW_REQUIRED",
    )
    render_method: Mapped[str] = mapped_column(
        String(32),
        default="HTTP",
        nullable=False,
        comment="HTTP, PLAYWRIGHT",
    )
    previous_snapshot_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Filesystem path to previous baseline/snapshot",
    )
    current_snapshot_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Filesystem path to current changed snapshot",
    )
    cleaned_snapshot_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Filesystem path to cleaned JSON snapshot",
    )
    diff_summary_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Filesystem path to structured diff.json artifact",
    )
    diff_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary counts and high priority change indicators",
    )
    text_changes_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    links_added_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    links_removed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    links_changed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    numeric_changes_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    has_high_priority_change: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    relevant_resources_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    uncertain_resources_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    irrelevant_resources_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    fetched_resources_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    ingested_documents_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    error_message_safe: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Relationships
    change_event: Mapped["SourceChangeEvent"] = relationship(
        "SourceChangeEvent",
        foreign_keys=[change_event_id],
    )
