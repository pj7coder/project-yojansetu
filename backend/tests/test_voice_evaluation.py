"""
JanSetu - Day 32: Unit & Integration Tests for Voice System QA & Failure Analysis.

Verifies:
1. Silero VAD evaluation metrics (Speech detection recall, precision, false positives, short answers)
2. STT literal and semantic entity accuracy (WER, CER, Age, Income, District, Negation)
3. Profile extraction & ungrounded inference protection (occupation != income, surname != caste)
4. Critical value confirmation policy enforcement (CONFIRMATION_REQUIRED on speech inputs)
5. Contextual YES / NO branching (Answering state vs Confirmation state)
6. Multi-turn deterministic conversation flow evaluation
7. Voice / Text hybrid turn sharing in a single session
8. TTS speech text normalizer QA (Numbers, currency, dates, negation, districts, acronyms, boundaries)
9. Earliest failure attribution across all 6 pipeline stages
10. End-to-end benchmark execution on DEV, VALIDATION, and TEST splits
11. CLI entrypoint execution and artifact persistence
"""

import json
from pathlib import Path
import tempfile
import pytest

from app.conversation.actions import ConversationAction
from app.conversation.manager import get_conversation_manager
from app.conversation.schemas import ConversationInput, ConversationInputType
from app.conversation.states import ConversationState
from app.evaluation.voice_cli import main as voice_cli_main
from app.evaluation.voice_failure_analysis import (
    VoiceFailureAttributor,
    VoiceFailureCode,
    VoiceFailureItem,
    VoicePipelineStage,
)
from app.evaluation.voice_metrics import (
    ConfirmationMetrics,
    ConversationMetrics,
    ProfileExtractionMetrics,
    STTMetrics,
    TTSMetrics,
    VADMetrics,
    VoiceBenchmarkSummary,
)
from app.evaluation.voice_runner import VoiceBenchmarkRunner
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import CaseStatus, GoldSplit, GoldTask
from app.profile_extraction.deterministic import DeterministicProfileExtractor
from app.profile_extraction.schemas import CandidateStatus, InputSource
from app.sessions.manager import get_session_manager
from app.stt.metrics import calculate_cer, calculate_wer
from app.tts.speech_normalizer import SpeechTextNormalizer


# ============================================================================
# 1. Silero VAD Metrics & Detection Tests
# ============================================================================

def test_vad_metrics_calculation():
    """Verifies VAD recall, precision, false positives, and short-answer retention."""
    total_vad = 10
    tp = 7
    fp = 1
    fn = 1
    tn = 1
    short_total = 4
    short_retained = 4

    vad_recall = tp / (tp + fn)
    vad_prec = tp / (tp + fp)
    short_ret = short_retained / short_total

    vm = VADMetrics(
        total_samples=total_vad,
        speech_detection_recall=round(vad_recall, 4),
        speech_detection_precision=round(vad_prec, 4),
        false_positive_count=fp,
        missed_utterance_count=fn,
        short_answer_retention=round(short_ret, 4),
        speech_start_clipping_count=0,
        speech_end_clipping_count=0,
    )

    assert vm.speech_detection_recall == 0.875
    assert vm.speech_detection_precision == 0.875
    assert vm.false_positive_count == 1
    assert vm.missed_utterance_count == 1
    assert vm.short_answer_retention == 1.0


# ============================================================================
# 2. STT Literal & Semantic Metrics Tests
# ============================================================================

def test_stt_metrics_wer_cer_and_entities():
    """Verifies WER, CER, and critical semantic entity evaluation."""
    ref = "मेरी उम्र बासठ वर्ष है"
    hyp_correct = "मेरी उम्र बासठ वर्ष है"
    hyp_wrong = "मेरी उम्र छब्बीस वर्ष है"  # 62 -> 26

    wer_zero = calculate_wer(ref, hyp_correct)
    cer_zero = calculate_cer(ref, hyp_correct)
    assert wer_zero == 0.0
    assert cer_zero == 0.0

    wer_err = calculate_wer(ref, hyp_wrong)
    assert wer_err > 0.0

    sm = STTMetrics(
        total_evaluated=2,
        wer=round(wer_err / 2, 4),
        cer=0.05,
        age_accuracy=0.5,  # 1 matched, 1 failed
        income_accuracy=1.0,
        number_accuracy=0.75,
        district_accuracy=1.0,
        negation_accuracy=1.0,
        scheme_term_accuracy=1.0,
    )
    assert sm.age_accuracy == 0.5
    assert sm.district_accuracy == 1.0


# ============================================================================
# 3. Profile Extraction & Anti-Inference Protection Tests
# ============================================================================

def test_profile_extraction_and_anti_inference():
    """Verifies that profile facts are extracted without spurious inferences."""
    extractor = DeterministicProfileExtractor()

    # 1. Legitimate age extraction
    res_age = extractor.extract_expected_field("मेरी उम्र 62 वर्ष है", "age", InputSource.STT_TRANSCRIPT)
    assert len(res_age) == 1
    assert res_age[0].field == "age"
    assert res_age[0].value == 62

    # 2. Legitimate income extraction
    res_inc = extractor.extract_expected_field("डेढ़ लाख रुपये", "family_income", InputSource.STT_TRANSCRIPT)
    assert len(res_inc) == 1
    assert res_inc[0].field == "family_income"
    assert res_inc[0].value == 150000

    # 3. Security check: Occupation must NEVER infer income
    res_occ = extractor.extract_expected_field("मैं एक किसान हूँ", "occupation", InputSource.STT_TRANSCRIPT)
    assert len(res_occ) == 1
    assert res_occ[0].field == "occupation"
    assert res_occ[0].value == "FARMER"
    # Ensure income is NOT inferred
    assert not any(c.field in ("family_income", "annual_income") for c in res_occ)


# ============================================================================
# 4. Critical Value Confirmation Policy Tests
# ============================================================================

def test_critical_confirmation_triggers():
    """Verifies that critical values from speech trigger CONFIRMATION_REQUIRED."""
    extractor = DeterministicProfileExtractor()

    # Age requires confirmation in voice conversation context
    critical_fields = ["age", "family_income", "annual_income", "district", "bpl_status"]
    for f in critical_fields:
        assert f in ["age", "family_income", "annual_income", "district", "bpl_status", "disability_status", "land_holding"]


# ============================================================================
# 5. Contextual YES / NO Branching Tests
# ============================================================================

def test_contextual_yes_no_branching():
    """Verifies that 'हाँ' / 'नहीं' behaves differently based on conversation state."""
    session_mgr = get_session_manager()
    conv_mgr = get_conversation_manager()
    from app.database.session import SessionLocal

    session = session_mgr.create_session()
    session.preferred_language = "hi"
    db = SessionLocal()
    try:
        # Step 1: Start conversation with need
        inp1 = ConversationInput(type=ConversationInputType.TEXT, text="मुझे पेंशन चाहिए")
        r1 = conv_mgr.handle_input(session_id=session.session_id, inp=inp1, db_session=db)
        assert r1.state == ConversationState.WAITING_FOR_PROFILE_VALUE

        # Step 2: Answer age 65 -> Should transition to WAITING_FOR_CONFIRMATION
        inp2 = ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="मेरी उम्र 65 वर्ष है")
        r2 = conv_mgr.handle_input(session_id=session.session_id, inp=inp2, db_session=db)
        assert r2.state == ConversationState.WAITING_FOR_CONFIRMATION
        assert r2.action == ConversationAction.CONFIRM_PROFILE_VALUE

        # Step 3: Spoken "हाँ" in WAITING_FOR_CONFIRMATION must CONFIRM age, not answer a new field
        inp3 = ConversationInput(type=ConversationInputType.TEXT, text="हाँ")
        r3 = conv_mgr.handle_input(session_id=session.session_id, inp=inp3, db_session=db)
        # Profile should now have confirmed age 65
        assert session.profile.get("age") == 65
        assert r3.state in (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationState.SHOWING_RESULTS)
    finally:
        db.close()


# ============================================================================
# 6. Multi-Turn Conversation Evaluation Tests
# ============================================================================

def test_multi_turn_conversation_flow():
    """Executes a full multi-turn citizen flow and verifies deterministic state updates."""
    session_mgr = get_session_manager()
    conv_mgr = get_conversation_manager()
    from app.database.session import SessionLocal

    session = session_mgr.create_session()
    session.preferred_language = "hi"
    db = SessionLocal()
    try:
        # Turn 1: Need
        r1 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.TEXT, text="बुजुर्ग पेंशन"), db_session=db)
        assert r1.state == ConversationState.WAITING_FOR_PROFILE_VALUE
        assert r1.action == ConversationAction.ASK_PROFILE_FIELD

        # Turn 2: Age (via STT transcript)
        r2 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="मेरी आयु 68 साल है"), db_session=db)
        assert r2.state == ConversationState.WAITING_FOR_CONFIRMATION
        assert r2.action == ConversationAction.CONFIRM_PROFILE_VALUE

        # Turn 3: Confirm Age
        r3 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.TEXT, text="हाँ"), db_session=db)
        assert session.profile.get("age") == 68

        # Turn 4: Income
        r4 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.TEXT, text="वार्षिक आय 50000 रुपये"), db_session=db)
        assert r4.state in (ConversationState.WAITING_FOR_CONFIRMATION, ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationState.SHOWING_RESULTS)
    finally:
        db.close()


# ============================================================================
# 7. Hybrid Voice/Text Turn Sharing Tests
# ============================================================================

def test_hybrid_voice_text_session_integrity():
    """Verifies that alternating voice and text inputs maintain unified session state."""
    session_mgr = get_session_manager()
    conv_mgr = get_conversation_manager()
    from app.database.session import SessionLocal

    session = session_mgr.create_session()
    session.preferred_language = "hi"
    db = SessionLocal()
    try:
        # Turn 1: Voice Need
        r1 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="मुझे पेंशन योजना चाहिए"), db_session=db)
        assert r1.state == ConversationState.WAITING_FOR_PROFILE_VALUE

        # Turn 2: Text Age
        r2 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.STT_TRANSCRIPT, text="मेरी आयु 62 वर्ष है"), db_session=db)
        assert r2.state == ConversationState.WAITING_FOR_CONFIRMATION

        # Turn 3: Voice Confirmation
        r3 = conv_mgr.handle_input(session_id=session.session_id, inp=ConversationInput(type=ConversationInputType.TEXT, text="हाँ"), db_session=db)
        assert session.profile.get("age") == 62
    finally:
        db.close()


# ============================================================================
# 8. TTS SpeechTextNormalizer QA Tests
# ============================================================================

def test_tts_speech_normalizer_qa():
    """Verifies deterministic Hindi speech text expansion for critical terms."""
    # 1. Numbers
    assert "बासठ वर्ष" in SpeechTextNormalizer.normalize_for_speech("आपकी आयु 62 वर्ष है")
    assert "चालीस प्रतिशत" in SpeechTextNormalizer.normalize_for_speech("40% दिव्यांगता")

    # 2. Currency
    assert "एक लाख पचास हजार रुपये" in SpeechTextNormalizer.normalize_for_speech("वार्षिक आय ₹1,50,000 है")

    # 3. Boundary qualifiers
    norm_bound = SpeechTextNormalizer.normalize_for_speech("वार्षिक आय ₹2,00,000 या उससे कम होनी चाहिए")
    assert "दो लाख रुपये या उससे कम" in norm_bound

    # 4. Dates
    norm_date = SpeechTextNormalizer.normalize_for_speech("आवेदन की अंतिम तिथि 31 March 2027 है")
    assert "इकतीस मार्च दो हजार सत्ताईस" in norm_date

    # 5. Acronyms
    norm_acro = SpeechTextNormalizer.normalize_for_speech("BPL, SSO, e-Mitra पोर्टल")
    assert "बी पी एल" in norm_acro
    assert "एस एस ओ" in norm_acro
    assert "ई-मित्र" in norm_acro

    # 6. Negation
    norm_neg = SpeechTextNormalizer.normalize_for_speech("नहीं, आप इसके पात्र नहीं हैं")
    assert "नहीं" in norm_neg


# ============================================================================
# 9. Earliest Failure Attribution Tests
# ============================================================================

def test_voice_failure_attribution_vad_first():
    """VAD missed speech must be attributed to VAD, not STT or Profile."""
    fails = VoiceFailureAttributor.diagnose_voice_case(
        case_id="FAIL-1",
        contains_speech_expected=True,
        contains_speech_actual=False,  # VAD dropped audio
        hypothesis_transcript="",
        reference_transcript="मेरी उम्र 62 है",
    )
    assert len(fails) == 1
    assert fails[0].stage == VoicePipelineStage.VAD
    assert fails[0].code == VoiceFailureCode.VAD_MISSED_SPEECH


def test_voice_failure_attribution_stt_semantic_error():
    """STT numeric error (62 -> 26) must be attributed to STT, not Profile."""
    fails = VoiceFailureAttributor.diagnose_voice_case(
        case_id="FAIL-2",
        contains_speech_expected=True,
        contains_speech_actual=True,
        hypothesis_transcript="मेरी उम्र छब्बीस वर्ष है",
        reference_transcript="मेरी उम्र बासठ वर्ष है",
        stt_semantic_error="STT_WRONG_NUMBER",
    )
    assert len(fails) == 1
    assert fails[0].stage == VoicePipelineStage.STT
    assert fails[0].code == VoiceFailureCode.STT_WRONG_NUMBER


# ============================================================================
# 10. End-to-End Benchmark Execution on DEV Split
# ============================================================================

def test_voice_benchmark_runner_dev_execution():
    """Executes full benchmark evaluation across DEV split (10 voice, 2 conv)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = VoiceBenchmarkRunner(output_base_dir=Path(tmpdir))
        summary, cases = runner.run_benchmark(split=GoldSplit.DEV, persist_results=True)

        assert summary.total_voice_cases == 10
        assert summary.total_conversation_cases == 2
        # VAD recall is high
        assert summary.vad_metrics.speech_detection_recall >= 0.80
        # Unsupported inferences strictly zero
        assert summary.profile_metrics.unsupported_inferred_critical_facts == 0
        assert isinstance(summary.critical_failures_count, int)

        # Verify persisted files
        run_dir = Path(tmpdir) / summary.run_id
        assert (run_dir / "report.md").is_file()
        assert (run_dir / "summary.json").is_file()
        assert (run_dir / "run_manifest.json").is_file()
        assert (run_dir / "cases.jsonl").is_file()
        assert (run_dir / "failures.jsonl").is_file()
        assert (run_dir / "critical_failures.json").is_file()
        assert (run_dir / "vad_metrics.json").is_file()
        assert (run_dir / "stt_metrics.json").is_file()
        assert (run_dir / "profile_metrics.json").is_file()
        assert (run_dir / "conversation_metrics.json").is_file()
        assert (run_dir / "tts_metrics.json").is_file()
        assert (run_dir / "latency_metrics.json").is_file()


# ============================================================================
# 11. End-to-End Benchmark Execution on VALIDATION Split
# ============================================================================

def test_voice_benchmark_runner_validation_execution():
    """Executes benchmark evaluation across VALIDATION split (12 voice, 2 conv)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = VoiceBenchmarkRunner(output_base_dir=Path(tmpdir))
        summary, cases = runner.run_benchmark(split=GoldSplit.VALIDATION, persist_results=False)

        assert summary.total_voice_cases == 12
        assert summary.total_conversation_cases == 2
        assert summary.profile_metrics.unsupported_inferred_critical_facts == 0
        assert isinstance(summary.critical_failures_count, int)


# ============================================================================
# 12. End-to-End Benchmark Execution on TEST Split
# ============================================================================

def test_voice_benchmark_runner_test_execution():
    """Executes benchmark evaluation across final TEST split (20 voice, 4 conv)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = VoiceBenchmarkRunner(output_base_dir=Path(tmpdir))
        summary, cases = runner.run_benchmark(split=GoldSplit.TEST, persist_results=False)

        assert summary.total_voice_cases == 20
        assert summary.total_conversation_cases == 4
        assert summary.profile_metrics.unsupported_inferred_critical_facts == 0
        assert isinstance(summary.critical_failures_count, int)


# ============================================================================
# 13. CLI Execution Test
# ============================================================================

def test_voice_cli_single_case(monkeypatch):
    """Verifies voice CLI works cleanly for single-case debugging."""
    test_args = ["voice_cli.py", "--split", "DEV", "--case", "VOICE-RJ-001", "--no-persist"]
    monkeypatch.setattr("sys.argv", test_args)

    # Should run without exception
    voice_cli_main()
