from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source_change_event import SourceChangeEvent
    from app.database.models.source_url import SourceUrl


class WebContentArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Authoritative scheme information extracted directly from an official HTML webpage without downloadable PDF."""

    __tablename__ = "web_content_artifacts"

    source_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated source URL where content was published",
    )
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_change_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated change event",
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Page or article title",
    )
    source_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Exact URL where the page content was captured",
    )
    cleaned_content: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Structured representation: headings, text_blocks, tables, links",
    )
    cleaned_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Normalized linear textual representation",
    )
    status: Mapped[str] = mapped_column(
        String(64),
        default="READY_FOR_WEB_CONTENT_PROCESSING",
        nullable=False,
        index=True,
        comment="READY_FOR_WEB_CONTENT_PROCESSING, PROCESSED, ARCHIVED",
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp when HTML content was fetched and cleaned",
    )

    # Relationships
    source_url_ref: Mapped["SourceUrl"] = relationship(
        "SourceUrl",
        foreign_keys=[source_url_id],
    )
    change_event: Mapped["SourceChangeEvent"] = relationship(
        "SourceChangeEvent",
        foreign_keys=[change_event_id],
    )
