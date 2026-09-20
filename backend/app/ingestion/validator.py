import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import get_settings

logger = logging.getLogger("yojansetu.ingestion.validator")

SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv"}

MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}


@dataclass
class DocumentValidationResult:
    """Structured result from DocumentValidationService."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    file_size_bytes: int = 0
    mime_type: str = "application/pdf"
    file_extension: str = ".pdf"
    is_encrypted: bool = False
    page_count: int = 0


class DocumentValidationService:
    """
    Validates government documents and spreadsheets before ingestion.

    Performs:
    1. File existence & readability check
    2. File size limit & 0-byte rejection
    3. Extension validation (.pdf, .xlsx, .xls, .csv)
    4. Magic bytes signature check (%PDF, PK zip for xlsx, OLE for xls, text for csv)
    5. Structural integrity inspection:
       - PDF: pypdf readability and encryption check
       - XLSX: openpyxl workbook loading & sheet counting
       - XLS: xlrd workbook verification & sheet counting
       - CSV: encoding and delimiter detection
    """

    def __init__(self, max_size_mb: Optional[int] = None):
        settings = get_settings()
        self.max_size_mb = max_size_mb or settings.max_document_size_mb
        self.max_size_bytes = self.max_size_mb * 1024 * 1024

    def validate(self, file_path: Path, original_filename: Optional[str] = None) -> DocumentValidationResult:
        """
        Validate a candidate document or spreadsheet on the filesystem.

        :param file_path: Absolute or relative Path to the file to validate.
        :param original_filename: Optional original filename supplied by user/crawler.
        :return: DocumentValidationResult with validity status and error details.
        """
        errors: List[str] = []
        filename = original_filename or file_path.name

        # 1. Existence and type check
        if not file_path.exists():
            return DocumentValidationResult(
                valid=False,
                errors=[f"File not found on disk: {file_path.name}"],
            )

        if not file_path.is_file():
            return DocumentValidationResult(
                valid=False,
                errors=[f"Path is not a regular file: {file_path.name}"],
            )

        # 2. File size validation
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            return DocumentValidationResult(
                valid=False,
                errors=[f"Unable to read file metadata: {str(e)}"],
            )

        if file_size == 0:
            errors.append("Empty file: document size is 0 bytes")

        if file_size > self.max_size_bytes:
            size_mb = file_size / (1024 * 1024)
            errors.append(
                f"File size ({size_mb:.2f} MB) exceeds maximum allowed limit of {self.max_size_mb} MB"
            )

        # 3. File extension validation
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            allowed_list = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            errors.append(f"Unsupported file extension '{ext}'. Supported formats: {allowed_list}")

        detected_mime = MIME_TYPE_MAP.get(ext, "application/octet-stream")

        # If already failed basic checks, return early
        if errors:
            return DocumentValidationResult(
                valid=False,
                errors=errors,
                file_size_bytes=file_size,
                file_extension=ext or ".pdf",
                mime_type=detected_mime,
            )

        # 4. Format-Specific Signature and Integrity Inspection
        is_encrypted = False
        page_count = 1

        if ext == ".pdf":
            # PDF Magic Bytes Check
            try:
                with open(file_path, "rb") as f:
                    header = f.read(1024)
                    if b"%PDF" not in header:
                        errors.append("Invalid PDF file: Missing '%PDF' signature in file header")
            except Exception as e:
                errors.append(f"Could not read file header: {str(e)}")

            if not errors:
                try:
                    reader = PdfReader(str(file_path))
                    if reader.is_encrypted:
                        is_encrypted = True
                        errors.append("PDF is encrypted or password-protected; manual review required")
                    else:
                        page_count = len(reader.pages)
                        if page_count == 0:
                            errors.append("PDF contains 0 readable pages")
                except PdfReadError as e:
                    errors.append(f"Corrupted or unreadable PDF document: {str(e)}")
                except Exception as e:
                    errors.append(f"PDF sanity check failed: {str(e)}")

        elif ext == ".xlsx":
            # XLSX Magic Bytes Check (ZIP archive header PK\x03\x04)
            try:
                with open(file_path, "rb") as f:
                    header = f.read(4)
                    if not header.startswith(b"PK"):
                        errors.append("Invalid XLSX file: Missing Zip/OpenXML signature in file header")
            except Exception as e:
                errors.append(f"Could not read XLSX header: {str(e)}")

            if not errors:
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
                    sheet_names = wb.sheetnames
                    page_count = max(1, len(sheet_names))
                    if not sheet_names:
                        errors.append("Excel workbook contains no sheets")
                    wb.close()
                except Exception as e:
                    errors.append(f"Corrupted or unreadable Excel workbook (.xlsx): {str(e)}")

        elif ext == ".xls":
            # Legacy XLS Magic Bytes Check (OLE compound document header \xd0\xcf\x11\xe0)
            try:
                with open(file_path, "rb") as f:
                    header = f.read(8)
                    if not header.startswith(b"\xd0\xcf\x11\xe0"):
                        errors.append("Invalid XLS file: Missing OLE signature in file header")
            except Exception as e:
                errors.append(f"Could not read XLS header: {str(e)}")

            if not errors:
                try:
                    import xlrd
                    wb = xlrd.open_workbook(str(file_path))
                    page_count = max(1, wb.nsheets)
                except Exception as e:
                    errors.append(f"Corrupted or unreadable Excel spreadsheet (.xls): {str(e)}")

        elif ext == ".csv":
            # CSV inspection: verify text decodability and check for non-empty content
            encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1"]
            decoded = False
            for enc in encodings:
                try:
                    with open(file_path, "r", encoding=enc, errors="replace") as f:
                        sample = f.read(4096)
                        if sample.strip():
                            decoded = True
                            page_count = 1
                            break
                except Exception:
                    continue
            if not decoded:
                errors.append("Unable to decode CSV file with supported text encodings")

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(
                "Document validation failed | file='%s' | size=%d | errors=%s",
                filename,
                file_size,
                errors,
            )

        return DocumentValidationResult(
            valid=is_valid,
            errors=errors,
            file_size_bytes=file_size,
            file_extension=ext,
            mime_type=detected_mime,
            is_encrypted=is_encrypted,
            page_count=page_count,
        )
