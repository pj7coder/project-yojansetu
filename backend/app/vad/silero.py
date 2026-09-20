"""
YojanSetu - Day 23: Silero VAD Provider.

Local, offline Voice Activity Detection using Silero VAD TorchScript JIT model.
Lazy-loaded to ensure zero memory or startup overhead until needed.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union
import logging
import numpy as np
import soundfile as sf

try:
    import torch
except Exception:
    torch = None

from app.audio.config import get_audio_settings
from app.audio.schemas import SpeechSegment, VADResult
from app.vad.interface import VoiceActivityDetector

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512  # 32 ms at 16 kHz
SUPPORTED_SAMPLE_RATE = 16000


class SileroVADProvider(VoiceActivityDetector):
    """
    Offline Silero VAD implementation running on CPU TorchScript JIT.
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        threshold: Optional[float] = None,
        min_speech_ms: Optional[int] = None,
        min_silence_ms: Optional[int] = None,
        speech_pad_ms: Optional[int] = None,
        max_speech_seconds: Optional[float] = None,
    ):
        settings = get_audio_settings()
        self.threshold = threshold if threshold is not None else settings.vad_threshold
        self.min_speech_ms = min_speech_ms if min_speech_ms is not None else settings.vad_min_speech_ms
        self.min_silence_ms = min_silence_ms if min_silence_ms is not None else settings.vad_min_silence_ms
        self.speech_pad_ms = speech_pad_ms if speech_pad_ms is not None else settings.vad_speech_pad_ms
        self.max_speech_seconds = max_speech_seconds if max_speech_seconds is not None else settings.vad_max_speech_seconds

        self._model_path = model_path or settings.vad_model_path
        self._model: Optional[torch.jit.ScriptModule] = None
        self._is_loaded = False

    def _resolve_model_path(self) -> Path:
        """Finds the local silero_vad.jit model file."""
        candidates = []
        if self._model_path:
            candidates.append(Path(self._model_path))

        # Check standard relative paths
        candidates.extend([
            Path("models/silero-vad/silero_vad.jit"),
            Path("../models/silero-vad/silero_vad.jit"),
            Path("../../models/silero-vad/silero_vad.jit"),
        ])

        # Check torch hub cache
        hub_dir = Path(torch.hub.get_dir()) / "snakers4_silero-vad_master" / "src" / "silero_vad" / "data" / "silero_vad.jit"
        candidates.append(hub_dir)

        for cand in candidates:
            if cand.exists() and cand.is_file():
                return cand.resolve()

        raise FileNotFoundError(
            f"Silero VAD model file not found in any candidate locations: {candidates}"
        )

    def _load_model(self) -> torch.jit.ScriptModule:
        """Lazy-loads the TorchScript JIT model onto CPU with 1 thread."""
        if self._model is None:
            model_file = self._resolve_model_path()
            logger.info(f"Loading Silero VAD model from {model_file}")
            torch.set_num_threads(1)
            model = torch.jit.load(str(model_file), map_location=torch.device("cpu"))
            model.eval()
            self._model = model
            self._is_loaded = True
            logger.info("Silero VAD model loaded successfully")
        return self._model

    def is_available(self) -> bool:
        try:
            self._load_model()
            return True
        except Exception as exc:
            logger.warning(f"Silero VAD unavailable: {exc}")
            return False

    def detect_speech_samples(
        self, samples: np.ndarray, sample_rate: int = SUPPORTED_SAMPLE_RATE
    ) -> VADResult:
        """
        Runs chunk-based VAD inference across 16 kHz audio samples.
        """
        if sample_rate != SUPPORTED_SAMPLE_RATE:
            raise ValueError(f"Silero VAD requires {SUPPORTED_SAMPLE_RATE} Hz, got {sample_rate} Hz.")

        if samples.ndim > 1:
            samples = np.mean(samples, axis=1)

        total_samples = len(samples)
        total_duration_ms = int((total_samples / sample_rate) * 1000)

        if total_samples < CHUNK_SIZE:
            return VADResult(
                contains_speech=False,
                speech_probability_summary={"mean": 0.0, "max": 0.0, "min": 0.0},
                segments=[],
                speech_duration_ms=0,
                silence_duration_ms=total_duration_ms,
                speech_ratio=0.0,
                vad_used=True,
            )

        model = self._load_model()
        if hasattr(model, "reset_states"):
            model.reset_states()

        # Step 1: Compute chunk probabilities
        chunk_times_ms: List[int] = []
        chunk_probs: List[float] = []

        num_chunks = total_samples // CHUNK_SIZE
        for i in range(num_chunks):
            start_idx = i * CHUNK_SIZE
            end_idx = start_idx + CHUNK_SIZE
            chunk_data = samples[start_idx:end_idx].astype(np.float32)
            chunk_tensor = torch.from_numpy(chunk_data).unsqueeze(0)

            with torch.no_grad():
                prob = float(model(chunk_tensor, sample_rate).item())

            chunk_times_ms.append(int((start_idx / sample_rate) * 1000))
            chunk_probs.append(prob)

        if not chunk_probs:
            return VADResult(
                contains_speech=False,
                speech_probability_summary={"mean": 0.0, "max": 0.0, "min": 0.0},
                segments=[],
                speech_duration_ms=0,
                silence_duration_ms=total_duration_ms,
                speech_ratio=0.0,
                vad_used=True,
            )

        # Step 2: State machine for speech interval detection
        # Hysteresis: trigger speech at threshold, release at neg_threshold
        neg_threshold = max(0.15, self.threshold - 0.15)
        min_silence_chunks = max(1, int((self.min_silence_ms / 1000.0) * (sample_rate / CHUNK_SIZE)))
        chunk_duration_ms = int((CHUNK_SIZE / sample_rate) * 1000)

        raw_segments: List[Tuple[int, int, float]] = []  # (start_ms, end_ms, avg_prob)
        in_speech = False
        speech_start_idx = 0
        silence_chunk_count = 0
        current_probs: List[float] = []

        for idx, prob in enumerate(chunk_probs):
            if prob >= self.threshold:
                if not in_speech:
                    in_speech = True
                    speech_start_idx = idx
                    current_probs = [prob]
                    silence_chunk_count = 0
                else:
                    current_probs.append(prob)
                    silence_chunk_count = 0
            elif prob < neg_threshold:
                if in_speech:
                    silence_chunk_count += 1
                    current_probs.append(prob)
                    if silence_chunk_count >= min_silence_chunks:
                        # End of speech segment (excluding silence chunks)
                        speech_end_idx = idx - silence_chunk_count + 1
                        seg_start_ms = chunk_times_ms[speech_start_idx]
                        seg_end_ms = chunk_times_ms[speech_end_idx] + chunk_duration_ms
                        avg_p = float(np.mean(current_probs[:-silence_chunk_count])) if len(current_probs) > silence_chunk_count else float(prob)
                        raw_segments.append((seg_start_ms, seg_end_ms, avg_p))
                        in_speech = False
                        current_probs = []
                        silence_chunk_count = 0
            else:
                # Intermediate probability band
                if in_speech:
                    current_probs.append(prob)

        # Close pending speech at EOF
        if in_speech:
            speech_end_idx = len(chunk_probs) - 1
            seg_start_ms = chunk_times_ms[speech_start_idx]
            seg_end_ms = min(total_duration_ms, chunk_times_ms[speech_end_idx] + chunk_duration_ms)
            avg_p = float(np.mean(current_probs)) if current_probs else float(self.threshold)
            raw_segments.append((seg_start_ms, seg_end_ms, avg_p))

        # Step 3: Apply speech padding and filter by minimum speech duration
        refined_segments: List[SpeechSegment] = []
        seg_counter = 1

        for raw_start, raw_end, avg_prob in raw_segments:
            # Acoustic padding
            padded_start = max(0, raw_start - self.speech_pad_ms)
            padded_end = min(total_duration_ms, raw_end + self.speech_pad_ms)
            dur = padded_end - padded_start

            # Check min speech duration (short answer protection)
            if dur >= self.min_speech_ms:
                refined_segments.append(
                    SpeechSegment(
                        segment_id=f"SEG-{seg_counter:03d}",
                        start_ms=padded_start,
                        end_ms=padded_end,
                        duration_ms=dur,
                        speech_probability=round(avg_prob, 4),
                    )
                )
                seg_counter += 1

        total_speech_ms = sum(s.duration_ms for s in refined_segments)
        silence_ms = max(0, total_duration_ms - total_speech_ms)
        speech_ratio = round(total_speech_ms / float(total_duration_ms), 4) if total_duration_ms > 0 else 0.0

        prob_summary = {
            "mean": round(float(np.mean(chunk_probs)), 4),
            "max": round(float(np.max(chunk_probs)), 4),
            "min": round(float(np.min(chunk_probs)), 4),
        }

        return VADResult(
            contains_speech=len(refined_segments) > 0,
            speech_probability_summary=prob_summary,
            segments=refined_segments,
            speech_duration_ms=total_speech_ms,
            silence_duration_ms=silence_ms,
            speech_ratio=speech_ratio,
            vad_used=True,
        )

    def detect_speech_file(self, audio_path: Union[str, Path]) -> VADResult:
        """Reads audio file and detects speech."""
        p = Path(audio_path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {p}")

        data, sr = sf.read(str(p), dtype="float32")
        return self.detect_speech_samples(data, sr)
