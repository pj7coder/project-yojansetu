"""
Conservative dialect normalization layer for common Rajasthani, Marwari, and Mewari expressions.
Maps verified vernacular phrases to standard Hindi tokens for predictable deterministic parsing.
"""

import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("yojansetu.profile_extraction.dialects")

DIALECT_LEXICON_VERSION = "1.0"


class DialectNormalizationService:
    """
    Applies conservative phrase and token replacement from curated dialect lexicons.
    """

    def __init__(self, lexicons_dir: Optional[Path] = None):
        if lexicons_dir is None:
            lexicons_dir = Path(__file__).resolve().parent.parent / "config" / "dialects"

        self.lexicons_dir = lexicons_dir
        self.mappings: List[Tuple[str, str, re.Pattern]] = []
        self._load_lexicons()

    def _load_lexicons(self) -> None:
        """Loads and compiles regex patterns for dialect phrase mappings."""
        combined_dict: Dict[str, str] = {}
        if not self.lexicons_dir.exists():
            logger.warning(f"Dialect lexicons directory not found at: {self.lexicons_dir}")
            return

        for path in sorted(self.lexicons_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    maps = data.get("mappings", {})
                    combined_dict.update(maps)
                    logger.debug(f"Loaded {len(maps)} dialect rules from {path.name}")
            except Exception as e:
                logger.error(f"Failed loading dialect lexicon from {path}: {e}")

        # Sort keys by length descending to match multi-word phrases before single tokens
        sorted_keys = sorted(combined_dict.keys(), key=lambda k: len(k), reverse=True)
        for k in sorted_keys:
            target = combined_dict[k]
            # Use negative lookbehind/lookahead or word boundary where applicable
            # In Hindi/Devanagari, \b does not always match Hindi consonants.
            # We match with whitespace/punctuation boundaries or string edges.
            pattern_str = r'(?<![^\s,।!?])' + re.escape(k) + r'(?![^\s,।!?])'
            compiled = re.compile(pattern_str, re.IGNORECASE)
            self.mappings.append((k, target, compiled))

    def normalize_dialect(self, text: str) -> str:
        """
        Replaces recognized vernacular phrases with standard Hindi equivalents.
        Leaves unknown words strictly intact.
        """
        if not text or not self.mappings:
            return text

        result = text
        for orig, target, pattern in self.mappings:
            result = pattern.sub(target, result)

        return result
