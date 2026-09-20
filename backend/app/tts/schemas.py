"""
YojanSetu - Day 26: TTS Schemas, Error Codes, and Data Transfer Objects.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TTSErrorCode(str, Enum):
    """Controlled error codes for TTS operations."""
    TTS_UNAVAILABLE = "TTS_UNAVAILABLE"
    TTS_MODEL_LOAD_FAILED = "TTS_MODEL_LOAD_FAILED"
    TTS_SYNTHESIS_FAILED = "TTS_SYNTHESIS_FAILED"
    TTS_EMPTY_AUDIO = "TTS_EMPTY_AUDIO"
    TTS_EMPTY_TEXT = "TTS_EMPTY_TEXT"
    TTS_TEXT_TOO_LONG = "TTS_TEXT_TOO_LONG"
    TTS_INVALID_LANGUAGE = "TTS_INVALID_LANGUAGE"
    TTS_AUDIO_VALIDATION_FAILED = "TTS_AUDIO_VALIDATION_FAILED"


class TTSAudioFormat(str, Enum):
    """Canonical audio container formats."""
    WAV = "wav"


class TTSResult(BaseModel):
    """
    Structured outcome of a speech synthesis operation.
    Reports concrete latency, audio parameters, and ephemeral path.
    """
    provider: str = Field(description="Name of provider adapter e.g. mms, piper, mock")
    model: str = Field(description="Model identifier or checkpoint name")
    voice: Optional[str] = Field(default=None, description="Voice identifier if multi-voice")
    language: str = Field(default="hi", description="ISO language code")
    duration_ms: float = Field(description="Duration of synthesized audio in milliseconds")
    synthesis_ms: float = Field(description="Time taken to synthesize in milliseconds")
    sample_rate: int = Field(description="Sample rate in Hz (e.g. 16000, 22050)")
    audio_format: str = Field(default="wav", description="Audio container format")
    audio_path: Optional[str] = Field(default=None, description="Filesystem path to generated audio")
    audio_bytes: Optional[bytes] = Field(default=None, description="Raw audio bytes if in-memory")
    cached: bool = Field(default=False, description="True if retrieved from generic prompt cache")
    rtf: Optional[float] = Field(default=None, description="Real-time factor: synthesis_ms / duration_ms")

    def model_post_init(self, __context: Any) -> None:
        if self.rtf is None and self.duration_ms > 0:
            self.rtf = round(self.synthesis_ms / self.duration_ms, 4)


class SynthesizeRequest(BaseModel):
    """API payload requesting text synthesis."""
    text: str = Field(description="Text to synthesize")
    language: str = Field(default="hi", description="Target language ('hi' or 'en')")
    voice: Optional[str] = Field(default=None, description="Optional voice name override")
    speaking_rate: Optional[float] = Field(default=None, description="Speaking rate multiplier (e.g. 0.9, 1.0, 1.1)")
    provider: Optional[str] = Field(default=None, description="Optional provider override ('mms', 'piper', 'mock')")
    is_generic: bool = Field(default=False, description="Whether text is eligible for generic prompt cache")


class TTSBenchmarkSample(BaseModel):
    """Single test sentence definition in benchmark dataset."""
    id: str
    category: str
    display_text: str
    expected_speech_text: str
    critical_terms: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class TTSBenchmarkResult(BaseModel):
    """Evaluated metric for a single benchmark sentence under a specific candidate."""
    sample_id: str
    category: str
    provider: str
    model: str
    voice: Optional[str] = None
    device: str = "cpu"
    display_text: str
    speech_text: str
    synthesis_ms: float
    duration_ms: float
    rtf: float
    sample_rate: int
    peak_amplitude: float
    rms: float
    audio_file: Optional[str] = None
    critical_terms_in_speech: bool = True
    round_trip_transcript: Optional[str] = None
    round_trip_passed: Optional[bool] = None
    notes: Optional[str] = None
