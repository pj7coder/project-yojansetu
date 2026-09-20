from typing import List, Optional
import uuid
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.database.models.extraction_run import ExtractionRun


class ExtractionRunRepository:
    """Data access repository for ExtractionRun entities."""

    def create(self, db: Session, run: ExtractionRun) -> ExtractionRun:
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def update(self, db: Session, run: ExtractionRun) -> ExtractionRun:
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def get_by_id(self, db: Session, run_id: uuid.UUID) -> Optional[ExtractionRun]:
        return db.get(ExtractionRun, run_id)

    def get_by_chunk_id(self, db: Session, chunk_id: uuid.UUID) -> Optional[ExtractionRun]:
        stmt = (
            select(ExtractionRun)
            .where(ExtractionRun.chunk_id == chunk_id)
            .order_by(desc(ExtractionRun.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_by_chunk_id_str(self, db: Session, chunk_id_str: str) -> Optional[ExtractionRun]:
        stmt = (
            select(ExtractionRun)
            .where(ExtractionRun.chunk_id_str == chunk_id_str)
            .order_by(desc(ExtractionRun.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_all_by_document_id(self, db: Session, document_id: uuid.UUID) -> List[ExtractionRun]:
        stmt = (
            select(ExtractionRun)
            .where(ExtractionRun.document_id == document_id)
            .order_by(ExtractionRun.created_at.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def delete_by_chunk_id(self, db: Session, chunk_id: uuid.UUID) -> int:
        stmt = delete(ExtractionRun).where(ExtractionRun.chunk_id == chunk_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0

    def delete_by_document_id(self, db: Session, document_id: uuid.UUID) -> int:
        stmt = delete(ExtractionRun).where(ExtractionRun.document_id == document_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
