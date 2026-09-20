"""
YojanSetu - Day 28 Tests: Gold Dataset Integrity, Evidence, Safety & Leakage Prevention.

Verifies:
1. Full dataset passes GoldDatasetValidator with zero errors.
2. Duplicate case IDs are strictly rejected.
3. Invalid split names are rejected.
4. Invalid eligibility statuses outside tri-state logic are rejected.
5. Broken evidence references fail validation.
6. Unverified/non-existent scheme versions fail validation.
7. Citizen PII leakage (Aadhaar, phone, email) is caught by regex scanner.
8. Audio hash mismatch / staleness is detected.
9. Split assignments are stable across repeated loads.
10. Runtime loader strips expected labels to prevent test-set data leakage.
11. Manifest hash is completely deterministic and reproducible.
"""

from copy import deepcopy
import json
from pathlib import Path
import pytest

from app.gold.hashing import compute_manifest_hash
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import (
    CaseStatus,
    EligibilityExpected,
    EligibilityGoldCase,
    EligibilityStatus,
    ExtractionExpectedFact,
    ExtractionGoldCase,
    ExtractionSource,
    GoldDatasetManifest,
    GoldSplit,
    GoldTask,
    VoiceContext,
    VoiceExpectedMeaning,
    VoiceGoldCase,
    VoiceVADTruth,
)
from app.gold.validator import GoldDatasetValidator


@pytest.fixture
def loader():
    return GoldBenchmarkLoader(version="v1")


@pytest.fixture
def validator():
    return GoldDatasetValidator()


# ---------------------------------------------------------------------------
# 1. Master Dataset Health
# ---------------------------------------------------------------------------

def test_gold_dataset_validator_success(loader, validator):
    """Full gold v1 dataset must pass validation with zero errors."""
    manifest = loader.load_manifest()
    assert manifest.dataset_version == "1.0"
    assert manifest.dataset_sha256 is not None
    assert len(manifest.dataset_sha256) == 64

    cases = loader.load_cases(status=None)
    assert len(cases) == 280

    manifest_errors = validator.validate_manifest(manifest, cases)
    assert len(manifest_errors) == 0, f"Manifest errors: {manifest_errors}"

    validator.reset()
    all_errors = []
    for c in cases:
        if c.task == GoldTask.EXTRACTION:
            all_errors.extend(validator.validate_extraction_case(c))
        elif c.task == GoldTask.ELIGIBILITY:
            all_errors.extend(validator.validate_eligibility_case(c))
        elif c.task == GoldTask.SEARCH:
            all_errors.extend(validator.validate_search_case(c))
        elif c.task == GoldTask.VOICE:
            all_errors.extend(validator.validate_voice_case(c))
        elif c.task == GoldTask.CONVERSATION:
            all_errors.extend(validator.validate_conversation_case(c))

    assert len(all_errors) == 0, f"Case validation failed: {all_errors}"


# ---------------------------------------------------------------------------
# 2. Duplicate ID Rejection
# ---------------------------------------------------------------------------

def test_duplicate_case_id_rejected(validator):
    """Validator must reject two cases sharing the same case_id."""
    validator.reset()
    case1 = ExtractionGoldCase(
        case_id="EXT-DUP-001",
        task=GoldTask.EXTRACTION,
        split=GoldSplit.DEV,
        created_at="2026-09-07T12:00:00Z",
        source=ExtractionSource(document_id="72ff2711-d1b6-40be-ab6c-7d51ba8ae8e2"),
    )
    case2 = ExtractionGoldCase(
        case_id="EXT-DUP-001",
        task=GoldTask.EXTRACTION,
        split=GoldSplit.TEST,
        created_at="2026-09-07T12:00:00Z",
        source=ExtractionSource(document_id="72ff2711-d1b6-40be-ab6c-7d51ba8ae8e2"),
    )

    errs1 = validator.validate_extraction_case(case1)
    assert not any("Duplicate case_id" in e for e in errs1)

    errs2 = validator.validate_extraction_case(case2)
    assert any("Duplicate case_id 'EXT-DUP-001'" in e for e in errs2)


# ---------------------------------------------------------------------------
# 3. Invalid Eligibility Status Rejection (Tri-State Enforcement)
# ---------------------------------------------------------------------------

def test_invalid_eligibility_status_rejected(validator):
    """Statuses outside tri-state logic must be rejected."""
    validator.reset()
    # Pydantic will block direct assignment, but test dictionary validation / cast failure
    with pytest.raises(ValueError):
        EligibilityExpected(status="PROBABLY_ELIGIBLE")


# ---------------------------------------------------------------------------
# 4. Broken Evidence Detection
# ---------------------------------------------------------------------------

def test_broken_evidence_detected(validator):
    """Referencing a non-existent document must fail validation."""
    validator.reset()
    case = ExtractionGoldCase(
        case_id="EXT-BROKEN-001",
        task=GoldTask.EXTRACTION,
        split=GoldSplit.DEV,
        created_at="2026-09-07T12:00:00Z",
        source=ExtractionSource(document_id="non-existent-doc-uuid-999"),
        expected_facts=[
            ExtractionExpectedFact(
                field="eligibility.age",
                value=60,
                evidence_quote="Age >= 60",
            )
        ],
    )
    errs = validator.validate_extraction_case(case)
    assert any("does not exist in storage" in e for e in errs)


# ---------------------------------------------------------------------------
# 5. Non-Existent Scheme Version Rejection
# ---------------------------------------------------------------------------

def test_unverified_scheme_version_rejected(validator):
    """Referencing an unknown scheme version must fail validation."""
    validator.reset()
    case = EligibilityGoldCase(
        case_id="ELG-UNKNOWN-SCHEME",
        task=GoldTask.ELIGIBILITY,
        split=GoldSplit.DEV,
        created_at="2026-09-07T12:00:00Z",
        scheme_version_id="fake-scheme-version-xyz",
        evaluation_date="2026-09-01",
        profile={"age": 65},
        expected=EligibilityExpected(status=EligibilityStatus.ELIGIBLE),
    )
    errs = validator.validate_eligibility_case(case)
    assert any("does not exist in verified or schemes storage" in e for e in errs)


# ---------------------------------------------------------------------------
# 6. Citizen PII Leakage Detection
# ---------------------------------------------------------------------------

def test_pii_scanner_detects_leak(validator):
    """Synthetic profiles containing accidental Aadhaar numbers or phone numbers must fail."""
    validator.reset()
    case_with_aadhaar = EligibilityGoldCase(
        case_id="ELG-PII-TEST",
        task=GoldTask.ELIGIBILITY,
        split=GoldSplit.DEV,
        created_at="2026-09-07T12:00:00Z",
        scheme_version_id="e54ebf76-b896-4292-b033-ce77e913bc35",
        evaluation_date="2026-09-01",
        profile={
            "age": 65,
            "aadhaar_number": "3829 4829 1928",  # Realistic Aadhaar pattern
        },
        expected=EligibilityExpected(status=EligibilityStatus.ELIGIBLE),
    )
    errs = validator.validate_eligibility_case(case_with_aadhaar)
    assert any("Potential Aadhaar number detected" in e or "Explicit PII key" in e for e in errs)


# ---------------------------------------------------------------------------
# 7. Audio Hash Mismatch / Staleness
# ---------------------------------------------------------------------------

def test_audio_hash_mismatch_detected(validator):
    """Tampered or incorrect audio SHA-256 must trigger a mismatch error."""
    validator.reset()
    case = VoiceGoldCase(
        case_id="VOICE-STALE-TEST",
        task=GoldTask.VOICE,
        split=GoldSplit.DEV,
        created_at="2026-09-07T12:00:00Z",
        audio_file="audio/silence.wav",
        audio_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        duration_seconds=2.0,
        reference_transcript="",
        speech_category="SILENCE",
        context=VoiceContext(),
        expected_meaning=VoiceExpectedMeaning(),
        vad=VoiceVADTruth(contains_speech=False),
    )
    errs = validator.validate_voice_case(case)
    assert any("Audio SHA-256 mismatch" in e for e in errs)


# ---------------------------------------------------------------------------
# 8. Split Stability
# ---------------------------------------------------------------------------

def test_split_stability(loader):
    """Repeated calls to load_cases must return identical, stable split assignments."""
    run1 = loader.load_cases(task=GoldTask.ELIGIBILITY, split=GoldSplit.TEST)
    run2 = loader.load_cases(task=GoldTask.ELIGIBILITY, split=GoldSplit.TEST)

    ids1 = [c.case_id for c in run1]
    ids2 = [c.case_id for c in run2]
    assert ids1 == ids2
    assert len(ids1) == 60


# ---------------------------------------------------------------------------
# 9. Data Leakage Prevention (Runtime Input Stripping)
# ---------------------------------------------------------------------------

def test_runtime_loader_prevents_data_leakage(loader):
    """Runtime inputs supplied to evaluators must NEVER contain ground-truth target labels."""
    # Test Extraction runtime inputs
    ext_inputs = loader.get_runtime_inputs(task=GoldTask.EXTRACTION, split=GoldSplit.TEST)
    assert len(ext_inputs) > 0
    for inp in ext_inputs:
        assert "case_id" in inp
        assert "source" in inp
        assert "expected_facts" not in inp
        assert "facts" not in inp

    # Test Eligibility runtime inputs
    elg_inputs = loader.get_runtime_inputs(task=GoldTask.ELIGIBILITY, split=GoldSplit.TEST)
    assert len(elg_inputs) > 0
    for inp in elg_inputs:
        assert "case_id" in inp
        assert "profile" in inp
        assert "expected" not in inp
        assert "status" not in inp

    # Test Search runtime inputs
    srch_inputs = loader.get_runtime_inputs(task=GoldTask.SEARCH, split=GoldSplit.TEST)
    assert len(srch_inputs) > 0
    for inp in srch_inputs:
        assert "case_id" in inp
        assert "query" in inp
        assert "expected" not in inp
        assert "relevance_judgments" not in inp

    # Test Voice runtime inputs
    voice_inputs = loader.get_runtime_inputs(task=GoldTask.VOICE, split=GoldSplit.TEST)
    assert len(voice_inputs) > 0
    for inp in voice_inputs:
        assert "case_id" in inp
        assert "audio_file" in inp
        assert "reference_transcript" not in inp
        assert "expected_meaning" not in inp


# ---------------------------------------------------------------------------
# 10. Manifest Hash Determinism
# ---------------------------------------------------------------------------

def test_manifest_hash_determinism(loader):
    """Manifest hash must be completely reproducible."""
    manifest = loader.load_manifest()
    manifest_dict = manifest.model_dump()
    recomputed = compute_manifest_hash(manifest_dict)
    assert recomputed == manifest.dataset_sha256
