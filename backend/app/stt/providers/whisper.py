"""
YojanSetu - Day 22: Faster-Whisper Speech-to-Text Provider.

Implements SpeechToTextProvider using faster-whisper (CTranslate2):
- Offline local execution (no network required after weights download)
- Fast C++ inference with INT8 quantization on CPU / FP16 on GPU
- Segments and token confidence capture
- Raw verbatim transcript preservation
"""

import gc
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from app.stt.audio_normalizer import AudioNormalizer
from app.stt.interface import SpeechToTextProvider
from app.stt.schemas import STTResult, STTSegment

logger = logging.getLogger("yojansetu.stt.providers.whisper")


class WhisperSTTProvider(SpeechToTextProvider):
    """
    Faster-Whisper STT adapter running CTranslate2 engine locally.
    Supports CPU (int8/float32) and CUDA (int8/float16).
    """

    def __init__(
        self,
        model_name: str = "tiny",
        device: str = "cpu",
        precision: str = "int8",
        download_root: Optional[Path] = None,
        initial_prompt: Optional[str] = None,
    ):
        self._model_name = model_name
        self._device = device.lower()
        self._precision = precision
        self._download_root = download_root
        self._initial_prompt = initial_prompt
        self._model = None
        self._load_time_seconds: float = 0.0

    @property
    def provider_id(self) -> str:
        return "whisper"

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
        """Checks if faster_whisper package is importable."""
        try:
            import faster_whisper
            return True
        except ImportError:
            return False

    def load(self) -> None:
        """Loads Whisper model weights via CTranslate2."""
        if self._model is not None:
            return

        if not self.is_available():
            raise RuntimeError(
                "faster_whisper is not installed. Install via `pip install faster-whisper`"
            )

        from faster_whisper import WhisperModel

        # Select compute type
        compute_type = "int8" if self._device == "cpu" else "float16"
        if self._precision in ["int8", "float16", "float32"]:
            compute_type = self._precision

        # Check if local model directory exists
        model_target = self._model_name
        local_path = Path(self._model_name)
        if not local_path.is_dir():
            candidate_roots = [
                Path(__file__).resolve().parents[3],
                Path(__file__).resolve().parents[4],
                Path.cwd(),
                Path.cwd().parent,
            ]
            for root in candidate_roots:
                c1 = root / "models" / f"faster-whisper-{self._model_name}"
                c2 = root / "models" / self._model_name
                if (c1 / "model.bin").is_file():
                    model_target = str(c1.resolve())
                    break
                elif (c2 / "model.bin").is_file():
                    model_target = str(c2.resolve())
                    break
        elif (local_path / "model.bin").is_file():
            model_target = str(local_path.resolve())

        logger.info(
            f"Loading Whisper model '{model_target}' on device='{self._device}' with compute_type='{compute_type}'..."
        )

        t0 = time.perf_counter()
        try:
            self._model = WhisperModel(
                model_target,
                device=self._device,
                compute_type=compute_type,
                cpu_threads=1,
                num_workers=1,
                download_root=str(self._download_root) if self._download_root else None,
            )
            self._load_time_seconds = time.perf_counter() - t0
            logger.info(
                f"Loaded Whisper model '{self._model_name}' successfully in {self._load_time_seconds:.2f}s"
            )
        except Exception as e:
            self._model = None
            raise RuntimeError(f"Failed to load Whisper model '{self._model_name}': {e}")

    def transcribe(
        self,
        audio_path: Path,
        language_hint: Optional[str] = "hi",
    ) -> STTResult:
        """
        Transcribes the normalized audio file.
        Returns immutable STTResult.
        """
        if self._model is None:
            self.load()

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

        t0 = time.perf_counter()
        segments_gen, info = self._model.transcribe(
            str(target_path),
            language=language_hint,
            beam_size=5,
            vad_filter=False,  # Day 22 evaluates raw audio without VAD
            initial_prompt=self._initial_prompt,
        )

        # Materialize segments generator
        segments_list: List[STTSegment] = []
        raw_text_parts: List[str] = []

        for seg in segments_gen:
            seg_text = seg.text.strip()
            if seg_text:
                raw_text_parts.append(seg_text)
                segments_list.append(
                    STTSegment(
                        id=seg.id,
                        start_seconds=round(seg.start, 2),
                        end_seconds=round(seg.end, 2),
                        text=seg_text,
                        avg_logprob=round(seg.avg_logprob, 3) if hasattr(seg, "avg_logprob") else None,
                        no_speech_prob=round(seg.no_speech_prob, 3) if hasattr(seg, "no_speech_prob") else None,
                    )
                )

        inference_ms = (time.perf_counter() - t0) * 1000.0
        full_raw_text = " ".join(raw_text_parts).strip()
        detected_lang = info.language if hasattr(info, "language") else (language_hint or "hi")

        return STTResult(
            raw_text=full_raw_text,
            text=full_raw_text,
            language=detected_lang,
            duration_seconds=round(duration, 2),
            inference_ms=round(inference_ms, 2),
            provider=self.provider_id,
            model=self._model_name,
            device=self._device,
            precision=self._precision,
            segments=segments_list,
            metadata={
                "language_probability": round(info.language_probability, 3) if hasattr(info, "language_probability") else None,
                "beam_size": 5,
            },
        )

    def unload(self) -> None:
        """Frees model from RAM/VRAM."""
        if self._model is not None:
            del self._model
            self._model = None
            gc.collect()
            logger.info(f"Unloaded Whisper model '{self._model_name}'")
