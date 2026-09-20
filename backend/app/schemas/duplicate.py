import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DuplicateRelationshipResponse(BaseModel):
    """Auditable document relationship record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    related_document_id: uuid.UUID
    relationship_type: str
    similarity_score: Optional[float] = None
    reason: Optional[str] = None
    created_at: datetime


class DuplicateAnalysisResponse(BaseModel):
    """Structured response detailing duplicate check findings for a document."""

    document_id: uuid.UUID
    document_code: str
    original_filename: str
    classification: str
    matched_document_id: Optional[uuid.UUID] = None
    canonical_document_id: Optional[uuid.UUID] = None
    similarity_score: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)
    diff_summary: Optional[str] = None
    processing_status: str
    relationships: List[DuplicateRelationshipResponse] = Field(default_factory=list)


class DuplicateResolutionRequest(BaseModel):
    """Payload for administrative human resolution of an ambiguous duplicate/version."""

    decision: str = Field(
        ...,
        description="Resolution decision: MARK_NEW_DOCUMENT, MARK_DUPLICATE, or MARK_VERSION",
        examples=["MARK_NEW_DOCUMENT"],
    )
    target_document_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Target canonical document ID if marking as duplicate or version",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Administrative rationale notes for audit log",
    )


class DocumentComparisonResponse(BaseModel):
    """Side-by-side comparison of two candidate documents."""

    document_a_id: uuid.UUID
    document_a_code: str
    document_b_id: uuid.UUID
    document_b_code: str
    exact_hash_match: bool
    normalized_hash_match: bool
    text_similarity: float
    title_similarity: float
    page_count_a: Optional[int] = None
    page_count_b: Optional[int] = None
    diff_summary: str
    version_keywords_detected: List[str] = Field(default_factory=list)
