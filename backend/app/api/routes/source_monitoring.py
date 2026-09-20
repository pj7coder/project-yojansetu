import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.monitoring.schemas import (
    ManualCheckResponse,
    SourceChangeEventResponse,
    SourceHealthSummaryResponse,
    SourceMonitorRunResponse,
    SourceMonitorStateResponse,
)
from app.monitoring.service import SourceMonitoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Source Monitoring"])
monitoring_service = SourceMonitoringService()


@router.post(
    "/sources/{source_url_id}/check",
    response_model=ManualCheckResponse,
    summary="Trigger Manual Source Monitor Check",
    description="Trigger an immediate staged monitoring check against a registered approved SourceUrl. Rejects arbitrary URLs.",
)
async def check_source_url(
    source_url_id: uuid.UUID,
    force: bool = Query(default=False, description="Force check even if recently verified"),
    db: Session = Depends(get_db),
) -> ManualCheckResponse:
    """Trigger manual check for an approved source URL ID."""
    try:
        result = await monitoring_service.check_source_url(
            db=db, source_url_id=source_url_id, force_check=force
        )
        return ManualCheckResponse(
            source_url_id=source_url_id,
            status=result.get("status", "UNKNOWN"),
            result=result.get("result", "UNKNOWN"),
            change_signals=result.get("change_signals"),
            http_status=result.get("http_status"),
            duration_ms=result.get("duration_ms", 0.0),
            next_check_at=result.get("next_check_at"),
            change_event_id=result.get("change_event_id"),
            message=result.get("message", ""),
        )
    except Exception as e:
        logger.error(f"Error checking source {source_url_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check source: {str(e)}",
        )


@router.get(
    "/source-monitoring/health-summary",
    response_model=SourceHealthSummaryResponse,
    summary="Source Monitoring Health Metrics",
    description="Get aggregated metrics on source monitoring health, failure counts, and pending change events.",
)
def get_source_health_summary(
    db: Session = Depends(get_db),
) -> SourceHealthSummaryResponse:
    """Return aggregated source monitoring health summary."""
    summary = monitoring_service.repo.get_source_health_summary(db)
    return SourceHealthSummaryResponse(**summary)


@router.get(
    "/source-monitoring",
    response_model=Dict[str, Any],
    summary="List Source Monitoring States",
    description="Retrieve paginated monitoring operational states with optional status and priority filtering.",
)
def list_source_monitoring(
    monitor_status: Optional[str] = Query(default=None, description="Filter by status (e.g. UNCHANGED, CHANGED, CHECK_FAILED)"),
    priority: Optional[str] = Query(default=None, description="Filter by priority tier"),
    due_only: bool = Query(default=False, description="Only return sources due for check"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List monitoring operational states."""
    items, total = monitoring_service.repo.list_states(
        db,
        status=monitor_status,
        priority=priority,
        due_only=due_only,
        limit=limit,
        offset=skip,
    )
    return {
        "items": [SourceMonitorStateResponse.model_validate(item) for item in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/source-monitoring/{source_url_id}",
    response_model=Dict[str, Any],
    summary="Get Source Monitoring State Details",
    description="Retrieve operational state and recent audit runs for a specific approved source URL.",
)
def get_source_monitoring_detail(
    source_url_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch monitoring state and recent runs for an approved source URL."""
    state = monitoring_service.repo.get_state_by_source_url_id(db, source_url_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No monitoring state found for source URL {source_url_id}",
        )

    recent_runs = monitoring_service.repo.get_recent_runs_by_source_url_id(
        db, source_url_id, limit=10
    )

    return {
        "state": SourceMonitorStateResponse.model_validate(state),
        "recent_runs": [
            SourceMonitorRunResponse.model_validate(run) for run in recent_runs
        ],
    }


@router.get(
    "/source-change-events",
    response_model=Dict[str, Any],
    summary="List Source Change Events",
    description="Retrieve paginated change events queued for Day 18 analysis.",
)
def list_source_change_events(
    processing_status: Optional[str] = Query(default=None, description="Filter by processing status (PENDING_ANALYSIS, ANALYZED, FAILED)"),
    change_type: Optional[str] = Query(default=None, description="Filter by change type"),
    source_url_id: Optional[uuid.UUID] = Query(default=None, description="Filter by source URL ID"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List source change events."""
    items, total = monitoring_service.repo.list_change_events(
        db,
        processing_status=processing_status,
        change_type=change_type,
        source_url_id=source_url_id,
        limit=limit,
        offset=skip,
    )
    return {
        "items": [SourceChangeEventResponse.model_validate(ev) for ev in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
