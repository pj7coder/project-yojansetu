from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.scheme_draft import SchemeDraft
    from app.database.models.validation_issue import ValidationIssue


class ValidationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks an execution of the Day 11 deterministic validation engine on a SchemeDraft.

    Artifacts reside under:
    `storage/validation/<scheme_draft_id>/validation_report.json`
    and `validation_summary.json`.
    """

    __tablename__ = "validation_runs"

    scheme_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated canonical scheme draft identifier",
    )
    validator_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version of validation engine (e.g. 1.0)",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Specification version of validation schema (e.g. 1.0)",
    )
    canonical_artifact_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 checksum of canonical.json draft validated in this run",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="VALIDATING",
        index=True,
        comment="VALIDATING, VALIDATION_PASSED, VALIDATION_REVIEW_REQUIRED, VALIDATION_FAILED, STALE",
    )
    blocker_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of BLOCKER issues detected",
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of ERROR issues detected",
    )
    warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of WARNING issues detected",
    )
    info_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of INFO issues detected",
    )
    rules_checked_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total validation rules evaluated in this run",
    )
    artifact_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Storage path to validation_report.json artifact",
    )
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary diagnostic metrics, category breakdowns, and performance info",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Execution start timestamp",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Execution finish timestamp",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="End-to-end validation latency in milliseconds",
    )

    # Relationships
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
        back_populates="validation_runs",
    )
    issues: Mapped[List["ValidationIssue"]] = relationship(
        "ValidationIssue",
        back_populates="validation_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_validation_runs_draft_status", "scheme_draft_id", "status"),
        Index("ix_validation_runs_draft_hash", "scheme_draft_id", "canonical_artifact_hash"),
    )
