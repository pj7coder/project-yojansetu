import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OCRRunResponse(BaseModel):
    """Schema for OCR execution metadata and document diagnostics."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    ocr_engine: str
    ocr_version: Optional[str] = None
    status: str
    pages_total: int
    pages_checked: int
    pages_ocr_required: int
    pages_ocr_success: int
    pages_ocr_failed: int
    low_confidence_numeric_regions: int
    output_path: Optional[str] = None
    chunking_source_path: str
    diagnostics: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    failure_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class OCRPageDetailResponse(BaseModel):
    """Schema for page-level OCR inspection."""
    document_id: uuid.UUID
    page_number: int
    engine: str
    success: bool
    regions_count: int
    regions: List[Dict[str, Any]] = Field(default_factory=list)
    raw_text: Optional[str] = None
    low_confidence_numeric_regions: int = 0


class OCRCheckTriggerResponse(BaseModel):
    """Schema returned upon initiating OCR evaluation/fallback."""
    document_id: uuid.UUID
    status: str
    message: str
    ocr_run: Optional[OCRRunResponse] = None
