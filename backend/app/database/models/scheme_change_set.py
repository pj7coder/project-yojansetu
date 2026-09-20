import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.document_relationship import DocumentRelationship
    from app.database.models.scheme import Scheme, SchemeVersion
    from app.database.models.scheme_change_item import SchemeChangeItem


class SchemeChangeSet(Base, UUIDPrimaryKeyMixin):
    """
    Groups proposed rule and metadata modifications detected between
    an existing verified SchemeVersion and a newly analyzed government document.
    """

    __tablename__ = "scheme_change_sets"

    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Target scheme being updated",
    )
    base_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Base verified version against which changes were detected",
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="New government document containing amendments or updates",
    )
    relationship_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_relationships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Document relationship linking source document to base document",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="DETECTED",
        nullable=False,
        index=True,
        comment="DETECTED, REVIEW_REQUIRED, HUMAN_APPROVED, HUMAN_REJECTED, APPLIED_TO_VERSION",
    )
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Legally declared effective date of the amendments",
    )
    publication_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Official publication or notification date of source document",
    )
    changes_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total count of detected change items",
    )
    critical_changes_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Count of CRITICAL risk items (eligibility, benefits, exclusions, dates)",
    )
    change_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Deterministic summary of changes",
    )
    conflict_reason: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="UNRESOLVED_SOURCE_CONFLICT, STALE_BASE_VERSION, RETROACTIVE_EFFECTIVE_DATE, etc.",
    )
    change_set_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Deterministic SHA-256 hash for idempotency and audit",
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

    # Relationships
    scheme: Mapped["Scheme"] = relationship("Scheme")
    base_version: Mapped["SchemeVersion"] = relationship("SchemeVersion", foreign_keys=[base_version_id])
    source_document: Mapped["Document"] = relationship("Document", foreign_keys=[source_document_id])
    relationship_ref: Mapped[Optional["DocumentRelationship"]] = relationship("DocumentRelationship", foreign_keys=[relationship_id])
    items: Mapped[List["SchemeChangeItem"]] = relationship(
        "SchemeChangeItem",
        back_populates="change_set",
        cascade="all, delete-orphan",
    )
