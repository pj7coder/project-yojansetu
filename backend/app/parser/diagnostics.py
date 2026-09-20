from dataclasses import dataclass, field
from typing import Dict, List
from app.parser.interface import PageTextStatus, RawPageData


@dataclass
class PageDiagnostic:
    """Quality metrics for a single physical PDF page."""
    page_number: int
    status: str  # TEXT_OK, LOW_TEXT, NO_TEXT, PARSE_ERROR
    text_character_count: int
    block_count: int
    table_count: int
    image_count: int = 0


@dataclass
class DocumentDiagnostics:
    """Quality and completeness metrics for the entire parsed document."""
    total_pages: int
    pages_with_text: int
    pages_without_text: int
    pages_low_text: int
    total_text_characters: int
    total_blocks: int
    total_tables: int
    needs_ocr: bool
    quality_assessment: str  # DIGITAL_COMPLETE, MIXED_TEXT_AND_SCANNED, SCANNED_NEEDS_OCR
    page_diagnostics: List[PageDiagnostic] = field(default_factory=list)


def evaluate_page_diagnostics(page: RawPageData) -> PageDiagnostic:
    """Evaluate text volume and structure for a single page."""
    char_count = sum(len(b.text) for b in page.blocks)
    table_count = sum(1 for b in page.blocks if b.block_type == "TABLE")

    if char_count == 0:
        status = PageTextStatus.NO_TEXT
    elif char_count < 100:
        status = PageTextStatus.LOW_TEXT
    else:
        status = PageTextStatus.TEXT_OK

    return PageDiagnostic(
        page_number=page.page_number,
        status=status,
        text_character_count=char_count,
        block_count=len(page.blocks),
        table_count=table_count,
        image_count=page.image_count,
    )


def evaluate_document_diagnostics(pages: List[RawPageData]) -> DocumentDiagnostics:
    """Compute aggregate diagnostic metrics across all pages of a document."""
    total_pages = len(pages)
    page_diagnostics: List[PageDiagnostic] = []

    pages_with_text = 0
    pages_without_text = 0
    pages_low_text = 0
    total_chars = 0
    total_blocks = 0
    total_tables = 0

    for page in pages:
        diag = evaluate_page_diagnostics(page)
        page_diagnostics.append(diag)

        if diag.status == PageTextStatus.NO_TEXT:
            pages_without_text += 1
        elif diag.status == PageTextStatus.LOW_TEXT:
            pages_with_text += 1
            pages_low_text += 1
        else:
            pages_with_text += 1

        total_chars += diag.text_character_count
        total_blocks += diag.block_count
        total_tables += diag.table_count

    needs_ocr = pages_without_text > 0 or (total_pages > 0 and pages_with_text == 0)

    if pages_without_text == 0 and pages_low_text == 0 and total_chars > 0:
        quality = "DIGITAL_COMPLETE"
    elif pages_with_text == 0:
        quality = "SCANNED_NEEDS_OCR"
    else:
        quality = "MIXED_TEXT_AND_SCANNED"

    return DocumentDiagnostics(
        total_pages=total_pages,
        pages_with_text=pages_with_text,
        pages_without_text=pages_without_text,
        pages_low_text=pages_low_text,
        total_text_characters=total_chars,
        total_blocks=total_blocks,
        total_tables=total_tables,
        needs_ocr=needs_ocr,
        quality_assessment=quality,
        page_diagnostics=page_diagnostics,
    )
