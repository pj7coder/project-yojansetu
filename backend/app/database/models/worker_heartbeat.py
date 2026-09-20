from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkerHeartbeat(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational heartbeat registry for asynchronous background workers."""

    __tablename__ = "worker_heartbeats"

    worker_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Type of worker: monitoring, change_analysis, parser, ocr, chunking, extraction, versioning",
    )
    worker_instance_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="Unique identifier of the running worker instance or process",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="UTC timestamp of the most recent heartbeat ping",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="HEALTHY",
        index=True,
        comment="Operational status: HEALTHY, IDLE, BUSY, STOPPED",
    )
    metadata_safe: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Sanitized operational metadata: current_task, items_processed, error_count",
    )

    __table_args__ = (
        UniqueConstraint(
            "worker_type",
            "worker_instance_id",
            name="uq_worker_heartbeats_type_instance",
        ),
        Index("ix_worker_heartbeats_type_seen", "worker_type", "last_seen_at"),
    )
