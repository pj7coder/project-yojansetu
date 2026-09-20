import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceBase(BaseModel):
    """Base source schema fields."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Official source name or title",
        examples=["Rajasthan Jan Soochna Portal"],
    )
    base_url: str = Field(
        ...,
        max_length=512,
        description="Source entrypoint URL",
        examples=["https://jansoochna.rajasthan.gov.in"],
    )
    department_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Department reference if source is department-specific",
    )
    source_type: str = Field(
        default="PORTAL",
        description="PORTAL, DEPARTMENT_WEBSITE, NOTIFICATION_PAGE, SCHEME_PAGE, BUDGET_PORTAL, OTHER",
    )
    priority: str = Field(
        default="TIER_1",
        description="TIER_1, TIER_2, TIER_3, TIER_4",
    )
    enabled: bool = True


class SourceCreate(SourceBase):
    """Schema for creating a source."""
    pass


class SourceResponse(SourceBase):
    """Schema for source response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    """Schema for listing sources."""

    items: List[SourceResponse]
    total: int
