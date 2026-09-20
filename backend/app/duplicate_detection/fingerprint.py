import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from pypdf import PdfReader

from app.core.config import get_settings

logger = logging.getLogger("yojansetu.duplicate_detection.fingerprint")


@dataclass
class TextFingerprint:
    """Structured text fingerprint representation of a PDF document."""

    normalized_text: str
    normalized_hash: str
    page_count: int
    text_length: int
    is_scanned_or_empty: bool


def normalize_text(raw_text: str) -> str:
    """
    Deterministically normalize rough text while preserving vernacular Hindi semantics.

    Steps:
    1. Unicode NFC normalization (composes base characters and matras properly).
    2. Convert Latin characters to lowercase while keeping Devanagari intact.
    3. Remove obvious page-number lines (e.g. 'Page 1', 'पृष्ठ 2', '1 of 5').
    4. Collapse multiple spaces and horizontal whitespace to a single space.
    5. Remove redundant consecutive blank lines.
    """
    if not raw_text:
        return ""

    # 1. Unicode NFC Normalization (crucial for Hindi conjuncts and matras)
    normalized = unicodedata.normalize("NFC", raw_text)

    # 2. Lowercase ASCII/Latin letters (does not alter Devanagari)
    normalized = normalized.lower()

    # Process line by line
    cleaned_lines = []
    # Pattern for page numbers: e.g. "page 12", "- 12 -", "पृष्ठ 5", "12/45", "12"
    page_number_pattern = re.compile(
        r"^\s*(?:[-–—]\s*)?(?:page|पृष्ठ|p\.)?\s*\d+\s*(?:of|/|\-)?\s*\d*(?:\s*[-–—])?\s*$",
        re.IGNORECASE,
    )

    for line in normalized.splitlines():
        # Collapse whitespace within line
        clean_line = re.sub(r"[ \t\u00A0\u3000]+", " ", line).strip()
        if not clean_line:
            continue
        # Drop page numbers
        if page_number_pattern.match(clean_line):
            continue
        cleaned_lines.append(clean_line)

    return "\n".join(cleaned_lines)


def extract_rough_text(file_path: Path) -> tuple[str, int]:
    """
    Extract raw text and page/sheet count from PDF, XLSX, XLS, or CSV.
    Returns (raw_text, page_count).
    """
    raw_parts = []
    page_count = 0
    ext = file_path.suffix.lower()

    # 1. Handle Excel OpenXML (.xlsx)
    if ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
            page_count = max(1, len(wb.sheetnames))
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                raw_parts.append(f"--- Sheet: {sheet_name} ---")
                for row in ws.iter_rows(values_only=True):
                    row_vals = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if row_vals:
                        raw_parts.append(" | ".join(row_vals))
            wb.close()
            return "\n".join(raw_parts), page_count
        except Exception as e:
            logger.warning("openpyxl text extraction failed for '%s': %s", file_path.name, e)
            return "", 1

    # 2. Handle Legacy Excel (.xls)
    if ext == ".xls":
        try:
            import xlrd
            wb = xlrd.open_workbook(str(file_path))
            page_count = max(1, wb.nsheets)
            for sheet_idx in range(wb.nsheets):
                sheet = wb.sheet_by_index(sheet_idx)
                raw_parts.append(f"--- Sheet: {sheet.name} ---")
                for rx in range(sheet.nrows):
                    row_vals = [str(sheet.cell_value(rx, cx)).strip() for cx in range(sheet.ncols) if str(sheet.cell_value(rx, cx)).strip()]
                    if row_vals:
                        raw_parts.append(" | ".join(row_vals))
            return "\n".join(raw_parts), page_count
        except Exception as e:
            logger.warning("xlrd text extraction failed for '%s': %s", file_path.name, e)
            return "", 1

    # 3. Handle CSV (.csv)
    if ext == ".csv":
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc, errors="replace") as f:
                    text = f.read()
                    return text, 1
            except Exception:
                continue
        return "", 1

    # 4. Handle PDF (Try PyMuPDF first, fallback to pypdf)
    if fitz is not None:
        try:
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            for page in doc:
                text = page.get_text()
                if text:
                    raw_parts.append(text)
            doc.close()
            return "\n".join(raw_parts), page_count
        except Exception as e:
            logger.warning("PyMuPDF text extraction failed for '%s': %s. Falling back to pypdf", file_path.name, e)

    # Fallback to pypdf
    try:
        reader = PdfReader(str(file_path))
        page_count = len(reader.pages)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                raw_parts.append(t)
        return "\n".join(raw_parts), page_count
    except Exception as e:
        logger.error("pypdf text extraction failed for '%s': %s", file_path.name, e)
        return "", page_count


def extract_text_fingerprint(
    file_path: Path,
    document_id: Optional[str] = None,
    cache_to_disk: bool = True,
) -> TextFingerprint:
    """
    Extract, normalize, and hash the rough text of a document for duplicate detection.

    :param file_path: Absolute or relative path to PDF on disk.
    :param document_id: Optional UUID string for disk caching in storage/fingerprints/.
    :param cache_to_disk: Whether to persist normalized text in fingerprints folder.
    :return: TextFingerprint dataclass.
    """
    settings = get_settings()

    # Check if cached fingerprint text exists
    cached_file: Optional[Path] = None
    if document_id:
        cached_file = settings.fingerprints_dir / f"{document_id}.txt"
        if cached_file.exists():
            try:
                cached_text = cached_file.read_text(encoding="utf-8")
                norm_hash = hashlib.sha256(cached_text.encode("utf-8")).hexdigest()
                return TextFingerprint(
                    normalized_text=cached_text,
                    normalized_hash=norm_hash,
                    page_count=0,  # Page count resolved from DB or extraction
                    text_length=len(cached_text),
                    is_scanned_or_empty=len(cached_text) < 50,
                )
            except Exception as e:
                logger.debug("Failed to read cached fingerprint '%s': %s", cached_file, e)

    # Extract fresh text
    raw_text, page_count = extract_rough_text(file_path)
    normalized = normalize_text(raw_text)
    text_length = len(normalized)
    is_scanned_or_empty = text_length < 50

    # Compute SHA-256 of normalized text
    norm_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""

    # Cache normalized text to disk if configured
    if cache_to_disk and cached_file and normalized:
        try:
            settings.fingerprints_dir.mkdir(parents=True, exist_ok=True)
            cached_file.write_text(normalized, encoding="utf-8")
        except Exception as e:
            logger.warning("Could not write fingerprint cache to '%s': %s", cached_file, e)

    return TextFingerprint(
        normalized_text=normalized,
        normalized_hash=norm_hash,
        page_count=page_count,
        text_length=text_length,
        is_scanned_or_empty=is_scanned_or_empty,
    )
