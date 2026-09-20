"""
YojanSetu - Day 26: TTS Provider Registry & Concurrency Manager.

Maintains an allowlisted registry of offline TTS providers and enforces
bounded concurrency guards for inference safety.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from app.config.tts import get_tts_settings
from app.tts.interface import TextToSpeechProvider
from app.tts.providers.mock import MockTTSProvider
from app.tts.providers.mms import MMSHindiTTSProvider
from app.tts.providers.piper import PiperTTSProvider
from app.tts.schemas import TTSErrorCode

logger = logging.getLogger(__name__)

# Strict allowlist mapping of provider names to factory constructors
ALLOWLISTED_PROVIDERS = {
    "mms": lambda: MMSHindiTTSProvider(
        model_name="storage/models/mms_tts_hin" if Path("storage/models/mms_tts_hin").exists() else "facebook/mms-tts-hin"
    ),
    "piper": lambda: PiperTTSProvider(),
    "mock": lambda: MockTTSProvider(),
}

from pathlib import Path


class TTSRegistry:
    """Singleton registry holding instantiated offline TTS providers."""

    def __init__(self):
        self._providers: Dict[str, TextToSpeechProvider] = {}
        settings = get_tts_settings()
        self._concurrency_semaphore = asyncio.Semaphore(settings.tts_max_concurrent_inference)

    def get_semaphore(self) -> asyncio.Semaphore:
        """Returns bounded concurrency semaphore."""
        return self._concurrency_semaphore

    def list_available_providers(self) -> List[str]:
        """Returns list of all allowlisted provider keys."""
        return list(ALLOWLISTED_PROVIDERS.keys())

    def get_provider(self, name: Optional[str] = None) -> TextToSpeechProvider:
        """
        Retrieves or lazily instantiates an allowlisted TTS provider.

        Args:
            name: Provider name ('mms', 'piper', 'mock'). If None, uses default settings.

        Raises:
            ValueError: If an untrusted/unallowlisted provider name is requested.
        """
        settings = get_tts_settings()
        provider_name = (name or settings.tts_default_provider).lower().strip()

        if provider_name not in ALLOWLISTED_PROVIDERS:
            raise ValueError(
                f"{TTSErrorCode.TTS_UNAVAILABLE.value}: Provider '{provider_name}' is not in allowlist: "
                f"{list(ALLOWLISTED_PROVIDERS.keys())}"
            )

        if provider_name not in self._providers:
            logger.info(f"Initializing TTS provider adapter: '{provider_name}'")
            factory = ALLOWLISTED_PROVIDERS[provider_name]
            self._providers[provider_name] = factory()

        return self._providers[provider_name]

    def unload_all(self) -> None:
        """Unloads all active models to release memory."""
        for name, prov in self._providers.items():
            if prov.is_loaded():
                logger.info(f"Unloading provider '{name}' from memory...")
                prov.unload_model()


_tts_registry_instance: Optional[TTSRegistry] = None


def get_tts_registry() -> TTSRegistry:
    """Returns singleton TTSRegistry."""
    global _tts_registry_instance
    if _tts_registry_instance is None:
        _tts_registry_instance = TTSRegistry()
    return _tts_registry_instance
