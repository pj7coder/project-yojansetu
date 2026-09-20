"""
YojanSetu - Day 26 Tests: Speech Synthesis Service & Lifecycle.

Tests service orchestration, caching boundaries, input constraints,
temporary storage cleanup, and provider safety using standard asyncio.run().
"""

import asyncio
from pathlib import Path
import numpy as np
import pytest

from app.tts.audio_validation import AudioValidationError, AudioValidator
from app.tts.cache import get_generic_prompt_cache
from app.tts.registry import get_tts_registry
from app.tts.schemas import TTSErrorCode, TTSResult
from app.tts.service import get_speech_synthesis_service
from app.tts.temp_storage import get_tts_temp_manager


class TestSpeechSynthesisService:
    """Tests for high-level SpeechSynthesisService."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = get_speech_synthesis_service()
        self.temp_mgr = get_tts_temp_manager()
        self.cache = get_generic_prompt_cache()

    def test_empty_and_whitespace_rejection(self):
        with pytest.raises(ValueError) as exc:
            asyncio.run(self.service.synthesize_text("", provider_name="mock"))
        assert TTSErrorCode.TTS_EMPTY_TEXT.value in str(exc.value)

        with pytest.raises(ValueError) as exc2:
            asyncio.run(self.service.synthesize_text("   \n\t  ", provider_name="mock"))
        assert TTSErrorCode.TTS_EMPTY_TEXT.value in str(exc2.value)

    def test_too_long_text_rejection(self):
        long_text = "योजना " * 150  # Over 600 chars
        with pytest.raises(ValueError) as exc:
            asyncio.run(self.service.synthesize_text(long_text, provider_name="mock"))
        assert TTSErrorCode.TTS_TEXT_TOO_LONG.value in str(exc.value)

    def test_mock_provider_synthesis(self):
        text = "आपकी आयु क्या है?"
        result: TTSResult = asyncio.run(self.service.synthesize_text(
            text=text,
            language="hi",
            provider_name="mock",
        ))
        assert result.provider == "mock"
        assert result.audio_format == "wav"
        assert result.sample_rate == 16000
        assert result.duration_ms > 0
        assert result.synthesis_ms > 0
        assert result.rtf is not None
        assert result.audio_path is not None
        assert Path(result.audio_path).exists()

        # Clean up
        self.service.cleanup_audio(result.audio_path)
        assert not Path(result.audio_path).exists()

    def test_generic_prompt_caching(self):
        import uuid
        # Unique generic prompt to test caching
        text = f"नमस्ते, राजस्थान सरकार के योजनसेतु पोर्टल में आपका स्वागत है {uuid.uuid4().hex}।"

        # First call: not cached
        res1 = asyncio.run(self.service.synthesize_text(
            text=text,
            provider_name="mock",
            is_generic=True,
        ))
        assert res1.cached is False

        # Second call: should hit generic prompt cache
        res2 = asyncio.run(self.service.synthesize_text(
            text=text,
            provider_name="mock",
            is_generic=True,
        ))
        assert res2.cached is True
        assert res2.audio_path == res1.audio_path

    def test_personalized_prompt_not_cached(self):
        # Sensitive prompt containing citizen income value
        text = "आपने वार्षिक पारिवारिक आय ₹1,50,000 बताई है।"

        res1 = asyncio.run(self.service.synthesize_text(
            text=text,
            provider_name="mock",
            is_generic=False,
        ))
        assert res1.cached is False

        res2 = asyncio.run(self.service.synthesize_text(
            text=text,
            provider_name="mock",
            is_generic=False,
        ))
        # Personalized prompts are not returned from cache
        assert res2.cached is False

        # Cleanup
        self.service.cleanup_audio(res1.audio_path)
        self.service.cleanup_audio(res2.audio_path)

    def test_audio_validator_silence_detection(self):
        silent_signal = np.zeros(16000, dtype=np.float32)
        with pytest.raises(AudioValidationError) as exc:
            AudioValidator.validate_and_measure(silent_signal, sample_rate=16000)
        assert exc.value.code == TTSErrorCode.TTS_EMPTY_AUDIO

    def test_temp_file_lifecycle_and_cleanup(self):
        temp_file = self.temp_mgr.create_temp_file(suffix=".wav")
        assert temp_file.exists()

        # Test context manager cleanup
        with self.temp_mgr.managed_temp_file() as p:
            assert p.exists()
            target_p = p
        assert not target_p.exists()

        # Manual cleanup
        cleaned = self.temp_mgr.cleanup_file(temp_file)
        assert cleaned is True
        assert not temp_file.exists()

    def test_unallowlisted_provider_rejection(self):
        registry = get_tts_registry()
        with pytest.raises(ValueError) as exc:
            registry.get_provider("untrusted_cloud_engine")
        assert TTSErrorCode.TTS_UNAVAILABLE.value in str(exc.value)

    def test_concurrency_semaphore(self):
        texts = [
            "आपकी आयु क्या है?",
            "आपका जिला कौन सा है?",
            "वार्षिक आय कितनी है?",
            "क्या आप बीपीएल हैं?"
        ]
        async def _run_all():
            tasks = [
                self.service.synthesize_text(t, provider_name="mock")
                for t in texts
            ]
            return await asyncio.gather(*tasks)

        results = asyncio.run(_run_all())
        assert len(results) == 4
        for r in results:
            assert r.duration_ms > 0
            self.service.cleanup_audio(r.audio_path)

    def test_service_status_diagnostics(self):
        status = self.service.get_status()
        assert "tts_enabled" in status
        assert "default_provider" in status
        assert "available_providers" in status
        assert "mock" in status["available_providers"]
        assert "mms" in status["available_providers"]
        assert "piper" in status["available_providers"]
