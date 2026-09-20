import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.scheme_change_set import SchemeChangeSet


class SchemeChangeItem(Base, UUIDPrimaryKeyMixin):
    """
    Individual structured diff item within a SchemeChangeSet.
    """

    __tablename__ = "scheme_change_items"

    change_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_change_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_path: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
        comment="e.g. eligibility.family_income, benefits.financial_benefit, exclusions[0]",
    )
    change_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="ADD, REMOVE, REPLACE, MODIFY, EXTEND_VALIDITY, NO_RULE_CHANGE, UNKNOWN_CHANGE",
    )
    old_value_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous canonical value from base version",
    )
    new_value_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Proposed new value from amendment document",
    )
    risk_level: Mapped[str] = mapped_column(
        String(32),
        default="NORMAL",
        nullable=False,
        index=True,
        comment="CRITICAL, NORMAL, LOW",
    )
    evidence_refs: Mapped[List[dict]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Grounding references: page, chunk_id, block_id, quote",
    )
    clause_reference: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="e.g. Rule 5, Clause 4(ii), पैरा 3",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        comment="PENDING, APPROVED, REJECTED",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    change_set: Mapped["SchemeChangeSet"] = relationship(
        "SchemeChangeSet",
        back_populates="items",
    )
