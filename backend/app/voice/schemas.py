"""
YojanSetu - Day 27: Schemas and DTOs for Voice Loop & Turn Orchestration.

Defines strict contracts for incoming voice turn requests, outgoing results,
audio retrieval descriptors, error classifications, and recovery suggestions.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.conversation.schemas import ConversationResponse
from app.voice.states import VoiceTransportState


class VoiceErrorCode(str, Enum):
    """Error classifications across Voice Input, VAD, STT, Conversation, and TTS layers."""
    # Audio / Input
    MICROPHONE_PERMISSION_DENIED = "MICROPHONE_PERMISSION_DENIED"
    INVALID_AUDIO = "INVALID_AUDIO"
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_TOO_SHORT = "AUDIO_TOO_SHORT"
    AUDIO_DECODE_FAILED = "AUDIO_DECODE_FAILED"

    # Concurrency & Idempotency
    VOICE_TURN_ALREADY_ACTIVE = "VOICE_TURN_ALREADY_ACTIVE"
    CONVERSATION_STATE_CONFLICT = "CONVERSATION_STATE_CONFLICT"

    # STT
    STT_UNAVAILABLE = "STT_UNAVAILABLE"
    STT_FAILED = "STT_FAILED"
    STT_EMPTY_RESULT = "STT_EMPTY_RESULT"

    # Conversation
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    TURN_PROCESSING_FAILED = "TURN_PROCESSING_FAILED"

    # TTS
    TTS_UNAVAILABLE = "TTS_UNAVAILABLE"
    TTS_FAILED = "TTS_FAILED"
    AUDIO_PLAYBACK_FAILED = "AUDIO_PLAYBACK_FAILED"


class VoiceRecoveryAction(str, Enum):
    """Prescribed client recovery strategy for a given error."""
    RETRY_SAME_TURN = "RETRY_SAME_TURN"
    CONTINUE_TEXT_ONLY = "CONTINUE_TEXT_ONLY"
    START_NEW_SESSION = "START_NEW_SESSION"


class VoiceAudioDescriptor(BaseModel):
    """
    Metadata for browser playback of synthesized TTS audio.
    Crucial: Never exposes local server filesystem paths.
    """
    response_id: str = Field(description="Opaque temporary token for audio streaming")
    format: str = Field(default="wav", description="Audio container format (wav)")
    duration_ms: float = Field(description="Audio duration in milliseconds")
    sample_rate: int = Field(default=16000, description="Audio sampling rate in Hz")
    audio_url: str = Field(description="Secure relative API endpoint to fetch audio stream")
    cached: bool = Field(default=False, description="Whether prompt audio was served from generic cache")


class VoiceTranscription(BaseModel):
    """Transcription metadata for client display or verification."""
    text: str = Field(description="Recognized Devanagari / Latin transcript from STT")
    confidence: Optional[float] = Field(default=None, description="STT confidence score if available")
    stt_provider: str = Field(description="Underlying STT engine used (e.g. whisper-tiny)")
    latency_ms: float = Field(default=0.0, description="Transcription latency in milliseconds")


class VoiceTurnTimings(BaseModel):
    """Non-PII diagnostic timing breakdown for performance benchmarking."""
    audio_validation_ms: float = 0.0
    normalization_ms: float = 0.0
    vad_ms: float = 0.0
    stt_ms: float = 0.0
    conversation_ms: float = 0.0
    tts_ms: float = 0.0
    total_processing_ms: float = 0.0


class VoiceTurnResult(BaseModel):
    """
    Unified result of an executed voice turn.
    Returns the Day 25 structured conversation response, transcript,
    and synthesized audio retrieval descriptor.
    """
    session_id: str
    voice_turn_id: str
    voice_state: VoiceTransportState
    conversation: ConversationResponse
    transcription: Optional[VoiceTranscription] = None
    audio: Optional[VoiceAudioDescriptor] = None
    warning: Optional[str] = None
    timings_ms: VoiceTurnTimings = Field(default_factory=VoiceTurnTimings)
    error_code: Optional[VoiceErrorCode] = None
    recovery_action: Optional[VoiceRecoveryAction] = None


class VoiceReplayResponse(BaseModel):
    """Result of re-synthesizing the last trusted system response."""
    session_id: str
    voice_state: VoiceTransportState
    audio: VoiceAudioDescriptor
    speech_text: str
    conversation_version: int


class VoiceStatusResponse(BaseModel):
    """Diagnostics on voice pipeline components, models, and transport readiness."""
    voice_enabled: bool
    current_transport_state: VoiceTransportState
    vad_available: bool
    stt_available: bool
    stt_provider: str
    stt_model: str
    tts_available: bool
    tts_provider: str
    tts_model: str
    active_turn: bool
    conversation_version: int
    pipeline_version: str
