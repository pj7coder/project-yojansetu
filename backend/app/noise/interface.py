"""
YojanSetu - Day 23: Noise Suppressor Interface.

Defines the abstract base class for audio noise suppression.
Implementations must process audio locally/offline without external network calls.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Union
import numpy as np


class NoiseSuppressor(ABC):
    """Abstract interface for offline audio noise suppression."""

    @abstractmethod
    def suppress_noise(
        self, samples: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, bool]:
        """
        Suppresses background noise from audio samples.

        Args:
            samples: 1D numpy float array in [-1.0, 1.0].
            sample_rate: Sample rate in Hz (e.g. 16000).

        Returns:
            Tuple of (denoised_samples, applied_flag).
        """
        pass

    @abstractmethod
    def suppress_file(
        self, input_path: Union[str, Path], output_path: Union[str, Path]
    ) -> bool:
        """
        Processes an audio file and saves the denoised output to output_path.

        Returns:
            True if noise suppression was applied, False if passthrough/failed.
        """
        pass
