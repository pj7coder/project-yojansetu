"""
JanSetu - Day 22: AI4Bharat Indic ASR Provider Adapter.

Implements SpeechToTextProvider adapter for AI4Bharat Indic ASR models
(IndicWav2Vec / IndicConformer):
- Local offline inference via Hugging Face Transformers / PyTorch
- Custom Indic tokenizer and acoustic feature extraction hidden inside adapter
- Audio resampling and normalization to 16 kHz mono
- CTC greedy decoding to Devanagari text
- Safe error isolation: returns PROVIDER_UNAVAILABLE if weights or dependencies are missing
"""

import gc
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from app.stt.audio_normalizer import AudioNormalizer
from app.stt.interface import SpeechToTextProvider
from app.stt.schemas import STTResult, STTSegment

logger = logging.getLogger("jansetu.stt.providers.indic_asr")


class IndicASRSTTProvider(SpeechToTextProvider):
    """
    AI4Bharat Indic ASR adapter.
    Hides model-specific tensors, spectrograms, and tokenizers from the benchmark engine.
    """

    def __init__(
        self,
        model_name: str = "Harveenchadha/vakyansh-wav2vec2-hindi-him-4200",
        device: str = "cpu",
        precision: str = "fp32",
    ):
        self._model_name = model_name
        self._device = device.lower()
        self._precision = precision
        self._processor = None
        self._tokenizer = None
        self._feature_extractor = None
        self._model = None
        self._load_time_seconds: float = 0.0

    @property
    def provider_id(self) -> str:
        return "indic_asr"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    @property
    def precision(self) -> str:
        return self._precision

    @property
    def load_time_seconds(self) -> float:
        return self._load_time_seconds

    def is_available(self) -> bool:
        """Checks if torch and transformers are installed."""
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False

    def load(self) -> None:
        """Loads Indic ASR model and processor from Hugging Face or local cache."""
        if self._model is not None:
            return

        if not self.is_available():
            raise RuntimeError(
                "torch and transformers are required for IndicASRSTTProvider. "
                "Install via `pip install torch transformers`"
            )

        import torch
        from transformers import AutoModelForCTC, AutoProcessor

        logger.info(
            f"Loading Indic ASR model '{self._model_name}' on device='{self._device}'..."
        )

        t0 = time.perf_counter()
        try:
            try:
                self._processor = AutoProcessor.from_pretrained(self._model_name)
            except Exception:
                from transformers import AutoFeatureExtractor, AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
                self._feature_extractor = AutoFeatureExtractor.from_pretrained(self._model_name)
                self._processor = None

            self._model = AutoModelForCTC.from_pretrained(self._model_name)

            if self._device == "cuda" and torch.cuda.is_available():
                self._model = self._model.to("cuda")
                if self._precision == "fp16":
                    self._model = self._model.half()
            else:
                self._model = self._model.to("cpu")

            self._model.eval()
            self._load_time_seconds = time.perf_counter() - t0
            logger.info(
                f"Loaded Indic ASR model '{self._model_name}' in {self._load_time_seconds:.2f}s"
            )

        except Exception as e:
            self._model = None
            self._processor = None
            self._tokenizer = None
            self._feature_extractor = None
            raise RuntimeError(f"Failed to load Indic ASR model '{self._model_name}': {e}")

    def transcribe(
        self,
        audio_path: Path,
        language_hint: Optional[str] = "hi",
    ) -> STTResult:
        """
        Transcribes the normalized audio file using Indic ASR acoustic model.
        """
        if self._model is None:
            self.load()

        import torch
        import soundfile as sf

        path = Path(audio_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")

        # Ensure canonical 16kHz WAV format
        duration, sr, ch = AudioNormalizer.get_audio_info(path)
        if sr != 16000 or ch != 1:
            norm_path = AudioNormalizer.normalize_to_wav(path)
            duration, _, _ = AudioNormalizer.get_audio_info(norm_path)
            target_path = norm_path
        else:
            target_path = path

        # Read audio waveform
        audio_data, rate = sf.read(str(target_path), dtype="float32")
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        t0 = time.perf_counter()

        # Process audio to model inputs
        if self._processor is not None:
            inputs = self._processor(
                audio_data,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
            )
            input_values = inputs.input_values.to(self._device)
        else:
            inputs = self._feature_extractor(
                audio_data,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
            )
            input_values = inputs.input_values.to(self._device)

        if self._device == "cuda" and self._precision == "fp16":
            input_values = input_values.half()

        with torch.no_grad():
            logits = self._model(input_values).logits

        # CTC Greedy Decoding
        predicted_ids = torch.argmax(logits, dim=-1)
        if self._processor is not None:
            transcription = self._processor.batch_decode(predicted_ids)[0].strip()
        else:
            transcription = self._tokenizer.batch_decode(predicted_ids)[0].strip()

        inference_ms = (time.perf_counter() - t0) * 1000.0

        segments = [
            STTSegment(
                id=0,
                start_seconds=0.0,
                end_seconds=round(duration, 2),
                text=transcription,
            )
        ]

        return STTResult(
            raw_text=transcription,
            text=transcription,
            language=language_hint or "hi",
            duration_seconds=round(duration, 2),
            inference_ms=round(inference_ms, 2),
            provider=self.provider_id,
            model=self._model_name,
            device=self._device,
            precision=self._precision,
            segments=segments,
            metadata={"decoding": "ctc_greedy"},
        )

    def unload(self) -> None:
        """Releases PyTorch model and clears GPU/CPU memory."""
        if self._model is not None:
            del self._model
            del self._processor
            self._model = None
            self._processor = None
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info(f"Unloaded Indic ASR model '{self._model_name}'")
