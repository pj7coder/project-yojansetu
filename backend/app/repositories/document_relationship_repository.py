import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.document_relationship import DocumentRelationship


class DocumentRelationshipRepository:
    """Repository handling persistence and queries for DocumentRelationship audit entities."""

    def create(self, db: Session, relationship: DocumentRelationship) -> DocumentRelationship:
        """Persist a new document relationship record."""
        db.add(relationship)
        db.commit()
        db.refresh(relationship)
        return relationship

    def get_by_document_id(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> List[DocumentRelationship]:
        """Retrieve all relationships where document is source or target."""
        query = (
            select(DocumentRelationship)
            .where(DocumentRelationship.document_id == document_id)
            .order_by(DocumentRelationship.created_at.desc())
        )
        return list(db.execute(query).scalars().all())

    def get_primary_relationship(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> Optional[DocumentRelationship]:
        """Retrieve the primary (most recent) relationship for a document."""
        query = (
            select(DocumentRelationship)
            .where(DocumentRelationship.document_id == document_id)
            .order_by(DocumentRelationship.created_at.desc())
            .limit(1)
        )
        return db.execute(query).scalar_one_or_none()
