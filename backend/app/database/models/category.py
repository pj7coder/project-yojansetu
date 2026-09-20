from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.scheme import Scheme


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Scheme domain classification category."""

    __tablename__ = "categories"

    code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        comment="Stable unique category slug, e.g. health, education, pension",
    )
    name_en: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="English category name",
    )
    name_hi: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Hindi (Devanagari) category name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Scope description of the category",
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether category is selectable",
    )

    # Relationships
    schemes: Mapped[List["Scheme"]] = relationship(
        "Scheme",
        back_populates="category",
    )
