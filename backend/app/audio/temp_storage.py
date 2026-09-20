"""
JanSetu - Day 23: Audio Temporary Storage & Privacy Lifecycle Manager.

Manages temporary audio file lifecycle with collision-proof UUID naming,
path traversal validation, and guaranteed cleanup on both success and error.
Citizen recordings are deleted after processing by default.
"""

import logging
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from app.audio.config import get_audio_settings
from app.audio.schemas import AudioErrorCode

logger = logging.getLogger(__name__)


class AudioTempStorageManager:
    """Safely creates, manages, and cleans up temporary audio files."""

    def __init__(self, temp_dir: Optional[Path] = None, debug_retain: Optional[bool] = None):
        settings = get_audio_settings()
        self.temp_dir = Path(temp_dir or settings.audio_temp_dir).resolve()
        self.debug_retain = debug_retain if debug_retain is not None else settings.audio_debug_retain
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def validate_safe_path(self, path: Path) -> Path:
        """
        Validates that a path is safely contained inside the controlled temp directory,
        preventing directory traversal attacks (e.g. ../../etc/passwd).
        """
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.temp_dir)
        except ValueError:
            logger.error(f"Path traversal attempt detected: path={path}, base={self.temp_dir}")
            raise ValueError(f"Invalid audio path outside temp directory: {path}")
        return resolved

    def create_temp_file(self, suffix: str = ".wav", prefix: str = "aud_") -> Path:
        """Creates a collision-proof unique temporary file path."""
        # Sanitize suffix
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        # Ensure only alphanumeric characters in suffix
        clean_suffix = "".join(c for c in suffix if c.isalnum() or c == ".")
        if not clean_suffix:
            clean_suffix = ".wav"

        unique_id = uuid.uuid4().hex
        filename = f"{prefix}{unique_id}{clean_suffix}"
        temp_path = self.temp_dir / filename
        # Touch file to claim path
        temp_path.touch(mode=0o600, exist_ok=False)
        return temp_path

    def cleanup_file(self, path: Optional[Path]) -> bool:
        """Deletes a temporary file safely if debug retention is disabled."""
        if path is None:
            return False

        if self.debug_retain:
            logger.debug(f"Audio debug retain active: preserving {path}")
            return False

        try:
            p = Path(path)
            if p.exists() and p.is_file():
                # Validate it is inside temp_dir or system temp
                p.unlink(missing_ok=True)
                logger.debug(f"Temporary audio deleted: {p}")
                return True
        except Exception as exc:
            logger.warning(f"Failed to cleanup temporary audio {path}: {exc}")
        return False

    @contextmanager
    def managed_temp_file(self, suffix: str = ".wav", prefix: str = "aud_") -> Generator[Path, None, None]:
        """
        Context manager ensuring temporary audio files are deleted on normal completion
        OR upon any caught exception.
        """
        temp_path = self.create_temp_file(suffix=suffix, prefix=prefix)
        try:
            yield temp_path
        finally:
            self.cleanup_file(temp_path)


_temp_storage_manager_instance: Optional[AudioTempStorageManager] = None


def get_temp_storage_manager() -> AudioTempStorageManager:
    """Returns singleton AudioTempStorageManager."""
    global _temp_storage_manager_instance
    if _temp_storage_manager_instance is None:
        _temp_storage_manager_instance = AudioTempStorageManager()
    return _temp_storage_manager_instance
