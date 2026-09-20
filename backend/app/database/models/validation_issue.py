from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.scheme_draft import SchemeDraft
    from app.database.models.validation_run import ValidationRun


class ValidationIssue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Individual validation finding or rule failure identified during a ValidationRun.
    """

    __tablename__ = "validation_issues"

    validation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated validation execution run",
    )
    scheme_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated canonical scheme draft",
    )
    rule_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Stable validation rule identifier, e.g. AGE_RANGE_INVALID",
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="INFO, WARNING, ERROR, BLOCKER",
    )
    field_path: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Dot-notation path to the invalid field, e.g. eligibility.root_rule.children[0]",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Precise description of the validation failure or anomaly",
    )
    actual_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Stringified or serialized actual extracted value causing the issue",
    )
    evidence_refs: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of evidence IDs (e.g. ['EVID-001']) linked to this condition",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
        index=True,
        comment="OPEN, ACKNOWLEDGED, RESOLVED, IGNORED_WITH_REASON",
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reviewer notes or reason for acknowledgement/resolution",
    )

    # Relationships
    validation_run: Mapped["ValidationRun"] = relationship(
        "ValidationRun",
        back_populates="issues",
    )
    scheme_draft: Mapped["SchemeDraft"] = relationship(
        "SchemeDraft",
    )

    __table_args__ = (
        Index("ix_validation_issues_draft_rule", "scheme_draft_id", "rule_code"),
        Index("ix_validation_issues_draft_severity", "scheme_draft_id", "severity"),
        Index("ix_validation_issues_status", "status"),
    )
