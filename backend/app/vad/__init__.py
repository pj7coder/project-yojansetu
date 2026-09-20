"""
JanSetu - Day 23: Voice Activity Detection Module.
"""

from typing import Optional
from app.audio.config import get_audio_settings
from app.vad.interface import VoiceActivityDetector
from app.vad.silero import SileroVADProvider

_vad_instance: Optional[VoiceActivityDetector] = None


def get_vad_provider(reload: bool = False) -> VoiceActivityDetector:
    """
    Returns singleton VoiceActivityDetector instance.
    Lazy-loads Silero VAD.
    """
    global _vad_instance
    if _vad_instance is None or reload:
        _vad_instance = SileroVADProvider()
    return _vad_instance


__all__ = [
    "VoiceActivityDetector",
    "SileroVADProvider",
    "get_vad_provider",
]
