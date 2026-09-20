import uuid
from typing import List, Optional
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models.document_chunk import DocumentChunk


class DocumentChunkRepository:
    """Data access repository for DocumentChunk entities."""

    def create(self, db: Session, chunk: DocumentChunk) -> DocumentChunk:
        db.add(chunk)
        db.commit()
        db.refresh(chunk)
        return chunk

    def create_all(self, db: Session, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        db.add_all(chunks)
        db.commit()
        for c in chunks:
            db.refresh(c)
        return chunks

    def get_by_id(self, db: Session, chunk_id: uuid.UUID) -> Optional[DocumentChunk]:
        return db.get(DocumentChunk, chunk_id)

    def get_by_chunk_id_str(self, db: Session, chunk_id_str: str) -> Optional[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.chunk_id_str == chunk_id_str)
        return db.execute(stmt).scalar_one_or_none()

    def get_by_document_id(self, db: Session, document_id: uuid.UUID) -> List[DocumentChunk]:
        """Fetch all chunks belonging to a document ordered by sequential chunk_index."""
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(db.execute(stmt).scalars().all())

    def delete_by_document_id(self, db: Session, document_id: uuid.UUID) -> int:
        """Delete all existing chunks for a given document (for idempotent re-chunking)."""
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
