"""
JanSetu - Day 23: Developer Audio Endpoints.

Protected, development/admin-only endpoints for evaluating the offline
audio preprocessing pipeline, Silero VAD segmentation, and Whisper STT transcription.
Citizen recordings are deleted after processing by default.
"""

import logging
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.audio.config import get_audio_settings
from app.audio.pipeline import AudioProcessingPipeline
from app.audio.schemas import (
    AudioProcessingStatus,
    AudioTranscriptionResult,
    ProcessedAudioResult,
)
from app.audio.transcription import AudioTranscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev/audio", tags=["Audio Development & Testing"])

_pipeline_instance: Optional[AudioProcessingPipeline] = None
_transcription_service_instance: Optional[AudioTranscriptionService] = None


def get_pipeline() -> AudioProcessingPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = AudioProcessingPipeline()
    return _pipeline_instance


def get_transcription_service() -> AudioTranscriptionService:
    global _transcription_service_instance
    if _transcription_service_instance is None:
        _transcription_service_instance = AudioTranscriptionService()
    return _transcription_service_instance


@router.post(
    "/process",
    response_model=ProcessedAudioResult,
    summary="[DEV ONLY] Process audio through validation, normalization, VAD, and segmentation",
)
async def dev_process_audio(
    file: UploadFile = File(..., description="Audio recording file (WAV, MP3, M4A, WebM)"),
):
    """
    Development endpoint for evaluating audio front-end preprocessing.
    Returns acoustic quality metrics, VAD speech boundaries, and segmented intervals.
    Internal temporary file paths are stripped for privacy.
    """
    settings = get_audio_settings()
    pipeline = get_pipeline()

    # Read uploaded bytes safely
    content = await file.read()
    if len(content) > settings.audio_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio payload size ({len(content)} bytes) exceeds maximum limit ({settings.audio_max_upload_bytes} bytes).",
        )

    result = pipeline.process(
        audio_input=content,
        filename_hint=file.filename or "upload.wav",
        slice_audio_files=False,  # No temporary slices needed for inspection
    )

    # Sanitize response: do not expose internal server paths
    sanitized_segments = [
        seg.model_copy(update={"audio_path": None}) for seg in result.segments
    ]
    return result.model_copy(
        update={
            "normalized_audio_path": None,
            "segments": sanitized_segments,
        }
    )


@router.post(
    "/transcribe",
    response_model=AudioTranscriptionResult,
    summary="[DEV ONLY] Full audio front-end + offline STT transcription",
)
async def dev_transcribe_audio(
    file: UploadFile = File(..., description="Audio recording file (WAV, MP3, M4A, WebM)"),
    language: str = Form("hi", description="Language code for STT"),
):
    """
    Development endpoint for end-to-end audio validation, normalization, VAD,
    and transcription using the Day 22 selected STT engine (Whisper tiny INT8).
    Does NOT invoke STT if no speech is detected.
    Citizen audio is immediately deleted after transcription.
    """
    settings = get_audio_settings()
    service = get_transcription_service()

    content = await file.read()
    if len(content) > settings.audio_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio payload size ({len(content)} bytes) exceeds maximum limit ({settings.audio_max_upload_bytes} bytes).",
        )

    result = service.transcribe_audio(
        audio_input=content,
        filename_hint=file.filename or "recording.wav",
        language=language,
    )
    return result
