"""
YojanSetu - Day 23: Voice Activity Detector (VAD) Interface.

Defines the abstract interface for offline voice activity detection.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union
import numpy as np

from app.audio.schemas import VADResult


class VoiceActivityDetector(ABC):
    """Abstract interface for local Voice Activity Detection."""

    @abstractmethod
    def detect_speech_samples(
        self, samples: np.ndarray, sample_rate: int
    ) -> VADResult:
        """
        Runs VAD on floating-point PCM audio array [-1.0, 1.0].

        Args:
            samples: 1D numpy array of audio samples.
            sample_rate: Audio sample rate in Hz (typically 16000).

        Returns:
            VADResult with speech presence, raw segments, durations, and probabilities.
        """
        pass

    @abstractmethod
    def detect_speech_file(self, audio_path: Union[str, Path]) -> VADResult:
        """
        Runs VAD on an audio file.

        Args:
            audio_path: Path to canonical WAV audio file.

        Returns:
            VADResult.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the VAD model is loaded and ready for inference."""
        pass
