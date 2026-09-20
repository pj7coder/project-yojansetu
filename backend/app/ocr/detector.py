import logging
import re
from typing import Any, Dict, List, Tuple
import unicodedata

from app.core.config import get_settings
from app.ocr.interface import OCRDecisionResult, PageOCRDecision, PageOCRReason

logger = logging.getLogger("jansetu.ocr.detector")

# Valid script character ranges for Rajasthan government documents
# Devanagari: \u0900-\u097F, Devanagari Extended: \uA8E0-\uA8FF
# Vedic Extensions: \u1CD0-\u1CFF
# Standard ASCII / Latin / Punctuation / Currency (₹ \u20B9)
VALID_CHARS_REGEX = re.compile(
    r"^[\u0900-\u097F\uA8E0-\uA8FF\u1CD0-\u1CFF\u20B9\u0020-\u007E\u00A0-\u00FF\u2010-\u2027\u2030-\u205E\s]+$"
)


def calculate_garbled_ratio(text: str) -> Tuple[float, int]:
    """
    Calculate the proportion of garbled, mojibake, or unmapped characters.

    Returns:
        Tuple of (garbled_ratio, replacement_char_count)
    """
    if not text:
        return 0.0, 0

    replacement_chars = text.count("\ufffd")
    garbled_count = replacement_chars

    for ch in text:
        # Replacement character already counted
        if ch == "\ufffd":
            continue

        cat = unicodedata.category(ch)
        # Control characters (excluding standard whitespace) and unassigned characters
        if cat.startswith("C") and ch not in ("\n", "\r", "\t"):
            garbled_count += 1
        elif not VALID_CHARS_REGEX.match(ch):
            # Non-standard unknown symbol or broken encoding
            garbled_count += 1

    ratio = garbled_count / len(text)
    return ratio, replacement_chars


class OCRDetectionService:
    """Evaluates page extraction diagnostics to determine which pages require OCR."""

    def __init__(
        self,
        min_text_chars: int | None = None,
        garbled_ratio_threshold: float | None = None,
    ):
        settings = get_settings()
        self.min_text_chars = min_text_chars or settings.ocr_min_text_chars
        self.garbled_ratio_threshold = (
            garbled_ratio_threshold or settings.ocr_garbled_ratio_threshold
        )

    def evaluate_page(
        self,
        page_number: int,
        status: str,
        blocks: List[Dict[str, Any]],
        image_count: int = 0,
    ) -> PageOCRDecision:
        """
        Evaluate a single page using deterministic observable signals.
        Avoids false triggers for blank divider pages and single-heading pages.
        """
        combined_text = " ".join(b.get("text", "") for b in blocks if b.get("text")).strip()
        text_chars = len(combined_text)
        garbled_ratio, replacement_count = calculate_garbled_ratio(combined_text)

        # Signal 1: Parser error recorded during parsing
        if status == "PARSE_ERROR":
            return PageOCRDecision(
                page_number=page_number,
                needs_ocr=True,
                reason=PageOCRReason.PARSE_ERROR.value,
                text_character_count=text_chars,
                image_count=image_count,
                garbled_ratio=garbled_ratio,
            )

        # Signal 2: Garbled text or high replacement character count
        if garbled_ratio > self.garbled_ratio_threshold or replacement_count >= 3:
            return PageOCRDecision(
                page_number=page_number,
                needs_ocr=True,
                reason=PageOCRReason.GARBLED_TEXT.value,
                text_character_count=text_chars,
                image_count=image_count,
                garbled_ratio=garbled_ratio,
            )

        # Signal 3: Completely zero text
        if text_chars == 0:
            if image_count > 0:
                # Page contains image(s) but no text -> scanned page
                return PageOCRDecision(
                    page_number=page_number,
                    needs_ocr=True,
                    reason=PageOCRReason.NO_TEXT_WITH_IMAGE.value,
                    text_character_count=0,
                    image_count=image_count,
                    garbled_ratio=0.0,
                )
            else:
                # Blank separator / empty page -> no OCR needed
                return PageOCRDecision(
                    page_number=page_number,
                    needs_ocr=False,
                    reason=PageOCRReason.BLANK_DIVIDER.value,
                    text_character_count=0,
                    image_count=0,
                    garbled_ratio=0.0,
                )

        # Signal 4: Low text characters (< threshold)
        if text_chars < self.min_text_chars:
            if image_count > 0:
                # Low text with image -> partial scan or missed text
                return PageOCRDecision(
                    page_number=page_number,
                    needs_ocr=True,
                    reason=PageOCRReason.LIKELY_SCANNED.value,
                    text_character_count=text_chars,
                    image_count=image_count,
                    garbled_ratio=garbled_ratio,
                )
            else:
                # Short valid text without image (e.g. single heading or signature line)
                return PageOCRDecision(
                    page_number=page_number,
                    needs_ocr=False,
                    reason=PageOCRReason.TEXT_OK.value,
                    text_character_count=text_chars,
                    image_count=0,
                    garbled_ratio=garbled_ratio,
                )

        # Signal 5: Substantial valid text
        return PageOCRDecision(
            page_number=page_number,
            needs_ocr=False,
            reason=PageOCRReason.TEXT_OK.value,
            text_character_count=text_chars,
            image_count=image_count,
            garbled_ratio=garbled_ratio,
        )

    def evaluate_document(
        self,
        document_id: str,
        parsed_doc_data: Dict[str, Any],
    ) -> OCRDecisionResult:
        """
        Evaluate full parsed document data from storage/parsed/<doc_id>/document.json.
        """
        pages = parsed_doc_data.get("pages", [])
        diagnostics = parsed_doc_data.get("diagnostics", {})
        doc_quality = diagnostics.get("quality_assessment", "")
        is_scanned_doc = doc_quality in ("SCANNED_NEEDS_OCR", "MIXED_TEXT_AND_SCANNED")

        page_decisions: List[PageOCRDecision] = []
        pages_needing_ocr: List[int] = []

        for p in pages:
            p_num = p.get("page_number", 1)
            p_status = p.get("status", "TEXT_OK")
            p_blocks = p.get("blocks", [])

            # Extract image count from page or block metadata
            image_count = p.get("image_count", 0)
            if image_count == 0:
                for b in p_blocks:
                    meta = b.get("metadata", {})
                    if isinstance(meta, dict) and "image_count" in meta:
                        image_count = max(image_count, int(meta.get("image_count", 0)))

            # If document was flagged overall as scanned and page has no text, treat as scanned
            if image_count == 0 and is_scanned_doc and p_status == "NO_TEXT":
                image_count = 1

            decision = self.evaluate_page(
                page_number=p_num,
                status=p_status,
                blocks=p_blocks,
                image_count=image_count,
            )
            page_decisions.append(decision)
            if decision.needs_ocr:
                pages_needing_ocr.append(p_num)

        ocr_required = len(pages_needing_ocr) > 0

        logger.info(
            "Document %s evaluated: %d total pages, %d require OCR (pages=%s)",
            document_id,
            len(pages),
            len(pages_needing_ocr),
            pages_needing_ocr,
        )

        return OCRDecisionResult(
            document_id=document_id,
            ocr_required=ocr_required,
            pages_total=len(pages),
            pages_needing_ocr=pages_needing_ocr,
            page_decisions=page_decisions,
        )
