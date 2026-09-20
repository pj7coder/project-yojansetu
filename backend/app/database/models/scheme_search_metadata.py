from datetime import date, datetime
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SchemeSearchMetadata(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Derived searchable metadata extracted from human-verified canonical schemes.
    Enables fast, coarse SQL candidate filtering before deterministic eligibility.
    """
    __tablename__ = "scheme_search_metadata"

    scheme_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="Canonical scheme identifier or internal code",
    )
    scheme_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Primary scheme title (English/official)",
    )
    scheme_name_hi: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Hindi official scheme name",
    )
    scheme_draft_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheme_drafts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated SchemeDraft UUID if verified from draft",
    )
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="Rajasthan",
        index=True,
        comment="State jurisdiction (e.g. Rajasthan)",
    )
    districts: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of specific district names if geographically constrained, empty if statewide",
    )
    rural_urban: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="BOTH",
        index=True,
        comment="RURAL, URBAN, BOTH, or ALL",
    )
    scheme_origin: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="RAJASTHAN_STATE",
        index=True,
        comment="RAJASTHAN_STATE, CENTRAL, CENTRALLY_SPONSORED, etc.",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Functional category (e.g. Agriculture, Pension, Education)",
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Target government department UUID",
    )
    beneficiary_tags: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Controlled beneficiary tags (FARMER, STUDENT, SENIOR_CITIZEN, etc.)",
    )
    occupation_tags: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Controlled occupation tags (FARMER, ARTISAN, LABOURER, etc.)",
    )
    valid_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Scheme launch or effective date",
    )
    valid_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Scheme expiration or sunset date",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="True if scheme is active and valid for recommendations",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Strictly True only for schemes that completed HUMAN_VERIFIED status",
    )
    search_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Concise bilingual searchable summary used for semantic embeddings",
    )
    search_text_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of search_text to detect stale embeddings",
    )

    __table_args__ = (
        Index("ix_scheme_search_metadata_districts_gin", "districts", postgresql_using="gin"),
        Index("ix_scheme_search_metadata_beneficiaries_gin", "beneficiary_tags", postgresql_using="gin"),
        Index("ix_scheme_search_metadata_occupations_gin", "occupation_tags", postgresql_using="gin"),
        Index("ix_scheme_search_active_verified", "is_active", "is_verified"),
    )
