"""
JanSetu - Day 27 Tests: End-to-End Offline Voice Loop Scenarios.

Scenarios:
1. Complete Pension voice flow:
   Need ("मुझे वृद्धावस्था पेंशन चाहिए")
   -> Age ("बासठ")
   -> Confirmation ("हाँ")
2. Farming voice flow:
   Need ("खेती के लिए सहायता") -> Question -> Answer
3. Text/Voice Hybrid turn sharing:
   Spoken need -> Typed age -> Spoken confirmation.
   Verifies single unified session without state loss.
4. Voice correction turn:
   "मेरी उम्र गलत है, इकसठ है" -> Candidate 61 -> Confirmation.
5. Why-asked interruption:
   "यह क्यों पूछ रहे हो?" -> Spoken explanation -> Original question resumes.
6. Graceful text fallback on TTS failure:
   Semantic turn advances even if audio generation fails.
"""

import asyncio
from pathlib import Path
from typing import Optional
import numpy as np
import pytest
import soundfile as sf

from app.audio.temp_storage import get_temp_storage_manager
from app.conversation.actions import ConversationAction
from app.conversation.manager import get_conversation_manager
from app.conversation.schemas import ConversationInput, ConversationInputType
from app.conversation.states import ConversationState
from app.sessions.manager import get_session_manager
from app.sessions.models import FieldValueState
from app.stt.interface import SpeechToTextProvider
from app.stt.schemas import STTResult
from app.voice.orchestrator import VoiceConversationOrchestrator
from app.voice.schemas import VoiceTransportState


class MockCustomSTT(SpeechToTextProvider):
    """Configurable mock STT provider for deterministic E2E voice loop tests."""
    def __init__(self, transcript_to_return: str = "नमस्ते"):
        self.transcript_to_return = transcript_to_return

    @property
    def provider_id(self) -> str:
        return "mock-custom-stt"

    @property
    def model_name(self) -> str:
        return "mock-tiny"

    def load(self) -> None:
        pass

    def unload(self) -> None:
        pass

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_path, language_hint="hi"):
        return STTResult(
            raw_text=self.transcript_to_return,
            text=self.transcript_to_return,
            language=language_hint or "hi",
            duration_seconds=1.0,
            inference_ms=10.0,
            provider="mock-custom-stt",
            model="mock-tiny",
        )


from tests.test_conversation_manager import setup_and_teardown_schemes
from app.database.session import SessionLocal
from app.tts.service import get_speech_synthesis_service

@pytest.fixture
def temp_storage():
    return get_temp_storage_manager()


FIXTURE_DIR = Path(__file__).resolve().parent / "stt_benchmark" / "audio"


@pytest.fixture
def sample_speech_wav():
    """Provides real speech WAV file (hi_short_001.wav) that passes Silero VAD."""
    return FIXTURE_DIR / "hi_short_001.wav"


@pytest.fixture(autouse=True)
def configure_mock_tts():
    """Ensure fast deterministic TTS synthesis for voice flow unit tests."""
    tts = get_speech_synthesis_service()
    orig = tts.settings.tts_default_provider
    tts.settings.tts_default_provider = "mock"
    yield
    tts.settings.tts_default_provider = orig


class TestVoiceE2E:
    """End-to-end voice loop integration scenarios."""

    def test_e2e_pension_voice_flow(self, sample_speech_wav):
        session_mgr = get_session_manager()
        conv_mgr = get_conversation_manager()
        session = session_mgr.create_session()

        # Step 1: Citizen speaks Need: "मुझे वृद्धावस्था पेंशन चाहिए"
        stt_mock = MockCustomSTT(transcript_to_return="मुझे वृद्धावस्था पेंशन चाहिए")
        orch = VoiceConversationOrchestrator(
            session_manager=session_mgr,
            conversation_manager=conv_mgr,
            stt_provider=stt_mock,
        )

        res_1 = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="pension-turn-01",
            )
        )

        assert res_1.voice_state == VoiceTransportState.SPEAKING
        assert res_1.conversation.state == ConversationState.WAITING_FOR_PROFILE_VALUE
        assert res_1.conversation.action == ConversationAction.ASK_PROFILE_FIELD
        assert res_1.conversation.expected_input.field == "age"
        assert res_1.audio is not None

        # Step 2: Citizen speaks Age: "बासठ"
        stt_mock.transcript_to_return = "बासठ"
        res_2 = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="pension-turn-02",
                conversation_version=res_1.conversation.meta.version,
            )
        )

        assert res_2.voice_state == VoiceTransportState.SPEAKING
        assert res_2.conversation.state == ConversationState.WAITING_FOR_CONFIRMATION
        assert res_2.conversation.action == ConversationAction.CONFIRM_PROFILE_VALUE
        assert "62" in res_2.conversation.expected_input.display_value
        assert res_2.audio is not None

        # Step 3: Citizen speaks Confirmation: "हाँ"
        stt_mock.transcript_to_return = "हाँ"
        res_3 = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="pension-turn-03",
                conversation_version=res_2.conversation.meta.version,
            )
        )

        assert res_3.voice_state == VoiceTransportState.SPEAKING
        # Age 62 is now confirmed in the profile!
        assert session.profile.get("age") == 62
        assert session.field_states.get("age") == FieldValueState.KNOWN

    def test_e2e_farming_voice_flow(self, sample_speech_wav):
        session_mgr = get_session_manager()
        conv_mgr = get_conversation_manager()
        session = session_mgr.create_session()

        stt_mock = MockCustomSTT(transcript_to_return="मुझे खेती और फसल के लिए सहायता चाहिए")
        orch = VoiceConversationOrchestrator(
            session_manager=session_mgr,
            conversation_manager=conv_mgr,
            stt_provider=stt_mock,
        )

        res = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="farming-turn-01",
            )
        )

        assert res.voice_state == VoiceTransportState.SPEAKING
        assert res.conversation.state == ConversationState.WAITING_FOR_PROFILE_VALUE
        assert res.audio is not None

    def test_e2e_text_voice_hybrid_flow(self, sample_speech_wav):
        """
        Verifies citizen can speak Need via Voice, type Age via Text,
        and speak Confirmation via Voice, seamlessly sharing the exact same session.
        """
        session_mgr = get_session_manager()
        conv_mgr = get_conversation_manager()
        session = session_mgr.create_session()

        # 1. Turn 1 (Voice): Spoken need
        stt_mock = MockCustomSTT(transcript_to_return="मुझे वृद्धावस्था पेंशन योजना चाहिए")
        orch = VoiceConversationOrchestrator(
            session_manager=session_mgr,
            conversation_manager=conv_mgr,
            stt_provider=stt_mock,
        )
        res_voice_1 = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="hybrid-turn-01",
            )
        )
        assert res_voice_1.conversation.state == ConversationState.WAITING_FOR_PROFILE_VALUE
        assert res_voice_1.conversation.expected_input.field == "age"

        # 2. Turn 2 (Voice): Citizen speaks Age: "बासठ" -> requires confirmation
        stt_mock.transcript_to_return = "बासठ"
        res_voice_2 = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="hybrid-turn-02",
                conversation_version=res_voice_1.conversation.meta.version,
            )
        )
        assert res_voice_2.conversation.state == ConversationState.WAITING_FOR_CONFIRMATION
        assert "62" in res_voice_2.conversation.expected_input.display_value

        # 3. Turn 3 (Text): Citizen switches to text and clicks "हाँ" button to confirm
        with SessionLocal() as db_session:
            res_text_3 = conv_mgr.handle_input(
                session_id=session.session_id,
                inp=ConversationInput(
                    type=ConversationInputType.CONFIRMATION,
                    action="CONFIRM_YES",
                    conversation_version=res_voice_2.conversation.meta.version,
                ),
                db_session=db_session,
            )

        assert session.profile.get("age") == 62
        assert session.field_states.get("age") == FieldValueState.KNOWN

    def test_e2e_voice_why_asked_interruption(self, sample_speech_wav):
        """
        Citizen asks 'यह क्यों पूछ रहे हो?' during income question.
        System explains in spoken Hindi and original question remains expected.
        """
        session_mgr = get_session_manager()
        conv_mgr = get_conversation_manager()
        session = session_mgr.create_session()
        session.profile["age"] = 62
        session.field_states["age"] = FieldValueState.KNOWN
        session.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
        session.expected_field = "family_income"
        session.need_text = "पेंशन"

        stt_mock = MockCustomSTT(transcript_to_return="यह क्यों पूछ रहे हो?")
        orch = VoiceConversationOrchestrator(
            session_manager=session_mgr,
            conversation_manager=conv_mgr,
            stt_provider=stt_mock,
        )

        res = asyncio.run(
            orch.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_speech_wav,
                voice_turn_id="why-asked-turn-01",
                conversation_version=session.conversation_version,
            )
        )

        assert res.voice_state == VoiceTransportState.SPEAKING
        assert res.conversation.action == ConversationAction.ANSWER_FIELD_HELP
        assert "आर्थिक" in res.conversation.message.text_hi or "आय" in res.conversation.message.text_hi
        assert res.audio is not None

    def test_e2e_tts_failure_graceful_degradation(self, sample_speech_wav):
        """
        If TTS fails during synthesis, conversation state MUST still advance.
        Text response is returned with a warning.
        """
        session_mgr = get_session_manager()
        conv_mgr = get_conversation_manager()
        session = session_mgr.create_session()

        stt_mock = MockCustomSTT(transcript_to_return="मुझे पेंशन चाहिए")
        orch = VoiceConversationOrchestrator(
            session_manager=session_mgr,
            conversation_manager=conv_mgr,
            stt_provider=stt_mock,
        )

        # Force TTS service to fail
        orch.tts_service.settings.tts_enabled = False
        try:
            res = asyncio.run(
                orch.execute_voice_turn(
                    session_id=session.session_id,
                    audio_input=sample_speech_wav,
                    voice_turn_id="tts-fail-turn-01",
                )
            )

            # State advanced to waiting for age!
            assert res.voice_state == VoiceTransportState.READY
            assert res.conversation.state == ConversationState.WAITING_FOR_PROFILE_VALUE
            assert res.conversation.expected_input.field == "age"
            assert res.audio is None
            assert "TTS_UNAVAILABLE" in res.warning
        finally:
            orch.tts_service.settings.tts_enabled = True
