import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Integer, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.extraction_run import ExtractionRun


class DocumentChunk(Base, UUIDPrimaryKeyMixin):
    """
    Metadata record for a logically coherent, token-aware semantic chunk.

    Chunks represent distinct scheme topics (e.g. Eligibility, Benefits, Documents Required)
    derived from structured PDF blocks, preserving physical page bounds and source block IDs
    for evidence verification. Text and JSON payloads reside under `storage/chunks/<doc_id>/`.
    """

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Document identifier from which this chunk was generated",
    )
    chunk_id_str: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Stable internal chunk identifier, e.g. DOC-XXXX-CHUNK-0001",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential 0-based order index of chunk in document",
    )
    section_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Controlled section category (ELIGIBILITY, BENEFITS, etc.)",
    )
    section_path: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Hierarchical section path list, e.g. ['Eligibility', 'Income Limit']",
    )
    chunk_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Human-readable title or heading of chunk",
    )
    page_start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="First physical 1-based page number included in this chunk",
    )
    page_end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Last physical 1-based page number included in this chunk",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Calibrated token count estimate for Llama 3.2",
    )
    contains_table: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if chunk contains at least one structured table",
    )
    contains_ocr: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if chunk contains blocks derived from PaddleOCR fallback",
    )
    source_block_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total source block IDs linked to this chunk",
    )
    artifact_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative path to storage/chunks/<doc_id>/chunks/chunk_XXXX.txt",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    extraction_runs: Mapped[List["ExtractionRun"]] = relationship(
        "ExtractionRun", back_populates="chunk", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_document_chunks_doc_idx", "document_id", "chunk_index"),
        Index("ix_document_chunks_doc_section", "document_id", "section_type"),
    )
