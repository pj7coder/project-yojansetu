import datetime
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger("jansetu.ingestion.storage")


class StorageManager:
    """
    Manages safe filesystem storage operations for government documents.

    Guarantees:
    - Path traversal prevention
    - Deterministic storage layout: storage/originals/<document_id>/original.pdf
    - Failed file isolation: storage/failed/<document_id>_<safe_filename>
    - Relative platform-agnostic path tracking in database
    """

    def __init__(self, storage_root: Optional[Path] = None):
        settings = get_settings()
        self.storage_root = (storage_root or settings.storage_path).resolve()
        self.incoming_dir = self.storage_root / "incoming"
        self.originals_dir = self.storage_root / "originals"
        self.failed_dir = self.storage_root / "failed"
        self.archived_dir = self.storage_root / "archived"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure all required storage directories exist."""
        for directory in [self.incoming_dir, self.originals_dir, self.failed_dir, self.archived_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize user-provided filename to prevent path traversal and unsafe characters.

        Preserves unicode characters (like Hindi) while removing control characters,
        path separators, and reserved system characters.
        """
        # Strip directory components to prevent path traversal
        clean_name = os.path.basename(filename).strip()
        # Remove null bytes
        clean_name = clean_name.replace("\x00", "")
        # Replace Windows/POSIX reserved characters: < > : " / \ | ? *
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)
        # Prevent leading dots/hidden files or parent traversal
        clean_name = clean_name.lstrip(".")
        if not clean_name:
            clean_name = "unnamed_document.pdf"
        return clean_name

    @staticmethod
    def generate_document_code() -> str:
        """
        Generate a unique, stable internal document code.
        Format: DOC-YYYY-XXXXXXXX (e.g., DOC-2026-A1B2C3D4)
        """
        current_year = datetime.datetime.now(datetime.timezone.utc).year
        random_suffix = uuid.uuid4().hex[:8].upper()
        return f"DOC-{current_year}-{random_suffix}"

    def get_relative_path(self, absolute_path: Path) -> str:
        """Convert an absolute Path inside storage_root to a relative POSIX string."""
        resolved = absolute_path.resolve()
        try:
            rel = resolved.relative_to(self.storage_root)
            return rel.as_posix()
        except ValueError:
            # If not relative to storage_root, return as posix string
            return str(resolved)

    def resolve_storage_path(self, relative_path: str) -> Optional[Path]:
        """
        Safely resolve a stored relative path to an absolute path on the filesystem.
        Ensures the path does not escape the storage_root directory.
        """
        # Normalize and resolve target path
        target = (self.storage_root / relative_path).resolve()
        # Check boundary containment (path traversal prevention)
        try:
            target.relative_to(self.storage_root)
        except ValueError:
            logger.error("Security violation: Attempted path traversal via '%s'", relative_path)
            return None

        if not target.exists() or not target.is_file():
            return None

        return target

    def store_original(
        self,
        source_path: Path,
        document_id: uuid.UUID,
        file_extension: str = ".pdf",
        move: bool = True,
    ) -> Path:
        """
        Store an untouched original government document/spreadsheet in its permanent deterministic location:
        storage/originals/<document_id>/original.<ext>

        :param source_path: Path to the source file to store.
        :param document_id: Unique UUID of the document entity.
        :param file_extension: File extension including dot, e.g. '.pdf', '.xlsx', '.xls', '.csv'.
        :param move: If True, moves the file; if False, copies the file.
        :return: Absolute Path to the stored original file.
        """
        doc_dir = self.originals_dir / str(document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        ext = file_extension if file_extension.startswith(".") else f".{file_extension}"
        target_path = doc_dir / f"original{ext.lower()}"

        if move:
            shutil.move(str(source_path), str(target_path))
            logger.info("Moved original document to %s", target_path)
        else:
            shutil.copy2(str(source_path), str(target_path))
            logger.info("Copied original document to %s", target_path)

        return target_path

    def store_failed(
        self,
        source_path: Path,
        document_id: uuid.UUID,
        original_filename: str,
        move: bool = True,
    ) -> Path:
        """
        Move an invalid or unprocessable document to storage/failed/ for isolation and inspection.

        :param source_path: Path to the failed file.
        :param document_id: Unique UUID of the document entity.
        :param original_filename: Original filename to include in failure path.
        :param move: If True, moves the file; if False, copies the file.
        :return: Absolute Path to the stored failed file.
        """
        safe_name = self.sanitize_filename(original_filename)
        target_filename = f"{document_id}_{safe_name}"
        target_path = self.failed_dir / target_filename

        if move and source_path.exists():
            shutil.move(str(source_path), str(target_path))
            logger.warning("Moved failed document to %s", target_path)
        elif source_path.exists():
            shutil.copy2(str(source_path), str(target_path))
            logger.warning("Copied failed document to %s", target_path)

        return target_path
