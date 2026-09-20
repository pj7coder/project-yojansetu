"""
JanSetu - Day 23: Noise Suppression Module.
"""

from typing import Optional
from app.audio.config import get_audio_settings
from app.noise.interface import NoiseSuppressor
from app.noise.passthrough import PassthroughNoiseSuppressor
from app.noise.spectral import SpectralGatingNoiseSuppressor


def get_noise_suppressor(suppressor_type: Optional[str] = None) -> NoiseSuppressor:
    """
    Factory providing configured noise suppressor.
    Defaults to PassthroughNoiseSuppressor unless explicitly configured.
    """
    settings = get_audio_settings()
    stype = (suppressor_type or settings.noise_suppressor_type).lower()

    if not settings.noise_suppression_enabled or stype == "passthrough":
        return PassthroughNoiseSuppressor()
    elif stype in ("spectral", "spectral_gating"):
        return SpectralGatingNoiseSuppressor()
    else:
        return PassthroughNoiseSuppressor()


__all__ = [
    "NoiseSuppressor",
    "PassthroughNoiseSuppressor",
    "SpectralGatingNoiseSuppressor",
    "get_noise_suppressor",
]
