from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.eligibility.result import ConditionEvaluationResult, EligibilityStatus, MissingFieldInfo


class SchemeDiscoveryRequest(BaseModel):
    """Input payload for scheme discovery: partial citizen profile + optional citizen need text."""
    model_config = ConfigDict(extra="ignore")

    profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Citizen demographic and socio-economic criteria (all optional)",
    )
    need_text: Optional[str] = Field(
        default=None,
        description="Citizen's expressed requirement (in Hindi, English, or Hinglish)",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of top recommendations per result bucket",
    )
    include_debug: bool = Field(
        default=False,
        description="Include internal diagnostic evaluation traces if True",
    )
    evaluation_date: Optional[date] = Field(
        default=None,
        description="Optional date for historical testing or time-travel",
    )


class EligibleSchemeItem(BaseModel):
    """A human-verified government scheme where the citizen is definitively ELIGIBLE."""
    model_config = ConfigDict(extra="ignore")

    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    eligibility_status: EligibilityStatus = EligibilityStatus.ELIGIBLE
    semantic_similarity: Optional[float] = Field(
        default=None,
        description="Cosine relevance score between citizen need and scheme (0.0 to 1.0)",
    )
    matched_signals: List[str] = Field(
        default_factory=list,
        description="Matched category, beneficiary, or occupation tags",
    )
    passed_conditions: List[ConditionEvaluationResult] = Field(default_factory=list)


class MoreInfoSchemeItem(BaseModel):
    """A verified scheme where citizen eligibility cannot be confirmed without additional details."""
    model_config = ConfigDict(extra="ignore")

    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    eligibility_status: EligibilityStatus = EligibilityStatus.MORE_INFORMATION_REQUIRED
    missing_fields: List[str] = Field(
        default_factory=list,
        description="Key citizen fields required to reach a definitive decision",
    )
    missing_field_details: List[MissingFieldInfo] = Field(default_factory=list)
    semantic_similarity: Optional[float] = None
    matched_signals: List[str] = Field(default_factory=list)


class DiscoveryMeta(BaseModel):
    """Search execution diagnostics and audit counts."""
    model_config = ConfigDict(extra="ignore")

    candidates_before_filter: int = 0
    sql_candidates: int = 0
    evaluated_count: int = 0
    eligible_count: int = 0
    more_information_required_count: int = 0
    not_eligible_count: int = 0
    semantic_ranking_used: bool = False
    semantic_ranking_available: bool = True
    evaluation_duration_ms: float = 0.0


class SchemeDiscoveryResponse(BaseModel):
    """Top-level structured discovery response with clearly separated outcome buckets."""
    model_config = ConfigDict(extra="ignore")

    eligible: List[EligibleSchemeItem] = Field(
        default_factory=list,
        description="Confirmed eligible schemes ordered by relevance",
    )
    more_information_required: List[MoreInfoSchemeItem] = Field(
        default_factory=list,
        description="Potentially matching schemes requiring 1 or more citizen details",
    )
    meta: DiscoveryMeta
    engine_version: str = "1.0"


class SearchIndexStatusResponse(BaseModel):
    """Administrative status of the verified search metadata and embedding index."""
    model_config = ConfigDict(extra="ignore")

    verified_schemes_count: int
    search_metadata_count: int
    embeddings_count: int
    stale_embeddings_count: int
    embedding_model: str
    embedding_dimension: int
    pgvector_available: bool
