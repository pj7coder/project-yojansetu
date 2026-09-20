"""
JanSetu - Day 23: Audio Processing Pipeline.

Orchestrates the offline audio front-end:
1. Safe input validation (size, duration, MIME/format, decode test)
2. Normalization to canonical 16kHz mono 16-bit PCM WAV via Day 22 AudioNormalizer
3. Audio quality analysis (RMS, peak, clipping, silence estimation)
4. Optional local noise suppression
5. Silero VAD speech detection
6. Utterance segmentation & gap merging
7. Clean temporary storage lifecycle
"""

import logging
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple, Union
import numpy as np
import soundfile as sf

from app.audio.config import get_audio_settings
from app.audio.quality import AudioQualityAnalyzer
from app.audio.schemas import (
    AudioErrorCode,
    AudioProcessingStatus,
    AudioQualityMetrics,
    ProcessedAudioResult,
    SpeechSegment,
)
from app.audio.segmentation import UtteranceSegmenter
from app.audio.temp_storage import get_temp_storage_manager
from app.noise import get_noise_suppressor
from app.stt.audio_normalizer import (
    ALLOWED_AUDIO_EXTENSIONS,
    AudioNormalizationError,
    AudioNormalizer,
)
from app.vad import get_vad_provider

logger = logging.getLogger(__name__)

# Global inference semaphore for bounded concurrency
_concurrency_semaphore: Optional[threading.Semaphore] = None


def _get_semaphore() -> threading.Semaphore:
    global _concurrency_semaphore
    if _concurrency_semaphore is None:
        settings = get_audio_settings()
        _concurrency_semaphore = threading.Semaphore(settings.audio_max_concurrent_inference)
    return _concurrency_semaphore


class AudioProcessingPipeline:
    """Orchestrates audio preprocessing before Speech-to-Text inference."""

    def __init__(
        self,
        vad_provider=None,
        noise_suppressor=None,
        quality_analyzer=None,
        segmenter=None,
    ):
        self.settings = get_audio_settings()
        self.storage = get_temp_storage_manager()
        self.vad = vad_provider or get_vad_provider()
        self.noise_suppressor = noise_suppressor or get_noise_suppressor()
        self.quality_analyzer = quality_analyzer or AudioQualityAnalyzer()
        self.segmenter = segmenter or UtteranceSegmenter()

    def validate_audio_file(self, file_path: Path) -> Tuple[bool, Optional[AudioErrorCode], Optional[str]]:
        """
        Validates audio file existence, size, extension, and duration limits.
        """
        if not file_path.exists() or not file_path.is_file():
            return False, AudioErrorCode.INVALID_AUDIO, f"Audio file not found: {file_path}"

        # Extension check
        ext = file_path.suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return False, AudioErrorCode.INVALID_AUDIO, f"Unsupported audio extension '{ext}'. Allowed: {sorted(ALLOWED_AUDIO_EXTENSIONS)}"

        # Size check
        size = file_path.stat().st_size
        if size == 0:
            return False, AudioErrorCode.INVALID_AUDIO, "Audio file is empty (0 bytes)."
        if size > self.settings.audio_max_upload_bytes:
            return False, AudioErrorCode.AUDIO_TOO_LARGE, f"Audio size {size} exceeds limit of {self.settings.audio_max_upload_bytes} bytes."

        # Probe duration and decode validity safely
        try:
            duration_sec, _, _ = AudioNormalizer.get_audio_info(file_path)
        except Exception as exc:
            logger.warning(f"Audio probe failed for {file_path}: {exc}")
            return False, AudioErrorCode.AUDIO_DECODE_FAILED, f"Failed to decode audio file: {exc}"

        if duration_sec > self.settings.audio_max_duration_seconds:
            return False, AudioErrorCode.AUDIO_TOO_LONG, f"Audio duration {duration_sec:.1f}s exceeds limit of {self.settings.audio_max_duration_seconds:.1f}s."

        if (duration_sec * 1000.0) < self.settings.audio_min_duration_ms:
            return False, AudioErrorCode.SPEECH_TOO_SHORT, f"Audio duration {duration_sec*1000:.0f}ms is below minimum {self.settings.audio_min_duration_ms:.0f}ms."

        return True, None, None

    def process(
        self,
        audio_input: Union[str, Path, bytes],
        filename_hint: str = "upload.wav",
        slice_audio_files: bool = True,
    ) -> ProcessedAudioResult:
        """
        Executes complete preprocessing pipeline on audio input.
        Guarantees cleanup of temporary files if exception occurs.
        """
        t_start = time.perf_counter()
        created_temp_files: List[Path] = []

        try:
            # 1. Acquire concurrency semaphore
            sem = _get_semaphore()
            with sem:
                # 2. Materialize input if provided as bytes
                if isinstance(audio_input, bytes):
                    ext = Path(filename_hint).suffix or ".wav"
                    input_path = self.storage.create_temp_file(suffix=ext, prefix="raw_input_")
                    created_temp_files.append(input_path)
                    input_path.write_bytes(audio_input)
                else:
                    input_path = Path(audio_input)

                # 3. Safe validation
                is_valid, err_code, err_msg = self.validate_audio_file(input_path)
                if not is_valid:
                    status = AudioProcessingStatus(err_code.value) if err_code else AudioProcessingStatus.INVALID_AUDIO
                    return ProcessedAudioResult(
                        status=status,
                        error_code=err_code,
                        error_message=err_msg,
                    )

                # 4. Normalization to 16kHz mono 16-bit PCM WAV
                norm_temp = self.storage.create_temp_file(suffix=".wav", prefix="norm_16k_")
                created_temp_files.append(norm_temp)
                try:
                    AudioNormalizer.normalize_to_wav(input_path, output_path=norm_temp)
                except Exception as exc:
                    logger.error(f"Audio normalization failed: {exc}")
                    return ProcessedAudioResult(
                        status=AudioProcessingStatus.AUDIO_DECODE_FAILED,
                        error_code=AudioErrorCode.AUDIO_DECODE_FAILED,
                        error_message=f"Normalization failed: {exc}",
                    )

                # 5. Read normalized samples & compute acoustic quality metrics
                try:
                    samples, sr = sf.read(str(norm_temp), dtype="float32")
                except Exception as exc:
                    return ProcessedAudioResult(
                        status=AudioProcessingStatus.AUDIO_DECODE_FAILED,
                        error_code=AudioErrorCode.AUDIO_DECODE_FAILED,
                        error_message=f"Failed to read normalized audio: {exc}",
                    )

                if samples.ndim > 1:
                    samples = np.mean(samples, axis=1)

                quality_metrics = self.quality_analyzer.analyze_samples(samples, sr)
                total_duration_ms = int(quality_metrics.duration_ms)

                # 6. Optional Noise Suppression
                denoise_applied = False
                if self.settings.noise_suppression_enabled:
                    try:
                        samples, denoise_applied = self.noise_suppressor.suppress_noise(samples, sr)
                    except Exception as exc:
                        logger.warning(f"Noise suppression failed, continuing raw: {exc}")

                # 7. Silero Voice Activity Detection
                if self.settings.vad_enabled:
                    try:
                        vad_res = self.vad.detect_speech_samples(samples, sr)
                    except Exception as exc:
                        logger.error(f"VAD inference failed: {exc}")
                        return ProcessedAudioResult(
                            status=AudioProcessingStatus.VAD_UNAVAILABLE,
                            error_code=AudioErrorCode.VAD_UNAVAILABLE,
                            error_message=f"Voice Activity Detection failed: {exc}",
                            original_duration_ms=total_duration_ms,
                            quality=quality_metrics,
                        )

                    if not vad_res.contains_speech or not vad_res.segments:
                        elapsed = (time.perf_counter() - t_start) * 1000.0
                        return ProcessedAudioResult(
                            status=AudioProcessingStatus.NO_SPEECH_DETECTED,
                            error_code=AudioErrorCode.NO_SPEECH_DETECTED,
                            error_message="No voice activity detected in audio.",
                            original_duration_ms=total_duration_ms,
                            speech_duration_ms=0,
                            segments=[],
                            quality=quality_metrics,
                            processing_time_ms=round(elapsed, 2),
                        )

                    raw_segments = vad_res.segments
                else:
                    # VAD bypassed: treat whole audio as one segment
                    raw_segments = [
                        SpeechSegment(
                            segment_id="SEG-001",
                            start_ms=0,
                            end_ms=total_duration_ms,
                            duration_ms=total_duration_ms,
                            speech_probability=1.0,
                        )
                    ]

                # 8. Utterance Segmentation & Gap Merging
                merged_segments = self.segmenter.merge_segments(raw_segments)

                if not merged_segments:
                    elapsed = (time.perf_counter() - t_start) * 1000.0
                    return ProcessedAudioResult(
                        status=AudioProcessingStatus.SPEECH_TOO_SHORT,
                        error_code=AudioErrorCode.SPEECH_TOO_SHORT,
                        error_message="Detected speech segments were too short for usable transcription.",
                        original_duration_ms=total_duration_ms,
                        speech_duration_ms=0,
                        segments=[],
                        quality=quality_metrics,
                        processing_time_ms=round(elapsed, 2),
                    )

                # 9. Optionally slice segment WAV files for STT
                final_segments = merged_segments
                if slice_audio_files:
                    final_segments = self.segmenter.slice_segment_audio(samples, sr, merged_segments)
                    for seg in final_segments:
                        if seg.audio_path:
                            created_temp_files.append(Path(seg.audio_path))

                speech_duration_ms = sum(s.duration_ms for s in final_segments)
                elapsed = (time.perf_counter() - t_start) * 1000.0

                return ProcessedAudioResult(
                    status=AudioProcessingStatus.READY_FOR_STT,
                    original_duration_ms=total_duration_ms,
                    speech_duration_ms=speech_duration_ms,
                    segments=final_segments,
                    quality=quality_metrics,
                    normalized_audio_path=str(norm_temp),
                    noise_suppression_used=denoise_applied,
                    vad_used=self.settings.vad_enabled,
                    processing_time_ms=round(elapsed, 2),
                )

        except Exception as exc:
            logger.error(f"Audio processing pipeline unexpected error: {exc}")
            # Guaranteed cleanup on exception
            for f in created_temp_files:
                self.storage.cleanup_file(f)
            return ProcessedAudioResult(
                status=AudioProcessingStatus.AUDIO_PROCESSING_FAILED,
                error_code=AudioErrorCode.AUDIO_PROCESSING_FAILED,
                error_message=str(exc),
            )
