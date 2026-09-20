import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database.models.ocr_run import OCRRun


class OCRRunRepository:
    """Data access repository for OCRRun entities."""

    def create(self, db: Session, ocr_run: OCRRun) -> OCRRun:
        db.add(ocr_run)
        db.commit()
        db.refresh(ocr_run)
        return ocr_run

    def get_by_id(self, db: Session, ocr_run_id: uuid.UUID) -> Optional[OCRRun]:
        return db.get(OCRRun, ocr_run_id)

    def get_latest_by_document_id(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> Optional[OCRRun]:
        """Fetch the most recent OCR run record for a document."""
        stmt = (
            select(OCRRun)
            .where(OCRRun.document_id == document_id)
            .order_by(desc(OCRRun.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_all_by_document_id(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> List[OCRRun]:
        """Fetch all OCR execution history for a document."""
        stmt = (
            select(OCRRun)
            .where(OCRRun.document_id == document_id)
            .order_by(desc(OCRRun.created_at))
        )
        return list(db.execute(stmt).scalars().all())

    def update(self, db: Session, ocr_run: OCRRun) -> OCRRun:
        db.add(ocr_run)
        db.commit()
        db.refresh(ocr_run)
        return ocr_run

    def delete(self, db: Session, ocr_run: OCRRun) -> None:
        db.delete(ocr_run)
        db.commit()
