import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    """Base category schema fields."""

    code: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description="Stable unique category slug",
        examples=["health"],
    )
    name_en: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="English category name",
        examples=["Health and Medical"],
    )
    name_hi: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Hindi category name",
        examples=["स्वास्थ्य एवं चिकित्सा"],
    )
    description: Optional[str] = None
    active: bool = True


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""
    pass


class CategoryResponse(CategoryBase):
    """Schema for category response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseModel):
    """Schema for listing categories."""

    items: List[CategoryResponse]
    total: int
