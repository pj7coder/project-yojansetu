"""
YojanSetu - Day 26: Temporary Audio Storage & Ephemeral Lifecycle Manager.

Ensures citizen-specific speech audio is saved to secure, collision-proof temporary
files and deleted immediately after serving or upon any synthesis failure.
"""

import logging
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from app.config.tts import get_tts_settings

logger = logging.getLogger(__name__)


class TTSTempStorageManager:
    """Manages ephemeral lifecycle of synthesized speech audio files."""

    def __init__(self, temp_dir: Optional[Path] = None, debug_retain: Optional[bool] = None):
        settings = get_tts_settings()
        self.temp_dir = Path(temp_dir or settings.tts_temp_dir).resolve()
        self.debug_retain = debug_retain if debug_retain is not None else settings.tts_debug_retain_audio
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def validate_safe_path(self, path: Path) -> Path:
        """Validates that a path is safely contained inside the controlled temp directory."""
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.temp_dir)
        except ValueError:
            logger.error(f"Path traversal attempt in TTS temp storage: path={path}, base={self.temp_dir}")
            raise ValueError(f"Invalid TTS audio path outside temp directory: {path}")
        return resolved

    def create_temp_file(self, suffix: str = ".wav", prefix: str = "tts_") -> Path:
        """Creates a collision-proof unique temporary file path."""
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        clean_suffix = "".join(c for c in suffix if c.isalnum() or c == ".")
        if not clean_suffix:
            clean_suffix = ".wav"

        unique_id = uuid.uuid4().hex
        filename = f"{prefix}{unique_id}{clean_suffix}"
        temp_path = self.temp_dir / filename
        # Ensure file exists
        temp_path.touch(mode=0o600, exist_ok=False)
        return temp_path

    def cleanup_file(self, path: Optional[Path]) -> bool:
        """Deletes a temporary audio file safely unless debug retention is active."""
        if path is None:
            return False

        if self.debug_retain:
            logger.debug(f"TTS debug retain active: preserving {path}")
            return False

        try:
            p = Path(path)
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
                logger.debug(f"Temporary TTS audio deleted: {p}")
                return True
        except Exception as exc:
            logger.warning(f"Failed to cleanup temporary TTS audio {path}: {exc}")
        return False

    @contextmanager
    def managed_temp_file(self, suffix: str = ".wav", prefix: str = "tts_") -> Generator[Path, None, None]:
        """
        Context manager guaranteeing that the created temporary file is cleaned up
        upon normal completion OR when any exception occurs.
        """
        temp_path = self.create_temp_file(suffix=suffix, prefix=prefix)
        try:
            yield temp_path
        finally:
            self.cleanup_file(temp_path)


_tts_temp_manager_instance: Optional[TTSTempStorageManager] = None


def get_tts_temp_manager() -> TTSTempStorageManager:
    """Returns singleton TTSTempStorageManager."""
    global _tts_temp_manager_instance
    if _tts_temp_manager_instance is None:
        _tts_temp_manager_instance = TTSTempStorageManager()
    return _tts_temp_manager_instance
