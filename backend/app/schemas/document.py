import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    """Base metadata for a government document."""

    title: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional human-readable document title",
    )
    source_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional foreign key to registered government source",
    )
    source_url_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional foreign key to registered source URL",
    )


class DocumentResponse(DocumentBase):
    """Safe document metadata response without exposing server filesystem paths."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_code: str
    original_filename: str
    stored_filename: str
    file_extension: str
    mime_type: str
    file_size_bytes: int
    ingestion_method: str
    processing_status: str
    sha256: Optional[str] = None
    normalized_text_sha256: Optional[str] = None
    page_count: Optional[int] = None
    text_length: Optional[int] = None
    duplicate_status: Optional[str] = None
    canonical_document_id: Optional[uuid.UUID] = None
    duplicate_of_document_id: Optional[uuid.UUID] = None
    possible_version_of_document_id: Optional[uuid.UUID] = None
    similarity_score: Optional[float] = None
    duplicate_checked_at: Optional[datetime] = None
    duplicate_check_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document listing response."""

    items: List[DocumentResponse]
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    total: int = Field(ge=0, description="Total matching documents")
