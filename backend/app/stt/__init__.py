"""
JanSetu - Speech-to-Text (STT) Module.

Provides:
- SpeechToTextProvider abstraction
- AudioNormalizer and TranscriptNormalizer
- Domain-specific critical entity accuracy metrics (Age, Income, District, Negation, Terms)
- STTBenchmarkRunner for offline local evaluation
"""

from app.stt.audio_normalizer import AudioNormalizer, AudioNormalizationError
from app.stt.benchmark import STTBenchmarkRunner
from app.stt.config import STTSettings, get_stt_settings
from app.stt.entity_metrics import EntityMetricsExtractor
from app.stt.interface import SpeechToTextProvider
from app.stt.metrics import BenchmarkMetricsEvaluator, calculate_cer, calculate_wer
from app.stt.schemas import (
    AudioNoiseLevel,
    BenchmarkCategory,
    BenchmarkSample,
    BenchmarkSummary,
    CriticalEntityTarget,
    CriticalFailureItem,
    FieldMatchResult,
    SampleResult,
    STTResult,
    STTSegment,
)
from app.stt.transcript_normalizer import TranscriptNormalizer

__all__ = [
    "AudioNormalizer",
    "AudioNormalizationError",
    "AudioNoiseLevel",
    "BenchmarkCategory",
    "BenchmarkMetricsEvaluator",
    "BenchmarkSample",
    "BenchmarkSummary",
    "CriticalEntityTarget",
    "CriticalFailureItem",
    "EntityMetricsExtractor",
    "FieldMatchResult",
    "SampleResult",
    "SpeechToTextProvider",
    "STTBenchmarkRunner",
    "STTSettings",
    "STTResult",
    "STTSegment",
    "TranscriptNormalizer",
    "calculate_cer",
    "calculate_wer",
    "get_stt_settings",
]
