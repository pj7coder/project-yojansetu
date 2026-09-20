import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.source import Source
    from app.database.models.source_monitor_state import SourceMonitorState
    from app.database.models.source_monitor_run import SourceMonitorRun
    from app.database.models.source_change_event import SourceChangeEvent


class SourceUrl(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Approved government URL belonging to an official registered Source."""

    __tablename__ = "source_urls"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated parent government source",
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        index=True,
        comment="Specific approved URL to monitor",
    )
    url_type: Mapped[str] = mapped_column(
        String(64),
        default="SCHEME_PAGE",
        nullable=False,
        comment="PORTAL, SCHEME_PAGE, NOTIFICATION_PAGE, CIRCULAR_PAGE, DIRECT_FILE, SITEMAP, FEED",
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        default="TIER_1",
        nullable=False,
        index=True,
        comment="Monitoring priority: TIER_1, TIER_2, TIER_3, TIER_4",
    )
    authority_level: Mapped[str] = mapped_column(
        String(32),
        default="OFFICIAL_PORTAL",
        nullable=False,
        comment="OFFICIAL_PORTAL, DEPARTMENT_PORTAL, GAZETTE, DIRECTORATE",
    )
    check_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
        comment="Base check frequency in minutes",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this URL is active for monitoring",
    )
    crawl_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Explicit authorization from registry to monitor this URL",
    )
    strategy: Mapped[str] = mapped_column(
        String(32),
        default="AUTO",
        nullable=False,
        comment="AUTO, HTML, DIRECT_FILE, SITEMAP, FEED",
    )

    @property
    def is_active(self) -> bool:
        return self.enabled

    @is_active.setter
    def is_active(self, value: bool):
        self.enabled = value

    @property
    def check_priority(self) -> str:
        return self.priority

    @property
    def monitor_strategy(self) -> str:
        return self.strategy


    # Relationships
    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="urls",
    )
    monitor_state: Mapped[Optional["SourceMonitorState"]] = relationship(
        "SourceMonitorState",
        back_populates="source_url",
        uselist=False,
        cascade="all, delete-orphan",
    )
    monitor_runs: Mapped[List["SourceMonitorRun"]] = relationship(
        "SourceMonitorRun",
        back_populates="source_url",
        cascade="all, delete-orphan",
    )
    change_events: Mapped[List["SourceChangeEvent"]] = relationship(
        "SourceChangeEvent",
        back_populates="source_url",
        cascade="all, delete-orphan",
    )
