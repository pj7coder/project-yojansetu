"""
YojanSetu - Day 23: Audio Preprocessing and Transcription Schemas.

Defines Pydantic models and Enums for audio validation, quality analysis,
VAD results, utterance segments, and transcription responses.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AudioProcessingStatus(str, Enum):
    """High-level status for audio processing and transcription pipelines."""
    READY_FOR_STT = "READY_FOR_STT"
    TRANSCRIBED = "TRANSCRIBED"
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    SPEECH_TOO_SHORT = "SPEECH_TOO_SHORT"
    INVALID_AUDIO = "INVALID_AUDIO"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
    AUDIO_DECODE_FAILED = "AUDIO_DECODE_FAILED"
    VAD_UNAVAILABLE = "VAD_UNAVAILABLE"
    STT_UNAVAILABLE = "STT_UNAVAILABLE"
    STT_FAILED = "STT_FAILED"
    STT_EMPTY_RESULT = "STT_EMPTY_RESULT"
    AUDIO_PROCESSING_FAILED = "AUDIO_PROCESSING_FAILED"


class AudioErrorCode(str, Enum):
    """Stable error codes per Day 23 specification."""
    INVALID_AUDIO = "INVALID_AUDIO"
    AUDIO_TOO_LONG = "AUDIO_TOO_LONG"
    AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
    AUDIO_DECODE_FAILED = "AUDIO_DECODE_FAILED"
    NO_SPEECH_DETECTED = "NO_SPEECH_DETECTED"
    SPEECH_TOO_SHORT = "SPEECH_TOO_SHORT"
    VAD_UNAVAILABLE = "VAD_UNAVAILABLE"
    STT_UNAVAILABLE = "STT_UNAVAILABLE"
    STT_FAILED = "STT_FAILED"
    STT_EMPTY_RESULT = "STT_EMPTY_RESULT"
    AUDIO_PROCESSING_FAILED = "AUDIO_PROCESSING_FAILED"


class AudioQualityMetrics(BaseModel):
    """Acoustic quality assessment metrics for input audio."""
    duration_ms: float = 0.0
    rms_level: float = 0.0
    peak_amplitude: float = 0.0
    clipping_ratio: float = 0.0
    is_too_quiet: bool = False
    is_clipping: bool = False
    estimated_silence_ratio: float = 0.0


class SpeechSegment(BaseModel):
    """Detected and merged speech segment ready for transcription."""
    segment_id: str
    start_ms: int
    end_ms: int
    duration_ms: int
    speech_probability: Optional[float] = None
    audio_path: Optional[str] = Field(
        default=None,
        description="Internal temporary file path for extracted segment audio. Never exposed to public API."
    )


class VADResult(BaseModel):
    """Raw result from Voice Activity Detection."""
    contains_speech: bool
    speech_probability_summary: Dict[str, float] = Field(default_factory=dict)
    segments: List[SpeechSegment] = Field(default_factory=list)
    speech_duration_ms: int = 0
    silence_duration_ms: int = 0
    speech_ratio: float = 0.0
    vad_used: bool = True


class ProcessedAudioResult(BaseModel):
    """Result of AudioProcessingPipeline containing validated speech segments."""
    status: AudioProcessingStatus
    error_code: Optional[AudioErrorCode] = None
    error_message: Optional[str] = None
    original_duration_ms: int = 0
    speech_duration_ms: int = 0
    segments: List[SpeechSegment] = Field(default_factory=list)
    quality: AudioQualityMetrics = Field(default_factory=AudioQualityMetrics)
    normalized_audio_path: Optional[str] = Field(
        default=None,
        description="Internal temporary path of canonical 16kHz mono WAV."
    )
    noise_suppression_used: bool = False
    vad_used: bool = True
    processing_time_ms: float = 0.0


class SegmentTranscript(BaseModel):
    """Transcript for an individual speech segment."""
    segment_id: str
    start_ms: int
    end_ms: int
    text: str
    language: str = "hi"


class AudioTranscriptionResult(BaseModel):
    """Final output from AudioTranscriptionService."""
    status: AudioProcessingStatus
    speech_detected: bool
    text: str = ""
    segments: List[SegmentTranscript] = Field(default_factory=list)
    original_duration_ms: int = 0
    speech_duration_ms: int = 0
    quality: Optional[AudioQualityMetrics] = None
    error_code: Optional[AudioErrorCode] = None
    timings: Dict[str, float] = Field(default_factory=dict)
