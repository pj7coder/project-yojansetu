from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.scheme_draft import SchemeDraft


class NormalizationRun(Base, UUIDPrimaryKeyMixin):
    """
    Metadata record for a canonical normalization execution on a document.

    Artifacts reside under:
    `storage/normalized/<document_id>/`
    while this table tracks lifecycle status, scheme counts, normalized metrics,
    duration, and diagnostics.
    """

    __tablename__ = "normalization_runs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated document identifier",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Canonical schema specification version (e.g. 1.0)",
    )
    normalizer_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version identifier of normalization engine (e.g. 1.0)",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="NORMALIZING",
        index=True,
        comment="NORMALIZING, NORMALIZED, NORMALIZATION_FAILED, NORMALIZATION_REVIEW_REQUIRED, NORMALIZATION_BLOCKED, NO_SCHEME_FOUND",
    )
    schemes_detected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of distinct scheme candidates identified in the document",
    )
    fields_normalized: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total count of canonical fields successfully normalized",
    )
    fields_ambiguous: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of fields marked AMBIGUOUS or REVIEW_REQUIRED",
    )
    conflicts_detected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of contradictory values detected across chunks",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="End-to-end normalization latency in milliseconds",
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message or violation explanation if normalization failed",
    )
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary report and counts across all schemes in document",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when normalization started",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when normalization finished",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="normalization_runs")
    scheme_drafts: Mapped[List["SchemeDraft"]] = relationship(
        "SchemeDraft",
        back_populates="normalization_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_normalization_runs_doc_status", "document_id", "status"),
        Index("ix_normalization_runs_status", "status"),
    )
