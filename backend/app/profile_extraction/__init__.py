"""
JanSetu - Day 24: Citizen Profile Extraction & Normalization Package.
Bridges raw citizen speech transcripts and text inputs to typed, deterministic citizen profiles.
"""

from app.profile_extraction.schemas import (
    CandidateProfileUpdate,
    CandidateStatus,
    ConfirmationRequest,
    ExtractionMethod,
    InputSource,
    IntentType,
    ProfileExtractionResult,
)
from app.profile_extraction.service import (
    CitizenProfileExtractionService,
    get_profile_extraction_service,
)

__all__ = [
    "CandidateProfileUpdate",
    "CandidateStatus",
    "ConfirmationRequest",
    "ExtractionMethod",
    "InputSource",
    "IntentType",
    "ProfileExtractionResult",
    "CitizenProfileExtractionService",
    "get_profile_extraction_service",
]
