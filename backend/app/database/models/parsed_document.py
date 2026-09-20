import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document


class ParsedDocument(Base, UUIDPrimaryKeyMixin):
    """
    Metadata record for a structured parsed document produced by MinerU / parser engine.

    Full page/block JSON and Markdown artifacts reside on the filesystem under
    `storage/parsed/<document_id>/`, while this model tracks status, diagnostics,
    and runtime performance for indexing and auditing.
    """

    __tablename__ = "parsed_documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Document identifier being parsed",
    )
    parser_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mineru",
        comment="Parser name (mineru, builtin, etc.)",
    )
    parser_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Version string of parser engine",
    )
    parse_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="PARSED",
        index=True,
        comment="PARSED, PARSING_FAILED, REQUIRES_MANUAL_REVIEW",
    )
    page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pages parsed in PDF",
    )
    pages_with_text: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of pages containing extractable digital text",
    )
    pages_without_text: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of zero-text pages (indicates scanned pages needing OCR)",
    )
    pages_low_text: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of low-text pages (< 100 characters)",
    )
    total_text_characters: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Sum of text characters across all blocks",
    )
    total_blocks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total structured blocks (headings, paragraphs, lists, tables)",
    )
    total_tables: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total structured tables preserved",
    )
    output_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative path to storage/parsed/<doc_id>/ directory",
    )
    artifact_sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 digest of normalized document.json artifact",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Parse execution time in milliseconds",
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed error or timeout message if parse failed",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when parsing commenced",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when parsing finished",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="parsed_documents")

    __table_args__ = (
        Index("ix_parsed_documents_doc_status", "document_id", "parse_status"),
    )
