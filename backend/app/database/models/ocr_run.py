import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document


class OCRRun(Base, UUIDPrimaryKeyMixin):
    """
    Metadata record for an OCR check or page-level fallback run.

    Full raw page OCR outputs and merged document JSON artifacts reside on the filesystem
    under `storage/ocr/<document_id>/`, while this model tracks lifecycle status,
    per-page statistics, numeric confidence warnings, and chunking source paths.
    """

    __tablename__ = "ocr_runs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Document identifier associated with this OCR run",
    )
    ocr_engine: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="paddleocr",
        comment="OCR engine name (paddleocr, mock, etc.)",
    )
    ocr_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Version string of OCR engine",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="COMPLETED",
        index=True,
        comment="COMPLETED, FAILED, PARTIAL_FAILURE, REVIEW_REQUIRED, SKIPPED_NOT_NEEDED",
    )
    pages_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pages in the document",
    )
    pages_checked: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total pages evaluated for OCR requirement",
    )
    pages_ocr_required: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of pages detected as needing OCR",
    )
    pages_ocr_success: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of pages where OCR successfully ran and merged",
    )
    pages_ocr_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of pages where OCR failed",
    )
    low_confidence_numeric_regions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of numeric regions below confidence threshold",
    )
    output_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Relative path to storage/ocr/<doc_id>/merged_document.json if OCR performed",
    )
    chunking_source_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Selected source path for Day 8 chunking (parsed document or merged OCR document)",
    )
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured diagnostics including page decisions and per-page metrics",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when OCR process commenced",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when OCR process finished",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total duration in milliseconds",
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Sanitized failure reason or error message if OCR failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="ocr_runs")

    __table_args__ = (
        Index("ix_ocr_runs_doc_status", "document_id", "status"),
    )
