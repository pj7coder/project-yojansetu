"""
YojanSetu - Day 26: Offline Text-to-Speech (TTS) Configuration.

Centralizes configuration parameters for TTS providers, voice selection,
speaking rates, audio format standards, text length boundaries,
generic prompt caching, and concurrency guards.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class TTSSettings(BaseSettings):
    """Configuration settings for speech synthesis and offline TTS engines."""

    # Master switch
    tts_enabled: bool = True

    # Default provider and model selection
    # Options: "mms", "piper", "mock"
    tts_default_provider: str = "mms"
    tts_default_model: str = "facebook/mms-tts-hin"
    tts_default_voice: Optional[str] = None
    tts_device: str = "cpu"

    # Audio format and rendering standard
    tts_output_format: str = "wav"
    tts_sample_rate: int = 16000  # Default 16 kHz mono (or provider-native)
    tts_speaking_rate: float = 1.0  # 1.0 is default normal rate
    tts_pitch: float = 1.0

    # Input constraints & safety
    tts_max_text_chars: int = 600  # Enforces concise conversational responses
    tts_max_concurrent_inference: int = 2  # Bounded semaphore guard for CPU safety

    # Temporary storage & privacy lifecycle
    tts_temp_dir: Path = Path("storage/audio/tts_tmp")
    tts_debug_retain_audio: bool = False  # Privacy by default: temporary audio deleted immediately

    # Generic Prompt Caching
    tts_cache_generic_prompts: bool = True
    tts_cache_dir: Path = Path("storage/audio/tts_cache")

    # Versioning
    tts_version: str = "1.0"
    speech_text_normalizer_version: str = "1.0"
    tts_benchmark_version: str = "1.0"
    tts_benchmark_dataset_version: str = "1.0"

    model_config = {
        "env_prefix": "TTS_",
        "extra": "ignore",
    }


_tts_settings_instance: Optional[TTSSettings] = None


def get_tts_settings() -> TTSSettings:
    """Returns singleton TTSSettings instance."""
    global _tts_settings_instance
    if _tts_settings_instance is None:
        _tts_settings_instance = TTSSettings()
        # Ensure directories exist
        _tts_settings_instance.tts_temp_dir.mkdir(parents=True, exist_ok=True)
        _tts_settings_instance.tts_cache_dir.mkdir(parents=True, exist_ok=True)
    return _tts_settings_instance
