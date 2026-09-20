from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.questioning.schemas import NextQuestionResult
from app.sessions.schemas import SessionSummary


class SessionEligibleSchemeItem(BaseModel):
    """Summary of a scheme for which the citizen is confirmed ELIGIBLE."""
    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    semantic_score: Optional[float] = None
    passed_conditions: List[str] = Field(default_factory=list)


class SessionMoreInfoSchemeItem(BaseModel):
    """Summary of a potential candidate scheme requiring missing citizen attributes."""
    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    semantic_score: Optional[float] = None
    missing_fields: List[str] = Field(default_factory=list)


class SessionDiscoveryMeta(BaseModel):
    """Execution and audit metadata for session-based discovery."""
    total_candidates: int
    eligible_count: int
    more_info_count: int
    duration_ms: float
    semantic_ranking_used: bool
    rule_cache_hit_rate: Optional[float] = None


class SessionDiscoveryResponse(BaseModel):
    """Comprehensive discovery response for a multi-turn citizen session."""
    session_id: str
    eligible: List[SessionEligibleSchemeItem] = Field(default_factory=list)
    more_information_required: List[SessionMoreInfoSchemeItem] = Field(default_factory=list)
    next_question: Optional[NextQuestionResult] = None
    session_summary: SessionSummary
    meta: SessionDiscoveryMeta
