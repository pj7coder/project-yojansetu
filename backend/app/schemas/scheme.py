import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SchemeVersionResponse(BaseModel):
    """Schema representing a specific historical or active scheme version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheme_id: uuid.UUID
    version_number: int
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    source_summary: Optional[str] = None
    change_summary: Optional[str] = None
    is_current: bool
    created_at: datetime
    updated_at: datetime


class SchemeBase(BaseModel):
    """Base scheme schema fields."""

    scheme_code: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="Unique scheme code, e.g. RJ-HEALTH-001",
        examples=["RJ-HEALTH-001"],
    )
    name_en: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Official English scheme name",
        examples=["Mukhyamantri Ayushman Arogya Yojana"],
    )
    name_hi: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Official Hindi (Devanagari) scheme name",
        examples=["मुख्यमंत्री आयुष्मान आरोग्य योजना"],
    )
    short_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Abbreviated or colloquial scheme name",
        examples=["MAAY"],
    )
    department_id: uuid.UUID = Field(
        ...,
        description="Foreign key of governing department",
    )
    category_id: uuid.UUID = Field(
        ...,
        description="Foreign key of functional category",
    )
    short_description: Optional[str] = Field(
        default=None,
        description="Concise description of scheme benefits and targets",
    )
    status: str = Field(
        default="DRAFT",
        description="Controlled state: DRAFT, REVIEW_REQUIRED, HUMAN_VERIFIED, ACTIVE, PRODUCTION, INACTIVE, ARCHIVED",
        examples=["ACTIVE"],
    )
    jurisdiction: str = Field(
        default="RAJASTHAN",
        description="RAJASTHAN, INDIA, OTHER",
        examples=["RAJASTHAN"],
    )
    scheme_origin: str = Field(
        default="UNKNOWN",
        description="RAJASTHAN_STATE, CENTRAL, CENTRALLY_SPONSORED, RAJASTHAN_MODIFIED_CSS, UNKNOWN",
        examples=["RAJASTHAN_STATE"],
    )


class SchemeCreate(SchemeBase):
    """Schema for creating a new canonical scheme."""

    initial_source_summary: Optional[str] = Field(
        default=None,
        description="Initial notification summary for Version 1 record",
    )


class SchemeUpdate(BaseModel):
    """Schema for updating scheme metadata."""

    name_en: Optional[str] = Field(default=None, min_length=2, max_length=255)
    name_hi: Optional[str] = Field(default=None, max_length=255)
    short_name: Optional[str] = Field(default=None, max_length=100)
    department_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    short_description: Optional[str] = None
    status: Optional[str] = None
    jurisdiction: Optional[str] = None
    scheme_origin: Optional[str] = None


class SchemeFullUpdate(BaseModel):
    """Comprehensive schema for updating both scheme metadata and canonical extracted details."""

    scheme_code: Optional[str] = Field(default=None, min_length=3, max_length=64)
    name_en: Optional[str] = Field(default=None, min_length=2, max_length=255)
    name_hi: Optional[str] = Field(default=None, max_length=255)
    short_name: Optional[str] = Field(default=None, max_length=100)
    department_id: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    short_description: Optional[str] = None
    status: Optional[str] = None
    jurisdiction: Optional[str] = None
    scheme_origin: Optional[str] = None

    # Canonical rule tree & extracted detail blocks
    canonical_data: Optional[Dict[str, Any]] = None
    benefits: Optional[List[Dict[str, Any]]] = None
    eligibility: Optional[Dict[str, Any]] = None
    required_documents: Optional[List[Dict[str, Any]]] = None
    application: Optional[Dict[str, Any]] = None
    important_dates: Optional[List[Dict[str, Any]]] = None


class SchemeResponse(SchemeBase):
    """Schema for scheme response with version metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    versions: List[SchemeVersionResponse] = Field(default_factory=list)


class SchemeDetailResponse(SchemeResponse):
    """Comprehensive scheme details including active version canonical data and relational names."""

    department_name: Optional[str] = None
    category_name: Optional[str] = None
    active_version_number: Optional[int] = 1
    canonical_data: Optional[Dict[str, Any]] = None
    source_filename: Optional[str] = None
    source_document_id: Optional[uuid.UUID] = None


class SchemeListResponse(BaseModel):
    """Paginated list of schemes."""

    items: List[SchemeResponse]
    page: int
    page_size: int
    total: int
    total_pages: int

