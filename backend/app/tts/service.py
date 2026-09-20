"""
YojanSetu - Day 26: High-Level Speech Synthesis Service.

Orchestrates speech text preparation, generic prompt caching, concurrency control,
provider dispatch, output validation, and ephemeral audio lifecycle.

TTS is strictly a voice renderer and never mutates conversation state or profile facts.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.tts import get_tts_settings
from app.conversation.schemas import ConversationResponse
from app.tts.audio_validation import AudioValidator
from app.tts.cache import get_generic_prompt_cache
from app.tts.registry import get_tts_registry
from app.tts.schemas import TTSErrorCode, TTSResult
from app.tts.speech_normalizer import SpeechTextNormalizer
from app.tts.speech_policy import ConversationSpeechPolicy, SpeakableTurn
from app.tts.temp_storage import get_tts_temp_manager

logger = logging.getLogger(__name__)


class SpeechSynthesisService:
    """
    Unified speech synthesis service for YojanSetu.
    """

    def __init__(self):
        self.settings = get_tts_settings()
        self.registry = get_tts_registry()
        self.cache = get_generic_prompt_cache()
        self.temp_storage = get_tts_temp_manager()

    async def synthesize_text(
        self,
        text: str,
        language: str = "hi",
        voice: Optional[str] = None,
        speaking_rate: Optional[float] = None,
        provider_name: Optional[str] = None,
        is_generic: bool = False,
    ) -> TTSResult:
        """
        Synthesizes text into speech audio.

        Args:
            text: Raw or display text to synthesize.
            language: 'hi' or 'en'.
            voice: Optional voice name.
            speaking_rate: Rate multiplier (e.g. 1.0).
            provider_name: Optional override ('mms', 'piper', 'mock').
            is_generic: If True, static non-sensitive prompt can be cached.

        Returns:
            TTSResult with latency and ephemeral audio path.
        """
        if not self.settings.tts_enabled:
            raise RuntimeError(f"{TTSErrorCode.TTS_UNAVAILABLE.value}: TTS is disabled in configuration")

        if not text or not text.strip():
            raise ValueError(f"{TTSErrorCode.TTS_EMPTY_TEXT.value}: Cannot synthesize empty or whitespace text")

        # Step 1: Deterministic Speech Normalization
        speech_text = SpeechTextNormalizer.normalize_for_speech(text)
        if not speech_text:
            raise ValueError(f"{TTSErrorCode.TTS_EMPTY_TEXT.value}: Text normalized to empty string")

        if len(speech_text) > self.settings.tts_max_text_chars:
            raise ValueError(
                f"{TTSErrorCode.TTS_TEXT_TOO_LONG.value}: Text length ({len(speech_text)} chars) "
                f"exceeds max threshold ({self.settings.tts_max_text_chars} chars)"
            )

        provider = self.registry.get_provider(provider_name)
        rate = speaking_rate or self.settings.tts_speaking_rate

        # Step 2: Check generic prompt cache if eligible
        cache_key = None
        if is_generic and self.settings.tts_cache_generic_prompts:
            cache_key = self.cache.generate_key(
                provider=provider.name,
                model=provider.model_name,
                voice=voice,
                language=language,
                speech_text=speech_text,
                speaking_rate=rate,
            )
            cached_entry = self.cache.get(cache_key)
            if cached_entry:
                audio_file, meta = cached_entry
                logger.debug(f"TTS generic prompt cache hit: {cache_key}")
                return TTSResult(
                    provider=provider.name,
                    model=provider.model_name,
                    voice=voice or meta.get("voice"),
                    language=language,
                    duration_ms=meta.get("duration_ms", 0.0),
                    synthesis_ms=meta.get("synthesis_ms", 0.0),
                    sample_rate=meta.get("sample_rate", provider.default_sample_rate),
                    audio_format="wav",
                    audio_path=str(audio_file),
                    cached=True,
                )

        # Step 3: Guarded synthesis with bounded concurrency
        semaphore = self.registry.get_semaphore()
        async with semaphore:
            # Run CPU-bound synthesis in thread pool to keep asyncio event loop responsive
            loop = asyncio.get_running_loop()
            result: TTSResult = await loop.run_in_executor(
                None,
                provider.synthesize,
                speech_text,
                language,
                voice,
                rate,
            )

        # Step 4: Store in generic prompt cache if eligible
        if is_generic and cache_key and result.audio_path:
            meta = {
                "provider": result.provider,
                "model": result.model,
                "voice": result.voice,
                "language": result.language,
                "duration_ms": result.duration_ms,
                "synthesis_ms": result.synthesis_ms,
                "sample_rate": result.sample_rate,
                "speech_text": speech_text,
            }
            cached_file = self.cache.store(cache_key, Path(result.audio_path), meta)
            if cached_file:
                # Cleanup ephemeral tmp file since cached version is now canonical
                self.temp_storage.cleanup_file(Path(result.audio_path))
                result.audio_path = str(cached_file)

        return result

    async def synthesize_conversation_response(
        self,
        response: ConversationResponse,
        preferred_language: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> TTSResult:
        """
        Synthesizes a Day 25 ConversationResponse according to ConversationSpeechPolicy.
        Conversation state machine and response data remain 100% UNTOUCHED.
        """
        # Step 1: Extract speakable turn
        turn: SpeakableTurn = ConversationSpeechPolicy.get_speakable_turn(
            response=response,
            preferred_language=preferred_language,
        )

        # Step 2: Synthesize
        return await self.synthesize_text(
            text=turn.speech_text,
            language=turn.language,
            provider_name=provider_name,
            is_generic=turn.is_generic,
        )

    def cleanup_audio(self, path: Optional[str]) -> bool:
        """Cleans up a temporary synthesized audio file."""
        if path:
            return self.temp_storage.cleanup_file(Path(path))
        return False

    def get_status(self) -> Dict[str, Any]:
        """Diagnostic health status for admin dashboard and monitoring."""
        try:
            default_prov = self.registry.get_provider()
            prov_name = default_prov.name
            prov_model = default_prov.model_name
            prov_avail = default_prov.is_available()
            prov_loaded = default_prov.is_loaded()
        except Exception as exc:
            prov_name = self.settings.tts_default_provider
            prov_model = self.settings.tts_default_model
            prov_avail = False
            prov_loaded = False

        return {
            "tts_enabled": self.settings.tts_enabled,
            "default_provider": prov_name,
            "default_model": prov_model,
            "provider_available": prov_avail,
            "model_loaded": prov_loaded,
            "available_providers": self.registry.list_available_providers(),
            "device": self.settings.tts_device,
            "cache_enabled": self.settings.tts_cache_generic_prompts,
            "version": self.settings.tts_version,
        }


_speech_service_instance: Optional[SpeechSynthesisService] = None


def get_speech_synthesis_service() -> SpeechSynthesisService:
    """Returns singleton SpeechSynthesisService."""
    global _speech_service_instance
    if _speech_service_instance is None:
        _speech_service_instance = SpeechSynthesisService()
    return _speech_service_instance
