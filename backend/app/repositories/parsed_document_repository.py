import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.models.parsed_document import ParsedDocument


class ParsedDocumentRepository:
    """Data access repository for ParsedDocument entities."""

    def create(self, db: Session, parsed_doc: ParsedDocument) -> ParsedDocument:
        db.add(parsed_doc)
        db.commit()
        db.refresh(parsed_doc)
        return parsed_doc

    def get_by_id(self, db: Session, parsed_doc_id: uuid.UUID) -> Optional[ParsedDocument]:
        return db.get(ParsedDocument, parsed_doc_id)

    def get_latest_by_document_id(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> Optional[ParsedDocument]:
        """Fetch the most recent parsed record for a document."""
        stmt = (
            select(ParsedDocument)
            .where(ParsedDocument.document_id == document_id)
            .order_by(desc(ParsedDocument.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_all_by_document_id(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> List[ParsedDocument]:
        """Fetch all parsing execution history for a document."""
        stmt = (
            select(ParsedDocument)
            .where(ParsedDocument.document_id == document_id)
            .order_by(desc(ParsedDocument.created_at))
        )
        return list(db.execute(stmt).scalars().all())

    def update(self, db: Session, parsed_doc: ParsedDocument) -> ParsedDocument:
        db.add(parsed_doc)
        db.commit()
        db.refresh(parsed_doc)
        return parsed_doc

    def delete(self, db: Session, parsed_doc: ParsedDocument) -> None:
        db.delete(parsed_doc)
        db.commit()
