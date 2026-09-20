"""
JanSetu - Day 27: Aggregated Voice Metrics.

Tracks non-PII operational counters and latency statistics across voice turns.
Strict invariant: Never stores citizen speech text, income, demographics, or audio.
"""

from dataclasses import dataclass, field
import threading
from typing import Dict, List


@dataclass
class VoiceMetricsCollector:
    """Thread-safe collector for voice turn latency and error rates."""
    total_voice_turns: int = 0
    no_speech_turns: int = 0
    stt_empty_turns: int = 0
    stt_failure_turns: int = 0
    tts_failure_turns: int = 0
    conflict_turns: int = 0
    replays_served: int = 0

    vad_timings_ms: List[float] = field(default_factory=list)
    stt_timings_ms: List[float] = field(default_factory=list)
    conversation_timings_ms: List[float] = field(default_factory=list)
    tts_timings_ms: List[float] = field(default_factory=list)
    total_timings_ms: List[float] = field(default_factory=list)

    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_turn(
        self,
        vad_ms: float = 0.0,
        stt_ms: float = 0.0,
        conv_ms: float = 0.0,
        tts_ms: float = 0.0,
        total_ms: float = 0.0,
        error_type: str = None,
    ) -> None:
        with self._lock:
            self.total_voice_turns += 1
            if error_type == "NO_SPEECH":
                self.no_speech_turns += 1
            elif error_type == "STT_EMPTY":
                self.stt_empty_turns += 1
            elif error_type == "STT_FAILURE":
                self.stt_failure_turns += 1
            elif error_type == "TTS_FAILURE":
                self.tts_failure_turns += 1
            elif error_type == "CONFLICT":
                self.conflict_turns += 1

            if vad_ms > 0:
                self.vad_timings_ms.append(vad_ms)
            if stt_ms > 0:
                self.stt_timings_ms.append(stt_ms)
            if conv_ms > 0:
                self.conversation_timings_ms.append(conv_ms)
            if tts_ms > 0:
                self.tts_timings_ms.append(tts_ms)
            if total_ms > 0:
                self.total_timings_ms.append(total_ms)

            # Cap rolling window to last 500 records
            if len(self.total_timings_ms) > 500:
                self.total_timings_ms = self.total_timings_ms[-500:]
                self.vad_timings_ms = self.vad_timings_ms[-500:]
                self.stt_timings_ms = self.stt_timings_ms[-500:]
                self.conversation_timings_ms = self.conversation_timings_ms[-500:]
                self.tts_timings_ms = self.tts_timings_ms[-500:]

    def get_summary(self) -> Dict[str, float]:
        with self._lock:
            def _avg(lst: List[float]) -> float:
                return round(sum(lst) / len(lst), 2) if lst else 0.0

            return {
                "total_voice_turns": self.total_voice_turns,
                "no_speech_turns": self.no_speech_turns,
                "stt_empty_turns": self.stt_empty_turns,
                "stt_failure_turns": self.stt_failure_turns,
                "tts_failure_turns": self.tts_failure_turns,
                "replays_served": self.replays_served,
                "average_vad_ms": _avg(self.vad_timings_ms),
                "average_stt_ms": _avg(self.stt_timings_ms),
                "average_conversation_ms": _avg(self.conversation_timings_ms),
                "average_tts_ms": _avg(self.tts_timings_ms),
                "average_turn_response_ms": _avg(self.total_timings_ms),
            }


_voice_metrics_instance = VoiceMetricsCollector()


def get_voice_metrics() -> VoiceMetricsCollector:
    """Returns singleton voice metrics collector."""
    return _voice_metrics_instance
