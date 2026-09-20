from typing import List, Optional
import uuid
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.database.models.normalization_run import NormalizationRun
from app.database.models.scheme_draft import SchemeDraft


class SchemeDraftRepository:
    """Data access repository for SchemeDraft entities."""

    def create(self, db: Session, draft: SchemeDraft) -> SchemeDraft:
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft

    def update(self, db: Session, draft: SchemeDraft) -> SchemeDraft:
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft

    def get_by_id(self, db: Session, draft_id: uuid.UUID) -> Optional[SchemeDraft]:
        return db.get(SchemeDraft, draft_id)

    def get_by_internal_code(self, db: Session, internal_code: str) -> Optional[SchemeDraft]:
        stmt = select(SchemeDraft).where(SchemeDraft.internal_scheme_code == internal_code)
        return db.execute(stmt).scalar_one_or_none()

    def get_all_by_document_id(self, db: Session, document_id: uuid.UUID) -> List[SchemeDraft]:
        stmt = (
            select(SchemeDraft)
            .where(SchemeDraft.document_id == document_id)
            .order_by(SchemeDraft.created_at.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def delete_by_document_id(self, db: Session, document_id: uuid.UUID) -> int:
        stmt = delete(SchemeDraft).where(SchemeDraft.document_id == document_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0

    def delete_by_id(self, db: Session, draft_id: uuid.UUID) -> int:
        stmt = delete(SchemeDraft).where(SchemeDraft.id == draft_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0


class NormalizationRunRepository:
    """Data access repository for NormalizationRun entities."""

    def create(self, db: Session, run: NormalizationRun) -> NormalizationRun:
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def update(self, db: Session, run: NormalizationRun) -> NormalizationRun:
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def get_by_id(self, db: Session, run_id: uuid.UUID) -> Optional[NormalizationRun]:
        return db.get(NormalizationRun, run_id)

    def get_latest_by_document_id(self, db: Session, document_id: uuid.UUID) -> Optional[NormalizationRun]:
        stmt = (
            select(NormalizationRun)
            .where(NormalizationRun.document_id == document_id)
            .order_by(desc(NormalizationRun.created_at))
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_all_by_document_id(self, db: Session, document_id: uuid.UUID) -> List[NormalizationRun]:
        stmt = (
            select(NormalizationRun)
            .where(NormalizationRun.document_id == document_id)
            .order_by(NormalizationRun.created_at.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def delete_by_document_id(self, db: Session, document_id: uuid.UUID) -> int:
        stmt = delete(NormalizationRun).where(NormalizationRun.document_id == document_id)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount or 0
