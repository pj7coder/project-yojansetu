"""
JanSetu - Day 22: Speech-to-Text Benchmark Unit & Integration Test Suite.

Tests:
1. AudioNormalizer (16kHz mono baseline, validation, corrupt audio handling)
2. TranscriptNormalizer (Unicode NFC, Devanagari digits, punctuation, whitespace)
3. WER & CER (Levenshtein distance calculation, edge cases)
4. Critical Entity Evaluator:
   - Age extraction (Hindi words, Devanagari numerals, 62 vs 26 detection)
   - Income extraction (डेढ़ लाख, ढाई लाख, compound lakh/thousand, monthly)
   - District extraction (Rajasthan 50-district registry matching)
   - Negation extraction (positive vs negative assertions)
   - Government terms (Jan Aadhaar, e-Mitra, SSO, Pension)
   - Multi-entity compound evaluations
5. Benchmark Runner with MockSTTProvider (end-to-end pipeline & persistence)
6. Failure isolation (corrupt audio sample failure does not crash run)
7. Startup isolation (STT models are NEVER loaded during normal FastAPI startup)
"""

import json
from pathlib import Path
import tempfile
import pytest

from app.stt.audio_normalizer import AudioNormalizationError, AudioNormalizer
from app.stt.benchmark import STTBenchmarkRunner
from app.stt.config import STTSettings
from app.stt.entity_metrics import EntityMetricsExtractor
from app.stt.metrics import (
    BenchmarkMetricsEvaluator,
    calculate_cer,
    calculate_wer,
    levenshtein_distance,
)
from app.stt.providers.mock import MockSTTProvider
from app.stt.schemas import (
    AudioNoiseLevel,
    BenchmarkCategory,
    BenchmarkSample,
    CriticalEntityTarget,
    STTResult,
)
from app.stt.transcript_normalizer import TranscriptNormalizer


# ============================================================================
# 1. TranscriptNormalizer Tests
# ============================================================================

def test_transcript_normalizer_devanagari_digits():
    """Verify Devanagari numerals are converted to Western Arabic digits."""
    text = "मेरी उम्र ६२ साल है और आय १.५ लाख है"
    normalized = TranscriptNormalizer.normalize_digits(text)
    assert "62" in normalized
    assert "1.5" in normalized
    assert "६" not in normalized


def test_transcript_normalizer_punctuation_and_danda():
    """Verify Hindi Purna Viram and Latin punctuation are removed cleanly."""
    text = "हाँ! मैं डूंगरपुर में रहता हूँ। क्या आप जानते हैं? (नहीं)"
    clean = TranscriptNormalizer.remove_punctuation(text)
    assert "।" not in clean
    assert "!" not in clean
    assert "?" not in clean
    assert "(" not in clean
    assert ")" not in clean
    assert "डूंगरपुर" in clean


def test_transcript_normalizer_composite():
    """Verify full normalization pipeline for metric computation."""
    raw = "  मेरी   उम्र  ६२ वर्ष  है।  Family  Income २.५ Lakh है! "
    norm = TranscriptNormalizer.normalize_for_metrics(raw)
    assert norm == "मेरी उम्र 62 वर्ष है family income 2.5 lakh है"


# ============================================================================
# 2. Levenshtein Distance, WER, CER Tests
# ============================================================================

def test_levenshtein_distance_exact_match():
    assert levenshtein_distance(["a", "b", "c"], ["a", "b", "c"]) == 0
    assert levenshtein_distance([], []) == 0


def test_levenshtein_distance_operations():
    # Substitution: 1
    assert levenshtein_distance(["a", "b", "c"], ["a", "x", "c"]) == 1
    # Insertion: 1
    assert levenshtein_distance(["a", "c"], ["a", "b", "c"]) == 1
    # Deletion: 1
    assert levenshtein_distance(["a", "b", "c"], ["a", "c"]) == 1


def test_calculate_wer():
    ref = "मेरी उम्र बासठ साल है"
    # Exact match
    assert calculate_wer(ref, ref) == 0.0

    # 1 substitution out of 5 words -> 0.2
    hyp_sub = "मेरी उम्र छब्बीस साल है"
    assert calculate_wer(ref, hyp_sub) == 0.2

    # Completely different
    assert calculate_wer(ref, "मैं किसान हूँ") > 0.5

    # Empty handling
    assert calculate_wer("", "") == 0.0
    assert calculate_wer(ref, "") == 1.0


def test_calculate_cer():
    ref = "उदयपुर"
    assert calculate_cer(ref, ref) == 0.0
    assert calculate_cer(ref, "डूंगरपुर") > 0.0


# ============================================================================
# 3. Critical Entity Extraction & Semantic Metrics Tests
# ============================================================================

def test_age_extraction_words_and_digits():
    """Verify Hindi number words and digits correctly map to integer age."""
    # Hindi word: बासठ -> 62
    assert EntityMetricsExtractor.extract_age("मेरी उम्र बासठ वर्ष है") == 62
    # Hindi word: अट्ठावन -> 58
    assert EntityMetricsExtractor.extract_age("मैं अट्ठावन साल का हूँ") == 58
    # Hindi word: साठ -> 60
    assert EntityMetricsExtractor.extract_age("मेरी उम्र साठ साल है") == 60
    # Hindi word: छब्बीस -> 26
    assert EntityMetricsExtractor.extract_age("मेरी उम्र छब्बीस साल है") == 26
    # Arabic digits: 62
    assert EntityMetricsExtractor.extract_age("उम्र 62 वर्ष") == 62
    # Devanagari digits: ६२ -> 62
    assert EntityMetricsExtractor.extract_age("आयु ६२ साल") == 62
    # Short answer standalone
    assert EntityMetricsExtractor.extract_age("बासठ") == 62


def test_age_digit_critical_failure_detection():
    """
    CRITICAL CHECK: 62 vs 26 must be detected as critical age failure.
    If reference is 62 and model outputs 26, it must trigger has_critical_failure.
    """
    target = CriticalEntityTarget(age=62)
    pred_text = "मेरी उम्र 26 साल है"
    field_res, all_correct, has_critical = EntityMetricsExtractor.evaluate_sample(pred_text, target)

    assert not all_correct
    assert has_critical
    assert "age" in field_res
    assert field_res["age"].is_critical_failure
    assert field_res["age"].expected == 62
    assert field_res["age"].predicted == 26


def test_income_extraction_varieties():
    """Verify extraction of various Hindi colloquial and numerical income forms."""
    # डेढ़ लाख -> 150000
    assert EntityMetricsExtractor.extract_income("वार्षिक आय डेढ़ लाख रुपये है") == 150000
    # ढाई लाख -> 250000
    assert EntityMetricsExtractor.extract_income("मेरी आय ढाई लाख रुपये है") == 250000
    # दो लाख -> 200000
    assert EntityMetricsExtractor.extract_income("सालाना आय दो लाख रुपये") == 200000
    # एक लाख पचास हजार -> 150000
    assert EntityMetricsExtractor.extract_income("आय एक लाख पचास हजार रुपये") == 150000
    # एक लाख अस्सी हजार -> 180000
    assert EntityMetricsExtractor.extract_income("कुल कमाई एक लाख अस्सी हजार है") == 180000
    # पंद्रह हजार -> 15000
    assert EntityMetricsExtractor.extract_income("मेरी आय पंद्रह हजार रुपये महीना है") == 15000
    # 1.5 लाख -> 150000
    assert EntityMetricsExtractor.extract_income("आय 1.5 लाख है") == 150000
    # 2.5 lakh -> 250000
    assert EntityMetricsExtractor.extract_income("family income 2.5 lakh") == 250000


def test_income_critical_failure_detection():
    """Verify incorrect income threshold triggers critical failure."""
    target = CriticalEntityTarget(family_income=150000)
    # Model predicted 2.5 lakh instead of 1.5 lakh
    pred_text = "वार्षिक आय ढाई लाख रुपये है"
    field_res, all_correct, has_critical = EntityMetricsExtractor.evaluate_sample(pred_text, target)

    assert not all_correct
    assert has_critical
    assert field_res["family_income"].is_critical_failure
    assert field_res["family_income"].expected == 150000
    assert field_res["family_income"].predicted == 250000


def test_district_extraction_rajasthan():
    """Verify Rajasthan districts are matched against canonical registry."""
    assert EntityMetricsExtractor.extract_district("मैं डूंगरपुर में रहता हूँ") == "Dungarpur"
    assert EntityMetricsExtractor.extract_district("उदयपुर जिले से") == "Udaipur"
    assert EntityMetricsExtractor.extract_district("हम चित्तौड़गढ़ के रहने वाले हैं") == "Chittorgarh"
    assert EntityMetricsExtractor.extract_district("बांसवाड़ा") == "Banswara"
    assert EntityMetricsExtractor.extract_district("सवाई माधोपुर") == "Sawai Madhopur"
    assert EntityMetricsExtractor.extract_district("श्रीगंगानगर") == "Sri Ganganagar"


def test_district_critical_failure_detection():
    """Verify wrong district assignment triggers critical failure."""
    target = CriticalEntityTarget(district="Dungarpur")
    pred_text = "मैं उदयपुर में रहता हूँ"
    field_res, all_correct, has_critical = EntityMetricsExtractor.evaluate_sample(pred_text, target)

    assert not all_correct
    assert has_critical
    assert field_res["district"].is_critical_failure
    assert field_res["district"].expected == "Dungarpur"
    assert field_res["district"].predicted == "Udaipur"


def test_negation_extraction():
    """Verify negation detection distinguishes 'नहीं हूँ' from 'हूँ'."""
    assert EntityMetricsExtractor.extract_negation("मैं बीपीएल में नहीं हूँ") is True
    assert EntityMetricsExtractor.extract_negation("मैं बीपीएल में हूँ") is False
    assert EntityMetricsExtractor.extract_negation("हाँ") is False
    assert EntityMetricsExtractor.extract_negation("नहीं") is True
    assert EntityMetricsExtractor.extract_negation("कार्ड बन्योड़ो कोनी") is False  # standard Hindi negation test


def test_negation_critical_failure():
    """A flip from 'नहीं हूँ' to 'हूँ' must trigger critical failure."""
    target = CriticalEntityTarget(negation=True)
    # Model omitted the 'नहीं'
    pred_text = "मैं बीपीएल परिवार में हूँ"
    field_res, all_correct, has_critical = EntityMetricsExtractor.evaluate_sample(pred_text, target)

    assert not all_correct
    assert has_critical
    assert field_res["negation"].is_critical_failure


def test_multi_entity_evaluation():
    """Verify multi-entity utterance passes only if all fields match."""
    target = CriticalEntityTarget(age=62, district="Udaipur", family_income=150000)

    # 1. All correct
    perfect_pred = "मैं उदयपुर जिले से हूँ, मेरी उम्र बासठ साल है और आय डेढ़ लाख है"
    _, all_corr_1, has_crit_1 = EntityMetricsExtractor.evaluate_sample(perfect_pred, target)
    assert all_corr_1 is True
    assert has_crit_1 is False

    # 2. One incorrect (age wrong)
    flawed_pred = "मैं उदयपुर जिले से हूँ, मेरी उम्र छब्बीस साल है और आय डेढ़ लाख है"
    _, all_corr_2, has_crit_2 = EntityMetricsExtractor.evaluate_sample(flawed_pred, target)
    assert all_corr_2 is False
    assert has_crit_2 is True


# ============================================================================
# 4. AudioNormalizer Tests
# ============================================================================

def test_audio_normalizer_validation():
    """Verify extension and existence checks."""
    with pytest.raises(AudioNormalizationError, match="does not exist"):
        AudioNormalizer.validate_file(Path("non_existent_file.wav"))

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"not audio")
        tmp_path = Path(tmp.name)

    try:
        with pytest.raises(AudioNormalizationError, match="Unsupported audio format"):
            AudioNormalizer.validate_file(tmp_path)
    finally:
        tmp_path.unlink()


def test_audio_normalizer_wav_inspection(tmp_path: Path):
    """Verify inspect and normalize functions on valid WAV."""
    from scripts.build_stt_benchmark_dataset import generate_synthesized_wav

    wav_file = tmp_path / "test_tone.wav"
    generate_synthesized_wav(wav_file, duration_sec=1.5, is_noisy=False)

    duration, rate, channels = AudioNormalizer.get_audio_info(wav_file)
    assert round(duration, 1) == 1.5
    assert rate == 16000
    assert channels == 1

    # Normalization should return path to canonical 16k WAV
    norm_wav = AudioNormalizer.normalize_to_wav(wav_file)
    assert norm_wav.exists()
    n_dur, n_rate, n_ch = AudioNormalizer.get_audio_info(norm_wav)
    assert n_rate == 16000
    assert n_ch == 1


# ============================================================================
# 5. Benchmark Runner & Mock Provider Integration Tests
# ============================================================================

def test_benchmark_runner_with_mock_provider(tmp_path: Path):
    """Verify end-to-end benchmark execution and artifact persistence."""
    from scripts.build_stt_benchmark_dataset import generate_synthesized_wav

    # 1. Create a mini dataset
    ds_dir = tmp_path / "dataset"
    audio_dir = ds_dir / "audio"
    audio_dir.mkdir(parents=True)

    wav1 = audio_dir / "sample_1.wav"
    wav2 = audio_dir / "sample_2.wav"
    generate_synthesized_wav(wav1, 2.0)
    generate_synthesized_wav(wav2, 2.0)

    manifest_data = {
        "dataset_version": "1.0",
        "benchmark_version": "1.0",
        "samples": [
            {
                "id": "TEST-001",
                "audio_file": "audio/sample_1.wav",
                "reference": "मेरी उम्र बासठ वर्ष है",
                "language": "hi",
                "category": "AGE",
                "noise_level": "CLEAN",
                "entities": {"age": 62},
            },
            {
                "id": "TEST-002",
                "audio_file": "audio/sample_2.wav",
                "reference": "मैं डूंगरपुर में रहता हूँ",
                "language": "hi",
                "category": "DISTRICT",
                "noise_level": "CLEAN",
                "entities": {"district": "Dungarpur"},
            },
        ],
    }
    with open(ds_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    # 2. Configure Mock Provider with exact predictions
    mock_p = MockSTTProvider(
        provider_id="mock_test",
        model_name="mock-tiny",
        transcriptions={
            "sample_1": "मेरी उम्र बासठ वर्ष है",
            "sample_2": "मैं डूंगरपुर में रहता हूँ",
        },
    )

    out_dir = tmp_path / "results"
    runner = STTBenchmarkRunner()
    samples = runner.load_manifest(ds_dir)

    summary, critical_failures = runner.run_provider_benchmark(
        provider=mock_p,
        samples=samples,
        dataset_path=ds_dir,
        output_dir=out_dir,
        run_id_prefix="test_run",
    )

    # 3. Assert metrics
    assert summary.total_samples == 2
    assert summary.successful_samples == 2
    assert summary.overall_wer == 0.0
    assert summary.age_accuracy == 1.0
    assert summary.district_accuracy == 1.0
    assert summary.total_critical_failures == 0
    assert len(critical_failures) == 0

    # 4. Assert artifacts exist
    run_dirs = list(out_dir.glob("test_run_*"))
    assert len(run_dirs) == 1
    r_dir = run_dirs[0]
    assert (r_dir / "summary.json").is_file()
    assert (r_dir / "samples.jsonl").is_file()
    assert (r_dir / "critical_failures.json").is_file()
    assert (r_dir / "report.md").is_file()


def test_benchmark_runner_sample_failure_isolation(tmp_path: Path):
    """
    CRITICAL CHECK: If a single audio file is missing/corrupted,
    the benchmark must isolate the error and complete the remaining samples.
    """
    from scripts.build_stt_benchmark_dataset import generate_synthesized_wav

    ds_dir = tmp_path / "dataset_iso"
    audio_dir = ds_dir / "audio"
    audio_dir.mkdir(parents=True)

    wav1 = audio_dir / "good.wav"
    generate_synthesized_wav(wav1, 2.0)
    # Note: 'bad.wav' is deliberately omitted to simulate file corruption / missing file

    manifest_data = {
        "dataset_version": "1.0",
        "benchmark_version": "1.0",
        "samples": [
            {
                "id": "SAMPLE-GOOD",
                "audio_file": "audio/good.wav",
                "reference": "मेरी उम्र साठ साल है",
                "language": "hi",
                "category": "AGE",
                "entities": {"age": 60},
            },
            {
                "id": "SAMPLE-BAD",
                "audio_file": "audio/bad_missing.wav",
                "reference": "मेरी उम्र बासठ साल है",
                "language": "hi",
                "category": "AGE",
                "entities": {"age": 62},
            },
        ],
    }
    with open(ds_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    mock_p = MockSTTProvider(
        transcriptions={"good": "मेरी उम्र साठ साल है"}
    )

    out_dir = tmp_path / "results_iso"
    runner = STTBenchmarkRunner()
    samples = runner.load_manifest(ds_dir)

    summary, _ = runner.run_provider_benchmark(
        provider=mock_p,
        samples=samples,
        dataset_path=ds_dir,
        output_dir=out_dir,
    )

    # 1 succeeded, 1 failed, benchmark completed without crashing!
    assert summary.total_samples == 2
    assert summary.successful_samples == 1
    assert summary.failed_samples == 1


def test_stt_models_not_loaded_on_fastapi_startup():
    """
    MANDATORY INVARIANT (Prompt #65):
    STT models must NOT be loaded when the normal FastAPI application starts.
    Confirm that neither WhisperModel nor IndicASR acoustic models are loaded in memory.
    """
    from app.main import app
    # Check app state or attributes
    assert not hasattr(app.state, "whisper_model")
    assert not hasattr(app.state, "indic_asr_model")
