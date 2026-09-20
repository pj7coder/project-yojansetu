import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.eligibility.profile import CitizenProfile
from app.search.discovery_service import SchemeDiscoveryService
from app.search.indexer import SchemeSearchIndexService
from app.search.schemas import (
    SchemeDiscoveryRequest,
    SchemeDiscoveryResponse,
    SearchIndexStatusResponse,
)

logger = logging.getLogger("yojansetu.api.discovery")

router = APIRouter(tags=["Scheme Discovery & Semantic Ranking"])


@router.post(
    "/schemes/discover",
    response_model=SchemeDiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover relevant verified government schemes for a citizen",
    description=(
        "Combines safe high-recall SQL candidate filtering, authoritative deterministic "
        "eligibility evaluation, and multilingual dense vector ranking to recommend schemes."
    ),
)
def discover_schemes(
    request: SchemeDiscoveryRequest,
    session: Session = Depends(get_db),
) -> SchemeDiscoveryResponse:
    # 1. Strict validation of citizen profile input
    try:
        CitizenProfile(**request.profile)
    except (ValidationError, ValueError) as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid citizen profile criteria: {ve}",
        )

    # 2. Execute scheme discovery pipeline
    try:
        return SchemeDiscoveryService.discover_schemes(
            session=session,
            request=request,
        )
    except Exception as e:
        logger.error(f"Scheme discovery execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scheme discovery error: {e}",
        )


@router.get(
    "/admin/search-index/status",
    response_model=SearchIndexStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get search metadata and embedding index diagnostics",
)
def get_search_index_status(
    session: Session = Depends(get_db),
) -> SearchIndexStatusResponse:
    try:
        status_dict = SchemeSearchIndexService.get_index_status(session)
        return SearchIndexStatusResponse(**status_dict)
    except Exception as e:
        logger.error(f"Error fetching search index status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving index status: {e}",
        )


@router.post(
    "/admin/search-index/rebuild",
    status_code=status.HTTP_200_OK,
    summary="Trigger rebuild of verified scheme search metadata and embeddings",
)
def rebuild_search_index(
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        result = SchemeSearchIndexService.rebuild_index(session)
        return {
            "status": "COMPLETED",
            "indexed_count": result.get("indexed_count", 0),
        }
    except Exception as e:
        logger.error(f"Error rebuilding search index: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rebuilding index: {e}",
        )
