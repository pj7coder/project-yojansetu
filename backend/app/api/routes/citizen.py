from datetime import date
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.citizen.schemas import CitizenSchemeDetailResponse, RajasthanDistrictItem
from app.citizen.service import CitizenDiscoveryFacade, load_rajasthan_districts
from app.database.session import get_db

logger = logging.getLogger("jansetu.api.citizen")

router = APIRouter(prefix="/citizen", tags=["Citizen Presentation & Exploration"])


@router.get(
    "/districts",
    response_model=List[RajasthanDistrictItem],
    summary="List curated active Rajasthan districts for citizen selection",
)
def get_rajasthan_districts() -> List[RajasthanDistrictItem]:
    """
    Returns verified Rajasthan districts with Hindi and English names
    from the Day 11 curated statutory reference dataset.
    """
    return load_rajasthan_districts()


@router.get(
    "/schemes/{scheme_id}",
    response_model=CitizenSchemeDetailResponse,
    summary="Get citizen-safe details for active verified scheme version",
)
def get_citizen_scheme_detail(
    scheme_id: str,
    evaluation_date: Optional[date] = Query(
        default=None,
        description="Optional date to evaluate active version rules (defaults to today)",
    ),
    db: Session = Depends(get_db),
) -> CitizenSchemeDetailResponse:
    """
    Returns citizen-safe scheme overview, matched eligibility reasons,
    benefits, documents checklist, application guidance, and official source.
    Guarantees superseded, future, or unverified rules are never presented.
    """
    return CitizenDiscoveryFacade.get_citizen_scheme_detail(
        scheme_id=scheme_id,
        db_session=db,
        evaluation_date=evaluation_date,
    )
