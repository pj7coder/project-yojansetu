"""
Citizen Conversation API Router (Day 25).
Unified conversational turn endpoint powering both typed text and voice speech transcripts.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.conversation.actions import ConversationAction
from app.conversation.manager import get_conversation_manager
from app.conversation.messages import ConversationMessageCatalog
from app.conversation.schemas import (
    ConversationInput,
    ConversationResponse,
    ExpectedInputDescriptor,
)
from app.conversation.states import ConversationState
from app.database.session import get_db
from app.sessions.manager import SessionNotFoundError

logger = logging.getLogger("yojansetu.api.conversation")

router = APIRouter(prefix="/citizen/sessions", tags=["Citizen Conversational Flow"])


@router.post(
    "/{session_id}/turn",
    response_model=ConversationResponse,
    summary="Submit a conversational turn (Text, STT transcript, or Action)",
)
def process_conversation_turn(
    session_id: str,
    payload: ConversationInput,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """
    Executes a single conversational turn in YojanSetu's deterministic state machine:
    - Ingests natural language text or STT transcript.
    - Evaluates confirmation, expected field, need, or query context.
    - Updates temporary RAM session facts.
    - Re-evaluates verified scheme eligibility and selects next action.
    """
    mgr = get_conversation_manager()
    try:
        return mgr.handle_input(session_id=session_id, inp=payload, db_session=db)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )


@router.get(
    "/{session_id}/conversation",
    response_model=ConversationResponse,
    summary="Get current conversation state and prompt (e.g. on page refresh)",
)
def get_conversation_state(
    session_id: str,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """
    Retrieves current active conversational state, prompt, and options for restoration.
    """
    mgr = get_conversation_manager()
    try:
        return mgr.get_current_state(session_id=session_id, db_session=db)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )


@router.post(
    "/{session_id}/start-over",
    response_model=ConversationResponse,
    summary="Reset session profile and restart conversation from beginning",
)
def start_over_conversation(
    session_id: str,
    db: Session = Depends(get_db),
) -> ConversationResponse:
    """
    Clears all temporary profile facts and resets conversation state to WAITING_FOR_NEED.
    """
    mgr = get_conversation_manager()
    try:
        session = mgr.session_mgr.reset_session_conversation(session_id)
        return mgr.initialize_session(session_id, language=session.preferred_language)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )


@router.post(
    "/{session_id}/end",
    response_model=ConversationResponse,
    summary="Explicitly complete and end conversation session",
)
def end_conversation(
    session_id: str,
) -> ConversationResponse:
    """
    Marks the conversational session COMPLETED and clears sensitive temporary facts.
    """
    mgr = get_conversation_manager()
    try:
        session = mgr.session_mgr.require_session(session_id)
        session.conversation_state = ConversationState.COMPLETED.value
        return ConversationResponse(
            session_id=session_id,
            state=ConversationState.COMPLETED,
            action=ConversationAction.END_CONVERSATION,
            message=ConversationMessageCatalog.completed(),
            expected_input=ExpectedInputDescriptor(type="NONE"),
            meta=mgr._build_meta(session, start_time=0.0),
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen session '{session_id}' not found or has expired.",
        )
