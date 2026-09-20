from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, Integer, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.scheme_draft import SchemeDraft
    from app.database.models.fact_verification import FactVerification


class EvidenceVerificationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Tracks an execution of the Day 12 second-pass evidence verification on a SchemeDraft.

    Artifacts reside under:
    `storage/verification/<scheme_draft_id>/verification_summary.json`
    and `runs/<run_id>.json`.
    """

    __tablename__ = "evidence_verification_runs"

    scheme_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated canonical scheme draft identifier",
    )
    canonical_artifact_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 checksum of canonical.json draft verified in this run",
    )
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="VERIFYING",
        index=True,
        comment="VERIFYING, EVIDENCE_VERIFIED, EVIDENCE_REVIEW_REQUIRED, EVIDENCE_VERIFICATION_FAILED, STALE",
    )
    facts_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total atomic facts evaluated in this run",
    )
    facts_supported: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total facts verified as SUPPORTED",
    )
    facts_contradicted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total facts verified as CONTRADICTED",
    )
    facts_insufficient: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total facts classified as NOT_ENOUGH_EVIDENCE",
    )
    facts_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total facts that failed verification due to technical or model errors",
    )
    critical_issues_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of critical-risk facts with CONTRADICTED or NOT_ENOUGH_EVIDENCE",
    )
    verifier_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Version of verification engine (e.g. 1.0)",
    )
    prompt_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Evidence verification prompt template version",
    )
    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Specification version of verification schema",
    )
    artifact_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Storage path to verification run artifact JSON",
    )
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary diagnostic metrics, risk breakdowns, and timing breakdown",
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
        comment="End-to-end verification latency in milliseconds",
    )

    # Relationships
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
        back_populates="evidence_verification_runs",
    )
    fact_verifications: Mapped[List["FactVerification"]] = relationship(
        "FactVerification",
        back_populates="verification_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_evid_verif_runs_draft_status", "scheme_draft_id", "status"),
        Index("ix_evid_verif_runs_draft_hash", "scheme_draft_id", "canonical_artifact_sha256"),
    )
