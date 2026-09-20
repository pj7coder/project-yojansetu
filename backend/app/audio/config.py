"""
YojanSetu - Day 23: Offline Audio Front-End & VAD Configuration.

Centralizes configuration parameters for audio limits, normalization,
Silero VAD thresholds, utterance segmentation, noise suppression,
and concurrency guards.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class AudioSettings(BaseSettings):
    """Configuration settings for audio validation, VAD, and preprocessing."""

    # Audio limits & normalization
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_max_duration_seconds: float = 60.0
    audio_min_duration_ms: float = 100.0
    audio_max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB limit for single turn
    audio_temp_dir: Path = Path("storage/audio/tmp")
    audio_debug_retain: bool = False  # Privacy by default: temporary files always deleted

    # Voice Activity Detection (Silero VAD)
    vad_enabled: bool = True
    vad_threshold: float = 0.5  # Speech probability threshold (0.4 - 0.6)
    vad_min_speech_ms: int = 150  # Retains verified short answers (हाँ, नहीं, साठ)
    vad_min_silence_ms: int = 400  # Pause duration to delineate speech boundaries
    vad_speech_pad_ms: int = 250  # Acoustic padding before start and after end
    vad_max_speech_seconds: float = 15.0  # Max single segment length before split
    vad_model_path: Optional[Path] = None  # Local cached JIT / ONNX model

    # Utterance Segmentation
    utterance_merge_gap_ms: int = 350  # Merge gaps smaller than this into one turn

    # Noise Suppression (Optional, disabled by default per benchmark safety)
    noise_suppression_enabled: bool = False
    noise_suppressor_type: str = "passthrough"  # "passthrough" or "spectral"

    # Concurrency & Runtime
    audio_max_concurrent_inference: int = 2  # Bounded semaphore guard
    audio_pipeline_version: str = "1.0"
    vad_config_version: str = "1.0"

    model_config = {
        "env_prefix": "AUDIO_",
        "extra": "ignore",
    }


_audio_settings_instance: Optional[AudioSettings] = None


def get_audio_settings() -> AudioSettings:
    """Returns singleton AudioSettings instance."""
    global _audio_settings_instance
    if _audio_settings_instance is None:
        _audio_settings_instance = AudioSettings()
    return _audio_settings_instance
