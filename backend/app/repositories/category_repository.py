import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.category import Category
from app.schemas.category import CategoryCreate


class CategoryRepository:
    """Repository handling database operations for Category entity."""

    def get_by_id(self, db: Session, category_id: uuid.UUID) -> Optional[Category]:
        """Fetch category by UUID primary key."""
        return db.get(Category, category_id)

    def get_by_code(self, db: Session, code: str) -> Optional[Category]:
        """Fetch category by unique code."""
        query = select(Category).where(Category.code == code.strip().lower())
        return db.execute(query).scalar_one_or_none()

    def list(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> List[Category]:
        """List categories with optional active filtering."""
        query = select(Category).order_by(Category.code)
        if active_only:
            query = query.where(Category.active == True)  # noqa: E712
        return list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    def create(self, db: Session, category_in: CategoryCreate) -> Category:
        """Persist a new category."""
        category = Category(
            code=category_in.code.strip().lower(),
            name_en=category_in.name_en.strip(),
            name_hi=category_in.name_hi.strip() if category_in.name_hi else None,
            description=category_in.description,
            active=category_in.active,
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        return category
