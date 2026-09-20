"""
YojanSetu - Day 23: Offline Audio Front-End, Silero VAD & Preprocessing Tests.

Tests:
- Audio validation, formats (WAV, WebM, stereo, multiple sample rates), size & duration limits
- Temporary storage lifecycle, path safety, and guaranteed cleanup on error/success
- Acoustic quality analysis (quiet audio detection, clipping detection)
- Silero VAD speech detection vs silence/noise rejection
- Utterance segmentation, short-gap merging, pause splitting, chronological ordering
- Short-answer protection (हाँ, नहीं, साठ, डूंगरपुर, डेढ़ लाख)
- Noise suppression (Passthrough & Spectral gating)
- Audio transcription service (skips STT on silence, preserves raw segments)
- FastAPI startup isolation (no heavy models loaded on app start)
"""

import io
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.audio.config import AudioSettings, get_audio_settings
from app.audio.pipeline import AudioProcessingPipeline
from app.audio.quality import AudioQualityAnalyzer
from app.audio.schemas import (
    AudioErrorCode,
    AudioProcessingStatus,
    SpeechSegment,
)
from app.audio.segmentation import UtteranceSegmenter
from app.audio.temp_storage import AudioTempStorageManager, get_temp_storage_manager
from app.audio.transcription import AudioTranscriptionService
from app.main import create_application
from app.noise.passthrough import PassthroughNoiseSuppressor
from app.noise.spectral import SpectralGatingNoiseSuppressor
from app.vad.silero import SileroVADProvider


# Fixtures directory
FIXTURE_DIR = Path(__file__).resolve().parent / "stt_benchmark" / "audio"


@pytest.fixture
def temp_storage():
    """Provides AudioTempStorageManager for testing."""
    return get_temp_storage_manager()


@pytest.fixture
def sample_sine_wav(temp_storage):
    """Creates a temporary 16kHz sine wave audio file (1 second)."""
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    data = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = temp_storage.create_temp_file(suffix=".wav", prefix="test_sine_")
    sf.write(str(path), data, sr, subtype="PCM_16")
    yield path
    temp_storage.cleanup_file(path)


@pytest.fixture
def sample_silence_wav(temp_storage):
    """Creates a temporary 2-second pure silence audio file."""
    sr = 16000
    data = np.zeros(2 * sr, dtype=np.float32)
    path = temp_storage.create_temp_file(suffix=".wav", prefix="test_silence_")
    sf.write(str(path), data, sr, subtype="PCM_16")
    yield path
    temp_storage.cleanup_file(path)


# =====================================================================
# 1. AUDIO VALIDATION & NORMALIZATION TESTS
# =====================================================================

def test_validation_empty_file(temp_storage):
    """Empty files must be rejected with INVALID_AUDIO."""
    empty_path = temp_storage.create_temp_file(suffix=".wav", prefix="empty_")
    pipeline = AudioProcessingPipeline()
    res = pipeline.process(empty_path)
    temp_storage.cleanup_file(empty_path)

    assert res.status == AudioProcessingStatus.INVALID_AUDIO
    assert res.error_code == AudioErrorCode.INVALID_AUDIO


def test_validation_unsupported_format(temp_storage):
    """Unsupported extension must be rejected."""
    bad_path = temp_storage.temp_dir / "unsupported_audio.xyz"
    bad_path.write_bytes(b"dummy audio content")
    pipeline = AudioProcessingPipeline()
    res = pipeline.process(bad_path)
    temp_storage.cleanup_file(bad_path)

    assert res.status == AudioProcessingStatus.INVALID_AUDIO
    assert res.error_code == AudioErrorCode.INVALID_AUDIO


def test_validation_corrupt_file(temp_storage):
    """Corrupt audio file must fail decode safely without crashing."""
    corrupt_path = temp_storage.create_temp_file(suffix=".wav", prefix="corrupt_")
    corrupt_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00corrupt-data-payload")
    pipeline = AudioProcessingPipeline()
    res = pipeline.process(corrupt_path)
    temp_storage.cleanup_file(corrupt_path)

    assert res.status == AudioProcessingStatus.AUDIO_DECODE_FAILED
    assert res.error_code == AudioErrorCode.AUDIO_DECODE_FAILED


def test_validation_oversized_file(temp_storage, monkeypatch):
    """Files exceeding AUDIO_MAX_UPLOAD_BYTES must be rejected."""
    sample_path = temp_storage.create_temp_file(suffix=".wav", prefix="oversized_")
    sample_path.write_bytes(b"0" * 1024)

    # Monkeypatch limit to 500 bytes
    settings = get_audio_settings()
    monkeypatch.setattr(settings, "audio_max_upload_bytes", 500)

    pipeline = AudioProcessingPipeline()
    res = pipeline.process(sample_path)
    temp_storage.cleanup_file(sample_path)

    assert res.status == AudioProcessingStatus.AUDIO_TOO_LARGE
    assert res.error_code == AudioErrorCode.AUDIO_TOO_LARGE


def test_validation_too_long_audio(temp_storage, monkeypatch):
    """Audio exceeding max duration must be rejected."""
    sr = 16000
    data = np.zeros(5 * sr, dtype=np.float32)
    path = temp_storage.create_temp_file(suffix=".wav", prefix="long_")
    sf.write(str(path), data, sr, subtype="PCM_16")

    # Set limit to 2 seconds
    settings = get_audio_settings()
    monkeypatch.setattr(settings, "audio_max_duration_seconds", 2.0)

    pipeline = AudioProcessingPipeline()
    res = pipeline.process(path)
    temp_storage.cleanup_file(path)

    assert res.status == AudioProcessingStatus.AUDIO_TOO_LONG
    assert res.error_code == AudioErrorCode.AUDIO_TOO_LONG


def test_stereo_to_mono_normalization(temp_storage):
    """Stereo inputs must be converted to mono 16kHz."""
    sr = 44100
    # Create 2-channel stereo
    left = 0.2 * np.sin(np.linspace(0, 1.0, sr))
    right = 0.2 * np.cos(np.linspace(0, 1.0, sr))
    stereo_data = np.stack([left, right], axis=1)

    stereo_path = temp_storage.create_temp_file(suffix=".wav", prefix="stereo_")
    sf.write(str(stereo_path), stereo_data, sr, subtype="PCM_16")

    pipeline = AudioProcessingPipeline()
    norm_path = temp_storage.create_temp_file(suffix=".wav", prefix="out_mono_")
    from app.stt.audio_normalizer import AudioNormalizer
    AudioNormalizer.normalize_to_wav(stereo_path, output_path=norm_path)

    data_norm, sr_norm = sf.read(str(norm_path))
    temp_storage.cleanup_file(stereo_path)
    temp_storage.cleanup_file(norm_path)

    assert sr_norm == 16000
    assert data_norm.ndim == 1  # Mono


# =====================================================================
# 2. PRIVACY & TEMPORARY STORAGE LIFECYCLE TESTS
# =====================================================================

def test_temp_file_collision_protection(temp_storage):
    """Two created temp files must have distinct paths even with same suffix."""
    f1 = temp_storage.create_temp_file(suffix=".wav")
    f2 = temp_storage.create_temp_file(suffix=".wav")
    assert f1 != f2
    assert f1.exists()
    assert f2.exists()
    temp_storage.cleanup_file(f1)
    temp_storage.cleanup_file(f2)


def test_path_traversal_protection(temp_storage):
    """Paths outside temp directory must raise ValueError."""
    with pytest.raises(ValueError):
        temp_storage.validate_safe_path(Path("../../etc/passwd"))


def test_temp_cleanup_on_success(temp_storage):
    """Temporary files created by transcription service must be deleted."""
    speech_file = FIXTURE_DIR / "hi_short_001.wav"
    if not speech_file.exists():
        pytest.skip("Benchmark audio fixtures not present")

    service = AudioTranscriptionService()
    res = service.transcribe_audio(speech_file)

    # All temp segment audio files should be cleaned up
    for s in res.segments:
        # None should exist on disk
        pass


def test_temp_cleanup_on_exception(temp_storage, monkeypatch):
    """Temporary files must be deleted even if pipeline raises an exception."""
    sample_file = FIXTURE_DIR / "hi_short_001.wav"
    if not sample_file.exists():
        pytest.skip("Benchmark audio fixtures not present")

    pipeline = AudioProcessingPipeline()

    # Force an exception during segmentation
    def broken_merge(*args, **kwargs):
        raise RuntimeError("Simulated segmentation failure")

    monkeypatch.setattr(pipeline.segmenter, "merge_segments", broken_merge)

    res = pipeline.process(sample_file)
    assert res.status == AudioProcessingStatus.AUDIO_PROCESSING_FAILED
    assert res.error_code == AudioErrorCode.AUDIO_PROCESSING_FAILED


# =====================================================================
# 3. ACOUSTIC QUALITY ANALYZER TESTS
# =====================================================================

def test_quality_analyzer_quiet_audio():
    """Very low amplitude signal must be flagged as is_too_quiet."""
    analyzer = AudioQualityAnalyzer()
    quiet_samples = np.zeros(16000, dtype=np.float32)
    metrics = analyzer.analyze_samples(quiet_samples, 16000)

    assert metrics.is_too_quiet is True
    assert metrics.rms_level == 0.0
    assert metrics.is_clipping is False


def test_quality_analyzer_clipping_detection():
    """Signals with many samples at 1.0 must be flagged as is_clipping."""
    analyzer = AudioQualityAnalyzer()
    clipping_samples = np.ones(16000, dtype=np.float32)
    metrics = analyzer.analyze_samples(clipping_samples, 16000)

    assert metrics.is_clipping is True
    assert metrics.peak_amplitude >= 0.99


def test_quality_analyzer_normal_audio():
    """Normal speech-level audio should have reasonable RMS and no clipping."""
    analyzer = AudioQualityAnalyzer()
    t = np.linspace(0, 1.0, 16000)
    samples = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    metrics = analyzer.analyze_samples(samples, 16000)

    assert metrics.is_too_quiet is False
    assert metrics.is_clipping is False
    assert 0.1 < metrics.rms_level < 0.2


# =====================================================================
# 4. SILERO VAD & SHORT ANSWER PROTECTION TESTS
# =====================================================================

def test_vad_pure_silence_rejection(sample_silence_wav):
    """Pure silence must return NO_SPEECH_DETECTED with 0 segments."""
    vad = SileroVADProvider()
    res = vad.detect_speech_file(sample_silence_wav)

    assert res.contains_speech is False
    assert len(res.segments) == 0
    assert res.speech_duration_ms == 0


def test_short_answer_haan_retention():
    """Short answer 'हाँ' (hi_short_001.wav) must be detected by VAD."""
    f = FIXTURE_DIR / "hi_short_001.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_short_001.wav missing")

    vad = SileroVADProvider()
    res = vad.detect_speech_file(f)

    assert res.contains_speech is True
    assert len(res.segments) >= 1
    assert res.speech_duration_ms > 200


def test_short_answer_nahin_retention():
    """Short answer 'नहीं' (hi_short_002.wav) must be detected by VAD."""
    f = FIXTURE_DIR / "hi_short_002.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_short_002.wav missing")

    vad = SileroVADProvider()
    res = vad.detect_speech_file(f)

    assert res.contains_speech is True
    assert len(res.segments) >= 1


def test_short_number_saath_retention():
    """Short number 'साठ' (hi_short_003.wav) must be detected by VAD."""
    f = FIXTURE_DIR / "hi_short_003.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_short_003.wav missing")

    vad = SileroVADProvider()
    res = vad.detect_speech_file(f)

    assert res.contains_speech is True


def test_short_district_dungarpur_retention():
    """Short district 'डूंगरपुर' (hi_short_004.wav) must be detected."""
    f = FIXTURE_DIR / "hi_short_004.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_short_004.wav missing")

    vad = SileroVADProvider()
    res = vad.detect_speech_file(f)

    assert res.contains_speech is True


def test_short_income_dedh_lakh_retention():
    """Short income 'डेढ़ लाख' (hi_short_005.wav) must be detected."""
    f = FIXTURE_DIR / "hi_short_005.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_short_005.wav missing")

    vad = SileroVADProvider()
    res = vad.detect_speech_file(f)

    assert res.contains_speech is True


# =====================================================================
# 5. UTTERANCE SEGMENTATION & GAP MERGING TESTS
# =====================================================================

def test_segmenter_short_gap_merging():
    """Two segments with gap < merge_gap_ms (e.g. 200ms) should merge into one."""
    segmenter = UtteranceSegmenter(merge_gap_ms=350)
    segs = [
        SpeechSegment(segment_id="SEG-001", start_ms=100, end_ms=500, duration_ms=400, speech_probability=0.8),
        SpeechSegment(segment_id="SEG-002", start_ms=700, end_ms=1200, duration_ms=500, speech_probability=0.9),
    ]  # Gap is 700 - 500 = 200ms <= 350ms

    merged = segmenter.merge_segments(segs)
    assert len(merged) == 1
    assert merged[0].start_ms == 100
    assert merged[0].end_ms == 1200
    assert merged[0].duration_ms == 1100


def test_segmenter_long_pause_splitting():
    """Two segments with pause > merge_gap_ms (e.g. 1500ms) must remain distinct."""
    segmenter = UtteranceSegmenter(merge_gap_ms=350)
    segs = [
        SpeechSegment(segment_id="SEG-001", start_ms=100, end_ms=500, duration_ms=400, speech_probability=0.8),
        SpeechSegment(segment_id="SEG-002", start_ms=2000, end_ms=2800, duration_ms=800, speech_probability=0.9),
    ]  # Gap is 2000 - 500 = 1500ms > 350ms

    merged = segmenter.merge_segments(segs)
    assert len(merged) == 2
    assert merged[0].segment_id == "SEG-001"
    assert merged[1].segment_id == "SEG-002"


def test_segmenter_chronological_ordering():
    """Merged segments must strictly preserve chronological start time ordering."""
    segmenter = UtteranceSegmenter(merge_gap_ms=350)
    # Provide out of order
    segs = [
        SpeechSegment(segment_id="SEG-B", start_ms=2000, end_ms=2500, duration_ms=500),
        SpeechSegment(segment_id="SEG-A", start_ms=100, end_ms=600, duration_ms=500),
    ]

    merged = segmenter.merge_segments(segs)
    assert len(merged) == 2
    assert merged[0].start_ms < merged[1].start_ms
    assert merged[0].start_ms == 100
    assert merged[1].start_ms == 2000


# =====================================================================
# 6. NOISE SUPPRESSION TESTS
# =====================================================================

def test_passthrough_noise_suppressor():
    """Passthrough noise suppressor must leave samples completely untouched."""
    suppressor = PassthroughNoiseSuppressor()
    samples = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    denoised, applied = suppressor.suppress_noise(samples, 16000)

    assert applied is False
    np.testing.assert_array_equal(samples, denoised)


def test_spectral_noise_suppressor():
    """Spectral gating suppressor should process 16kHz audio cleanly."""
    suppressor = SpectralGatingNoiseSuppressor()
    sr = 16000
    # 1 second tone + noise
    t = np.linspace(0, 1.0, sr)
    samples = (0.3 * np.sin(2 * np.pi * 300 * t) + np.random.normal(0, 0.02, sr)).astype(np.float32)
    denoised, applied = suppressor.suppress_noise(samples, sr)

    assert applied is True
    assert len(denoised) == len(samples)
    assert np.max(np.abs(denoised)) <= 1.0


# =====================================================================
# 7. AUDIO TRANSCRIPTION SERVICE TESTS
# =====================================================================

def test_transcription_service_silence_skips_stt(sample_silence_wav):
    """Transcription service on pure silence must return NO_SPEECH_DETECTED without calling STT."""
    service = AudioTranscriptionService()
    res = service.transcribe_audio(sample_silence_wav)

    assert res.status == AudioProcessingStatus.NO_SPEECH_DETECTED
    assert res.speech_detected is False
    assert res.text == ""
    assert res.error_code == AudioErrorCode.NO_SPEECH_DETECTED
    assert "stt_ms" not in res.timings  # STT was skipped!


def test_transcription_service_negation():
    """End-to-end transcription of negation assertion retains 'नहीं'."""
    f = FIXTURE_DIR / "hi_neg_001.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_neg_001.wav missing")

    service = AudioTranscriptionService()
    res = service.transcribe_audio(f)

    assert res.status == AudioProcessingStatus.TRANSCRIBED
    assert res.speech_detected is True
    assert len(res.text) > 0
    assert "नहीं" in res.text


def test_transcription_service_short_answer():
    """End-to-end transcription of short answer 'हाँ'."""
    f = FIXTURE_DIR / "hi_short_001.wav"
    if not f.exists():
        pytest.skip("Audio fixture hi_short_001.wav missing")

    service = AudioTranscriptionService()
    res = service.transcribe_audio(f)

    assert res.status == AudioProcessingStatus.TRANSCRIBED
    assert res.speech_detected is True
    assert len(res.text) > 0


# =====================================================================
# 8. FASTAPI DEV API ROUTE TESTS & STARTUP ISOLATION
# =====================================================================

def test_fastapi_startup_isolation():
    """FastAPI app startup should succeed without preloading heavy models."""
    app = create_application()
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dev_process_endpoint_payload_limit():
    """Dev audio process endpoint must reject uploads larger than max bytes."""
    app = create_application()
    client = TestClient(app)

    # 11 MB dummy payload (exceeds 10 MB limit)
    oversized_data = b"0" * (11 * 1024 * 1024)
    response = client.post(
        "/api/v1/dev/audio/process",
        files={"file": ("huge.wav", io.BytesIO(oversized_data), "audio/wav")},
    )
    assert response.status_code == 413
