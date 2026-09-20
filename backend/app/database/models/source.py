import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.department import Department
    from app.database.models.source_url import SourceUrl


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Official government portal, notification page, or circular source."""

    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Source descriptive title",
    )
    base_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Primary entrypoint URL for this source",
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated department, if department-specific",
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        default="PORTAL",
        nullable=False,
        index=True,
        comment="PORTAL, DEPARTMENT_WEBSITE, NOTIFICATION_PAGE, SCHEME_PAGE, BUDGET_PORTAL, OTHER",
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        default="TIER_1",
        nullable=False,
        index=True,
        comment="Crawling/monitoring priority: TIER_1, TIER_2, TIER_3, TIER_4",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this source is currently active for monitoring",
    )

    @property
    def is_active(self) -> bool:
        return self.enabled

    @is_active.setter
    def is_active(self, value: bool):
        self.enabled = value


    # Relationships
    department: Mapped[Optional["Department"]] = relationship(
        "Department",
        back_populates="sources",
    )
    urls: Mapped[List["SourceUrl"]] = relationship(
        "SourceUrl",
        back_populates="source",
        cascade="all, delete-orphan",
    )

