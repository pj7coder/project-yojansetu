"""JanSetu Duplicate Detection and Document Version Identification Subsystem."""
from app.duplicate_detection.fingerprint import (
    TextFingerprint,
    extract_text_fingerprint,
    normalize_text,
)
from app.duplicate_detection.similarity import (
    calculate_jaccard_similarity,
    generate_word_shingles,
    calculate_title_similarity,
)
from app.duplicate_detection.diff import (
    DiffAnalysis,
    analyze_document_diff,
    detect_version_keywords,
)
from app.duplicate_detection.service import (
    DuplicateDetectionResult,
    DuplicateDetectionService,
)

__all__ = [
    "TextFingerprint",
    "extract_text_fingerprint",
    "normalize_text",
    "calculate_jaccard_similarity",
    "generate_word_shingles",
    "calculate_title_similarity",
    "DiffAnalysis",
    "analyze_document_diff",
    "detect_version_keywords",
    "DuplicateDetectionResult",
    "DuplicateDetectionService",
]
