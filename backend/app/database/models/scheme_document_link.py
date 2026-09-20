import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.database.models.document import Document
    from app.database.models.scheme import Scheme


class SchemeDocumentLink(Base, UUIDPrimaryKeyMixin):
    """
    Links government documents directly to Schemes with explicit roles.
    """

    __tablename__ = "scheme_document_links"
    __table_args__ = (
        UniqueConstraint("scheme_id", "document_id", "link_type", name="uq_scheme_doc_link"),
    )

    scheme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="PRIMARY_GUIDELINE, NOTIFICATION, AMENDMENT, CORRIGENDUM, APPLICATION_GUIDE, CLARIFICATION, OTHER",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="AUTO_LINKED",
        nullable=False,
        comment="AUTO_LINKED, CONFIRMED, REJECTED",
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

    scheme: Mapped["Scheme"] = relationship("Scheme")
    document: Mapped["Document"] = relationship("Document")
