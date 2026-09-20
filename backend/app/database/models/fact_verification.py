from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import Boolean, DateTime, Integer, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.evidence_verification_run import EvidenceVerificationRun
    from app.database.models.scheme_draft import SchemeDraft


class FactVerification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Verification record for an individual atomic fact extracted from a scheme draft
    evaluated against its exact source evidence.
    """

    __tablename__ = "fact_verifications"

    verification_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated evidence verification run",
    )
    scheme_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated canonical scheme draft",
    )
    fact_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Stable atomic fact identifier, e.g. FACT-001",
    )
    field_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Dot-notation path to target canonical field, e.g. eligibility.root_rule.children[0]",
    )
    fact_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="ELIGIBILITY, LOGICAL_CONNECTOR, EXCLUSION, BENEFIT, DOCUMENT, APPLICATION, DATE, DEFINITION, IDENTITY",
    )
    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="NORMAL",
        index=True,
        comment="CRITICAL, HIGH, NORMAL, LOW",
    )
    statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable fact assertion being challenged against evidence",
    )
    canonical_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured dictionary of the canonical claim values",
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Verbatim text of the supporting government evidence",
    )
    result: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="SUPPORTED, CONTRADICTED, NOT_ENOUGH_EVIDENCE, VERIFICATION_FAILED, VERIFICATION_BLOCKED",
    )
    reason_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Stable reason code (DIRECT_MATCH, VALUE_CONFLICT, OPERATOR_CONFLICT, etc.)",
    )
    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Concise explanation for debugging and human review",
    )
    verification_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="DETERMINISTIC",
        index=True,
        comment="DETERMINISTIC, LLM, COMBINED",
    )
    evidence_refs: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of evidence IDs (e.g. ['EVID-001']) cited by this fact",
    )
    ocr_risk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if the supporting evidence originates from low-confidence OCR",
    )
    model_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="LLM provider used (e.g. ollama)",
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Model identifier (e.g. llama3.2:3b)",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Verification latency for this individual fact",
    )

    # Relationships
    verification_run: Mapped["EvidenceVerificationRun"] = relationship(
        "EvidenceVerificationRun",
        back_populates="fact_verifications",
    )
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
    )

    __table_args__ = (
        Index("ix_fact_verif_draft_result", "scheme_draft_id", "result"),
        Index("ix_fact_verif_draft_risk", "scheme_draft_id", "risk_level"),
        Index("ix_fact_verif_draft_type", "scheme_draft_id", "fact_type"),
    )
