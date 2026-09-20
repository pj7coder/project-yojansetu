from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.human_review_session import HumanReviewSession
    from app.database.models.scheme_draft import SchemeDraft


class HumanReviewItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Individual atomic review item corresponding to a verifiable claim, field,
    rule node, benefit, document, or conflict in the canonical scheme draft.
    Allows granular human decisions (APPROVE, EDIT, REJECT, NOT_APPLICABLE).
    """

    __tablename__ = "human_review_items"

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated review session",
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
        comment="Stable atomic fact identifier, e.g. FACT-001 or CONF-001",
    )
    field_path: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Dot-notation path to target canonical field",
    )
    item_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment="IDENTITY, SCOPE, ELIGIBILITY, LOGICAL_CONNECTOR, EXCLUSION, BENEFIT, DOCUMENT, APPLICATION, DATE, DEFINITION, CONFLICT",
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
        comment="Human-readable claim being evaluated",
    )
    original_value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Original canonical value prior to any reviewer edits",
    )
    current_value_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Current value, reflecting reviewer edits if any",
    )
    raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Verbatim text extracted from the document",
    )
    evidence_refs: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of supporting evidence citation IDs",
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Snippet of resolved official government evidence text",
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Physical page number for PDF viewer navigation",
    )
    block_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Source layout block identifier",
    )
    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
        comment="PENDING, APPROVED, EDITED, REJECTED, NOT_APPLICABLE",
    )
    reviewer_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reviewer commentary or audit notes",
    )
    edit_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Mandatory reason explaining why this field was edited",
    )
    override_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Mandatory reason if overriding CONTRADICTED or NOT_ENOUGH_EVIDENCE",
    )
    validation_issues_summary: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Any Day 11 validation warnings or errors linked to this field",
    )
    verification_result: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="SUPPORTED, CONTRADICTED, NOT_ENOUGH_EVIDENCE",
    )
    verification_reason_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Day 12 reason code, e.g. VALUE_CONFLICT, DIRECT_MATCH",
    )
    ocr_risk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag indicating low-confidence OCR evidence requiring manual inspection",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when reviewer made their decision",
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Identity of reviewer who made the decision",
    )

    # Relationships
    review_session: Mapped["HumanReviewSession"] = relationship(
        "HumanReviewSession",
        back_populates="items",
    )
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
    )

    __table_args__ = (
        Index("ix_review_item_session_decision", "review_session_id", "decision"),
        Index("ix_review_item_draft_decision", "scheme_draft_id", "decision"),
    )
