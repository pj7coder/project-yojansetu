"""
JanSetu - Day 22: Mock STT Provider for Testing and Isolation.

Provides deterministic responses and failure simulation for unit testing
and CI/CD pipelines without downloading neural network checkpoints.
"""

from pathlib import Path
import time
from typing import Dict, Optional

from app.stt.audio_normalizer import AudioNormalizer
from app.stt.interface import SpeechToTextProvider
from app.stt.schemas import STTResult, STTSegment


class MockSTTProvider(SpeechToTextProvider):
    """
    Mock STT provider for unit and regression testing.
    Can be programmed with sample_id -> transcript mappings or fallback behavior.
    """

    def __init__(
        self,
        provider_id: str = "mock_provider",
        model_name: str = "mock-model-v1",
        device: str = "cpu",
        simulated_latency_ms: float = 50.0,
        load_time_seconds: float = 0.1,
        transcriptions: Optional[Dict[str, str]] = None,
        raise_on_load: bool = False,
        raise_on_transcribe: bool = False,
    ):
        self._provider_id = provider_id
        self._model_name = model_name
        self._device = device
        self._simulated_latency_ms = simulated_latency_ms
        self._load_time_seconds = load_time_seconds
        self._transcriptions = transcriptions or {}
        self._raise_on_load = raise_on_load
        self._raise_on_transcribe = raise_on_transcribe
        self._is_loaded = False

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    @property
    def load_time_seconds(self) -> float:
        return self._load_time_seconds

    def is_available(self) -> bool:
        return True

    def load(self) -> None:
        if self._raise_on_load:
            raise RuntimeError("Simulated model load failure in MockSTTProvider")
        self._is_loaded = True

    def set_transcript(self, key: str, transcript: str) -> None:
        """Sets expected transcript for audio filename stem or sample ID."""
        self._transcriptions[key] = transcript

    def transcribe(
        self,
        audio_path: Path,
        language_hint: Optional[str] = "hi",
    ) -> STTResult:
        if self._raise_on_transcribe:
            raise RuntimeError("Simulated transcription error in MockSTTProvider")

        path = Path(audio_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")

        duration, _, _ = AudioNormalizer.get_audio_info(path)

        # Lookup transcript by filename stem or generic fallback
        stem = path.stem
        # If stem has '_normalized_16k', check original stem
        orig_stem = stem.replace("_normalized_16k", "")
        text = (
            self._transcriptions.get(stem)
            or self._transcriptions.get(orig_stem)
            or self._transcriptions.get("default", "मेरी उम्र साठ साल है")
        )

        segments = [
            STTSegment(
                id=0,
                start_seconds=0.0,
                end_seconds=round(duration, 2),
                text=text,
                avg_logprob=-0.15,
                no_speech_prob=0.01,
            )
        ]

        return STTResult(
            raw_text=text,
            text=text,
            language=language_hint or "hi",
            duration_seconds=round(duration, 2),
            inference_ms=self._simulated_latency_ms,
            provider=self.provider_id,
            model=self._model_name,
            device=self._device,
            precision="fp32",
            segments=segments,
            metadata={"simulated": True},
        )

    def unload(self) -> None:
        self._is_loaded = False
