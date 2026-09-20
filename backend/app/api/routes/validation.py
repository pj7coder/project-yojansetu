import logging
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.validation_repository import ValidationRepository
from app.validation.schemas import (
    ValidationIssueResponse,
    ValidationReportDTO,
    ValidationRunResponse,
)
from app.validation.service import SchemeValidationService

logger = logging.getLogger("jansetu.api.validation")

router = APIRouter()


@router.post(
    "/scheme-drafts/{draft_id}/validate",
    response_model=ValidationReportDTO,
    summary="Execute deterministic validation on a scheme draft",
    status_code=status.HTTP_200_OK,
)
def validate_scheme_draft(
    draft_id: uuid.UUID,
    force: bool = Query(default=False, description="Force re-validation regardless of cache"),
    db: Session = Depends(get_db),
):
    service = SchemeValidationService(db)
    try:
        report = service.validate_draft(draft_id, force=force)
        return report
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as ex:
        logger.error(f"Error validating scheme draft {draft_id}: {ex}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(ex)}",
        )


@router.get(
    "/scheme-drafts/{draft_id}/validation",
    response_model=ValidationRunResponse,
    summary="Get latest validation run for a scheme draft",
)
def get_latest_validation_run(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = ValidationRepository()
    run = repo.get_latest_run_by_draft_id(db, draft_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No validation runs found for scheme draft {draft_id}",
        )
    return run


@router.get(
    "/scheme-drafts/{draft_id}/validation/issues",
    response_model=List[ValidationIssueResponse],
    summary="Get validation issues for a scheme draft with optional filtering",
)
def get_validation_issues(
    draft_id: uuid.UUID,
    severity: Optional[str] = Query(default=None, description="Filter by severity: INFO, WARNING, ERROR, BLOCKER"),
    rule_code: Optional[str] = Query(default=None, description="Filter by rule code, e.g. AGE_RANGE_INVALID"),
    status: Optional[str] = Query(default=None, description="Filter by status: OPEN, ACKNOWLEDGED, RESOLVED"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    repo = ValidationRepository()
    issues = repo.get_issues_by_draft(
        db,
        draft_id=draft_id,
        severity=severity,
        rule_code=rule_code,
        status=status,
        limit=limit,
        offset=offset,
    )
    return issues


@router.get(
    "/validation-runs/{run_id}",
    response_model=ValidationRunResponse,
    summary="Get a validation run by its ID",
)
def get_validation_run_by_id(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = ValidationRepository()
    run = repo.get_run_by_id(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation run with ID {run_id} not found",
        )
    return run
