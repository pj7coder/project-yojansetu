import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ParsedDocumentResponse(BaseModel):
    """Schema for parsed document metadata and quality diagnostics."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    parser_name: str
    parser_version: Optional[str] = None
    parse_status: str
    page_count: int
    pages_with_text: int
    pages_without_text: int
    pages_low_text: int
    total_text_characters: int
    total_blocks: int
    total_tables: int
    output_path: str
    artifact_sha256: Optional[str] = None
    duration_ms: Optional[int] = None
    failure_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ParsedPageResponse(BaseModel):
    """Schema for a single physical page's blocks and evidence location."""
    document_id: uuid.UUID
    page_number: int
    status: str
    text_character_count: int
    block_count: int
    blocks: List[Dict[str, Any]] = Field(default_factory=list)


class ParseTriggerResponse(BaseModel):
    """Schema returned upon triggering document parsing."""
    document_id: uuid.UUID
    status: str
    message: str
    parsed_record: Optional[ParsedDocumentResponse] = None
