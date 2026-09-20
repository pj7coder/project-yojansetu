from typing import Any, List, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SchemeEmbedding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Multilingual dense vector embedding of verified scheme search text.
    Indexed using pgvector when extension is available.
    """
    __tablename__ = "scheme_embeddings"

    scheme_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Associated canonical scheme identifier",
    )
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Model identifier, e.g. sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    embedding_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Embedding generator pipeline version",
    )
    search_text_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of search_text at time of embedding generation",
    )
    embedding: Mapped[List[float]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Vector embedding coordinates (384 floats) serialized as JSONB or pgvector",
    )

    __table_args__ = (
        Index("ix_scheme_embeddings_scheme_model", "scheme_id", "embedding_model"),
        Index("ix_scheme_embeddings_hash", "search_text_hash"),
    )
