from datetime import date
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.citizen.schemas import CitizenDiscoveryResponse
from app.citizen.service import CitizenDiscoveryFacade
from app.database.session import get_db
from app.discovery.schemas import SessionDiscoveryResponse
from app.discovery.session_discovery_service import SessionDiscoveryService
from app.sessions.manager import SessionNotFoundError, get_session_manager
from app.sessions.schemas import (
    CreateSessionResponse,
    DeclineFieldRequest,
    SessionDetailResponse,
    SessionSummary,
    UpdateProfileRequest,
)

logger = logging.getLogger("yojansetu.api.citizen_sessions")

router = APIRouter(prefix="/citizen/sessions", tags=["Citizen Multi-Turn Sessions"])


class SessionDiscoverPayload(BaseModel):
    need_text: Optional[str] = Field(default=None, description="Optional citizen need or intent text")
    evaluation_date: Optional[date] = Field(default=None, description="Optional date for eligibility checking")


@router.post(
    "",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new temporary citizen session",
)
def create_session() -> CreateSessionResponse:
    """
    Creates an ephemeral, privacy-preserving citizen session in process RAM.
    Does not persist citizen identity or profile data to PostgreSQL.
    """
    mgr = get_session_manager()
    session = mgr.create_session()
    return CreateSessionResponse(
        session_id=session.session_id,
        expires_at=session.expires_at,
        created_at=session.created_at,
    )


@router.get(
    "/{session_id}",
    response_model=SessionSummary,
    summary="Retrieve citizen session summary",
)
def get_session_summary(session_id: str) -> SessionSummary:
    """
    Returns high-level session status (known fields, declined fields, expiration).
    Omits sensitive citizen values.
    """
    mgr = get_session_manager()
    session = mgr.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )

    return SessionSummary(
        session_id=session.session_id,
        known_fields=session.get_known_field_names(),
        declined_fields=session.get_declined_field_names(),
        asked_fields=list(session.asked_fields),
        need_text=session.need_text,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        profile_version=session.profile_version,
    )


@router.get(
    "/{session_id}/profile",
    response_model=SessionDetailResponse,
    summary="Retrieve citizen session profile facts",
)
def get_session_profile_detail(session_id: str) -> SessionDetailResponse:
    """
    Returns full in-memory profile facts for development / frontend integration.
    """
    mgr = get_session_manager()
    session = mgr.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )

    return SessionDetailResponse(
        session_id=session.session_id,
        profile=session.profile,
        known_fields=session.get_known_field_names(),
        declined_fields=session.get_declined_field_names(),
        asked_fields=list(session.asked_fields),
        need_text=session.need_text,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        profile_version=session.profile_version,
    )


@router.patch(
    "/{session_id}/profile",
    response_model=SessionSummary,
    summary="Update or patch citizen profile facts",
)
def patch_session_profile(
    session_id: str,
    payload: UpdateProfileRequest,
) -> SessionSummary:
    """
    Applies partial profile updates with patch semantics.
    Validates data against Day 14 domain rules (e.g. age bounds).
    Preserves boolean false.
    """
    mgr = get_session_manager()
    try:
        session = mgr.update_profile(
            session_id=session_id,
            patch=payload.profile,
            clear_fields=payload.clear_fields,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )
    except Exception as e:
        logger.warning(f"Profile validation error on session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid profile data: {str(e)}",
        )

    return SessionSummary(
        session_id=session.session_id,
        known_fields=session.get_known_field_names(),
        declined_fields=session.get_declined_field_names(),
        asked_fields=list(session.asked_fields),
        need_text=session.need_text,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        profile_version=session.profile_version,
    )


@router.post(
    "/{session_id}/decline-field",
    response_model=SessionSummary,
    summary="Record citizen refusal to answer a specific field",
)
def decline_session_field(
    session_id: str,
    payload: DeclineFieldRequest,
) -> SessionSummary:
    """
    Marks a field as DECLINED by citizen, avoiding repeated interrogation.
    """
    mgr = get_session_manager()
    try:
        session = mgr.decline_field(
            session_id=session_id,
            field_name=payload.field_name,
            reason=payload.reason,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )

    return SessionSummary(
        session_id=session.session_id,
        known_fields=session.get_known_field_names(),
        declined_fields=session.get_declined_field_names(),
        asked_fields=list(session.asked_fields),
        need_text=session.need_text,
        expires_at=session.expires_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        profile_version=session.profile_version,
    )


@router.post(
    "/{session_id}/discover",
    response_model=CitizenDiscoveryResponse,
    summary="Run scheme discovery using current session profile and receive next question",
)
def discover_with_session(
    session_id: str,
    payload: Optional[SessionDiscoverPayload] = None,
    db: Session = Depends(get_db),
) -> CitizenDiscoveryResponse:
    """
    Executes candidate discovery, cached rule evaluation, and next-question selection.
    Returns citizen-ready presentation structures and next question.
    """
    need = payload.need_text if payload else None
    eval_date = payload.evaluation_date if payload else None

    try:
        return CitizenDiscoveryFacade.discover_for_citizen(
            session_id=session_id,
            db_session=db,
            need_text=need,
            evaluation_date=eval_date,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Explicitly delete citizen session",
)
def delete_session(session_id: str) -> Dict[str, str]:
    """
    Explicitly removes temporary session state from RAM.
    """
    mgr = get_session_manager()
    deleted = mgr.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or already deleted.",
        )
    return {"status": "deleted", "session_id": session_id}
