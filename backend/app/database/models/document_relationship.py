import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document


class DocumentRelationship(Base, UUIDPrimaryKeyMixin):
    """
    Explicit relationship tracking between government documents.

    Models:
    - EXACT_DUPLICATE_OF: identical SHA-256 byte digest
    - CONTENT_DUPLICATE_OF: identical normalized text fingerprint
    - POSSIBLE_NEAR_DUPLICATE_OF: high shingle text similarity (>= 0.98) without version markers
    - POSSIBLE_VERSION_OF: high text similarity with amendment keywords or meaningful text diff
    """

    __tablename__ = "document_relationships"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source document identifier being checked or classified",
    )
    related_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Target canonical or reference document identifier",
    )
    relationship_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="EXACT_DUPLICATE_OF, CONTENT_DUPLICATE_OF, POSSIBLE_NEAR_DUPLICATE_OF, POSSIBLE_VERSION_OF",
    )
    similarity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Jaccard / shingle similarity score between 0.0 and 1.0",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed human-readable classification reason or diff summary",
    )
    detection_method: Mapped[str] = mapped_column(
        String(32),
        default="DETERMINISTIC_METADATA",
        nullable=False,
        comment="EXPLICIT_REFERENCE, DETERMINISTIC_METADATA, TEXTUAL_SIGNAL, LLM_ASSISTED, HUMAN",
    )
    relationship_status: Mapped[str] = mapped_column(
        String(32),
        default="CANDIDATE",
        nullable=False,
        comment="CANDIDATE, AUTO_SUPPORTED, REVIEW_REQUIRED, HUMAN_CONFIRMED, HUMAN_REJECTED",
    )
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Effective date indicated by the relationship if any",
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted textual excerpt proving relationship",
    )
    evidence_page: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Document page number of the relationship evidence",
    )
    evidence_block_ids: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Block identifiers in parsed document containing evidence",
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

    @property
    def source_document_id(self) -> uuid.UUID:
        return self.document_id

    @source_document_id.setter
    def source_document_id(self, val: uuid.UUID) -> None:
        self.document_id = val

    @property
    def target_document_id(self) -> uuid.UUID:
        return self.related_document_id

    @target_document_id.setter
    def target_document_id(self, val: uuid.UUID) -> None:
        self.related_document_id = val

    # ORM Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[document_id],
        back_populates="relationships",
    )
    related_document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[related_document_id],
    )

    __table_args__ = (
        Index("ix_doc_rel_pair", "document_id", "related_document_id"),
    )
