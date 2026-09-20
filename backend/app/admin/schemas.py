from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Top-Level Operational Overview
# ---------------------------------------------------------------------------

class SourceOverview(BaseModel):
    total: int
    active: int
    failing: int
    recently_changed: int


class DocumentOverview(BaseModel):
    total: int
    processing: int
    failed: int
    waiting_review: int


class PipelineStageCount(BaseModel):
    stage: str
    waiting: int
    processing: int
    failed: int
    oldest_waiting_seconds: Optional[int] = None


class ReviewOverview(BaseModel):
    pending: int
    critical: int
    in_review: int


class SchemeOverview(BaseModel):
    total: int
    human_verified: int
    active_versions: int
    future_versions: int
    superseded_versions: int


class ConflictOverview(BaseModel):
    total_unresolved: int
    critical_count: int


class CriticalIssue(BaseModel):
    id: str
    category: str  # SOURCE, DOCUMENT, REVIEW, CONFLICT, VERSION
    severity: str  # CRITICAL, WARNING
    title: str
    description: str
    link: str
    created_at: str


class AdminOverviewResponse(BaseModel):
    system_status: str  # HEALTHY, WARNING, CRITICAL
    system_status_reasons: List[str]
    sources: SourceOverview
    documents: DocumentOverview
    reviews: ReviewOverview
    schemes: SchemeOverview
    conflicts: ConflictOverview
    pipeline_stages: List[PipelineStageCount]
    critical_issues: List[CriticalIssue]
    generated_at: str


# ---------------------------------------------------------------------------
# 2. Pipeline Workload & Stuck Items
# ---------------------------------------------------------------------------

class StuckItem(BaseModel):
    document_id: str
    document_code: str
    stage: str
    status: str
    elapsed_minutes: int
    title: Optional[str] = None
    retry_valid: bool = True
    valid_retry_action: Optional[str] = None


class AdminPipelineResponse(BaseModel):
    stages: List[PipelineStageCount]
    stuck_items: List[StuckItem]
    total_waiting: int
    total_processing: int
    total_failed: int
    generated_at: str


# ---------------------------------------------------------------------------
# 3. System Component Health
# ---------------------------------------------------------------------------

class DatabaseHealth(BaseModel):
    status: str  # HEALTHY, UNAVAILABLE
    pool_size: int
    overflow: int
    latency_ms: Optional[float] = None


class OllamaHealth(BaseModel):
    status: str  # HEALTHY, UNAVAILABLE
    model: str
    model_available: bool
    provider: str


class SearchIndexHealth(BaseModel):
    status: str  # HEALTHY, DEGRADED, UNAVAILABLE
    verified_schemes_count: int
    search_metadata_count: int
    embeddings_count: int
    stale_embeddings_count: int
    embedding_model: str
    pgvector_available: bool


class RuleCacheHealth(BaseModel):
    status: str  # HEALTHY, EMPTY, WARNING
    entries: int
    hits: int
    misses: int
    compile_failures: int
    refreshes: int


class WorkerHeartbeatItem(BaseModel):
    worker_type: str
    worker_instance_id: str
    last_seen_at: str
    status: str  # HEALTHY, BUSY, IDLE, STOPPED
    is_stale: bool
    metadata_safe: Dict[str, Any] = Field(default_factory=dict)


class StorageCountItem(BaseModel):
    original_documents: int
    parsed_documents: int
    ocr_runs: int
    document_chunks: int
    scheme_drafts: int
    source_snapshots: int
    verified_scheme_artifacts: int


class AdminSystemStatusResponse(BaseModel):
    overall_status: str  # HEALTHY, WARNING, CRITICAL
    database: DatabaseHealth
    ollama: OllamaHealth
    search_index: SearchIndexHealth
    rule_cache: RuleCacheHealth
    workers: List[WorkerHeartbeatItem]
    storage: StorageCountItem
    tts: Optional[Dict[str, Any]] = None
    generated_at: str


# ---------------------------------------------------------------------------
# 4. Activity Feed (Strictly Operational - Zero Citizen Data)
# ---------------------------------------------------------------------------

class AdminActivityItem(BaseModel):
    id: str
    event_type: str  # INGESTION, SOURCE_CHANGE, PARSING, REVIEW, VERSIONING, RETRY
    actor: str
    title: str
    description: str
    target_id: Optional[str] = None
    target_link: Optional[str] = None
    timestamp: str
    severity: str = "INFO"  # INFO, WARNING, ERROR, SUCCESS


class AdminActivityResponse(BaseModel):
    items: List[AdminActivityItem]
    total: int


# ---------------------------------------------------------------------------
# 5. Unresolved Conflicts
# ---------------------------------------------------------------------------

class AdminConflictItem(BaseModel):
    id: str
    conflict_type: str  # FIELD_VALUE_CONFLICT, SOURCE_CONFLICT, VERSION_RELATIONSHIP_CONFLICT, EFFECTIVE_DATE_CONFLICT, SCHEME_ASSOCIATION_CONFLICT
    severity: str  # CRITICAL, WARNING
    title: str
    description: str
    scheme_id: Optional[str] = None
    scheme_name: Optional[str] = None
    document_id: Optional[str] = None
    source_count: int = 1
    status: str
    link: str
    created_at: str


class AdminConflictListResponse(BaseModel):
    items: List[AdminConflictItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# 6. Document Operations
# ---------------------------------------------------------------------------

class AdminDocumentListItem(BaseModel):
    id: str
    document_code: str
    original_filename: str
    source_name: Optional[str] = None
    ingestion_method: str
    processing_status: str
    current_stage: str
    page_count: Optional[int] = None
    file_size_bytes: int
    failure_reason: Optional[str] = None
    retry_valid: bool
    valid_retry_action: Optional[str] = None
    created_at: str
    updated_at: str


class AdminDocumentListResponse(BaseModel):
    items: List[AdminDocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentRetryResponse(BaseModel):
    document_id: str
    action_taken: str
    new_status: str
    message: str


# ---------------------------------------------------------------------------
# 7. Scheme Operations & Versions
# ---------------------------------------------------------------------------

class AdminSchemeListItem(BaseModel):
    id: str
    scheme_code: str
    name_en: str
    name_hi: Optional[str] = None
    department_name: Optional[str] = None
    scheme_origin: str
    current_version_number: Optional[int] = None
    current_version_status: Optional[str] = None
    has_future_version: bool = False
    future_effective_date: Optional[str] = None
    is_active: bool
    last_reviewed_at: Optional[str] = None


class AdminSchemeListResponse(BaseModel):
    items: List[AdminSchemeListItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# 8. Monitored Sources Operations
# ---------------------------------------------------------------------------

class AdminSourceListItem(BaseModel):
    id: str
    source_url_id: Optional[str] = None
    source_name: str
    url: str
    authority_level: str
    priority_tier: str
    monitor_status: str  # HEALTHY, CHECK_FAILED, CHANGED, UNCHECKED, DISABLED
    last_check_at: Optional[str] = None
    last_change_at: Optional[str] = None
    next_check_at: Optional[str] = None
    failure_count: int
    enabled: bool


class AdminSourceListResponse(BaseModel):
    items: List[AdminSourceListItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# 9. Global Search
# ---------------------------------------------------------------------------

class AdminSearchHit(BaseModel):
    id: str
    entity_type: str  # SCHEME, DOCUMENT, SOURCE
    title: str
    subtitle: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None
    link: str


class AdminGlobalSearchResponse(BaseModel):
    query: str
    schemes: List[AdminSearchHit]
    documents: List[AdminSearchHit]
    sources: List[AdminSearchHit]
    total_hits: int


# ---------------------------------------------------------------------------
# 10. Worker Heartbeat Registration
# ---------------------------------------------------------------------------

class WorkerHeartbeatRequest(BaseModel):
    worker_type: str
    worker_instance_id: str
    status: str = "HEALTHY"
    metadata_safe: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 11. System Platform Factory Reset
# ---------------------------------------------------------------------------

class SystemResetRequest(BaseModel):
    confirmation: str = Field(..., description="Must equal 'DELETE' to confirm destructive platform purge")


class SystemResetResponse(BaseModel):
    status: str
    message: str
    tables_cleared: int
    files_removed: int

