"""
YojanSetu - Day 26: Development & Evaluation TTS Routes.

Provides development-only endpoints for synthesizing speech, testing pronunciation,
and inspecting offline TTS provider health.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.tts.schemas import SynthesizeRequest, TTSErrorCode, TTSResult
from app.tts.service import get_speech_synthesis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev/tts", tags=["Dev TTS"])


@router.post("/synthesize", summary="Synthesize arbitrary text into offline speech audio")
async def dev_synthesize(
    payload: SynthesizeRequest,
    format: str = Query(default="json", description="'json' for metadata or 'audio' for WAV stream"),
):
    """
    Synthesizes normalized text using offline TTS providers for development testing.
    """
    service = get_speech_synthesis_service()

    try:
        result: TTSResult = await service.synthesize_text(
            text=payload.text,
            language=payload.language,
            voice=payload.voice,
            speaking_rate=payload.speaking_rate,
            provider_name=payload.provider,
            is_generic=payload.is_generic,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": TTSErrorCode.TTS_EMPTY_TEXT.value, "message": str(val_err)}
        )
    except Exception as exc:
        logger.error(f"Dev TTS synthesis error: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": TTSErrorCode.TTS_SYNTHESIS_FAILED.value, "message": str(exc)}
        )

    if format.lower() == "audio" and result.audio_path:
        return FileResponse(
            path=result.audio_path,
            media_type="audio/wav",
            filename="response.wav",
        )

    return result.model_dump()


@router.get("/status", summary="Get TTS engine availability and provider health")
async def dev_tts_status():
    """
    Returns diagnostics on installed offline TTS providers, active models, and caching.
    """
    service = get_speech_synthesis_service()
    return service.get_status()
