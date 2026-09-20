import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.chunking.section_patterns import (
    SECTION_HEADING_PATTERNS,
    SectionType,
)

logger = logging.getLogger("yojansetu.chunking.section_detector")

HEADING_BLOCK_TYPES = {"TITLE", "HEADING"}


class SectionDetector:
    """
    Identifies semantic section boundaries and maintains heading hierarchy
    from structured document blocks.
    """

    def __init__(self):
        self.current_section_type: SectionType = SectionType.GENERAL
        self.current_section_path: List[str] = []

    def classify_heading_text(self, text: str) -> Optional[SectionType]:
        """Match text against bilingual section dictionaries."""
        text_clean = text.strip()
        if not text_clean:
            return None

        for sec_type, patterns in SECTION_HEADING_PATTERNS.items():
            for pat in patterns:
                if pat.search(text_clean):
                    return sec_type

        return None

    def detect_section(
        self,
        block: Dict[str, Any],
    ) -> Optional[Tuple[SectionType, str]]:
        """
        Evaluate if a block initiates a new semantic section or subsection.

        Returns:
            Tuple of (SectionType, heading_title) if a heading/section shift occurs, else None.
        """
        block_type = block.get("block_type", "PARAGRAPH")
        text = block.get("text", "").strip()

        is_heading_type = block_type in HEADING_BLOCK_TYPES

        # Check if paragraph starts with an explicit section lead-in keyword e.g. "पात्रता:" or "Eligibility:"
        is_inline_heading = False
        lead_in_text = ""
        if block_type == "PARAGRAPH" and (":" in text or "—" in text or "-" in text):
            first_clause = re.split(r"[:\-\—\n]", text, maxsplit=1)[0].strip()
            if len(first_clause) <= 40 and self.classify_heading_text(first_clause) is not None:
                is_inline_heading = True
                lead_in_text = first_clause

        if not is_heading_type and not is_inline_heading:
            return None

        eval_text = text if is_heading_type else lead_in_text
        classified_type = self.classify_heading_text(eval_text)

        if classified_type:
            section_type = classified_type
        elif is_heading_type:
            # Unrecognized structural heading maps to UNKNOWN safely
            section_type = SectionType.UNKNOWN
        else:
            return None

        # Clean title string
        title = eval_text.split("\n")[0][:120].strip()
        return section_type, title

    def update_hierarchy(
        self,
        section_type: SectionType,
        heading_title: str,
        section_path_hint: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Update stateful section hierarchy.
        Preserves parent topic while allowing specific subheadings.
        """
        is_same_section = (section_type == self.current_section_type)
        self.current_section_type = section_type

        if section_path_hint and len(section_path_hint) > 1:
            self.current_section_path = list(section_path_hint)
        elif self.current_section_path and is_same_section:
            # Sibling or child under current major section
            if heading_title not in self.current_section_path:
                if len(self.current_section_path) >= 2:
                    self.current_section_path = [self.current_section_path[0], heading_title]
                else:
                    self.current_section_path.append(heading_title)
        else:
            # Fresh top-level section
            self.current_section_path = [heading_title]

        return list(self.current_section_path)
