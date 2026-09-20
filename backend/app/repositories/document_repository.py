import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.document import Document


class DocumentRepository:
    """Repository handling database operations for Document entities."""

    def create(self, db: Session, document: Document) -> Document:
        """Persist a new Document record."""
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def get_by_id(self, db: Session, document_id: uuid.UUID) -> Optional[Document]:
        """Retrieve a document by its primary UUID."""
        query = select(Document).where(Document.id == document_id)
        return db.execute(query).scalar_one_or_none()

    def get_by_code(self, db: Session, document_code: str) -> Optional[Document]:
        """Retrieve a document by its unique internal code."""
        query = select(Document).where(Document.document_code == document_code.strip())
        return db.execute(query).scalar_one_or_none()

    def list(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        processing_status: Optional[str] = None,
        ingestion_method: Optional[str] = None,
        source_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[Document], int]:
        """
        Query paginated documents with optional filters.
        Returns a tuple of (items, total_count).
        """
        base_query = select(Document)

        if processing_status:
            base_query = base_query.where(Document.processing_status == processing_status.strip().upper())
        if ingestion_method:
            base_query = base_query.where(Document.ingestion_method == ingestion_method.strip().upper())
        if source_id:
            base_query = base_query.where(Document.source_id == source_id)

        # Count total matching records
        count_query = select(func.count()).select_from(base_query.subquery())
        total = db.execute(count_query).scalar_one()

        # Paginated results ordered by creation time descending
        offset = (page - 1) * page_size
        items_query = (
            base_query
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(db.execute(items_query).scalars().all())

        return items, total

    def update(self, db: Session, document: Document) -> Document:
        """Persist changes to an existing Document record."""
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def update_status(
        self,
        db: Session,
        document_id: uuid.UUID,
        status: str,
        failure_reason: Optional[str] = None,
    ) -> Optional[Document]:
        """Update processing status and optional failure reason of a document."""
        document = self.get_by_id(db, document_id)
        if not document:
            return None

        document.processing_status = status.strip().upper()
        if failure_reason is not None:
            document.failure_reason = failure_reason
        db.commit()
        db.refresh(document)
        return document

    def find_exact_sha256_match(
        self,
        db: Session,
        sha256: str,
        exclude_id: uuid.UUID,
        created_before: Optional[object] = None,
    ) -> Optional[Document]:
        """Find the earliest established document sharing identical file bytes."""
        query = (
            select(Document)
            .where(
                Document.sha256 == sha256,
                Document.id != exclude_id,
                Document.processing_status.not_in(["INVALID", "FAILED", "READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING"]),
            )
        )
        if created_before is not None:
            query = query.where(Document.created_at <= created_before)

        query = query.order_by(Document.created_at.asc()).limit(1)
        return db.execute(query).scalar_one_or_none()

    def find_content_hash_match(
        self,
        db: Session,
        normalized_hash: str,
        exclude_id: uuid.UUID,
        created_before: Optional[object] = None,
    ) -> Optional[Document]:
        """Find the earliest established document sharing identical normalized rough text."""
        query = (
            select(Document)
            .where(
                Document.normalized_text_sha256 == normalized_hash,
                Document.id != exclude_id,
                Document.processing_status.not_in(["INVALID", "FAILED", "READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING"]),
            )
        )
        if created_before is not None:
            query = query.where(Document.created_at <= created_before)

        query = query.order_by(Document.created_at.asc()).limit(1)
        return db.execute(query).scalar_one_or_none()

    def find_candidates_for_comparison(
        self,
        db: Session,
        target_doc: Document,
        limit: int = 25,
    ) -> List[Document]:
        """
        Query candidate documents for similarity inspection using narrowing filters.
        Avoids comparing against un-evaluated documents and limits search space.
        """
        base_query = (
            select(Document)
            .where(
                Document.id != target_doc.id,
                Document.created_at <= target_doc.created_at,
                Document.processing_status.in_(["READY_FOR_PARSING", "DUPLICATE", "VERSION_REVIEW_REQUIRED"]),
            )
        )

        # If page count is known, narrow to documents within +/- 5 pages or +/- 25%
        if target_doc.page_count and target_doc.page_count > 0:
            min_pages = max(1, target_doc.page_count - 5)
            max_pages = target_doc.page_count + 5
            base_query = base_query.where(
                (Document.page_count >= min_pages) & (Document.page_count <= max_pages)
            )

        # Prefer most recent candidates up to limit
        query = base_query.order_by(Document.created_at.desc()).limit(limit)
        return list(db.execute(query).scalars().all())

    def get_pending_duplicate_checks(
        self,
        db: Session,
        limit: int = 50,
    ) -> List[Document]:
        """Retrieve documents currently queued in READY_FOR_DUPLICATE_CHECK status."""
        query = (
            select(Document)
            .where(Document.processing_status == "READY_FOR_DUPLICATE_CHECK")
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        return list(db.execute(query).scalars().all())
