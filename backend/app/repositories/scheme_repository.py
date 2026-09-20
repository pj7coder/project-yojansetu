import math
import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models.scheme import Scheme, SchemeVersion
from app.schemas.scheme import SchemeCreate, SchemeUpdate


class SchemeRepository:
    """Repository handling persistence and queries for Scheme and SchemeVersion entities."""

    def get_by_id(self, db: Session, scheme_id: uuid.UUID) -> Optional[Scheme]:
        """Retrieve a scheme by UUID including its version records."""
        query = (
            select(Scheme)
            .where(Scheme.id == scheme_id)
            .options(selectinload(Scheme.versions))
        )
        return db.execute(query).scalar_one_or_none()

    def get_by_code(self, db: Session, scheme_code: str) -> Optional[Scheme]:
        """Retrieve a scheme by its unique alphanumeric scheme_code."""
        query = (
            select(Scheme)
            .where(Scheme.scheme_code == scheme_code.strip().upper())
            .options(selectinload(Scheme.versions))
        )
        return db.execute(query).scalar_one_or_none()

    def list(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        department_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        scheme_origin: Optional[str] = None,
    ) -> Tuple[List[Scheme], int]:
        """
        Query paginated schemes with optional status and category filters.
        Returns a tuple of (items, total_count).
        """
        base_query = select(Scheme)

        # Apply optional filters
        if status:
            base_query = base_query.where(Scheme.status == status.strip().upper())
        if department_id:
            base_query = base_query.where(Scheme.department_id == department_id)
        if category_id:
            base_query = base_query.where(Scheme.category_id == category_id)
        if scheme_origin:
            base_query = base_query.where(Scheme.scheme_origin == scheme_origin.strip().upper())

        # Count total matching records
        count_query = select(func.count()).select_from(base_query.subquery())
        total = db.execute(count_query).scalar_one()

        # Apply ordering, eager loading, and pagination
        offset = (page - 1) * page_size
        items_query = (
            base_query.order_by(Scheme.created_at.desc())
            .options(selectinload(Scheme.versions))
            .offset(offset)
            .limit(page_size)
        )
        items = list(db.execute(items_query).scalars().all())

        return items, total

    def create(self, db: Session, scheme_in: SchemeCreate) -> Scheme:
        """
        Persist a new canonical Scheme alongside its initial Version 1 record.
        Enforces scheme identity and version coupling within a single transaction.
        """
        scheme = Scheme(
            scheme_code=scheme_in.scheme_code.strip().upper(),
            name_en=scheme_in.name_en.strip(),
            name_hi=scheme_in.name_hi.strip() if scheme_in.name_hi else None,
            short_name=scheme_in.short_name.strip() if scheme_in.short_name else None,
            department_id=scheme_in.department_id,
            category_id=scheme_in.category_id,
            short_description=scheme_in.short_description,
            status=scheme_in.status.strip().upper(),
            jurisdiction=scheme_in.jurisdiction.strip().upper(),
            scheme_origin=scheme_in.scheme_origin.strip().upper(),
        )
        db.add(scheme)
        db.flush()  # Obtain scheme.id for the version FK

        # Create initial Version 1
        initial_version = SchemeVersion(
            scheme_id=scheme.id,
            version_number=1,
            source_summary=scheme_in.initial_source_summary or "Initial scheme record creation",
            change_summary="Version 1 baseline",
            is_current=True,
        )
        db.add(initial_version)

        db.commit()
        db.refresh(scheme)
        return scheme

    def update(
        self, db: Session, db_scheme: Scheme, update_in: SchemeUpdate
    ) -> Scheme:
        """Update mutable metadata on a scheme record."""
        update_data = update_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in ["status", "jurisdiction", "scheme_origin"] and isinstance(value, str):
                value = value.strip().upper()
            setattr(db_scheme, field, value)

        db.commit()
        db.refresh(db_scheme)
        return db_scheme
