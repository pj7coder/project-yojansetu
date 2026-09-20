from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, and_, or_, desc
from sqlalchemy.orm import Session

from app.admin.activity_service import AdminActivityService
from app.admin.conflict_service import AdminConflictService
from app.admin.dashboard_service import AdminDashboardService
from app.admin.pipeline_service import AdminPipelineService
from app.admin.schemas import (
    AdminActivityResponse,
    AdminConflictListResponse,
    AdminDocumentListItem,
    AdminDocumentListResponse,
    AdminGlobalSearchResponse,
    AdminOverviewResponse,
    AdminPipelineResponse,
    AdminSchemeListItem,
    AdminSchemeListResponse,
    AdminSourceListItem,
    AdminSourceListResponse,
    AdminSystemStatusResponse,
    DocumentRetryResponse,
    WorkerHeartbeatItem,
    WorkerHeartbeatRequest,
    SystemResetRequest,
    SystemResetResponse,
)
from app.admin.reset_service import AdminResetService
from app.admin.search_service import AdminGlobalSearchService
from app.admin.system_health import AdminSystemHealthService
from app.cache.verified_rule_cache import get_rule_cache
from app.database.models.admin_operation_event import AdminOperationEvent
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.source import Source
from app.database.models.source_monitor_state import SourceMonitorState
from app.database.models.source_url import SourceUrl
from app.database.session import get_db
from app.review.authorization import ReviewAuthorizationService
from app.search.indexer import SchemeSearchIndexService

logger = logging.getLogger("yojansetu.api.admin_dashboard")

router = APIRouter(prefix="/admin", tags=["Admin Dashboard & Operations"])

dashboard_service = AdminDashboardService()
pipeline_service = AdminPipelineService()
system_health_service = AdminSystemHealthService()
activity_service = AdminActivityService()
conflict_service = AdminConflictService()
search_service = AdminGlobalSearchService()
reset_service = AdminResetService()


# ---------------------------------------------------------------------------
# 1. Dashboard Top-Level Overview
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard/overview",
    response_model=AdminOverviewResponse,
    summary="Get consolidated system operational overview",
)
def get_dashboard_overview(
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminOverviewResponse:
    return dashboard_service.get_overview(db, force_refresh=force_refresh)


# ---------------------------------------------------------------------------
# 2. Pipeline Workload & Stuck Items
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard/pipeline",
    response_model=AdminPipelineResponse,
    summary="Get document processing pipeline workload and stuck items",
)
def get_dashboard_pipeline(
    stuck_threshold_minutes: Optional[int] = Query(30, ge=1, le=1440),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminPipelineResponse:
    return pipeline_service.get_pipeline_summary(db, stuck_threshold_minutes=stuck_threshold_minutes)


@router.post(
    "/documents/{document_id}/retry",
    response_model=DocumentRetryResponse,
    summary="Contextual safe retry for failed or stuck document",
)
def retry_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> DocumentRetryResponse:
    return pipeline_service.retry_document(db, document_id, actor_id=reviewer_id)


# ---------------------------------------------------------------------------
# 3. System Component Health
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard/system",
    response_model=AdminSystemStatusResponse,
    summary="Get component-level system operational health",
)
def get_system_status(
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminSystemStatusResponse:
    return system_health_service.get_system_status(db)


@router.post(
    "/workers/heartbeat",
    response_model=WorkerHeartbeatItem,
    summary="Register worker operational heartbeat",
)
def register_worker_heartbeat(
    payload: WorkerHeartbeatRequest,
    db: Session = Depends(get_db),
) -> WorkerHeartbeatItem:
    wh = system_health_service.register_heartbeat(
        db,
        worker_type=payload.worker_type,
        worker_instance_id=payload.worker_instance_id,
        status_val=payload.status,
        metadata_safe=payload.metadata_safe,
    )
    return WorkerHeartbeatItem(
        worker_type=wh.worker_type,
        worker_instance_id=wh.worker_instance_id,
        last_seen_at=wh.last_seen_at.isoformat(),
        status=wh.status,
        is_stale=False,
        metadata_safe=wh.metadata_safe or {},
    )


@router.post(
    "/search-index/reindex-stale",
    summary="Trigger re-indexing of stale verified scheme embeddings",
)
def reindex_stale_embeddings(
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> Dict[str, Any]:
    res = SchemeSearchIndexService.rebuild_index(db)
    
    # Audit log
    audit_event = AdminOperationEvent(
        actor_id=reviewer_id,
        action_type="SEARCH_REINDEX_TRIGGERED",
        target_type="SEARCH_INDEX",
        metadata_safe=res,
    )
    db.add(audit_event)
    db.commit()

    return {
        "status": "success",
        "message": f"Successfully reindexed {res.get('indexed_count', 0)} verified schemes.",
        "details": res,
    }


@router.post(
    "/cache/refresh",
    summary="Trigger full refresh of verified rule cache from database",
)
def refresh_rule_cache(
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> Dict[str, Any]:
    cache = get_rule_cache()
    loaded_count = cache.refresh_all(session=db)

    # Audit log
    audit_event = AdminOperationEvent(
        actor_id=reviewer_id,
        action_type="RULE_CACHE_REFRESHED",
        target_type="RULE_CACHE",
        metadata_safe={"loaded_entries": loaded_count},
    )
    db.add(audit_event)
    db.commit()

    return {
        "status": "success",
        "message": f"Successfully refreshed rule cache with {loaded_count} active schemes.",
        "entries": loaded_count,
    }


# ---------------------------------------------------------------------------
# 4. Activity Feed (Zero Citizen Data)
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard/activity",
    response_model=AdminActivityResponse,
    summary="Get recent operational activity feed",
)
def get_recent_activity(
    limit: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminActivityResponse:
    return activity_service.get_recent_activity(db, limit=limit)


# ---------------------------------------------------------------------------
# 5. Unresolved Conflicts
# ---------------------------------------------------------------------------

@router.get(
    "/conflicts",
    response_model=AdminConflictListResponse,
    summary="List unresolved operational and versioning conflicts",
)
def list_conflicts(
    conflict_type: Optional[str] = Query(None, description="Filter by conflict category"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, WARNING)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminConflictListResponse:
    return conflict_service.list_conflicts(
        db,
        conflict_type=conflict_type,
        severity=severity,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 6. Unified Documents Operations View
# ---------------------------------------------------------------------------

@router.get(
    "/documents",
    response_model=AdminDocumentListResponse,
    summary="List documents across all pipeline stages with failure details",
)
def list_admin_documents(
    processing_status: Optional[str] = Query(None, description="Filter by exact processing status"),
    failed_only: bool = Query(False, description="Only return documents in failed statuses"),
    ingestion_method: Optional[str] = Query(None, description="Filter by ingestion method"),
    query: Optional[str] = Query(None, description="Filter by code or filename"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminDocumentListResponse:
    stmt = select(Document, Source.name).outerjoin(Source, Document.source_id == Source.id)

    conditions = []
    if failed_only:
        conditions.append(Document.processing_status.in_(AdminDashboardService.FAILED_STATUSES))
    elif processing_status:
        conditions.append(Document.processing_status == processing_status)

    if ingestion_method:
        conditions.append(Document.ingestion_method == ingestion_method)

    if query:
        pattern = f"%{query.strip()}%"
        conditions.append(
            or_(
                Document.document_code.ilike(pattern),
                Document.original_filename.ilike(pattern),
                Document.title.ilike(pattern),
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(desc(Document.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).all()

    items = []
    for doc, source_name in rows:
        # Determine stage
        curr_stage = "UNKNOWN"
        for stg, statuses in AdminPipelineService.STAGE_STATUS_MAP.items():
            if doc.processing_status in statuses:
                curr_stage = stg
                break
        if curr_stage == "UNKNOWN":
            for stg, statuses in AdminPipelineService.FAILED_STAGE_STATUS_MAP.items():
                if doc.processing_status in statuses:
                    curr_stage = stg
                    break

        retry_valid = doc.processing_status in AdminPipelineService.FAILED_STATUS_ACTION_MAP or doc.processing_status in AdminPipelineService.TRANSIENT_STATUSES
        retry_act = AdminPipelineService.FAILED_STATUS_ACTION_MAP.get(doc.processing_status)
        if not retry_act and doc.processing_status in AdminPipelineService.TRANSIENT_STATUSES:
            _, retry_act = AdminPipelineService.TRANSIENT_STATUSES[doc.processing_status]

        items.append(
            AdminDocumentListItem(
                id=str(doc.id),
                document_code=doc.document_code,
                original_filename=doc.original_filename,
                source_name=source_name,
                ingestion_method=doc.ingestion_method,
                processing_status=doc.processing_status,
                current_stage=curr_stage,
                page_count=doc.page_count,
                file_size_bytes=doc.file_size_bytes,
                failure_reason=doc.failure_reason,
                retry_valid=retry_valid,
                valid_retry_action=retry_act,
                created_at=doc.created_at.isoformat(),
                updated_at=(doc.updated_at or doc.created_at).isoformat(),
            )
        )

    return AdminDocumentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 7. Schemes Operations & Version Timeline Summary
# ---------------------------------------------------------------------------

@router.get(
    "/schemes",
    response_model=AdminSchemeListResponse,
    summary="List schemes with verified version status",
)
def list_admin_schemes(
    status_filter: Optional[str] = Query(None, alias="status"),
    department_id: Optional[uuid.UUID] = Query(None),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminSchemeListResponse:
    now = datetime.now(timezone.utc).date()
    stmt = select(Scheme, Department.name_en).outerjoin(Department, Scheme.department_id == Department.id)

    conditions = []
    if status_filter:
        conditions.append(Scheme.status == status_filter)
    if department_id:
        conditions.append(Scheme.department_id == department_id)
    if query:
        pattern = f"%{query.strip()}%"
        conditions.append(
            or_(
                Scheme.scheme_code.ilike(pattern),
                Scheme.name_en.ilike(pattern),
                Scheme.name_hi.ilike(pattern),
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(desc(Scheme.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).all()

    items = []
    for s, dept_name in rows:
        # Check active current version
        curr_ver = db.execute(
            select(SchemeVersion)
            .where(
                and_(
                    SchemeVersion.scheme_id == s.id,
                    SchemeVersion.is_current.is_(True),
                )
            )
            .order_by(desc(SchemeVersion.version_number))
        ).scalars().first()

        # Check future version
        fut_ver = db.execute(
            select(SchemeVersion)
            .where(
                and_(
                    SchemeVersion.scheme_id == s.id,
                    or_(
                        SchemeVersion.valid_from > now,
                        and_(
                            SchemeVersion.status == "HUMAN_VERIFIED",
                            SchemeVersion.effective_date > now,
                        ),
                    ),
                )
            )
            .order_by(desc(SchemeVersion.version_number))
        ).scalars().first()

        items.append(
            AdminSchemeListItem(
                id=str(s.id),
                scheme_code=s.scheme_code,
                name_en=s.name_en,
                name_hi=s.name_hi,
                department_name=dept_name,
                scheme_origin=s.scheme_origin,
                current_version_number=curr_ver.version_number if curr_ver else None,
                current_version_status=curr_ver.status if curr_ver else None,
                has_future_version=fut_ver is not None,
                future_effective_date=(fut_ver.effective_date or fut_ver.valid_from).isoformat() if fut_ver and (fut_ver.effective_date or fut_ver.valid_from) else None,
                is_active=s.status in ["HUMAN_VERIFIED", "PRODUCTION"],
                last_reviewed_at=s.updated_at.isoformat() if s.updated_at else None,
            )
        )

    return AdminSchemeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 8. Monitored Sources Operations
# ---------------------------------------------------------------------------

@router.get(
    "/sources",
    response_model=AdminSourceListResponse,
    summary="List monitored official sources with health and check statuses",
)
def list_admin_sources(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_tier: Optional[str] = Query(None),
    authority_level: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
    query: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminSourceListResponse:
    stmt = (
        select(Source, SourceUrl, SourceMonitorState)
        .outerjoin(SourceUrl, Source.id == SourceUrl.source_id)
        .outerjoin(SourceMonitorState, SourceUrl.id == SourceMonitorState.source_url_id)
    )

    conditions = []
    if status_filter:
        conditions.append(SourceMonitorState.monitor_status == status_filter)
    if priority_tier:
        conditions.append(or_(SourceUrl.priority == priority_tier, Source.priority == priority_tier))
    if authority_level:
        conditions.append(SourceUrl.authority_level == authority_level)
    if enabled_only:
        conditions.append(Source.enabled.is_(True))
    if query:
        pattern = f"%{query.strip()}%"
        conditions.append(
            or_(
                Source.name.ilike(pattern),
                Source.base_url.ilike(pattern),
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(desc(Source.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).all()

    items = []
    for src, s_url, state in rows:
        m_status = state.monitor_status if state else "UNCHECKED"
        if not src.enabled:
            m_status = "DISABLED"

        items.append(
            AdminSourceListItem(
                id=str(src.id),
                source_url_id=str(s_url.id) if s_url else None,
                source_name=src.name,
                url=s_url.url if s_url else src.base_url,
                authority_level=s_url.authority_level if s_url else "OFFICIAL_PORTAL",
                priority_tier=s_url.priority if s_url else src.priority,
                monitor_status=m_status,
                last_check_at=state.last_attempt_at.isoformat() if state and state.last_attempt_at else None,
                last_change_at=state.last_change_at.isoformat() if state and state.last_change_at else None,
                next_check_at=state.next_check_at.isoformat() if state and state.next_check_at else None,
                failure_count=state.consecutive_failures if state else 0,
                enabled=src.enabled,
            )
        )

    return AdminSourceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# 9. Global Search
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=AdminGlobalSearchResponse,
    summary="Global operational text search across schemes, documents, and sources",
)
def global_admin_search(
    q: str = Query(..., min_length=1, description="Search term"),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> AdminGlobalSearchResponse:
    return search_service.search(db, query=q)


# ---------------------------------------------------------------------------
# 10. Platform Factory Reset
# ---------------------------------------------------------------------------

@router.post(
    "/system/reset-all",
    response_model=SystemResetResponse,
    summary="Purge all platform schemes, documents, sources, and data",
    description="Destructive factory reset. Requires payload {'confirmation': 'DELETE'}.",
)
def reset_all_platform_data(
    payload: SystemResetRequest,
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
) -> SystemResetResponse:
    res = reset_service.reset_all_data(confirmation=payload.confirmation)
    return SystemResetResponse(**res)

