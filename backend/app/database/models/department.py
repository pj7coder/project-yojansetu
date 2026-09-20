from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.scheme import Scheme
    from app.database.models.source import Source


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Rajasthan government department entity."""

    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        comment="Stable unique department identifier, e.g. SJE, HEALTH, WCD",
    )
    name_en: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Official English name of the department",
    )
    name_hi: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Official Hindi (Devanagari) name of the department",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Department mandate and overview",
    )
    official_website: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Official portal URL",
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Operational active status",
    )

    # Relationships
    schemes: Mapped[List["Scheme"]] = relationship(
        "Scheme",
        back_populates="department",
        cascade="all, delete-orphan",
    )
    sources: Mapped[List["Source"]] = relationship(
        "Source",
        back_populates="department",
    )
