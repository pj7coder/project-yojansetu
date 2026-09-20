"""
JanSetu - Day 28: Gold-Standard Evaluation Dataset Engine.

Provides schemas, validation, artifact hashing, provenance tracking,
and data-leakage protected loaders for independent QA benchmarks.
"""

from app.gold.schemas import (
    GoldTask,
    GoldSplit,
    CaseStatus,
    DifficultyLevel,
    EligibilityStatus,
    RelevanceGrade,
    GoldCaseMeta,
    ExtractionGoldCase,
    EligibilityGoldCase,
    SearchGoldCase,
    VoiceGoldCase,
    ConversationGoldCase,
    GoldDatasetManifest,
)
from app.gold.loader import GoldBenchmarkLoader
from app.gold.validator import GoldDatasetValidator
from app.gold.hashing import compute_sha256, compute_manifest_hash

__all__ = [
    "GoldTask",
    "GoldSplit",
    "CaseStatus",
    "DifficultyLevel",
    "EligibilityStatus",
    "RelevanceGrade",
    "GoldCaseMeta",
    "ExtractionGoldCase",
    "EligibilityGoldCase",
    "SearchGoldCase",
    "VoiceGoldCase",
    "ConversationGoldCase",
    "GoldDatasetManifest",
    "GoldBenchmarkLoader",
    "GoldDatasetValidator",
    "compute_sha256",
    "compute_manifest_hash",
]
