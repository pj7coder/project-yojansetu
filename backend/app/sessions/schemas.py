from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    """Response returned upon creating a new ephemeral citizen session."""
    session_id: str = Field(..., description="Cryptographically secure session identifier")
    expires_at: datetime = Field(..., description="UTC timestamp when this session will automatically expire")
    created_at: datetime = Field(..., description="UTC creation timestamp")


class UpdateProfileRequest(BaseModel):
    """Request payload for updating or patching citizen profile facts."""
    profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Profile fields to add or update (partial patch semantics)"
    )
    clear_fields: Optional[List[str]] = Field(
        default=None,
        description="Optional list of field names to explicitly clear/revert to UNKNOWN"
    )


class DeclineFieldRequest(BaseModel):
    """Request to mark a specific field as DECLINED by the citizen."""
    field_name: str = Field(..., description="Canonical name of the profile field declined")
    reason: Optional[str] = Field(default=None, description="Optional explanation or reason for refusal")


class SessionSummary(BaseModel):
    """Privacy-conscious summary of citizen session state without exposing sensitive values."""
    session_id: str
    known_fields: List[str]
    declined_fields: List[str]
    asked_fields: List[str]
    need_text: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    profile_version: int


class SessionDetailResponse(BaseModel):
    """Full structured profile response for frontend profile inspection."""
    session_id: str
    profile: Dict[str, Any]
    known_fields: List[str]
    declined_fields: List[str]
    asked_fields: List[str]
    need_text: Optional[str] = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    profile_version: int
