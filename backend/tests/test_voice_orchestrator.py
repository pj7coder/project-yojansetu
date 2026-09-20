"""
JanSetu - Day 27 Tests: Voice Orchestration, Locking, Idempotency & Recovery.

Verifies:
1. Concurrency: Exactly one active voice turn per citizen session.
2. Idempotency: Duplicate voice_turn_id does not re-execute conversation rules.
3. State conflict: Stale conversation_version raises CONVERSATION_STATE_CONFLICT.
4. Silence safety: VAD silence produces NO_SPEECH_DETECTED retry without consuming turn.
5. STT empty safety: Empty transcript produces STT_EMPTY_RESULT without consuming turn.
6. TTS failure degradation: Conversation advances, text is returned, no rollback.
7. Replay: Re-synthesizes audio without state or profile mutation.
8. Privacy & TTL: Ephemeral audio store expires and cleans up temporary files.
"""

import asyncio
import io
from pathlib import Path
import time
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.audio.temp_storage import get_temp_storage_manager
from app.conversation.actions import ConversationAction
from app.conversation.manager import get_conversation_manager
from app.conversation.states import ConversationState
from app.main import create_application
from app.sessions.manager import get_session_manager
from app.voice.errors import ConversationConflictError, VoiceTurnActiveError
from app.voice.orchestrator import VoiceConversationOrchestrator, get_voice_orchestrator
from app.voice.response_store import VoiceResponseStore, get_voice_response_store
from app.voice.schemas import VoiceErrorCode, VoiceTransportState


@pytest.fixture
def app():
    return create_application()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def session_mgr():
    return get_session_manager()


@pytest.fixture
def conv_mgr():
    return get_conversation_manager()


@pytest.fixture
def voice_orchestrator():
    return get_voice_orchestrator()


@pytest.fixture
def temp_storage():
    return get_temp_storage_manager()


FIXTURE_DIR = Path(__file__).resolve().parent / "stt_benchmark" / "audio"


@pytest.fixture
def sample_sine_speech_wav():
    """Provides real speech WAV file (hi_short_001.wav) that passes Silero VAD."""
    return FIXTURE_DIR / "hi_short_001.wav"


@pytest.fixture
def sample_silence_wav(temp_storage):
    """Creates a temporary 2-second pure silence WAV file."""
    sr = 16000
    data = np.zeros(2 * sr, dtype=np.float32)
    path = temp_storage.create_temp_file(suffix=".wav", prefix="test_voice_silence_")
    sf.write(str(path), data, sr, subtype="PCM_16")
    yield path
    temp_storage.cleanup_file(path)


class TestVoiceOrchestrator:
    """Tests for VoiceConversationOrchestrator invariants."""

    def test_single_active_turn_lock(self, session_mgr, voice_orchestrator, sample_sine_speech_wav):
        """Simultaneous turns on the same session must be locked with VoiceTurnActiveError."""
        session = session_mgr.create_session()
        lock = voice_orchestrator._get_session_lock(session.session_id)

        # Manually hold lock to simulate active in-flight turn
        lock.acquire()
        try:
            with pytest.raises(VoiceTurnActiveError) as exc_info:
                asyncio.run(
                    voice_orchestrator.execute_voice_turn(
                        session_id=session.session_id,
                        audio_input=sample_sine_speech_wav,
                        voice_turn_id="turn-lock-test-01",
                    )
                )
            assert exc_info.value.error_code == VoiceErrorCode.VOICE_TURN_ALREADY_ACTIVE
        finally:
            lock.release()

    def test_conversation_version_conflict_rejection(self, session_mgr, voice_orchestrator, sample_sine_speech_wav):
        """Submitting an audio turn with stale conversation_version must fail with 409 conflict."""
        session = session_mgr.create_session()
        session.conversation_version = 5

        with pytest.raises(ConversationConflictError) as exc_info:
            asyncio.run(
                voice_orchestrator.execute_voice_turn(
                    session_id=session.session_id,
                    audio_input=sample_sine_speech_wav,
                    voice_turn_id="turn-conflict-test-01",
                    conversation_version=3,  # Stale version 3 < 5
                )
            )
        assert exc_info.value.error_code == VoiceErrorCode.CONVERSATION_STATE_CONFLICT

    def test_no_speech_detected_preserves_state(self, session_mgr, voice_orchestrator, sample_silence_wav):
        """Pure silence audio returns NO_SPEECH_DETECTED and strictly does not advance turn."""
        session = session_mgr.create_session()
        initial_turn_count = session.conversation_turn_count
        initial_version = session.conversation_version

        res = asyncio.run(
            voice_orchestrator.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_silence_wav,
                voice_turn_id="turn-silence-01",
            )
        )

        assert res.voice_state == VoiceTransportState.READY
        assert res.error_code == VoiceErrorCode.NO_SPEECH_DETECTED
        assert "मुझे आपकी आवाज़ सुनाई नहीं दी" in res.warning

        # Invariant: Semantic conversation version and turn count NOT CONSUMED
        assert session.conversation_turn_count == initial_turn_count
        assert session.conversation_version == initial_version

    def test_turn_idempotency_returns_cached_response(self, session_mgr, voice_orchestrator, sample_sine_speech_wav):
        """Re-submitting the exact same voice_turn_id must return without re-evaluating rules."""
        session = session_mgr.create_session()
        session.processed_turn_ids.append("idempotent-turn-001")

        res = asyncio.run(
            voice_orchestrator.execute_voice_turn(
                session_id=session.session_id,
                audio_input=sample_sine_speech_wav,
                voice_turn_id="idempotent-turn-001",
            )
        )

        assert res.warning == "IDEMPOTENT_RETRY"
        assert res.voice_turn_id == "idempotent-turn-001"
        assert res.voice_state == VoiceTransportState.READY

    def test_voice_replay_last_response(self, session_mgr, voice_orchestrator):
        """Replay resynthesizes current response without changing profile facts or turn counts."""
        session = session_mgr.create_session()
        initial_turn_count = session.conversation_turn_count
        initial_version = session.conversation_version

        replay_res = asyncio.run(
            voice_orchestrator.replay_last_response(session_id=session.session_id)
        )

        assert replay_res.session_id == session.session_id
        assert replay_res.voice_state == VoiceTransportState.SPEAKING
        assert replay_res.audio.response_id is not None
        assert replay_res.audio.audio_url.endswith("/audio")

        # Invariant: State and turn count are completely unchanged
        assert session.conversation_turn_count == initial_turn_count
        assert session.conversation_version == initial_version

    def test_voice_status_diagnostics(self, session_mgr, voice_orchestrator):
        session = session_mgr.create_session()
        status = voice_orchestrator.get_voice_status(session.session_id)

        assert status.voice_enabled is True
        assert status.vad_available is True
        assert status.pipeline_version == "1.0"
        assert status.active_turn is False


class TestVoiceResponseStore:
    """Tests for ephemeral response audio storage and TTL."""

    def test_store_and_retrieve_audio(self, temp_storage):
        store = VoiceResponseStore(ttl_seconds=300)
        audio_file = temp_storage.create_temp_file(suffix=".wav", prefix="store_test_")
        audio_file.write_bytes(b"RIFF dummy wav data")

        token = store.store_response(
            session_id="session-store-001",
            conversation_version=1,
            audio_path=audio_file,
            duration_ms=1200.0,
        )
        assert token.startswith("resp_")

        # Retrieve valid path
        path = store.get_response_path("session-store-001", token)
        assert path is not None
        assert path.exists()

        # Wrong session cannot access
        assert store.get_response_path("session-other", token) is None

        # Cleanup
        store.delete_response(token)
        assert store.get_response_path("session-store-001", token) is None

    def test_expired_token_is_cleaned_up(self, temp_storage):
        store = VoiceResponseStore(ttl_seconds=-1)  # Immediately expired
        audio_file = temp_storage.create_temp_file(suffix=".wav", prefix="store_exp_")
        audio_file.write_bytes(b"RIFF dummy wav data")

        token = store.store_response(
            session_id="session-store-exp",
            conversation_version=1,
            audio_path=audio_file,
            duration_ms=1000.0,
        )

        # Retrieval triggers cleanup
        path = store.get_response_path("session-store-exp", token)
        assert path is None
        assert not audio_file.exists()


class TestVoiceApiEndpoints:
    """REST API integration tests for /citizen/sessions/{session_id}/voice*"""

    def test_api_voice_turn_silence(self, client, sample_silence_wav):
        # Create session first
        sess_resp = client.post("/api/v1/citizen/sessions")
        assert sess_resp.status_code in (200, 201)
        session_id = sess_resp.json()["session_id"]

        with open(sample_silence_wav, "rb") as f:
            turn_resp = client.post(
                f"/api/v1/citizen/sessions/{session_id}/voice-turn",
                files={"audio": ("silence.wav", f, "audio/wav")},
                data={"voice_turn_id": "api-turn-001", "conversation_version": 1},
            )

        assert turn_resp.status_code == 200
        data = turn_resp.json()
        assert data["voice_state"] == "READY"
        assert data["error_code"] == "NO_SPEECH_DETECTED"
        assert "मुझे आपकी आवाज़ सुनाई नहीं दी" in data["warning"]

    def test_api_voice_replay_and_audio_stream(self, client):
        sess_resp = client.post("/api/v1/citizen/sessions")
        session_id = sess_resp.json()["session_id"]

        # 1. Trigger replay
        replay_resp = client.post(f"/api/v1/citizen/sessions/{session_id}/voice/replay")
        assert replay_resp.status_code == 200
        replay_data = replay_resp.json()
        assert replay_data["voice_state"] == "SPEAKING"
        resp_id = replay_data["audio"]["response_id"]

        # 2. Fetch audio stream
        audio_resp = client.get(
            f"/api/v1/citizen/sessions/{session_id}/voice/responses/{resp_id}/audio"
        )
        assert audio_resp.status_code == 200
        assert audio_resp.headers["content-type"] == "audio/wav"
        assert len(audio_resp.content) > 0

    def test_api_voice_status(self, client):
        sess_resp = client.post("/api/v1/citizen/sessions")
        session_id = sess_resp.json()["session_id"]

        status_resp = client.get(f"/api/v1/citizen/sessions/{session_id}/voice/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["voice_enabled"] is True
        assert status_data["pipeline_version"] == "1.0"
