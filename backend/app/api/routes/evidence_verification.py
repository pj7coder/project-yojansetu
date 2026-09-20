import logging
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.evidence_verification_repository import (
    EvidenceVerificationRepository,
)
from app.verification.schemas import (
    EvidenceVerificationReportDTO,
    EvidenceVerificationRunResponse,
    FactVerificationResponse,
)
from app.verification.service import EvidenceVerificationService

logger = logging.getLogger("jansetu.api.evidence_verification")

router = APIRouter()


@router.post(
    "/scheme-drafts/{draft_id}/verify-evidence",
    response_model=EvidenceVerificationReportDTO,
    summary="Execute second-pass evidence verification on a scheme draft",
    status_code=status.HTTP_200_OK,
)
def verify_scheme_draft_evidence(
    draft_id: uuid.UUID,
    force: bool = Query(
        default=False, description="Force re-verification regardless of cache"
    ),
    db: Session = Depends(get_db),
):
    service = EvidenceVerificationService(db)
    try:
        report = service.verify_scheme_draft(draft_id, force=force)
        return report
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except FileNotFoundError as fe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fe))
    except Exception as ex:
        logger.error(
            f"Error verifying evidence for scheme draft {draft_id}: {ex}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence verification failed: {str(ex)}",
        )


@router.get(
    "/scheme-drafts/{draft_id}/evidence-verification",
    response_model=EvidenceVerificationRunResponse,
    summary="Get latest evidence verification run for a scheme draft",
)
def get_latest_evidence_verification_run(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = EvidenceVerificationRepository()
    run = repo.get_latest_run_by_draft_id(db, draft_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evidence verification runs found for scheme draft {draft_id}",
        )
    return run


@router.get(
    "/scheme-drafts/{draft_id}/fact-verifications",
    response_model=List[FactVerificationResponse],
    summary="Get fact verifications for a scheme draft with optional filtering",
)
def get_fact_verifications(
    draft_id: uuid.UUID,
    result: Optional[str] = Query(
        default=None,
        description="Filter by result: SUPPORTED, CONTRADICTED, NOT_ENOUGH_EVIDENCE",
    ),
    fact_type: Optional[str] = Query(
        default=None,
        description="Filter by fact type: ELIGIBILITY, EXCLUSION, BENEFIT, DOCUMENT, APPLICATION, DATE, DEFINITION, LOGICAL_CONNECTOR",
    ),
    risk_level: Optional[str] = Query(
        default=None,
        description="Filter by risk level: CRITICAL, HIGH, NORMAL, LOW",
    ),
    verification_method: Optional[str] = Query(
        default=None,
        description="Filter by verification method: DETERMINISTIC, LLM, COMBINED",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    repo = EvidenceVerificationRepository()
    facts = repo.get_facts_by_draft(
        db,
        draft_id=draft_id,
        result=result,
        fact_type=fact_type,
        risk_level=risk_level,
        verification_method=verification_method,
        limit=limit,
        offset=offset,
    )
    return facts


@router.get(
    "/fact-verifications/{fact_id}",
    response_model=FactVerificationResponse,
    summary="Get single fact verification by ID",
)
def get_fact_verification_by_id(
    fact_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = EvidenceVerificationRepository()
    record = repo.get_fact_by_id(db, fact_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fact verification with ID {fact_id} not found",
        )
    return record


@router.get(
    "/evidence-verification-runs/{run_id}",
    response_model=EvidenceVerificationRunResponse,
    summary="Get evidence verification run by ID",
)
def get_evidence_verification_run_by_id(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = EvidenceVerificationRepository()
    run = repo.get_run_by_id(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence verification run with ID {run_id} not found",
        )
    return run
