"""
YojanSetu - Day 26: Mock / Offline Deterministic TTS Provider.

Generates valid 16-bit PCM WAV audio for automated testing, continuous integration,
and degraded text-only fallback operation without requiring neural network weights.
"""

import time
from typing import Optional

import numpy as np

from app.tts.audio_validation import AudioValidator
from app.tts.interface import TextToSpeechProvider
from app.tts.schemas import TTSErrorCode, TTSResult
from app.tts.temp_storage import get_tts_temp_manager


class MockTTSProvider(TextToSpeechProvider):
    """Deterministic offline mock TTS provider for testing and validation."""

    def __init__(self, sample_rate: int = 16000):
        self._sample_rate = sample_rate
        self._loaded = True

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-offline-v1"

    @property
    def default_sample_rate(self) -> int:
        return self._sample_rate

    def is_available(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> None:
        self._loaded = True

    def unload_model(self) -> None:
        self._loaded = False

    def synthesize(
        self,
        text: str,
        language: str = "hi",
        voice: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSResult:
        if not text or not text.strip():
            raise ValueError(TTSErrorCode.TTS_EMPTY_TEXT.value)

        rate = speaking_rate or 1.0
        t0 = time.perf_counter()

        # Generate duration proportional to text length (approx ~70ms per character at 1.0 rate)
        char_count = len(text.strip())
        duration_sec = max(0.5, (char_count * 0.07) / rate)
        num_samples = int(duration_sec * self._sample_rate)

        # Generate a gentle multi-tone acoustic signal with envelope so it is valid speech-like audio
        t = np.linspace(0, duration_sec, num_samples, endpoint=False)
        # 220 Hz fundamental with 440 Hz harmonic
        signal = 0.25 * np.sin(2 * np.pi * 220 * t) + 0.15 * np.sin(2 * np.pi * 440 * t)

        # Smooth attack and decay envelope
        fade_samples = min(int(0.05 * self._sample_rate), num_samples // 4)
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            signal[:fade_samples] *= fade_in
            signal[-fade_samples:] *= fade_out

        # Safe normalize
        norm_signal = AudioValidator.safe_normalize_volume(signal, target_peak=0.85)

        # Write to temporary file
        temp_mgr = get_tts_temp_manager()
        temp_path = temp_mgr.create_temp_file(suffix=".wav", prefix="mock_")
        AudioValidator.write_wav(temp_path, norm_signal, self._sample_rate)

        # Validate
        _, sr, duration_ms, peak, rms = AudioValidator.validate_and_measure(temp_path)
        synthesis_ms = (time.perf_counter() - t0) * 1000.0

        return TTSResult(
            provider=self.name,
            model=self.model_name,
            voice=voice or "mock-neutral",
            language=language,
            duration_ms=duration_ms,
            synthesis_ms=synthesis_ms,
            sample_rate=sr,
            audio_format="wav",
            audio_path=str(temp_path),
            cached=False,
        )
