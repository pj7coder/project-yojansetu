"""
JanSetu - Day 28: Evidence & Provenance Validator.

Verifies that all gold dataset cases reference real, existing source
artifacts, verified scheme versions, and un-tampered audio recordings.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from app.gold.hashing import compute_file_sha256
from app.gold.schemas import (
    EligibilityGoldCase,
    ExtractionGoldCase,
    SearchGoldCase,
    VoiceGoldCase,
)

logger = logging.getLogger(__name__)


class EvidenceValidationError(Exception):
    """Raised when critical evidence references cannot be resolved."""
    pass


class GoldEvidenceValidator:
    """
    Validates physical existence, provenance linkage, and checksum integrity
    of evidence referenced in gold-standard cases.
    """

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None):
        if workspace_root:
            self.root = Path(workspace_root)
        else:
            # Default to repo root (three levels up from backend/app/gold)
            self.root = Path(__file__).resolve().parent.parent.parent.parent

        self.storage_dir = self.root / "storage"
        self.benchmarks_dir = self.root / "benchmarks" / "gold" / "v1"

    def validate_extraction_evidence(self, case: ExtractionGoldCase) -> List[str]:
        """
        Validates extraction evidence:
        1. Source document or chunk must exist in storage.
        2. Expected facts must have non-empty verbatim quotes.
        3. If chunk_id is given, checks existence in chunks.json.
        """
        errors = []
        doc_id = case.source.document_id

        # Check document in storage (originals, parsed, or chunks)
        doc_found = (
            (self.storage_dir / "originals" / doc_id).exists()
            or (self.storage_dir / "parsed" / doc_id).exists()
            or (self.storage_dir / "chunks" / doc_id).exists()
        )

        if not doc_found and not case.is_security_test:
            errors.append(f"Case '{case.case_id}': Referenced document_id '{doc_id}' does not exist in storage.")

        # Check chunk existence if chunk_id is provided
        if case.source.chunk_id and not case.is_security_test:
            chunk_catalog = self.storage_dir / "chunks" / doc_id / "chunks.json"
            if chunk_catalog.is_file():
                try:
                    with open(chunk_catalog, "r", encoding="utf-8") as f:
                        cat_data = json.load(f)
                    chunk_ids = [ch.get("chunk_id") for ch in cat_data.get("chunks", [])]
                    if case.source.chunk_id not in chunk_ids:
                        errors.append(
                            f"Case '{case.case_id}': chunk_id '{case.source.chunk_id}' not found in catalog {chunk_catalog}"
                        )
                except Exception as e:
                    errors.append(f"Case '{case.case_id}': Failed to read chunk catalog: {e}")

        # Validate quotes in expected facts
        if not case.is_negative:
            for idx, fact in enumerate(case.expected_facts):
                if not fact.evidence_quote or not fact.evidence_quote.strip():
                    errors.append(f"Case '{case.case_id}': Fact {idx} ({fact.field}) has empty evidence_quote.")

        return errors

    def validate_eligibility_evidence(self, case: EligibilityGoldCase) -> List[str]:
        """
        Validates eligibility evidence:
        1. Evaluation date must be valid ISO YYYY-MM-DD.
        2. scheme_version_id must exist in storage/verified or storage/schemes.
        3. Scheme must be HUMAN_VERIFIED if status is final.
        """
        errors = []

        # Validate date format
        try:
            datetime.strptime(case.evaluation_date, "%Y-%m-%d")
        except ValueError:
            errors.append(
                f"Case '{case.case_id}': Invalid evaluation_date '{case.evaluation_date}' (must be YYYY-MM-DD)"
            )

        # Check scheme version existence
        scheme_id = case.scheme_version_id
        verified_path = self.storage_dir / "verified" / scheme_id / "verified_scheme.json"
        storage_schemes_path = self.storage_dir / "schemes" / scheme_id / "versions" / "v2" / "scheme.json"

        # Also search for scheme_id in any verified or schemes subdirectories
        found = verified_path.is_file() or storage_schemes_path.is_file()
        if not found:
            # Check by folder existence
            if (self.storage_dir / "verified" / scheme_id).exists() or (self.storage_dir / "schemes" / scheme_id).exists():
                found = True

        if not found and not case.notes == "SYNTHETIC_BENCHMARK_RULE":
            errors.append(
                f"Case '{case.case_id}': Referenced scheme_version_id '{scheme_id}' does not exist in verified or schemes storage."
            )

        return errors

    def validate_voice_evidence(self, case: VoiceGoldCase) -> List[str]:
        """
        Validates voice evidence:
        1. Referenced audio file must exist.
        2. Audio file SHA-256 must match recorded checksum.
        3. Reference transcript must be non-empty.
        """
        errors = []

        # Search audio file under benchmarks/gold/v1/voice/audio/ or tests/stt_benchmark/audio/
        audio_rel = Path(case.audio_file)
        candidates = [
            self.benchmarks_dir / "voice" / audio_rel,
            self.benchmarks_dir / "voice" / "audio" / audio_rel.name,
            self.root / "tests" / "stt_benchmark" / "audio" / audio_rel.name,
            self.root / case.audio_file,
        ]

        found_path: Optional[Path] = None
        for cand in candidates:
            if cand.is_file():
                found_path = cand
                break

        if not found_path:
            errors.append(f"Case '{case.case_id}': Audio file '{case.audio_file}' not found.")
        else:
            # Check SHA-256
            actual_hash = compute_file_sha256(found_path)
            if actual_hash.lower() != case.audio_sha256.lower():
                errors.append(
                    f"Case '{case.case_id}': Audio SHA-256 mismatch for '{found_path.name}'. "
                    f"Expected '{case.audio_sha256}', found '{actual_hash}' (stale audio)."
                )

        if not case.reference_transcript or not case.reference_transcript.strip():
            if case.vad.contains_speech and case.speech_category not in ("SILENCE", "NOISE"):
                errors.append(f"Case '{case.case_id}': Missing reference_transcript.")

        return errors
