"""
YojanSetu - Day 23: Utterance Segmentation & Gap Merging.

Refines raw VAD segments into citizen speaking turns:
- Merges micro-gaps shorter than UTTERANCE_MERGE_GAP_MS
- Preserves distinct turns separated by pauses > UTTERANCE_MERGE_GAP_MS
- Splits segments exceeding VAD_MAX_SPEECH_SECONDS
- Enforces chronological ordering
- Slices segment audio files for downstream STT processing
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
import soundfile as sf

from app.audio.config import get_audio_settings
from app.audio.schemas import SpeechSegment
from app.audio.temp_storage import get_temp_storage_manager

logger = logging.getLogger(__name__)


class UtteranceSegmenter:
    """Refines raw speech segments into coherent conversational utterances."""

    def __init__(
        self,
        merge_gap_ms: Optional[int] = None,
        min_speech_ms: Optional[int] = None,
        max_speech_seconds: Optional[float] = None,
    ):
        settings = get_audio_settings()
        self.merge_gap_ms = merge_gap_ms if merge_gap_ms is not None else settings.utterance_merge_gap_ms
        self.min_speech_ms = min_speech_ms if min_speech_ms is not None else settings.vad_min_speech_ms
        self.max_speech_ms = int((max_speech_seconds or settings.vad_max_speech_seconds) * 1000)

    def merge_segments(self, raw_segments: List[SpeechSegment]) -> List[SpeechSegment]:
        """
        Merges adjacent segments separated by short pauses (< merge_gap_ms)
        and preserves chronological ordering.
        """
        if not raw_segments:
            return []

        # Ensure strict chronological ordering by start_ms
        sorted_segs = sorted(raw_segments, key=lambda s: s.start_ms)

        merged: List[SpeechSegment] = []
        current = sorted_segs[0]

        for nxt in sorted_segs[1:]:
            gap = nxt.start_ms - current.end_ms
            combined_duration = nxt.end_ms - current.start_ms

            # Merge if gap is small AND combined length does not exceed max_speech_ms
            if gap <= self.merge_gap_ms and combined_duration <= self.max_speech_ms:
                # Merge into current
                new_start = min(current.start_ms, nxt.start_ms)
                new_end = max(current.end_ms, nxt.end_ms)
                new_dur = new_end - new_start

                # Weighted average speech probability if available
                avg_prob = None
                if current.speech_probability is not None and nxt.speech_probability is not None:
                    p1 = current.speech_probability * current.duration_ms
                    p2 = nxt.speech_probability * nxt.duration_ms
                    avg_prob = round((p1 + p2) / (current.duration_ms + nxt.duration_ms), 4)
                elif current.speech_probability is not None:
                    avg_prob = current.speech_probability
                else:
                    avg_prob = nxt.speech_probability

                current = SpeechSegment(
                    segment_id=current.segment_id,
                    start_ms=new_start,
                    end_ms=new_end,
                    duration_ms=new_dur,
                    speech_probability=avg_prob,
                )
            else:
                merged.append(current)
                current = nxt

        merged.append(current)

        # Step 2: Handle segments exceeding max_speech_ms by splitting
        final_segments: List[SpeechSegment] = []
        seg_idx = 1

        for seg in merged:
            if seg.duration_ms > self.max_speech_ms:
                # Split into chunks of at most max_speech_ms
                start = seg.start_ms
                while start < seg.end_ms:
                    end = min(seg.end_ms, start + self.max_speech_ms)
                    dur = end - start
                    if dur >= self.min_speech_ms:
                        final_segments.append(
                            SpeechSegment(
                                segment_id=f"SEG-{seg_idx:03d}",
                                start_ms=start,
                                end_ms=end,
                                duration_ms=dur,
                                speech_probability=seg.speech_probability,
                            )
                        )
                        seg_idx += 1
                    start = end
            elif seg.duration_ms >= self.min_speech_ms:
                final_segments.append(
                    SpeechSegment(
                        segment_id=f"SEG-{seg_idx:03d}",
                        start_ms=seg.start_ms,
                        end_ms=seg.end_ms,
                        duration_ms=seg.duration_ms,
                        speech_probability=seg.speech_probability,
                    )
                )
                seg_idx += 1

        return final_segments

    def slice_segment_audio(
        self,
        audio_samples: np.ndarray,
        sample_rate: int,
        segments: List[SpeechSegment],
    ) -> List[SpeechSegment]:
        """
        Slices audio samples for each segment and writes them to temporary files.
        Returns the updated segments with audio_path set.
        """
        storage = get_temp_storage_manager()
        sliced_segments: List[SpeechSegment] = []

        total_samples = len(audio_samples)

        for seg in segments:
            start_sample = max(0, int((seg.start_ms / 1000.0) * sample_rate))
            end_sample = min(total_samples, int((seg.end_ms / 1000.0) * sample_rate))

            if end_sample <= start_sample:
                continue

            seg_data = audio_samples[start_sample:end_sample]
            temp_path = storage.create_temp_file(suffix=".wav", prefix=f"{seg.segment_id}_")

            try:
                sf.write(str(temp_path), seg_data, sample_rate, subtype="PCM_16")
                updated_seg = seg.model_copy(update={"audio_path": str(temp_path)})
                sliced_segments.append(updated_seg)
            except Exception as exc:
                logger.error(f"Failed to slice segment audio for {seg.segment_id}: {exc}")
                storage.cleanup_file(temp_path)

        return sliced_segments
