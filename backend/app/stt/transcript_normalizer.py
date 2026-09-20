"""
YojanSetu - Day 22: Transcript Normalizer.

Standardizes transcripts for metric calculation (WER, CER) ONLY.
CRITICAL INVARIANT: The benchmark keeps the raw transcript completely
immutable. TranscriptNormalizer produces an auxiliary normalized string
used solely during distance calculation.
"""

import re
import unicodedata
from typing import Dict

# Devanagari to Western Arabic numeral mapping
DEVANAGARI_TO_ARABIC_DIGITS: Dict[str, str] = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}

class TranscriptNormalizer:
    """
    Standardizes Unicode, whitespace, punctuation, and numerals for WER/CER calculation.
    """

    @classmethod
    def normalize_digits(cls, text: str) -> str:
        """Translates Devanagari numerals (e.g. '६२') to Arabic digits ('62')."""
        result = []
        for char in text:
            result.append(DEVANAGARI_TO_ARABIC_DIGITS.get(char, char))
        return "".join(result)

    @classmethod
    def remove_punctuation(cls, text: str) -> str:
        """Removes punctuation and dandas, preserving word tokens and decimal numbers (e.g. 2.5)."""
        # Remove periods that are NOT decimal points between digits
        cleaned = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
        # Remove punctuation, dandas, and hyphens (with '-' at the end to prevent range parsing)
        cleaned = re.sub(r"[?!;:\"'„“”—–()[\]{}/\\।॥,\-]", " ", cleaned)
        return cleaned

    @classmethod
    def normalize_for_metrics(
        cls,
        text: str,
        convert_digits: bool = True,
        remove_punct: bool = True,
        lowercase_latin: bool = True,
    ) -> str:
        """
        Normalizes transcript string for metric comparison:
        1. Unicode NFC canonical decomposition/composition
        2. Optional Devanagari numeral translation
        3. Optional punctuation removal (including Hindi Purna Viram ।)
        4. Lowercase Latin characters (for code-mixed terms like 'e-Mitra', 'SSO')
        5. Whitespace trimming and collapse
        """
        if not text:
            return ""

        # 1. Unicode NFC normalization
        normalized = unicodedata.normalize("NFC", text)

        # 2. Translate Devanagari digits
        if convert_digits:
            normalized = cls.normalize_digits(normalized)

        # 3. Lowercase Latin characters
        if lowercase_latin:
            normalized = normalized.lower()

        # 4. Remove punctuation
        if remove_punct:
            normalized = cls.remove_punctuation(normalized)

        # 5. Collapse multiple whitespace characters
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized
