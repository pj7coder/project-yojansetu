import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DepartmentBase(BaseModel):
    """Base department schema fields."""

    code: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description="Stable unique department identifier",
        examples=["SJE"],
    )
    name_en: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="English department title",
        examples=["Social Justice and Empowerment Department"],
    )
    name_hi: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Hindi (Devanagari) department title",
        examples=["सामाजिक न्याय एवं अधिकारिता विभाग"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Department overview and mandate",
    )
    official_website: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Official department web portal URL",
        examples=["https://sje.rajasthan.gov.in"],
    )
    active: bool = Field(
        default=True,
        description="Whether department is actively issuing schemes",
    )


class DepartmentCreate(DepartmentBase):
    """Schema for creating a new department."""
    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating department details."""

    name_en: Optional[str] = Field(default=None, min_length=2, max_length=255)
    name_hi: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    official_website: Optional[str] = Field(default=None, max_length=512)
    active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    """Schema for department response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DepartmentListResponse(BaseModel):
    """Schema for listing departments."""

    items: List[DepartmentResponse]
    total: int
