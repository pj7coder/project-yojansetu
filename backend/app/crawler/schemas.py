from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SourceChangeAnalysisResponse(BaseModel):
    id: uuid.UUID
    change_event_id: uuid.UUID
    status: str
    render_method: str
    previous_snapshot_path: Optional[str] = None
    current_snapshot_path: Optional[str] = None
    cleaned_snapshot_path: Optional[str] = None
    diff_summary_path: Optional[str] = None
    diff_summary: Optional[Dict[str, Any]] = None
    text_changes_count: int
    links_added_count: int
    links_removed_count: int
    links_changed_count: int
    numeric_changes_count: int
    has_high_priority_change: bool
    relevant_resources_count: int
    uncertain_resources_count: int
    irrelevant_resources_count: int
    fetched_resources_count: int
    ingested_documents_count: int
    error_code: Optional[str] = None
    error_message_safe: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscoveredResourceResponse(BaseModel):
    id: uuid.UUID
    change_event_id: uuid.UUID
    source_url_id: uuid.UUID
    url: str
    normalized_url: str
    anchor_text: Optional[str] = None
    context_text: Optional[str] = None
    resource_type: str
    discovery_reason: str
    relevance_status: str
    relevance_reason: Optional[Dict[str, Any]] = None
    fetch_status: str
    fetch_error: Optional[str] = None
    document_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedChangeAnalysesResponse(BaseModel):
    items: List[SourceChangeAnalysisResponse]
    total: int
    limit: int
    offset: int


class PaginatedDiscoveredResourcesResponse(BaseModel):
    items: List[DiscoveredResourceResponse]
    total: int
    limit: int
    offset: int


class ResourceRelevanceUpdateRequest(BaseModel):
    relevance_status: str = Field(..., pattern="^(RELEVANT|IRRELEVANT|UNCERTAIN)$")
    reason: str = Field(..., min_length=3, max_length=500)
