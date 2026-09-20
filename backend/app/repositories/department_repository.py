import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentRepository:
    """Repository handling database operations for Department entity."""

    def get_by_id(self, db: Session, department_id: uuid.UUID) -> Optional[Department]:
        """Fetch department by UUID primary key."""
        return db.get(Department, department_id)

    def get_by_code(self, db: Session, code: str) -> Optional[Department]:
        """Fetch department by unique code."""
        query = select(Department).where(Department.code == code.strip().upper())
        return db.execute(query).scalar_one_or_none()

    def list(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> List[Department]:
        """List departments with optional active filtering."""
        query = select(Department).order_by(Department.code)
        if active_only:
            query = query.where(Department.active == True)  # noqa: E712
        return list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    def get_all(self, db: Session) -> List[Department]:
        """Fetch all departments."""
        return list(db.execute(select(Department).order_by(Department.name_en)).scalars().all())

    def create(self, db: Session, department_in: DepartmentCreate) -> Department:
        """Persist a new department."""
        dept = Department(
            code=department_in.code.strip().upper(),
            name_en=department_in.name_en.strip(),
            name_hi=department_in.name_hi.strip() if department_in.name_hi else None,
            description=department_in.description,
            official_website=department_in.official_website,
            active=department_in.active,
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)
        return dept

    def update(
        self, db: Session, db_dept: Department, update_in: DepartmentUpdate
    ) -> Department:
        """Update existing department fields."""
        update_data = update_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_dept, field, value)
        db.commit()
        db.refresh(db_dept)
        return db_dept
