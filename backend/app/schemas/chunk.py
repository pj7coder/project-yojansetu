import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChunkMetadataResponse(BaseModel):
    """Schema for individual chunk metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_id_str: str
    chunk_index: int
    section_type: str
    section_path: Optional[List[str]] = None
    chunk_title: Optional[str] = None
    page_start: int
    page_end: int
    token_count: int
    contains_table: bool
    contains_ocr: bool
    source_block_count: int
    created_at: datetime


class ChunkDetailResponse(ChunkMetadataResponse):
    """Detailed chunk representation including prompt text for inspection and debugging."""
    text: Optional[str] = None
    source_block_ids: Optional[List[str]] = None


class ChunkListResponse(BaseModel):
    """Schema for document chunk collection."""
    document_id: uuid.UUID
    total_chunks: int
    quality_summary: Optional[Dict[str, Any]] = None
    chunks: List[ChunkMetadataResponse] = Field(default_factory=list)


class ChunkTriggerResponse(BaseModel):
    """Schema returned upon triggering semantic chunking."""
    document_id: uuid.UUID
    status: str
    message: str
    chunk_count: int = 0
    quality_summary: Optional[Dict[str, Any]] = None
