from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source_url import SourceUrl
    from app.database.models.source_change_event import SourceChangeEvent


class SourceMonitorRun(Base, UUIDPrimaryKeyMixin):
    """Historical audit record of an individual monitoring check against a source URL."""

    __tablename__ = "source_monitor_runs"

    source_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Monitored source URL identifier",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC check commencement timestamp",
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC check termination timestamp",
    )
    http_method: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="GET",
        comment="HTTP method executed (HEAD or GET)",
    )
    http_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP response status code",
    )
    result: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="BASELINE_CREATED, UNCHANGED, CHANGED, CHECK_FAILED, BLOCKED_BY_POLICY, ACCESS_FORBIDDEN",
    )
    change_signals: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed signals map (etag_changed, body_fingerprint_changed, etc.)",
    )
    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Check duration in milliseconds",
    )
    response_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total payload bytes received from server",
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Standardized error category if check failed",
    )
    error_message_safe: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Sanitized exception explanation (no internal credentials)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    source_url: Mapped["SourceUrl"] = relationship(
        "SourceUrl",
        back_populates="monitor_runs",
    )
    change_events: Mapped[List["SourceChangeEvent"]] = relationship(
        "SourceChangeEvent",
        back_populates="monitor_run",
    )
