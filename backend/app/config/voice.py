"""
YojanSetu - Day 27: Offline Voice Loop Configuration.

Centralizes configuration parameters for voice transport states, turn timeouts,
silence thresholds, concurrency locks, push-to-talk defaults, and temporary audio TTL.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class VoiceSettings(BaseSettings):
    """Configuration settings for citizen offline voice turn loop."""

    # Master switch
    voice_enabled: bool = True

    # Turn duration limits
    voice_max_turn_seconds: float = 60.0
    voice_min_turn_duration_ms: float = 150.0

    # Client-side / transport silence heuristics
    voice_initial_silence_timeout_ms: int = 7000  # Prompt retry if no speech begins in 7s
    voice_end_silence_ms: int = 1200  # Auto-end threshold after speech has completed

    # Concurrency and locking
    voice_max_concurrent_turns: int = 2  # Max simultaneous voice turns across sessions
    voice_turn_timeout_seconds: float = 30.0  # Lock acquire timeout

    # Playback & Turn-taking policies (Half-duplex)
    voice_auto_play_response: bool = True  # Auto-play YojanSetu responses when voice active
    voice_auto_listen_after_playback: bool = False  # Default to Push-To-Talk for maximum reliability

    # Ephemeral Response Audio Storage & Privacy Lifecycle
    voice_audio_response_ttl_seconds: int = 300  # 5 minutes TTL for synthesized response audio
    voice_response_temp_dir: Path = Path("storage/audio/voice_tmp")

    # Diagnostics & Tracing
    voice_pipeline_version: str = "1.0"
    voice_ui_version: str = "1.0"
    voice_debug: bool = False

    model_config = {
        "env_prefix": "VOICE_",
        "extra": "ignore",
    }


_voice_settings_instance: Optional[VoiceSettings] = None


def get_voice_settings() -> VoiceSettings:
    """Returns singleton VoiceSettings instance."""
    global _voice_settings_instance
    if _voice_settings_instance is None:
        _voice_settings_instance = VoiceSettings()
        _voice_settings_instance.voice_response_temp_dir.mkdir(parents=True, exist_ok=True)
    return _voice_settings_instance
