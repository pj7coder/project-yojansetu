from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source_url import SourceUrl


class SourceMonitorState(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Current operational monitoring state and scheduling coordinates for an approved source URL."""

    __tablename__ = "source_monitor_states"

    source_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_urls.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="Associated source URL identifier",
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of the most recent check attempt",
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of the most recent successful response",
    )
    last_change_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp of the most recent detected change",
    )
    next_check_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Scheduled UTC timestamp when this source becomes due for check",
    )
    last_http_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP status code received on most recent attempt",
    )
    etag: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="Server ETag header for conditional requests",
    )
    last_modified: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="Server Last-Modified header for conditional requests",
    )
    content_length: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Observed content length in bytes",
    )
    content_type: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="MIME content type reported by server",
    )
    body_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Deterministic SHA-256 hash of normalized body content",
    )
    link_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Deterministic SHA-256 hash of extracted normalized link set",
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of continuous consecutive check errors",
    )
    consecutive_unchanged: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of continuous checks without any change detected",
    )
    current_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
        comment="Active polling interval in minutes (adaptive backoff/reset)",
    )
    monitor_status: Mapped[str] = mapped_column(
        String(32),
        default="NEVER_CHECKED",
        nullable=False,
        index=True,
        comment="NEVER_CHECKED, UNCHANGED, CHANGED, CHECK_FAILED, TEMPORARILY_UNAVAILABLE, DISABLED, BLOCKED_BY_POLICY, CHECKING",
    )

    # Relationships
    source_url: Mapped["SourceUrl"] = relationship(
        "SourceUrl",
        back_populates="monitor_state",
    )

    __table_args__ = (
        Index("ix_source_monitor_due_query", "next_check_at", "monitor_status"),
    )
