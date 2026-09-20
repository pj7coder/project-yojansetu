from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.department import Department
    from app.database.models.normalization_run import NormalizationRun
    from app.database.models.validation_run import ValidationRun
    from app.database.models.evidence_verification_run import EvidenceVerificationRun
    from app.database.models.human_review_session import HumanReviewSession


class SchemeDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Canonical Rajasthan scheme candidate extracted from an official document.

    Maintains unverified structured scheme draft representations, strictly separated
    from the verified production `schemes` table until human verification (Day 12+).
    Full canonical JSON resides under:
    `storage/normalized/<document_id>/<draft_id>/canonical.json`
    """

    __tablename__ = "scheme_drafts"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source document identifier",
    )
    normalization_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("normalization_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated normalization execution run",
    )
    internal_scheme_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="Stable internal draft identity code (e.g. RJ-DRAFT-<UUID>)",
    )
    detected_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Primary scheme name detected from document context",
    )
    official_name_raw: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Unmodified official scheme name verbatim from government text",
    )
    official_name_hi: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Explicit Hindi scheme name if present in source text",
    )
    official_name_en: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Explicit English scheme name if present in source text",
    )
    normalized_name_for_matching: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Unicode/whitespace/case-normalized name for matching candidates",
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Matched Department registry ID if high-confidence deterministic match",
    )
    department_name_raw: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Raw department string from government text",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Canonical schema specification version",
    )
    normalizer_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version of normalization engine used",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="READY_FOR_VALIDATION",
        index=True,
        comment="READY_FOR_VALIDATION, NORMALIZATION_REVIEW_REQUIRED, NORMALIZATION_FAILED, SCHEME_ASSOCIATION_REVIEW_REQUIRED",
    )
    artifact_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative path to storage/normalized/<doc_id>/<draft_id>/canonical.json",
    )
    conflict_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of unresolved contradictions flagged in this draft",
    )
    unresolved_field_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of fields marked AMBIGUOUS or REVIEW_REQUIRED",
    )
    summary_counts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Breakdown of fields normalized, ambiguous, conflicts, evidence count",
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="scheme_drafts")
    normalization_run: Mapped[Optional["NormalizationRun"]] = relationship(
        "NormalizationRun", back_populates="scheme_drafts"
    )
    department: Mapped[Optional["Department"]] = relationship("Department")
    validation_runs: Mapped[List["ValidationRun"]] = relationship(
        "ValidationRun",
        back_populates="scheme_draft",
        cascade="all, delete-orphan",
    )
    evidence_verification_runs: Mapped[List["EvidenceVerificationRun"]] = relationship(
        "EvidenceVerificationRun",
        back_populates="scheme_draft",
        cascade="all, delete-orphan",
    )
    review_sessions: Mapped[List["HumanReviewSession"]] = relationship(
        "HumanReviewSession",
        back_populates="scheme_draft",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_scheme_drafts_doc_status", "document_id", "status"),
        Index("ix_scheme_drafts_matching_name", "normalized_name_for_matching"),
    )
