import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models.department import Department
from app.repositories.department_repository import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentService:
    """Business logic and validation service for Department entities."""

    def __init__(self, repo: Optional[DepartmentRepository] = None):
        self.repo = repo or DepartmentRepository()

    def get_department(self, db: Session, department_id: uuid.UUID) -> Department:
        """Fetch department or raise 404."""
        dept = self.repo.get_by_id(db, department_id)
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id '{department_id}' not found",
            )
        return dept

    def list_departments(
        self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = False
    ) -> List[Department]:
        """List departments."""
        return self.repo.list(db, skip=skip, limit=limit, active_only=active_only)

    def create_department(self, db: Session, department_in: DepartmentCreate) -> Department:
        """Create department after ensuring code uniqueness."""
        existing = self.repo.get_by_code(db, department_in.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department with code '{department_in.code.upper()}' already exists",
            )
        return self.repo.create(db, department_in)
