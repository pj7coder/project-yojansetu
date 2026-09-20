import logging
import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.document_relationship import DocumentRelationship
from app.database.models.scheme import SchemeVersion
from app.database.models.scheme_change_item import SchemeChangeItem
from app.database.models.scheme_change_set import SchemeChangeSet
from app.database.models.scheme_document_link import SchemeDocumentLink

logger = logging.getLogger("yojansetu.versioning.repository")


class VersioningRepository:
    """
    Data access layer for SchemeVersions, SchemeChangeSets, SchemeChangeItems,
    and SchemeDocumentLinks.
    """

    def get_version(self, db: Session, version_id: uuid.UUID) -> Optional[SchemeVersion]:
        return db.get(SchemeVersion, version_id)

    def list_versions_for_scheme(
        self,
        db: Session,
        scheme_id: uuid.UUID,
    ) -> List[SchemeVersion]:
        stmt = (
            select(SchemeVersion)
            .where(SchemeVersion.scheme_id == scheme_id)
            .order_by(desc(SchemeVersion.version_number))
        )
        return list(db.execute(stmt).scalars().all())

    def get_change_set(
        self,
        db: Session,
        change_set_id: uuid.UUID,
    ) -> Optional[SchemeChangeSet]:
        stmt = (
            select(SchemeChangeSet)
            .options(
                joinedload(SchemeChangeSet.items),
                joinedload(SchemeChangeSet.scheme),
                joinedload(SchemeChangeSet.base_version),
                joinedload(SchemeChangeSet.source_document),
            )
            .where(SchemeChangeSet.id == change_set_id)
        )
        return db.execute(stmt).scalars().first()

    def get_change_set_by_hash(
        self,
        db: Session,
        change_set_hash: str,
    ) -> Optional[SchemeChangeSet]:
        stmt = select(SchemeChangeSet).where(SchemeChangeSet.change_set_hash == change_set_hash)
        return db.execute(stmt).scalars().first()

    def list_change_sets(
        self,
        db: Session,
        status: Optional[str] = None,
        scheme_id: Optional[uuid.UUID] = None,
        critical_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> List[SchemeChangeSet]:
        stmt = (
            select(SchemeChangeSet)
            .options(joinedload(SchemeChangeSet.items))
            .order_by(desc(SchemeChangeSet.created_at))
        )
        if status:
            stmt = stmt.where(SchemeChangeSet.status == status)
        if scheme_id:
            stmt = stmt.where(SchemeChangeSet.scheme_id == scheme_id)
        if critical_only:
            stmt = stmt.where(SchemeChangeSet.critical_changes_count > 0)

        stmt = stmt.offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().unique().all())

    def link_document_to_scheme(
        self,
        db: Session,
        scheme_id: uuid.UUID,
        document_id: uuid.UUID,
        link_type: str,
        status: str = "AUTO_LINKED",
    ) -> SchemeDocumentLink:
        # Check if already linked
        stmt = select(SchemeDocumentLink).where(
            SchemeDocumentLink.scheme_id == scheme_id,
            SchemeDocumentLink.document_id == document_id,
            SchemeDocumentLink.link_type == link_type,
        )
        existing = db.execute(stmt).scalars().first()
        if existing:
            return existing

        link = SchemeDocumentLink(
            id=uuid.uuid4(),
            scheme_id=scheme_id,
            document_id=document_id,
            link_type=link_type,
            status=status,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    def list_links_for_scheme(
        self,
        db: Session,
        scheme_id: uuid.UUID,
    ) -> List[SchemeDocumentLink]:
        stmt = (
            select(SchemeDocumentLink)
            .where(SchemeDocumentLink.scheme_id == scheme_id)
            .order_by(desc(SchemeDocumentLink.created_at))
        )
        return list(db.execute(stmt).scalars().all())
