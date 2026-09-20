"""
JanSetu - Day 32: Voice System Quality Evaluation Metrics.

Defines schemas and calculators for:
1. Silero VAD metrics (Recall, precision, false positives, missed speech, short answers, clipping)
2. STT metrics (WER, CER, Age, Income, District, Negation, Term accuracy)
3. Profile extraction metrics (Precision, recall, normalized value, ungrounded inferences)
4. Confirmation safety metrics (Critical confirmation triggers, contextual YES/NO)
5. Multi-turn conversation metrics (State transitions, action correctness, field selection)
6. TTS QA metrics (Number, currency, percentage, date, negation, district, acronym pronunciations)
7. Noise condition slices (Clean, fan, street, echo, soft, fast speech)
8. Latency profiling (VAD, STT, Profile, Conversation, TTS, End-to-End P50/P95)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VADMetrics(BaseModel):
    """Metrics assessing Silero VAD speech detection accuracy."""
    total_samples: int = 0
    speech_detection_recall: float = 0.0
    speech_detection_precision: float = 0.0
    false_positive_count: int = 0  # Speech detected on silence/noise
    missed_utterance_count: int = 0  # Speech missed
    short_answer_retention: float = 0.0  # Retention on short words ("हाँ", "नहीं", etc.)
    speech_start_clipping_count: int = 0
    speech_end_clipping_count: int = 0


class STTMetrics(BaseModel):
    """Metrics assessing literal transcription and critical entity recognition."""
    total_evaluated: int = 0
    wer: float = 0.0  # Word Error Rate
    cer: float = 0.0  # Character Error Rate
    age_accuracy: float = 0.0  # 62 vs 26
    income_accuracy: float = 0.0  # 1.5 lakh vs 2.5 lakh
    number_accuracy: float = 0.0
    district_accuracy: float = 0.0  # Rajasthan district entities
    negation_accuracy: float = 0.0  # "नहीं" preserved and not dropped/hallucinated
    scheme_term_accuracy: float = 0.0


class ProfileExtractionMetrics(BaseModel):
    """Metrics assessing transcript-to-profile extraction and ungrounded inference safety."""
    total_evaluated: int = 0
    field_detection_precision: float = 0.0
    field_detection_recall: float = 0.0
    normalized_value_accuracy: float = 0.0
    false_inference_count: int = 0
    unsupported_inferred_critical_facts: int = 0  # CRITICAL SAFETY TARGET: 0


class ConfirmationMetrics(BaseModel):
    """Metrics assessing critical value confirmation triggers and contextual YES/NO."""
    total_critical_candidates: int = 0
    critical_confirmation_trigger_rate: float = 0.0  # TARGET: 1.0 (100%)
    contextual_yes_accuracy: float = 0.0  # "हाँ" in answering vs confirming
    contextual_no_accuracy: float = 0.0  # "नहीं" in answering vs rejecting


class ConversationMetrics(BaseModel):
    """Metrics assessing multi-turn deterministic conversation flow."""
    total_turns: int = 0
    state_transition_accuracy: float = 0.0
    action_accuracy: float = 0.0
    field_selection_accuracy: float = 0.0
    multi_turn_flow_completion_rate: float = 0.0


class TTSMetrics(BaseModel):
    """Metrics assessing SpeechTextNormalizer pronunciation and boundary audio fidelity."""
    total_evaluated: int = 0
    number_pronunciation_accuracy: float = 0.0  # 62 -> बासठ, 40% -> चालीस प्रतिशत
    currency_pronunciation_accuracy: float = 0.0  # ₹1,50,000 -> एक लाख पचास हजार रुपये
    district_pronunciation_accuracy: float = 0.0  # Udaipur, Dungarpur, Chittorgarh
    acronym_pronunciation_accuracy: float = 0.0  # BPL, SSO, e-Mitra
    negation_audible_accuracy: float = 0.0  # "नहीं"
    boundary_preservation_accuracy: float = 0.0  # "या उससे कम"


class NoiseSliceMetrics(BaseModel):
    """Performance breakdown for a specific acoustic noise condition."""
    noise_condition: str
    sample_count: int = 0
    vad_recall: float = 0.0
    stt_wer: float = 0.0
    critical_value_accuracy: float = 0.0


class VoiceLatencyMetrics(BaseModel):
    """Latency distribution across pipeline stages in milliseconds."""
    vad_avg_ms: float = 0.0
    stt_avg_ms: float = 0.0
    profile_avg_ms: float = 0.0
    conversation_avg_ms: float = 0.0
    tts_avg_ms: float = 0.0
    p50_total_ms: float = 0.0
    p95_total_ms: float = 0.0
    avg_total_ms: float = 0.0


class VoiceCaseEvaluation(BaseModel):
    """Comprehensive evaluation record for a single voice gold case."""
    case_id: str
    split: str
    audio_file: str
    speech_category: str
    noise_condition: str
    reference_transcript: str
    hypothesis_transcript: Optional[str] = None
    expected_field: Optional[str] = None
    extracted_field: Optional[str] = None
    expected_value: Any = None
    extracted_value: Any = None
    expected_state: Optional[str] = None
    actual_state: Optional[str] = None
    expected_action: Optional[str] = None
    actual_action: Optional[str] = None
    vad_match: bool = True
    stt_semantic_pass: bool = True
    profile_match: bool = True
    confirmation_triggered: Optional[bool] = None
    strict_pass: bool = True
    duration_ms: float = 0.0
    failure_codes: List[str] = Field(default_factory=list)


class VoiceBenchmarkSummary(BaseModel):
    """Master benchmark report schema for Day 32 voice evaluation."""
    run_id: str
    gold_version: str
    split: str
    timestamp: str
    duration_seconds: float
    total_voice_cases: int
    total_conversation_cases: int
    strict_turn_pass_rate: float
    end_to_end_critical_value_pass_rate: float
    conversation_state_pass_rate: float
    critical_failures_count: int
    vad_metrics: VADMetrics
    stt_metrics: STTMetrics
    profile_metrics: ProfileExtractionMetrics
    confirmation_metrics: ConfirmationMetrics
    conversation_metrics: ConversationMetrics
    tts_metrics: TTSMetrics
    noise_slices: Dict[str, NoiseSliceMetrics] = Field(default_factory=dict)
    latency_metrics: VoiceLatencyMetrics
    offline_functional: bool = True
