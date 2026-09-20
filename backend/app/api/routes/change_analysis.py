import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crawler.resource_fetcher import DiscoveredResourceFetcher
from app.crawler.schemas import (
    DiscoveredResourceResponse,
    PaginatedChangeAnalysesResponse,
    PaginatedDiscoveredResourcesResponse,
    ResourceRelevanceUpdateRequest,
    SourceChangeAnalysisResponse,
)
from app.database.models.discovered_resource import DiscoveredResource
from app.database.models.source_url import SourceUrl
from app.database.session import get_db
from app.repositories.change_analysis_repository import ChangeAnalysisRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["change-analysis"])


def get_repository() -> ChangeAnalysisRepository:
    return ChangeAnalysisRepository()


def get_fetcher() -> DiscoveredResourceFetcher:
    return DiscoveredResourceFetcher()


@router.get(
    "/change-analyses",
    response_model=PaginatedChangeAnalysesResponse,
    summary="List change analyses with optional status filtering",
)
def list_change_analyses(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    repo: ChangeAnalysisRepository = Depends(get_repository),
):
    items, total = repo.list_analyses(db, limit=limit, offset=offset, status=status)
    return PaginatedChangeAnalysesResponse(
        items=[SourceChangeAnalysisResponse.model_validate(x) for x in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/change-analyses/{analysis_id}",
    response_model=SourceChangeAnalysisResponse,
    summary="Get single change analysis record by ID",
)
def get_change_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    repo: ChangeAnalysisRepository = Depends(get_repository),
):
    record = repo.get_analysis_by_id(db, analysis_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change analysis {analysis_id} not found",
        )
    return SourceChangeAnalysisResponse.model_validate(record)


@router.get(
    "/discovered-resources",
    response_model=PaginatedDiscoveredResourcesResponse,
    summary="List discovered candidate resources with multi-field filtering",
)
def list_discovered_resources(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    relevance_status: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    fetch_status: Optional[str] = Query(None),
    change_event_id: Optional[uuid.UUID] = Query(None),
    source_url_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    repo: ChangeAnalysisRepository = Depends(get_repository),
):
    items, total = repo.list_discovered_resources(
        db,
        limit=limit,
        offset=offset,
        relevance_status=relevance_status,
        resource_type=resource_type,
        fetch_status=fetch_status,
        change_event_id=change_event_id,
        source_url_id=source_url_id,
    )
    return PaginatedDiscoveredResourcesResponse(
        items=[DiscoveredResourceResponse.model_validate(x) for x in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/discovered-resources/{resource_id}/relevance",
    response_model=DiscoveredResourceResponse,
    summary="Manually resolve or override discovered resource relevance",
)
def update_resource_relevance(
    resource_id: uuid.UUID,
    body: ResourceRelevanceUpdateRequest,
    db: Session = Depends(get_db),
    repo: ChangeAnalysisRepository = Depends(get_repository),
):
    updated = repo.update_resource_relevance(
        db,
        resource_id=resource_id,
        new_status=body.relevance_status,
        reason_text=body.reason,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovered resource {resource_id} not found",
        )
    return DiscoveredResourceResponse.model_validate(updated)


@router.post(
    "/discovered-resources/{resource_id}/fetch",
    response_model=DiscoveredResourceResponse,
    summary="Manually trigger download and ingestion of an approved discovered resource",
)
def fetch_discovered_resource(
    resource_id: uuid.UUID,
    db: Session = Depends(get_db),
    repo: ChangeAnalysisRepository = Depends(get_repository),
    fetcher: DiscoveredResourceFetcher = Depends(get_fetcher),
):
    res = repo.get_resource_by_id(db, resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovered resource {resource_id} not found",
        )

    source_url = db.get(SourceUrl, res.source_url_id)
    base_url = source_url.url if source_url else res.normalized_url
    source_id = source_url.source_id if source_url else None

    success, err = fetcher.fetch_and_ingest_candidate(
        db=db,
        candidate_record=res,
        source_base_url=base_url,
        source_id=source_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch resource: {err}",
        )

    db.refresh(res)
    return DiscoveredResourceResponse.model_validate(res)
