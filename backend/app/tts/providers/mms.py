"""
YojanSetu - Day 26: Meta MMS-TTS Hindi Provider Adapter.

Implements TextToSpeechProvider using Meta's Massively Multilingual Speech (MMS)
VITS model checkpoint for Hindi (facebook/mms-tts-hin). Runs 100% offline on CPU.
"""

import gc
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from app.tts.audio_validation import AudioValidator
from app.tts.interface import TextToSpeechProvider
from app.tts.schemas import TTSErrorCode, TTSResult
from app.tts.temp_storage import get_tts_temp_manager

try:
    import torch
except Exception:
    torch = None

logger = logging.getLogger(__name__)


class MMSHindiTTSProvider(TextToSpeechProvider):
    """
    Adapter for Meta MMS-TTS Hindi (VITS architecture).
    """

    def __init__(
        self,
        model_name: str = "facebook/mms-tts-hin",
        device: str = "cpu",
    ):
        self._model_name = model_name
        self._device = device
        self._model = None
        self._tokenizer = None
        self._sample_rate = 16000

    @property
    def name(self) -> str:
        return "mms"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def default_sample_rate(self) -> int:
        return self._sample_rate

    _cached_available: Optional[bool] = None

    def is_available(self) -> bool:
        """Checks if torch and transformers are importable without loading heavy weights or compiling JIT scripts."""
        if MMSHindiTTSProvider._cached_available is not None:
            return MMSHindiTTSProvider._cached_available
        try:
            import importlib.util
            t_spec = importlib.util.find_spec("transformers")
            torch_spec = importlib.util.find_spec("torch")
            MMSHindiTTSProvider._cached_available = bool(t_spec and torch_spec)
        except Exception:
            MMSHindiTTSProvider._cached_available = False
        return MMSHindiTTSProvider._cached_available

    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def _resolve_model_target(self) -> str:
        local_path = Path(self._model_name)
        if local_path.is_dir() and (local_path / "config.json").is_file():
            return str(local_path.resolve())

        candidate_roots = [
            Path.cwd(),
            Path.cwd() / "backend",
            Path(__file__).resolve().parents[2],
            Path(__file__).resolve().parents[3],
            Path(__file__).resolve().parents[4],
        ]
        for root in candidate_roots:
            cand = root / "storage" / "models" / "mms_tts_hin"
            if (cand / "config.json").is_file():
                return str(cand.resolve())

        return self._model_name

    def load_model(self) -> None:
        """Loads MMS VITS model and tokenizer onto target device."""
        if self.is_loaded():
            return

        model_target = self._resolve_model_target()
        logger.info(f"Loading MMS-TTS model '{model_target}' on {self._device}...")
        t0 = time.perf_counter()
        try:
            from transformers import AutoTokenizer, VitsModel

            self._tokenizer = AutoTokenizer.from_pretrained(model_target)
            self._model = VitsModel.from_pretrained(model_target)
            self._model.to(self._device)
            self._model.eval()

            if hasattr(self._model.config, "sampling_rate"):
                self._sample_rate = int(self._model.config.sampling_rate)

            elapsed = time.perf_counter() - t0
            logger.info(f"MMS-TTS loaded in {elapsed:.2f}s (sampling_rate={self._sample_rate})")
        except Exception as exc:
            logger.error(f"Failed to load MMS-TTS model: {exc}")
            self.unload_model()
            raise RuntimeError(f"{TTSErrorCode.TTS_MODEL_LOAD_FAILED.value}: {exc}")

    def unload_model(self) -> None:
        """Releases model weights and frees CPU memory."""
        self._model = None
        self._tokenizer = None
        gc.collect()
        if torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("MMS-TTS model unloaded from memory.")

    def synthesize(
        self,
        text: str,
        language: str = "hi",
        voice: Optional[str] = None,
        speaking_rate: Optional[float] = None,
    ) -> TTSResult:
        if not text or not text.strip():
            raise ValueError(TTSErrorCode.TTS_EMPTY_TEXT.value)

        if not self.is_loaded():
            self.load_model()

        t0 = time.perf_counter()
        try:
            # Tokenize Hindi text
            inputs = self._tokenizer(text, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            if torch is not None:
                with torch.no_grad():
                    output = self._model(**inputs).waveform
            else:
                output = self._model(**inputs).waveform

            waveform = output.squeeze().cpu().numpy()
        except Exception as exc:
            logger.error(f"MMS-TTS inference failed for text: {exc}")
            raise RuntimeError(f"{TTSErrorCode.TTS_SYNTHESIS_FAILED.value}: {exc}")

        synthesis_ms = (time.perf_counter() - t0) * 1000.0

        # Safe normalize audio volume
        norm_audio = AudioValidator.safe_normalize_volume(waveform, target_peak=0.95)

        # Write to collision-proof ephemeral file
        temp_mgr = get_tts_temp_manager()
        temp_path = temp_mgr.create_temp_file(suffix=".wav", prefix="mms_")
        AudioValidator.write_wav(temp_path, norm_audio, self._sample_rate)

        # Validate generated audio
        _, sr, duration_ms, peak, rms = AudioValidator.validate_and_measure(temp_path)

        return TTSResult(
            provider=self.name,
            model=self._model_name,
            voice=voice or "mms-hindi-standard",
            language=language,
            duration_ms=duration_ms,
            synthesis_ms=synthesis_ms,
            sample_rate=sr,
            audio_format="wav",
            audio_path=str(temp_path),
            cached=False,
        )
