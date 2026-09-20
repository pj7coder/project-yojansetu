from datetime import date
import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.eligibility.profile import CitizenProfile
from app.eligibility.repository import SchemeNotFoundError, UnverifiedSchemeAccessError
from app.eligibility.service import EligibilityService
from app.schemas.eligibility import (
    EligibilityEvaluationRequest,
    EligibilityEvaluationResponse,
    MultiSchemeEvaluationRequest,
)

logger = logging.getLogger("yojansetu.api.eligibility")

router = APIRouter(prefix="/eligibility", tags=["Deterministic Eligibility Engine"])


@router.post(
    "/evaluate/{scheme_id}",
    response_model=EligibilityEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate citizen profile against a verified government scheme",
    description="Evaluates citizen profile criteria against a human-verified scheme rule tree using pure deterministic logic.",
)
def evaluate_single_scheme(
    scheme_id: str,
    request: EligibilityEvaluationRequest,
    session: Session = Depends(get_db),
) -> EligibilityEvaluationResponse:
    # 1. Validate citizen profile data strictly
    try:
        CitizenProfile(**request.profile)
    except (ValidationError, ValueError) as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid citizen profile data: {ve}",
        )

    # 2. Evaluate scheme
    try:
        result = EligibilityService.evaluate_single_scheme(
            session=session,
            scheme_id=scheme_id,
            profile_data=request.profile,
            evaluation_date=request.evaluation_date,
        )
        return EligibilityEvaluationResponse(**result.model_dump())
    except UnverifiedSchemeAccessError as ue:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ue),
        )
    except SchemeNotFoundError as se:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(se),
        )
    except Exception as e:
        logger.error(f"Unexpected error during eligibility evaluation for '{scheme_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal engine evaluation error: {e}",
        )


@router.post(
    "/evaluate",
    response_model=List[EligibilityEvaluationResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate citizen profile against multiple verified schemes",
    description="Evaluates a single citizen profile against multiple specified verified government schemes.",
)
def evaluate_multiple_schemes(
    request: MultiSchemeEvaluationRequest,
    session: Session = Depends(get_db),
) -> List[EligibilityEvaluationResponse]:
    try:
        CitizenProfile(**request.profile)
    except (ValidationError, ValueError) as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid citizen profile data: {ve}",
        )

    try:
        results = EligibilityService.evaluate_multiple_schemes(
            session=session,
            scheme_ids=request.scheme_ids,
            profile_data=request.profile,
            evaluation_date=request.evaluation_date,
        )
        return [EligibilityEvaluationResponse(**r.model_dump()) for r in results]
    except Exception as e:
        logger.error(f"Unexpected error during multi-scheme evaluation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal engine evaluation error: {e}",
        )
