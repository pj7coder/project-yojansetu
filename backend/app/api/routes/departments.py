from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.department import DepartmentCreate, DepartmentListResponse, DepartmentResponse
from app.services.department_service import DepartmentService

router = APIRouter()
dept_service = DepartmentService()


@router.get(
    "",
    response_model=DepartmentListResponse,
    summary="List Departments",
    description="Retrieve all registered departments.",
)
def list_departments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DepartmentListResponse:
    """List departments."""
    items = dept_service.list_departments(db, skip=skip, limit=limit, active_only=active_only)
    return DepartmentListResponse(
        items=[DepartmentResponse.model_validate(d) for d in items],
        total=len(items),
    )


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Department",
    description="Register a new government department.",
)
def create_department(
    department_in: DepartmentCreate,
    db: Session = Depends(get_db),
) -> DepartmentResponse:
    """Create a new department."""
    dept = dept_service.create_department(db, department_in)
    return DepartmentResponse.model_validate(dept)
