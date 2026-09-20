"""
YojanSetu - Day 26: Text-to-Speech Provider Interface.

Defines the abstract contract for all offline TTS engine adapters.
TTS is strictly a voice renderer and must never modify conversation state,
extracted profile facts, or eligibility rules.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.tts.schemas import TTSResult


class TextToSpeechProvider(ABC):
    """
    Abstract Base Class for offline Hindi and multilingual TTS adapters.
    Encapsulates model initialization, memory management, and deterministic synthesis.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier e.g. 'mms', 'piper', 'mock'."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Underlying model checkpoint or voice identifier."""
        pass

    @property
    @abstractmethod
    def default_sample_rate(self) -> int:
        """Native sampling rate of output audio (e.g. 16000 or 22050)."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if dependencies and local assets for this provider are installed."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Returns True if the underlying model weights are currently resident in memory."""
        pass

    @abstractmethod
    def load_model(self) -> None:
        """Loads model weights into memory (CPU/GPU). Idempotent if already loaded."""
        pass

    @abstractmethod
    def unload_model(self) -> None:
        """Unloads model weights and releases memory."""
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        language: str = "hi",
        voice: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSResult:
        """
        Synthesizes normalized plain text into speech audio.

        Args:
            text: Normalized text to speak (must not be raw un-normalized currency/numbers).
            language: Target ISO language code ('hi' or 'en').
            voice: Optional voice checkpoint/speaker ID.
            speaking_rate: Speed multiplier (1.0 = normal).

        Returns:
            TTSResult containing metadata, duration, synthesis latency, and audio.
        """
        pass
