from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ChangeSignalsModel(BaseModel):
    etag_changed: bool = False
    last_modified_changed: bool = False
    content_length_changed: bool = False
    body_fingerprint_changed: bool = False
    link_fingerprint_changed: bool = False
    is_304: bool = False


class SourceMonitorStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url_id: uuid.UUID
    monitor_status: str
    last_attempt_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_change_at: Optional[datetime] = None
    next_check_at: Optional[datetime] = None
    last_http_status: Optional[int] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_length: Optional[int] = None
    content_type: Optional[str] = None
    body_fingerprint: Optional[str] = None
    link_fingerprint: Optional[str] = None
    consecutive_failures: int = 0
    created_at: datetime
    updated_at: datetime


class SourceMonitorRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url_id: uuid.UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    http_method: str
    http_status: Optional[int] = None
    result: str
    change_signals: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error_code: Optional[str] = None
    error_message_safe: Optional[str] = None


class SourceChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url_id: uuid.UUID
    monitor_run_id: Optional[uuid.UUID] = None
    change_type: str
    detected_at: datetime
    previous_state_reference: Optional[Dict[str, Any]] = None
    new_state_reference: Optional[Dict[str, Any]] = None
    processing_status: str
    created_at: datetime


class SourceHealthSummaryResponse(BaseModel):
    total_monitored_sources: int
    healthy: int
    temporarily_failing: int
    long_term_failing: int
    blocked: int
    never_checked: int
    disabled: int
    pending_change_events: int


class ManualCheckResponse(BaseModel):
    source_url_id: uuid.UUID
    status: str
    result: str
    change_signals: Optional[Dict[str, Any]] = None
    http_status: Optional[int] = None
    duration_ms: float
    next_check_at: Optional[datetime] = None
    change_event_id: Optional[uuid.UUID] = None
    message: str
