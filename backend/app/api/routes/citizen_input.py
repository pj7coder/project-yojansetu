"""
Citizen Input & Confirmation API Router.
Safe conversational bridge receiving natural language speech transcripts or typed text,
handling critical value confirmation dialogues, and updating ephemeral citizen sessions.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.profile_extraction.schemas import (
    ConfirmationRequest,
    CandidateStatus,
    InputSource,
    IntentType,
    ProfileExtractionResult,
)
from app.profile_extraction.service import get_profile_extraction_service
from app.sessions.manager import get_session_manager

logger = logging.getLogger("yojansetu.api.citizen_input")

router = APIRouter(prefix="/citizen/sessions", tags=["Citizen Natural Language Input & Confirmation"])


class CitizenInputRequest(BaseModel):
    text: str = Field(description="Raw speech transcript or typed citizen input")
    source: InputSource = Field(default=InputSource.TEXT_INPUT, description="STT_TRANSCRIPT or TEXT_INPUT")
    expected_field: Optional[str] = Field(default=None, description="Expected question field if replying to system")


class ConfirmationDecisionRequest(BaseModel):
    decision: str = Field(description="YES or NO")
    correction_text: Optional[str] = Field(default=None, description="Optional revised text if citizen corrects value")


class CitizenInputResponse(BaseModel):
    session_id: str
    status: str
    intent: IntentType
    need_text: Optional[str] = None
    confirmation: Optional[ConfirmationRequest] = None
    applied_fields: List[str] = Field(default_factory=list)
    extraction_result: ProfileExtractionResult


class ConfirmationResponse(BaseModel):
    session_id: str
    status: str
    confirmed_field: Optional[str] = None
    profile_version: int
    profile: Dict[str, Any]
    next_confirmation: Optional[ConfirmationRequest] = None


@router.post(
    "/{session_id}/input",
    response_model=CitizenInputResponse,
    summary="Submit citizen speech transcript or text input to active session",
)
def process_citizen_utterance(
    session_id: str,
    payload: CitizenInputRequest,
) -> CitizenInputResponse:
    """
    Ingests natural language input, normalizes vernacular expressions, extracts candidate facts,
    and requires explicit confirmation before applying critical/uncertain facts to session state.
    """
    mgr = get_session_manager()
    session = mgr.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )

    extractor = get_profile_extraction_service()
    result = extractor.process_citizen_input(
        text=payload.text,
        input_source=payload.source,
        expected_field=payload.expected_field,
        existing_profile=session.profile,
    )

    applied_fields: List[str] = []

    # If need_text was recognized, record on session
    if result.need_text:
        mgr.set_need_text(session_id, result.need_text)

    # If confirmation is required, queue it in process RAM session
    if result.pending_confirmation:
        mgr.set_pending_confirmation(
            session_id=session_id,
            confirmation=result.pending_confirmation.model_dump(),
            pending_updates=[c.model_dump() for c in result.candidates],
        )
        return CitizenInputResponse(
            session_id=session_id,
            status="CONFIRMATION_REQUIRED",
            intent=result.intent,
            need_text=result.need_text,
            confirmation=result.pending_confirmation,
            applied_fields=[],
            extraction_result=result,
        )

    # Otherwise, apply accepted candidates directly
    patch: Dict[str, Any] = {}
    for cand in result.candidates:
        if cand.status == CandidateStatus.ACCEPTED:
            if cand.value is not None:
                patch[cand.field] = cand.value
                applied_fields.append(cand.field)
                if cand.frequency and cand.field in ("annual_income", "family_income"):
                    patch[f"{cand.field}_frequency"] = cand.frequency
                if cand.unit and cand.field == "land_holding":
                    patch["land_holding_unit"] = cand.unit
            elif cand.confirmation_reason == "CITIZEN_DECLINED_FIELD":
                mgr.decline_field(session_id, cand.field)
                applied_fields.append(cand.field)

    if patch:
        mgr.update_profile(session_id, patch=patch, source="CITIZEN_NATURAL_LANGUAGE")

    return CitizenInputResponse(
        session_id=session_id,
        status="ACCEPTED" if applied_fields else result.status,
        intent=result.intent,
        need_text=result.need_text,
        confirmation=None,
        applied_fields=applied_fields,
        extraction_result=result,
    )


@router.post(
    "/{session_id}/confirm",
    response_model=ConfirmationResponse,
    summary="Confirm or reject pending candidate profile value",
)
def confirm_candidate_value(
    session_id: str,
    payload: ConfirmationDecisionRequest,
) -> ConfirmationResponse:
    """
    Processes citizen confirmation decision (YES / NO / correction).
    Applies validated facts into session profile only upon explicit confirmation.
    """
    mgr = get_session_manager()
    session = mgr.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )

    if not session.pending_confirmation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending confirmation found for this session.",
        )

    pending_field = session.pending_confirmation.get("field")

    # If citizen supplied correction text instead of direct confirmation
    if payload.correction_text:
        extractor = get_profile_extraction_service()
        res = extractor.process_citizen_input(
            text=payload.correction_text,
            input_source=InputSource.TEXT_INPUT,
            expected_field=pending_field,
            existing_profile=session.profile,
        )
        if res.pending_confirmation:
            mgr.set_pending_confirmation(session_id, res.pending_confirmation.model_dump())
            return ConfirmationResponse(
                session_id=session_id,
                status="CORRECTION_PENDING_CONFIRMATION",
                confirmed_field=pending_field,
                profile_version=session.profile_version,
                profile=session.profile,
                next_confirmation=res.pending_confirmation,
            )

    # Process YES / NO
    session, accepted, field_name = mgr.confirm_pending(session_id, payload.decision)

    # Check if remaining candidates in pending_profile_updates need confirmation
    next_req: Optional[ConfirmationRequest] = None
    if accepted and session.pending_profile_updates:
        extractor = get_profile_extraction_service()
        for cand_dict in session.pending_profile_updates:
            if cand_dict.get("requires_confirmation") and cand_dict.get("field") != field_name:
                from app.profile_extraction.schemas import CandidateProfileUpdate
                c_obj = CandidateProfileUpdate.model_validate(cand_dict)
                next_req = extractor.confirmation_policy.create_confirmation_request(c_obj)
                mgr.set_pending_confirmation(session_id, next_req.model_dump())
                break

    return ConfirmationResponse(
        session_id=session_id,
        status="CONFIRMED" if accepted else "REJECTED_BY_CITIZEN",
        confirmed_field=field_name,
        profile_version=session.profile_version,
        profile=session.profile,
        next_confirmation=next_req,
    )
