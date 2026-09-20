"""
YojanSetu - Day 27: Citizen Voice Turn API Router.

Exposes REST endpoints for citizen speech interaction:
1. POST /citizen/sessions/{session_id}/voice-turn - Submits audio turn
2. GET  /citizen/sessions/{session_id}/voice/responses/{response_id}/audio - Streams synthesized response
3. POST /citizen/sessions/{session_id}/voice/replay - Re-synthesizes last response without turn mutation
4. GET  /citizen/sessions/{session_id}/voice/status - Diagnostics and engine readiness
"""

import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.sessions.manager import SessionNotFoundError
from app.voice.errors import ConversationConflictError, VoiceTurnActiveError
from app.voice.orchestrator import VoiceConversationOrchestrator, get_voice_orchestrator
from app.voice.schemas import (
    VoiceErrorCode,
    VoiceReplayResponse,
    VoiceStatusResponse,
    VoiceTurnResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/citizen/sessions", tags=["Citizen Voice Flow"])


@router.post(
    "/{session_id}/voice-turn",
    response_model=VoiceTurnResult,
    summary="Submit citizen speech audio for end-to-end voice turn processing",
)
async def submit_voice_turn(
    session_id: str,
    audio: UploadFile = File(..., description="Captured citizen microphone audio (WebM, WAV, OGG)"),
    voice_turn_id: str = Form(..., description="Client-generated turn UUID for idempotency"),
    conversation_version: Optional[int] = Form(None, description="Client known conversation version"),
    orchestrator: VoiceConversationOrchestrator = Depends(get_voice_orchestrator),
    db: Session = Depends(get_db),
) -> VoiceTurnResult:
    """
    Ingests speech audio, executes normalization + VAD + STT, forwards transcript
    to Day 25 ConversationManager, synthesizes TTS response, and returns audio metadata.
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": VoiceErrorCode.INVALID_AUDIO.value, "message": "Uploaded audio file is empty (0 bytes)."},
            )

        return await orchestrator.execute_voice_turn(
            session_id=session_id,
            audio_input=audio_bytes,
            voice_turn_id=voice_turn_id,
            conversation_version=conversation_version,
            filename_hint=audio.filename or "recording.webm",
            db_session=db,
        )

    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": VoiceErrorCode.SESSION_NOT_FOUND.value, "message": f"Session '{session_id}' not found or expired."},
        )
    except VoiceTurnActiveError as vtae:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": vtae.error_code.value, "message": vtae.message},
        )
    except ConversationConflictError as cce:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": cce.error_code.value, "message": cce.message},
        )
    except Exception as exc:
        logger.error(f"Unexpected voice turn error on session '{session_id}': {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": VoiceErrorCode.TURN_PROCESSING_FAILED.value, "message": str(exc)},
        )


@router.get(
    "/{session_id}/voice/responses/{response_id}/audio",
    summary="Fetch synthesized response audio stream for browser playback",
)
def get_response_audio(
    session_id: str,
    response_id: str,
    orchestrator: VoiceConversationOrchestrator = Depends(get_voice_orchestrator),
):
    """
    Streams the ephemeral WAV response audio. Enforces token ownership and TTL.
    Never exposes local storage paths.
    """
    audio_path = orchestrator.response_store.get_response_path(
        session_id=session_id,
        response_id=response_id,
    )
    if not audio_path or not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice response audio not found or has expired.",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"response_{response_id}.wav",
    )


@router.post(
    "/{session_id}/voice/replay",
    response_model=VoiceReplayResponse,
    summary="Replay the last system response without re-executing conversation rules",
)
async def replay_last_response(
    session_id: str,
    orchestrator: VoiceConversationOrchestrator = Depends(get_voice_orchestrator),
    db: Session = Depends(get_db),
) -> VoiceReplayResponse:
    """
    Re-synthesizes the current conversation response without mutating profile facts.
    """
    try:
        return await orchestrator.replay_last_response(session_id=session_id, db_session=db)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": VoiceErrorCode.SESSION_NOT_FOUND.value, "message": f"Session '{session_id}' not found or expired."},
        )


@router.get(
    "/{session_id}/voice/status",
    response_model=VoiceStatusResponse,
    summary="Get voice transport state and model readiness for citizen session",
)
def get_voice_status(
    session_id: str,
    orchestrator: VoiceConversationOrchestrator = Depends(get_voice_orchestrator),
) -> VoiceStatusResponse:
    """
    Returns diagnostic health and transport state for the citizen voice interface.
    """
    return orchestrator.get_voice_status(session_id=session_id)
