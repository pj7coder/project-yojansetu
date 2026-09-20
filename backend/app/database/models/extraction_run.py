from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
import uuid
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.document_chunk import DocumentChunk


class ExtractionRun(Base, UUIDPrimaryKeyMixin):
    """
    Metadata record for a local LLM structured extraction run on a document chunk.

    Full JSON artifacts and raw LLM responses reside under:
    `storage/extracted/<document_id>/<chunk_id>/`
    while this table tracks lifecycle status, model execution metrics,
    token counts, and validation results.
    """

    __tablename__ = "extraction_runs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated document identifier",
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated semantic chunk identifier",
    )
    chunk_id_str: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Stable chunk identifier string (e.g. DOC-XXXX-CHUNK-0001)",
    )
    model_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ollama",
        comment="LLM provider name (ollama, mock, etc.)",
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="llama3.2:3b",
        comment="Exact LLM model name used for extraction",
    )
    prompt_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version identifier of extraction system/prompt template",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version identifier of output extraction schema",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="QUEUED",
        index=True,
        comment="QUEUED, EXTRACTING, EXTRACTED, EXTRACTION_FAILED, EXTRACTION_REVIEW_REQUIRED",
    )
    artifact_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative path to storage/extracted/<doc_id>/<chunk_id>/extraction.json",
    )
    input_token_estimate: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Estimated prompt token count",
    )
    output_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Actual output token count reported by provider",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total end-to-end extraction latency in milliseconds",
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message or violation explanation if extraction failed",
    )
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured validation diagnostics (facts extracted, evidence matches)",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when model inference started",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when extraction and evidence validation finished",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extraction_runs")
    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", back_populates="extraction_runs")

    __table_args__ = (
        Index("ix_extraction_runs_doc_chunk", "document_id", "chunk_id"),
        Index("ix_extraction_runs_status", "status"),
    )
