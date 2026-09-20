"""
Citizen text normalization layer.
Ensures clean Unicode representation, Devanagari numerals translation, and whitespace sanity
while preserving raw citizen input immutability.
"""

import re
import unicodedata
from app.normalization.numbers import devanagari_to_ascii


class CitizenTextNormalizer:
    """
    Normalizes raw natural language citizen input into a canonical text representation.
    """

    def __init__(self, version: str = "1.0"):
        self.version = version

    def normalize(self, text: str) -> str:
        """
        Normalizes surface text:
        1. Unicode normalization (NFC).
        2. Translates Devanagari digits (०-९) to ASCII (0-9).
        3. Collapses multiple spaces and strips leading/trailing whitespace.
        4. Standardizes common quotes and hyphens.
        """
        if not text:
            return ""

        # Step 1: Unicode NFC normalization
        normalized = unicodedata.normalize("NFC", text)

        # Step 2: Convert Devanagari digits to ASCII digits
        normalized = devanagari_to_ascii(normalized)

        # Step 3: Normalize unicode punctuation/quotes/hyphens
        normalized = re.sub(r'[\u2018\u2019\u201a\u201b]', "'", normalized)
        normalized = re.sub(r'[\u201c\u201d\u201e\u201f]', '"', normalized)
        normalized = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015]', "-", normalized)

        # Step 4: Condense whitespace
        normalized = re.sub(r'\s+', " ", normalized).strip()

        # Step 5: Detect STT transcription noise/failure (only '?', '*', '.' chars)
        # Whisper tiny can return '??' or '...' on unintelligible short audio
        # Treat such output as empty to prevent spurious NO_PROFILE_FACT_EXTRACTED noise
        if normalized and re.fullmatch(r'[?*\.\s]+', normalized):
            return ""

        return normalized
