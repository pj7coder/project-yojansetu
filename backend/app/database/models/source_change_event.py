from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source_url import SourceUrl
    from app.database.models.source_monitor_run import SourceMonitorRun


class SourceChangeEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Change detection event emitted by monitoring service and queued for Day 18 analysis."""

    __tablename__ = "source_change_events"

    source_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source URL where the change occurred",
    )
    monitor_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_monitor_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Monitor audit run that detected this change",
    )
    change_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="METADATA_CHANGED, CONTENT_CHANGED, LINK_SET_CHANGED, MULTIPLE_SIGNALS, UNKNOWN_CHANGE",
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC timestamp when change was confirmed",
    )
    previous_state_reference: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot path, previous fingerprints, and header metadata",
    )
    new_state_reference: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Snapshot path, new fingerprints, and header metadata",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
        comment="Deterministic key (e.g. source_url_id + new_fingerprint) preventing duplicates",
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING_ANALYSIS",
        nullable=False,
        index=True,
        comment="PENDING_ANALYSIS, ANALYZING, ANALYZED, FAILED",
    )

    # Relationships
    source_url: Mapped["SourceUrl"] = relationship(
        "SourceUrl",
        back_populates="change_events",
    )
    monitor_run: Mapped["SourceMonitorRun"] = relationship(
        "SourceMonitorRun",
        back_populates="change_events",
    )
