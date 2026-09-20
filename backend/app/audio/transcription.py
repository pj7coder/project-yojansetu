"""
YojanSetu - Day 23: Audio Transcription Composition Service.

Composes the AudioProcessingPipeline and the Day 22 Selected Speech-to-Text Provider
(Whisper INT8 with Devanagari prompt conditioning).
Preserves raw segment transcripts, enforces strict offline privacy,
and avoids invoking STT when no speech is detected.
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Union

from app.audio.config import get_audio_settings
from app.audio.pipeline import AudioProcessingPipeline
from app.audio.schemas import (
    AudioErrorCode,
    AudioProcessingStatus,
    AudioTranscriptionResult,
    ProcessedAudioResult,
    SegmentTranscript,
)
from app.audio.temp_storage import get_temp_storage_manager
from app.stt.config import get_stt_settings
from app.stt.interface import SpeechToTextProvider
from app.stt.providers.whisper import WhisperSTTProvider

logger = logging.getLogger(__name__)

# Lazy singleton for default STT provider
_default_stt_provider: Optional[SpeechToTextProvider] = None


def get_selected_stt_provider() -> SpeechToTextProvider:
    """
    Returns the Day 22 benchmark winner (Whisper tiny INT8 CPU with prompt conditioning).
    Lazy-loaded to preserve FastAPI startup isolation.
    """
    global _default_stt_provider
    if _default_stt_provider is None:
        stt_settings = get_stt_settings()
        logger.info(
            f"Initializing selected STT provider: whisper ({stt_settings.whisper_model}) on {stt_settings.device} with {stt_settings.precision}"
        )
        _default_stt_provider = WhisperSTTProvider(
            model_name=stt_settings.whisper_model,
            device=stt_settings.device,
            precision=stt_settings.precision,
            initial_prompt="नमस्ते राजस्थान सरकार योजना",
        )
    return _default_stt_provider


class AudioTranscriptionService:
    """
    Coordinates offline audio preprocessing, VAD segmentation,
    and Speech-to-Text transcription.
    """

    def __init__(
        self,
        pipeline: Optional[AudioProcessingPipeline] = None,
        stt_provider: Optional[SpeechToTextProvider] = None,
    ):
        self.pipeline = pipeline or AudioProcessingPipeline()
        self._stt_provider = stt_provider
        self.storage = get_temp_storage_manager()

    @property
    def stt(self) -> SpeechToTextProvider:
        if self._stt_provider is None:
            self._stt_provider = get_selected_stt_provider()
        return self._stt_provider

    def transcribe_audio(
        self,
        audio_input: Union[str, Path, bytes],
        filename_hint: str = "recording.wav",
        language: str = "hi",
    ) -> AudioTranscriptionResult:
        """
        Processes audio through pipeline and transcribes speech segments.
        Guarantees cleanup of all temporary audio files after completion.
        """
        t_total_start = time.perf_counter()
        timings = {}

        # 1. Pipeline execution (Validation -> Normalization -> VAD -> Segmentation)
        processed: ProcessedAudioResult = self.pipeline.process(
            audio_input=audio_input,
            filename_hint=filename_hint,
            slice_audio_files=True,
        )
        timings["pipeline_ms"] = processed.processing_time_ms

        # Temporary files to guarantee cleanup
        temp_files_to_clean: List[Path] = []
        if processed.normalized_audio_path:
            temp_files_to_clean.append(Path(processed.normalized_audio_path))
        for seg in processed.segments:
            if seg.audio_path:
                temp_files_to_clean.append(Path(seg.audio_path))

        try:
            # 2. Check pipeline status
            if processed.status == AudioProcessingStatus.NO_SPEECH_DETECTED:
                total_ms = (time.perf_counter() - t_total_start) * 1000.0
                timings["total_ms"] = round(total_ms, 2)
                return AudioTranscriptionResult(
                    status=AudioProcessingStatus.NO_SPEECH_DETECTED,
                    speech_detected=False,
                    text="",
                    segments=[],
                    original_duration_ms=processed.original_duration_ms,
                    speech_duration_ms=0,
                    quality=processed.quality,
                    error_code=AudioErrorCode.NO_SPEECH_DETECTED,
                    timings=timings,
                )

            if processed.status != AudioProcessingStatus.READY_FOR_STT:
                total_ms = (time.perf_counter() - t_total_start) * 1000.0
                timings["total_ms"] = round(total_ms, 2)
                return AudioTranscriptionResult(
                    status=processed.status,
                    speech_detected=False,
                    text="",
                    segments=[],
                    original_duration_ms=processed.original_duration_ms,
                    speech_duration_ms=processed.speech_duration_ms,
                    quality=processed.quality,
                    error_code=processed.error_code,
                    timings=timings,
                )

            # 3. Transcribe each speech segment using Day 22 selected STT engine
            t_stt_start = time.perf_counter()
            segment_transcripts: List[SegmentTranscript] = []

            # Check STT provider readiness
            try:
                provider = self.stt
            except Exception as exc:
                logger.error(f"STT provider initialization failed: {exc}")
                total_ms = (time.perf_counter() - t_total_start) * 1000.0
                timings["total_ms"] = round(total_ms, 2)
                return AudioTranscriptionResult(
                    status=AudioProcessingStatus.STT_UNAVAILABLE,
                    speech_detected=True,
                    text="",
                    segments=[],
                    original_duration_ms=processed.original_duration_ms,
                    speech_duration_ms=processed.speech_duration_ms,
                    quality=processed.quality,
                    error_code=AudioErrorCode.STT_UNAVAILABLE,
                    timings=timings,
                )

            for seg in processed.segments:
                seg_path = Path(seg.audio_path) if seg.audio_path else None
                if not seg_path or not seg_path.exists():
                    logger.warning(f"Missing segment audio file: {seg.segment_id}")
                    continue

                try:
                    stt_res = provider.transcribe(seg_path, language_hint=language)
                    seg_text = stt_res.raw_text.strip()
                    segment_transcripts.append(
                        SegmentTranscript(
                            segment_id=seg.segment_id,
                            start_ms=seg.start_ms,
                            end_ms=seg.end_ms,
                            text=seg_text,
                            language=language,
                        )
                    )
                except Exception as exc:
                    logger.error(f"Segment transcription failed for {seg.segment_id}: {exc}")
                    segment_transcripts.append(
                        SegmentTranscript(
                            segment_id=seg.segment_id,
                            start_ms=seg.start_ms,
                            end_ms=seg.end_ms,
                            text="",
                            language=language,
                        )
                    )

            stt_elapsed_ms = (time.perf_counter() - t_stt_start) * 1000.0
            timings["stt_ms"] = round(stt_elapsed_ms, 2)

            # 4. Chronological combination of segment texts
            combined_text = " ".join(t.text for t in segment_transcripts if t.text).strip()

            # 5. Handle empty STT result despite detected speech
            if not combined_text:
                status = AudioProcessingStatus.STT_EMPTY_RESULT
                err_code = AudioErrorCode.STT_EMPTY_RESULT
            else:
                status = AudioProcessingStatus.TRANSCRIBED
                err_code = None

            total_ms = (time.perf_counter() - t_total_start) * 1000.0
            timings["total_ms"] = round(total_ms, 2)

            return AudioTranscriptionResult(
                status=status,
                speech_detected=True,
                text=combined_text,
                segments=segment_transcripts,
                original_duration_ms=processed.original_duration_ms,
                speech_duration_ms=processed.speech_duration_ms,
                quality=processed.quality,
                error_code=err_code,
                timings=timings,
            )

        finally:
            # 6. Strict audio privacy: always clean up temporary files
            for temp_f in temp_files_to_clean:
                self.storage.cleanup_file(temp_f)
