from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.eligibility.result import (
    ConditionEvaluationResult,
    EligibilityResult,
    EligibilityStatus,
    MissingFieldInfo,
    SchemeAvailability,
)


class CitizenProfileInput(BaseModel):
    """Input payload representing citizen profile criteria."""
    model_config = ConfigDict(extra="allow")

    age: Optional[int] = None
    state: Optional[str] = None
    district: Optional[str] = None
    domicile_status: Optional[str] = None
    rural_urban: Optional[str] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    farmer_status: Optional[bool] = None
    annual_income: Optional[float] = None
    annual_income_frequency: Optional[str] = "ANNUAL"
    family_income: Optional[float] = None
    family_income_frequency: Optional[str] = "ANNUAL"
    social_category: Optional[str] = None
    bpl_status: Optional[bool] = None
    disability_status: Optional[bool] = None
    disability_percentage: Optional[float] = None
    student_status: Optional[bool] = None
    education_level: Optional[str] = None
    marks_percentage: Optional[float] = None
    marital_status: Optional[str] = None
    widow_status: Optional[bool] = None
    land_holding: Optional[float] = None
    family_size: Optional[int] = None
    existing_scheme_benefits: List[str] = Field(default_factory=list)
    pension_status: Optional[bool] = None
    receiving_pension_x: Optional[bool] = None


class EligibilityEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: Dict[str, Any] = Field(..., description="Citizen profile attributes for evaluation")
    evaluation_date: Optional[date] = Field(default=None, description="Optional evaluation date for testing or time-travel")


class MultiSchemeEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: Dict[str, Any] = Field(..., description="Citizen profile attributes")
    scheme_ids: List[str] = Field(..., description="List of verified scheme identifiers to evaluate")
    evaluation_date: Optional[date] = Field(default=None)


class EligibilityEvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    availability: SchemeAvailability
    eligibility_status: EligibilityStatus
    missing_fields: List[MissingFieldInfo] = Field(default_factory=list)
    failed_conditions: List[ConditionEvaluationResult] = Field(default_factory=list)
    passed_conditions: List[ConditionEvaluationResult] = Field(default_factory=list)
    exclusions_triggered: List[ConditionEvaluationResult] = Field(default_factory=list)
    preferences_matched: List[ConditionEvaluationResult] = Field(default_factory=list)
    evaluation_trace: Optional[Dict[str, Any]] = None
    engine_version: str = "1.0"
    evaluation_duration_ms: float = 0.0
