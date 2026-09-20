import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.scheme import (
    SchemeCreate,
    SchemeDetailResponse,
    SchemeFullUpdate,
    SchemeListResponse,
    SchemeResponse,
    SchemeUpdate,
)
from app.services.scheme_service import SchemeService

router = APIRouter()
scheme_service = SchemeService()


@router.post(
    "",
    response_model=SchemeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Scheme",
    description="Create a new draft government scheme record and its initial version.",
)
def create_scheme(
    scheme_in: SchemeCreate,
    db: Session = Depends(get_db),
) -> SchemeResponse:
    """Create a new canonical scheme with initial version."""
    scheme = scheme_service.create_scheme(db, scheme_in)
    return SchemeResponse.model_validate(scheme)


@router.get(
    "",
    response_model=SchemeListResponse,
    summary="List Schemes",
    description="Retrieve a paginated list of schemes with optional status, department, and category filtering.",
)
def list_schemes(
    page: int = Query(default=1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(default=None, description="Filter by status, e.g. DRAFT, ACTIVE, PRODUCTION"),
    department_id: Optional[uuid.UUID] = Query(default=None, description="Filter by department UUID"),
    category_id: Optional[uuid.UUID] = Query(default=None, description="Filter by category UUID"),
    scheme_origin: Optional[str] = Query(default=None, description="Filter by scheme origin"),
    db: Session = Depends(get_db),
) -> SchemeListResponse:
    """List schemes with pagination and filters."""
    return scheme_service.list_schemes(
        db,
        page=page,
        page_size=page_size,
        status_filter=status,
        department_id=department_id,
        category_id=category_id,
        scheme_origin=scheme_origin,
    )


@router.get(
    "/{scheme_id}",
    response_model=SchemeDetailResponse,
    summary="Get Scheme Detail",
    description="Retrieve full scheme details, including active version canonical rule tree, benefits, eligibility, and PDF extraction.",
)
def get_scheme(
    scheme_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SchemeDetailResponse:
    """Fetch complete scheme detail by UUID."""
    return scheme_service.get_scheme_detail(db, scheme_id)


@router.put(
    "/{scheme_id}",
    response_model=SchemeDetailResponse,
    summary="Update Scheme (Full)",
    description="Update scheme metadata, identity, eligibility rules, benefits, application process, and documents.",
)
def update_scheme_full(
    scheme_id: uuid.UUID,
    update_in: SchemeFullUpdate,
    db: Session = Depends(get_db),
) -> SchemeDetailResponse:
    """Update all fields and canonical rules of an existing scheme."""
    return scheme_service.update_scheme_full(db, scheme_id, update_in)


@router.patch(
    "/{scheme_id}",
    response_model=SchemeDetailResponse,
    summary="Partial Update Scheme",
    description="Partially update scheme metadata and canonical extracted rules.",
)
def update_scheme_partial(
    scheme_id: uuid.UUID,
    update_in: SchemeFullUpdate,
    db: Session = Depends(get_db),
) -> SchemeDetailResponse:
    """Partially update an existing scheme."""
    return scheme_service.update_scheme_full(db, scheme_id, update_in)


@router.delete(
    "/{scheme_id}",
    summary="Delete Scheme",
    description="Delete a scheme record and associated versions.",
)
def delete_scheme(
    scheme_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Delete scheme by UUID."""
    scheme_service.delete_scheme(db, scheme_id)
    return {"status": "success", "message": f"Scheme {scheme_id} deleted successfully"}

