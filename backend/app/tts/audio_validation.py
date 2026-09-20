"""
YojanSetu - Day 26: Audio Output Validation & Postprocessing.

Validates that synthesized audio meets strict quality, duration,
channel, sample rate, and non-empty acoustic constraints.
"""

import io
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import soundfile as sf

from app.tts.schemas import TTSErrorCode

logger = logging.getLogger(__name__)


class AudioValidationError(Exception):
    """Raised when synthesized audio fails validation checks."""
    def __init__(self, code: TTSErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AudioValidator:
    """Validates and measures properties of synthesized audio files/buffers."""

    @classmethod
    def validate_and_measure(
        cls,
        audio_source: Union[Path, str, bytes, np.ndarray],
        sample_rate: Optional[int] = None,
        min_duration_ms: float = 50.0,
        max_duration_ms: float = 60000.0,
    ) -> Tuple[np.ndarray, int, float, float, float]:
        """
        Validates audio content and extracts metrics.

        Returns:
            Tuple of (audio_data, sample_rate, duration_ms, peak_amplitude, rms)

        Raises:
            AudioValidationError if output is empty, corrupted, or out of bounds.
        """
        data: np.ndarray
        sr: int

        try:
            if isinstance(audio_source, (Path, str)):
                p = Path(audio_source)
                if not p.exists() or p.stat().st_size == 0:
                    raise AudioValidationError(
                        TTSErrorCode.TTS_EMPTY_AUDIO,
                        f"Audio file is missing or empty: {audio_source}"
                    )
                data, sr = sf.read(str(p), dtype="float32")
            elif isinstance(audio_source, (bytes, bytearray)):
                if len(audio_source) == 0:
                    raise AudioValidationError(
                        TTSErrorCode.TTS_EMPTY_AUDIO,
                        "Audio buffer is empty (0 bytes)"
                    )
                with io.BytesIO(audio_source) as bio:
                    data, sr = sf.read(bio, dtype="float32")
            elif isinstance(audio_source, np.ndarray):
                if sample_rate is None:
                    raise ValueError("sample_rate must be provided when audio_source is np.ndarray")
                data = audio_source.astype("float32")
                sr = sample_rate
            else:
                raise ValueError(f"Unsupported audio source type: {type(audio_source)}")
        except AudioValidationError:
            raise
        except Exception as exc:
            raise AudioValidationError(
                TTSErrorCode.TTS_AUDIO_VALIDATION_FAILED,
                f"Failed to decode audio stream: {exc}"
            )

        # Convert stereo to mono if needed
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        total_samples = len(data)
        if total_samples == 0:
            raise AudioValidationError(
                TTSErrorCode.TTS_EMPTY_AUDIO,
                "Decoded audio has 0 samples"
            )

        duration_ms = (total_samples / sr) * 1000.0

        if duration_ms < min_duration_ms:
            raise AudioValidationError(
                TTSErrorCode.TTS_EMPTY_AUDIO,
                f"Audio duration ({duration_ms:.1f}ms) is below minimum threshold ({min_duration_ms}ms)"
            )

        if duration_ms > max_duration_ms:
            raise AudioValidationError(
                TTSErrorCode.TTS_TEXT_TOO_LONG,
                f"Audio duration ({duration_ms:.1f}ms) exceeds max limit ({max_duration_ms}ms)"
            )

        peak_amplitude = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data ** 2)))

        # Detect pure silence or imperceptible signal
        if peak_amplitude < 1e-4:
            raise AudioValidationError(
                TTSErrorCode.TTS_EMPTY_AUDIO,
                f"Synthesized audio is silent (peak amplitude: {peak_amplitude:.6f})"
            )

        return data, sr, duration_ms, peak_amplitude, rms

    @classmethod
    def safe_normalize_volume(cls, audio_data: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
        """
        Applies safe peak normalization to prevent clipping and ensure consistent loudness.
        """
        peak = np.max(np.abs(audio_data))
        if peak > 1e-4:
            normalized = audio_data * (target_peak / peak)
            # Clip between -1.0 and 1.0
            return np.clip(normalized, -1.0, 1.0)
        return audio_data

    @classmethod
    def write_wav(cls, output_path: Union[Path, str], audio_data: np.ndarray, sample_rate: int) -> Path:
        """Writes audio data to a 16-bit PCM mono WAV file."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Ensure 1D mono
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)
        sf.write(str(p), audio_data, sample_rate, subtype="PCM_16", format="WAV")
        return p
