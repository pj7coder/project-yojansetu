import uuid
from datetime import date
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.category import Category
    from app.database.models.department import Department


class Scheme(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Canonical Rajasthan government scheme entity.
    Maintains stable scheme identity independent of versioned rule changes.
    """

    __tablename__ = "schemes"

    scheme_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique machine-readable identifier, e.g. RJ-HEALTH-001",
    )
    name_en: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Official English scheme name",
    )
    name_hi: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Official Hindi (Devanagari) scheme name",
    )
    short_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Colloquial or abbreviated name, e.g. Chiranjeevi / RGHS",
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Issuing and governing department",
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Functional category classification",
    )
    short_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Brief overview of scheme objective and beneficiaries",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="DRAFT",
        nullable=False,
        index=True,
        comment="DRAFT, REVIEW_REQUIRED, HUMAN_VERIFIED, PRODUCTION, INACTIVE, ARCHIVED",
    )
    jurisdiction: Mapped[str] = mapped_column(
        String(32),
        default="RAJASTHAN",
        nullable=False,
        index=True,
        comment="RAJASTHAN, INDIA, OTHER",
    )
    scheme_origin: Mapped[str] = mapped_column(
        String(32),
        default="UNKNOWN",
        nullable=False,
        index=True,
        comment="RAJASTHAN_STATE, CENTRAL, CENTRALLY_SPONSORED, RAJASTHAN_MODIFIED_CSS, UNKNOWN",
    )

    # Relationships
    department: Mapped["Department"] = relationship(
        "Department",
        back_populates="schemes",
    )
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="schemes",
    )
    versions: Mapped[List["SchemeVersion"]] = relationship(
        "SchemeVersion",
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="desc(SchemeVersion.version_number)",
    )


class SchemeVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Historical or current version of scheme eligibility rules and benefits.
    Ensures amendments do not overwrite past scheme states.
    """

    __tablename__ = "scheme_versions"
    __table_args__ = (
        UniqueConstraint("scheme_id", "version_number", name="uq_scheme_version_number"),
    )

    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent scheme reference",
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Monotonically increasing version iteration (1, 2, 3...)",
    )
    version_label: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Human-readable label, e.g. v1.0, 2026 Revision",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="DRAFT",
        nullable=False,
        index=True,
        comment="DRAFT, REVIEW_REQUIRED, HUMAN_VERIFIED, ACTIVE, SUPERSEDED, EXPIRED, REJECTED",
    )
    valid_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Start date of policy validity",
    )
    valid_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="End or sunset date of policy validity",
    )
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Legally effective date of this version rules",
    )
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Primary document establishing this version",
    )
    supersedes_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Predecessor version superseded by this version",
    )
    created_from_relationship_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_relationships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Relationship record from which this version was created",
    )
    canonical_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete canonical scheme JSON snapshot for this version",
    )
    artifact_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Path to version JSON artifact on disk",
    )
    artifact_sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of canonical artifact JSON",
    )
    source_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Summary of notification/circular establishing this version",
    )
    change_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Summary of what changed from the preceding version",
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Flag indicating if this is the actively evaluated version",
    )

    # Relationships
    scheme: Mapped["Scheme"] = relationship(
        "Scheme",
        back_populates="versions",
    )

