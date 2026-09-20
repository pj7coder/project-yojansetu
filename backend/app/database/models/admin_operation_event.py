from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class AdminOperationEvent(Base, UUIDPrimaryKeyMixin):
    """Audit event tracking privileged administrative and recovery operations."""

    __tablename__ = "admin_operation_events"

    actor_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="DEV_REVIEWER",
        index=True,
        comment="Identifier of the operator or automated administrative actor",
    )
    action_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SOURCE_CHECK_TRIGGERED, DOCUMENT_RETRY_TRIGGERED, SEARCH_REINDEX_TRIGGERED, RULE_CACHE_REFRESHED",
    )
    target_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Target entity type: SOURCE_URL, DOCUMENT, SEARCH_INDEX, RULE_CACHE",
    )
    target_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="Identifier of the target entity if applicable",
    )
    metadata_safe: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Sanitized operational parameters and results",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="UTC timestamp of the operation event",
    )

    __table_args__ = (
        Index("ix_admin_op_action_created", "action_type", "created_at"),
    )
