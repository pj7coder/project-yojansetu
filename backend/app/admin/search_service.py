import logging
from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.admin.schemas import AdminGlobalSearchResponse, AdminSearchHit
from app.database.models.document import Document
from app.database.models.scheme import Scheme
from app.database.models.source import Source

logger = logging.getLogger("yojansetu.admin.search")


class AdminGlobalSearchService:
    """Operations search service performing safe indexed text lookups across admin entities."""

    def search(self, db: Session, query: str, limit_per_type: int = 10) -> AdminGlobalSearchResponse:
        q = (query or "").strip()
        if not q:
            return AdminGlobalSearchResponse(query="", schemes=[], documents=[], sources=[], total_hits=0)

        pattern = f"%{q}%"

        # 1. Schemes
        scheme_hits: List[AdminSearchHit] = []
        scheme_stmt = (
            select(Scheme)
            .where(
                or_(
                    Scheme.scheme_code.ilike(pattern),
                    Scheme.name_en.ilike(pattern),
                    Scheme.name_hi.ilike(pattern),
                )
            )
            .limit(limit_per_type)
        )
        schemes = db.execute(scheme_stmt).scalars().all()
        for s in schemes:
            scheme_hits.append(
                AdminSearchHit(
                    id=str(s.id),
                    entity_type="SCHEME",
                    title=s.name_hi or s.name_en,
                    subtitle=s.name_en if s.name_hi else None,
                    code=s.scheme_code,
                    status=s.status,
                    link=f"/admin/schemes",
                )
            )

        # 2. Documents
        doc_hits: List[AdminSearchHit] = []
        doc_stmt = (
            select(Document)
            .where(
                or_(
                    Document.document_code.ilike(pattern),
                    Document.original_filename.ilike(pattern),
                    Document.title.ilike(pattern),
                )
            )
            .limit(limit_per_type)
        )
        docs = db.execute(doc_stmt).scalars().all()
        for d in docs:
            doc_hits.append(
                AdminSearchHit(
                    id=str(d.id),
                    entity_type="DOCUMENT",
                    title=d.title or d.original_filename,
                    subtitle=d.original_filename if d.title else None,
                    code=d.document_code,
                    status=d.processing_status,
                    link=f"/admin/documents?code={d.document_code}",
                )
            )

        # 3. Sources
        source_hits: List[AdminSearchHit] = []
        source_stmt = (
            select(Source)
            .where(
                or_(
                    Source.name.ilike(pattern),
                    Source.base_url.ilike(pattern),
                )
            )
            .limit(limit_per_type)
        )
        sources = db.execute(source_stmt).scalars().all()
        for src in sources:
            source_hits.append(
                AdminSearchHit(
                    id=str(src.id),
                    entity_type="SOURCE",
                    title=src.name,
                    subtitle=src.base_url,
                    code=src.source_type,
                    status="ACTIVE" if src.enabled else "INACTIVE",
                    link=f"/admin/sources",
                )
            )

        total = len(scheme_hits) + len(doc_hits) + len(source_hits)

        return AdminGlobalSearchResponse(
            query=q,
            schemes=scheme_hits,
            documents=doc_hits,
            sources=source_hits,
            total_hits=total,
        )
