from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.source_change_event import SourceChangeEvent
    from app.database.models.source_url import SourceUrl


class DiscoveredResource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Candidate document or page discovered on a changed official source."""

    __tablename__ = "discovered_resources"

    change_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_change_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source change event that surfaced this candidate",
    )
    source_url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Monitored webpage where the link was discovered",
    )
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Original href target URL as extracted",
    )
    normalized_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        index=True,
        comment="Canonicalized absolute target URL (fragments stripped, query preserved)",
    )
    anchor_text: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Visible anchor text describing the resource",
    )
    context_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Surrounding paragraph or section text",
    )
    resource_type: Mapped[str] = mapped_column(
        String(32),
        default="PDF",
        nullable=False,
        index=True,
        comment="PDF, HTML_PAGE, DOC, DOCX, XLS, XLSX, IMAGE, UNKNOWN",
    )
    discovery_reason: Mapped[str] = mapped_column(
        String(64),
        default="NEW_LINK",
        nullable=False,
        comment="NEW_LINK, CHANGED_LINK, NEW_NOTIFICATION, NEW_PDF, CHANGED_SCHEME_TEXT",
    )
    relevance_status: Mapped[str] = mapped_column(
        String(32),
        default="UNCERTAIN",
        nullable=False,
        index=True,
        comment="RELEVANT, IRRELEVANT, UNCERTAIN",
    )
    relevance_reason: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Signals, positive keywords, negative filters, and explanation",
    )
    fetch_status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True,
        comment="PENDING, FETCHING, FETCHED, FAILED, SKIPPED",
    )
    fetch_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Safe error description if download failed",
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID of created Document record if handed to Day 4 ingestion",
    )

    # Relationships
    change_event: Mapped["SourceChangeEvent"] = relationship(
        "SourceChangeEvent",
        foreign_keys=[change_event_id],
    )
    source_url: Mapped["SourceUrl"] = relationship(
        "SourceUrl",
        foreign_keys=[source_url_id],
    )
    document: Mapped[Optional["Document"]] = relationship(
        "Document",
        foreign_keys=[document_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "change_event_id",
            "normalized_url",
            name="uq_discovered_resource_event_url",
        ),
        Index("ix_discovered_res_event_rel", "change_event_id", "relevance_status"),
    )
