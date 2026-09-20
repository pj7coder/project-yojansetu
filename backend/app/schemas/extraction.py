from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExtractionRunResponse(BaseModel):
    """Schema for extraction execution metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_id_str: str
    model_provider: str
    model_name: str
    prompt_version: str
    schema_version: str
    status: str
    artifact_path: str
    input_token_estimate: int
    output_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    failure_reason: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ChunkExtractionDetailResponse(ExtractionRunResponse):
    """Detailed chunk extraction response including JSON payload and raw response."""
    extraction_payload: Optional[Dict[str, Any]] = None
    raw_response_text: Optional[str] = None


class DocumentExtractionsListResponse(BaseModel):
    """Collection of extraction runs for a document along with master aggregation."""
    document_id: uuid.UUID
    status: str
    total_runs: int
    runs: List[ExtractionRunResponse] = Field(default_factory=list)
    master_summary: Optional[Dict[str, Any]] = None


class LLMHealthResponse(BaseModel):
    """Response returned by LLM health check."""
    status: str
    provider: str
    model: str
    model_available: bool
    installed_models: Optional[List[str]] = None
