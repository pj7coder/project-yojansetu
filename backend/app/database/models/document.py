import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source import Source
    from app.database.models.document_relationship import DocumentRelationship
    from app.database.models.parsed_document import ParsedDocument
    from app.database.models.ocr_run import OCRRun
    from app.database.models.document_chunk import DocumentChunk
    from app.database.models.extraction_run import ExtractionRun
    from app.database.models.normalization_run import NormalizationRun
    from app.database.models.scheme_draft import SchemeDraft


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Official Rajasthan government document entity for ingestion and audit trail."""

    __tablename__ = "documents"

    # Stable internal code (e.g. DOC-2026-000001 or DOC-UUID)
    document_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique internal document identifier",
    )

    # Filenames
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Preserved original filename including Unicode and spaces",
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="original.pdf",
        comment="Standard internal stored filename",
    )

    # File attributes
    file_extension: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=".pdf",
        comment="Normalized file extension",
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/pdf",
        comment="Detected MIME content type",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="File size in bytes",
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Relative path from storage root to preserved file",
    )

    # Source references (optional for Day 4 manual/folder uploads)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated Day 3 government source if known",
    )
    source_url_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Associated source URL identifier if crawler-driven",
    )

    # Ingestion metadata
    ingestion_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="MANUAL_UPLOAD, FOLDER_WATCHER, WEB_MONITOR, API",
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="RECEIVED",
        index=True,
        comment="RECEIVED, VALIDATING, READY_FOR_DUPLICATE_CHECK, INVALID, FAILED",
    )
    sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 hash digest (non-unique in Day 4)",
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional human-readable title",
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Sanitized failure reason if validation or ingestion failed",
    )
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when upload/receipt was initiated",
    )

    # Duplicate & Version Detection Metadata (Day 5)
    normalized_text_sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 hash digest of normalized rough text fingerprint",
    )
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total pages detected in the PDF document",
    )
    text_length: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Character length of extracted normalized rough text",
    )
    duplicate_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        comment="NEW_DOCUMENT, EXACT_DUPLICATE, CONTENT_DUPLICATE, POSSIBLE_VERSION, POSSIBLE_NEAR_DUPLICATE, REVIEW_REQUIRED, CONFIRMED_VERSION",
    )
    canonical_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Resolved root canonical document identifier",
    )
    duplicate_of_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Direct matched duplicate document identifier",
    )
    possible_version_of_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Predecessor document of which this is an amendment or version",
    )
    similarity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Highest shingle similarity score against matched document",
    )
    duplicate_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when duplicate analysis was completed",
    )
    duplicate_check_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed classification rationale or text difference summary",
    )

    # Relationships
    source: Mapped[Optional["Source"]] = relationship("Source")
    relationships: Mapped[list["DocumentRelationship"]] = relationship(
        "DocumentRelationship",
        foreign_keys="[DocumentRelationship.document_id]",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    parsed_documents: Mapped[list["ParsedDocument"]] = relationship(
        "ParsedDocument",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    ocr_runs: Mapped[list["OCRRun"]] = relationship(
        "OCRRun",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(
        "ExtractionRun",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    normalization_runs: Mapped[list["NormalizationRun"]] = relationship(
        "NormalizationRun",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    scheme_drafts: Mapped[list["SchemeDraft"]] = relationship(
        "SchemeDraft",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_documents_created_at", "created_at"),
    )
