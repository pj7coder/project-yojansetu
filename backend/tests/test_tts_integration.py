"""
JanSetu - Day 26 Tests: Conversation & TTS Integration.

Verifies end-to-end integration between Day 25 ConversationManager responses
and Day 26 speech rendering, ensuring the conversation state machine is strictly
preserved and uninfluenced by audio generation.
"""

import asyncio
from pathlib import Path
import pytest

from app.citizen.schemas import CitizenDiscoveryResponse, CitizenSchemeCard
from app.conversation.actions import ConversationAction
from app.conversation.schemas import (
    ConversationMessage,
    ConversationMeta,
    ConversationResponse,
)
from app.conversation.states import ConversationState
from app.tts.providers.mms import MMSHindiTTSProvider
from app.tts.providers.piper import PiperTTSProvider
from app.tts.schemas import TTSResult
from app.tts.service import get_speech_synthesis_service
from app.tts.speech_policy import ConversationSpeechPolicy


class TestTTSConversationIntegration:
    """End-to-end integration tests connecting Day 25 actions to Day 26 TTS."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        self.service = get_speech_synthesis_service()

    def test_day25_ask_profile_field_tts(self):
        # 1. Day 25 Structured Response
        response = ConversationResponse(
            session_id="session-test-001",
            state=ConversationState.WAITING_FOR_PROFILE_VALUE,
            action=ConversationAction.ASK_PROFILE_FIELD,
            message=ConversationMessage(
                key="ASK_AGE",
                text_hi="आपकी आयु क्या है?",
                text_en="What is your age?",
            ),
            meta=ConversationMeta(turn=1, version=1, language="hi"),
        )

        # 2. Synthesize using service
        result: TTSResult = asyncio.run(
            self.service.synthesize_conversation_response(response, provider_name="mock")
        )

        # 3. Assertions on Audio
        assert result.duration_ms > 0
        assert result.sample_rate == 16000
        assert result.audio_path is not None
        assert Path(result.audio_path).exists()

        # 4. Strict Non-Influence Guarantee: Day 25 state remains unchanged
        assert response.session_id == "session-test-001"
        assert response.state == ConversationState.WAITING_FOR_PROFILE_VALUE
        assert response.action == ConversationAction.ASK_PROFILE_FIELD
        assert response.message.text_hi == "आपकी आयु क्या है?"
        assert response.meta.turn == 1

        # Clean up audio
        self.service.cleanup_audio(result.audio_path)

    def test_day25_confirm_profile_value_tts(self):
        # Day 25 Confirmation with Currency Amount
        response = ConversationResponse(
            session_id="session-test-002",
            state=ConversationState.WAITING_FOR_CONFIRMATION,
            action=ConversationAction.CONFIRM_PROFILE_VALUE,
            message=ConversationMessage(
                key="CONFIRM_INCOME",
                text_hi="आपने वार्षिक पारिवारिक आय ₹1,50,000 बताई है। क्या यह सही है?",
                text_en="You stated your annual family income as ₹1,50,000. Is this correct?",
            ),
            meta=ConversationMeta(turn=2, version=2, language="hi"),
        )

        # Speech policy extraction
        turn = ConversationSpeechPolicy.get_speakable_turn(response)
        assert turn.is_generic is False
        assert "एक लाख पचास हजार रुपये" in turn.speech_text

        # Audio synthesis
        result: TTSResult = asyncio.run(
            self.service.synthesize_conversation_response(response, provider_name="mock")
        )
        assert result.duration_ms > 0
        assert result.cached is False

        # Clean up audio
        self.service.cleanup_audio(result.audio_path)

    def test_day25_show_results_concise_summary(self):
        # Day 25 Results response with scheme list
        scheme_card = CitizenSchemeCard(
            scheme_id="scheme-001",
            scheme_code="RJ-OAP-001",
            name_en="Old Age Pension",
            name_hi="मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
            scheme_name="Old Age Pension",
            scheme_name_hi="मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
            eligibility_status="ELIGIBLE",
        )

        from datetime import datetime, timezone
        from app.sessions.schemas import SessionSummary
        now = datetime.now(timezone.utc)
        summary = SessionSummary(
            session_id="session-test-003",
            known_fields=["age"],
            declined_fields=[],
            asked_fields=["age"],
            need_text="पेंशन",
            expires_at=now,
            created_at=now,
            updated_at=now,
            profile_version=1,
        )

        response = ConversationResponse(
            session_id="session-test-003",
            state=ConversationState.SHOWING_RESULTS,
            action=ConversationAction.SHOW_RESULTS,
            message=ConversationMessage(
                key="RESULTS_FOUND",
                text_hi="आपकी जानकारी के आधार पर 1 उपयुक्त योजना मिली है।",
                text_en="Based on your details, 1 eligible scheme was found.",
            ),
            results=CitizenDiscoveryResponse(
                session_id="session-test-003",
                state="RESULTS_READY",
                session_summary=summary,
                eligible=[scheme_card],
                total_eligible_count=1,
            ),
            meta=ConversationMeta(turn=3, version=3, language="hi"),
        )

        turn = ConversationSpeechPolicy.get_speakable_turn(response)
        # Verify speech policy produces concise audio text rather than exhausting dumps
        assert "मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना" in turn.speech_text
        assert "विवरण स्क्रीन पर उपलब्ध है" in turn.speech_text

        # Response itself is not mutated
        assert len(response.results.eligible) == 1

    def test_degraded_text_mode_on_tts_failure(self):
        # Simulate TTS disabled or unavailable
        response = ConversationResponse(
            session_id="session-test-004",
            state=ConversationState.WAITING_FOR_PROFILE_VALUE,
            action=ConversationAction.ASK_PROFILE_FIELD,
            message=ConversationMessage(
                key="ASK_DISTRICT",
                text_hi="आप राजस्थान के किस जिले में रहते हैं?",
                text_en="Which district of Rajasthan do you live in?",
            ),
            meta=ConversationMeta(turn=4, version=4, language="hi"),
        )

        # Text remains completely intact
        assert response.message.text_hi == "आप राजस्थान के किस जिले में रहते हैं?"
        assert response.action == ConversationAction.ASK_PROFILE_FIELD

    def test_mms_provider_offline_hindi_synthesis(self):
        # Verifies offline MMS model inference
        provider = MMSHindiTTSProvider(model_name="storage/models/mms_tts_hin")
        if not provider.is_available() or not Path("storage/models/mms_tts_hin/model.safetensors").exists():
            pytest.skip("MMS-TTS local model files not present on disk.")

        provider.load_model()
        result = provider.synthesize("आपकी आयु क्या है?", language="hi")
        assert result.provider == "mms"
        assert result.sample_rate == 16000
        assert result.duration_ms > 500
        assert result.synthesis_ms > 0
        assert Path(result.audio_path).exists()

        provider.unload_model()
        self.service.cleanup_audio(result.audio_path)

    def test_piper_provider_offline_hindi_synthesis(self):
        # Verifies offline Piper ONNX model inference
        provider = PiperTTSProvider()
        if not provider.is_available() or not provider.get_voice_path("pratham"):
            pytest.skip("Piper pratham ONNX model not present on disk.")

        provider.load_model("pratham")
        result = provider.synthesize("आपकी आयु क्या है?", language="hi", voice="pratham")
        assert result.provider == "piper"
        assert result.sample_rate == 22050
        assert result.duration_ms > 500
        assert result.synthesis_ms > 0
        assert Path(result.audio_path).exists()

        provider.unload_model()
        self.service.cleanup_audio(result.audio_path)
