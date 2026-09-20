"""
YojanSetu - Day 22: Speech-to-Text Provider Common Abstraction.

Establishes common interface SpeechToTextProvider keeping benchmark
evaluation logic completely decoupled from model internals and dependencies.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from app.stt.schemas import STTResult


class SpeechToTextProvider(ABC):
    """
    Common abstraction for Speech-To-Text local inference providers.
    All providers must implement:
    - load()
    - is_available()
    - transcribe(audio_path, language_hint)
    - unload()
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Provider identifier string (e.g. 'whisper', 'indic_asr')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier or checkpoint name."""
        pass

    @property
    def device(self) -> str:
        """Inference device ('cpu' or 'cuda')."""
        return "cpu"

    @property
    def precision(self) -> str:
        """Inference precision ('int8', 'fp16', 'fp32')."""
        return "int8"

    @abstractmethod
    def load(self) -> None:
        """
        Loads model into memory/device.
        Records model load time.
        Must raise RuntimeError or ProviderUnavailableError if loading fails.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if required library dependencies and model files are present."""
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        language_hint: Optional[str] = None,
    ) -> STTResult:
        """
        Transcribes normalized audio file.
        Returns immutable STTResult with raw_text, latency, and duration.
        """
        pass

    @abstractmethod
    def unload(self) -> None:
        """Releases model weights and frees memory."""
        pass
