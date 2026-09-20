"""
JanSetu - Day 26: Generic Prompt Audio Cache.

Provides deterministic filesystem caching for static, non-sensitive prompts
(e.g., greetings, standard questions, confirmations).
Strictly prevents caching of personalized citizen data.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from app.config.tts import get_tts_settings
from app.tts.schemas import TTSResult

logger = logging.getLogger(__name__)


class GenericPromptCache:
    """Deterministic local disk cache for generic system prompts."""

    def __init__(self, cache_dir: Optional[Path] = None, enabled: Optional[bool] = None):
        settings = get_tts_settings()
        self.cache_dir = Path(cache_dir or settings.tts_cache_dir).resolve()
        self.enabled = enabled if enabled is not None else settings.tts_cache_generic_prompts
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_key(
        self,
        provider: str,
        model: str,
        voice: Optional[str],
        language: str,
        speech_text: str,
        speaking_rate: float,
    ) -> str:
        """Computes a deterministic SHA-256 fingerprint for a synthesis request."""
        payload = f"{provider.lower()}|{model.lower()}|{voice or ''}|{language.lower()}|{speech_text.strip()}|{speaking_rate:.2f}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Tuple[Path, dict]]:
        """
        Retrieves cached audio path and metadata if present.
        Returns None if cache is disabled or key not found.
        """
        if not self.enabled:
            return None

        audio_file = self.cache_dir / f"{cache_key}.wav"
        meta_file = self.cache_dir / f"{cache_key}.json"

        if audio_file.exists() and meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                return audio_file, meta
            except Exception as exc:
                logger.warning(f"Error reading TTS cache entry {cache_key}: {exc}")
                return None
        return None

    def store(
        self,
        cache_key: str,
        audio_path_or_bytes: Path | bytes,
        meta: dict,
    ) -> Optional[Path]:
        """
        Stores synthesized audio and its metadata in the generic prompt cache.
        """
        if not self.enabled:
            return None

        target_audio = self.cache_dir / f"{cache_key}.wav"
        target_meta = self.cache_dir / f"{cache_key}.json"

        try:
            if isinstance(audio_path_or_bytes, (bytes, bytearray)):
                with open(target_audio, "wb") as f:
                    f.write(audio_path_or_bytes)
            elif isinstance(audio_path_or_bytes, Path):
                with open(audio_path_or_bytes, "rb") as src, open(target_audio, "wb") as dst:
                    dst.write(src.read())

            with open(target_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)

            logger.debug(f"Stored prompt in TTS cache: key={cache_key}")
            return target_audio
        except Exception as exc:
            logger.warning(f"Failed to store prompt in TTS cache: {exc}")
            return None


_generic_prompt_cache_instance: Optional[GenericPromptCache] = None


def get_generic_prompt_cache() -> GenericPromptCache:
    """Returns singleton GenericPromptCache."""
    global _generic_prompt_cache_instance
    if _generic_prompt_cache_instance is None:
        _generic_prompt_cache_instance = GenericPromptCache()
    return _generic_prompt_cache_instance
