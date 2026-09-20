"""
YojanSetu - Day 23: Lightweight Audio Quality Analyzer.

Computes basic acoustic quality metrics (RMS level, peak amplitude,
clipping ratio, silence ratio) and flags abnormal conditions (too quiet, clipping).
"""

import logging
import math
from pathlib import Path
from typing import Union
import numpy as np
import soundfile as sf

from app.audio.schemas import AudioQualityMetrics

logger = logging.getLogger(__name__)

# Thresholds for quality flags
QUIET_RMS_THRESHOLD = 0.005  # Below ~ -46 dBFS is considered suspiciously quiet
PEAK_CLIPPING_THRESHOLD = 0.99  # > 99% full scale
CLIPPING_RATIO_THRESHOLD = 0.005  # > 0.5% of samples at ceiling
SILENCE_ENERGY_THRESHOLD = 0.01  # Frame energy for silence estimation


class AudioQualityAnalyzer:
    """Lightweight analyzer for audio signal health and acoustics."""

    def analyze_samples(self, samples: np.ndarray, sample_rate: int) -> AudioQualityMetrics:
        """
        Analyzes 1D floating-point audio array in [-1.0, 1.0].
        """
        if len(samples) == 0:
            return AudioQualityMetrics(
                duration_ms=0.0,
                rms_level=0.0,
                peak_amplitude=0.0,
                clipping_ratio=0.0,
                is_too_quiet=True,
                is_clipping=False,
                estimated_silence_ratio=1.0,
            )

        # Normalize 1D
        if samples.ndim > 1:
            samples = np.mean(samples, axis=1)

        total_samples = len(samples)
        duration_ms = (total_samples / float(sample_rate)) * 1000.0

        # Peak amplitude
        peak = float(np.max(np.abs(samples)))

        # Root Mean Square (RMS)
        rms = float(np.sqrt(np.mean(np.square(samples))))

        # Clipping detection
        clipped_count = int(np.sum(np.abs(samples) >= PEAK_CLIPPING_THRESHOLD))
        clipping_ratio = float(clipped_count / total_samples) if total_samples > 0 else 0.0
        is_clipping = clipping_ratio >= CLIPPING_RATIO_THRESHOLD

        # Quiet detection
        is_too_quiet = rms < QUIET_RMS_THRESHOLD and peak < 0.05

        # Estimated silence ratio via short-time energy (frame-based)
        frame_size = int(sample_rate * 0.02)  # 20ms frames
        silence_ratio = 0.0
        if frame_size > 0 and total_samples >= frame_size:
            num_frames = total_samples // frame_size
            frame_energies = [
                float(np.sqrt(np.mean(np.square(samples[i * frame_size : (i + 1) * frame_size]))))
                for i in range(num_frames)
            ]
            silent_frames = sum(1 for e in frame_energies if e < SILENCE_ENERGY_THRESHOLD)
            silence_ratio = float(silent_frames / num_frames) if num_frames > 0 else 0.0

        return AudioQualityMetrics(
            duration_ms=round(duration_ms, 2),
            rms_level=round(rms, 6),
            peak_amplitude=round(peak, 6),
            clipping_ratio=round(clipping_ratio, 6),
            is_too_quiet=is_too_quiet,
            is_clipping=is_clipping,
            estimated_silence_ratio=round(silence_ratio, 4),
        )

    def analyze_file(self, audio_path: Union[str, Path]) -> AudioQualityMetrics:
        """Reads audio file and computes quality metrics."""
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        try:
            data, sr = sf.read(str(path), dtype="float32")
            return self.analyze_samples(data, sr)
        except Exception as exc:
            logger.warning(f"Audio quality analysis failed for {path}: {exc}")
            return AudioQualityMetrics()
