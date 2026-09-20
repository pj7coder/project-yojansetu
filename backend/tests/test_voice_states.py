"""
JanSetu - Day 27 Tests: Voice Transport State Machine.

Verifies:
1. Legal state transitions matching the physical turn-taking lifecycle.
2. Invariant: SPEAKING -> LISTENING is strictly forbidden without playback completion or stop.
3. Reset and exception handling on illegal state transitions.
"""

import pytest
from app.voice.states import VoiceStateMachine, VoiceStateTransitionError, VoiceTransportState


class TestVoiceStateMachine:
    """Unit tests for VoiceStateMachine half-duplex rules and transitions."""

    def test_initial_state_is_ready(self):
        sm = VoiceStateMachine()
        assert sm.current_state == VoiceTransportState.READY

    def test_valid_turn_lifecycle(self):
        sm = VoiceStateMachine()

        # 1. Citizen taps mic
        assert sm.can_transition_to(VoiceTransportState.LISTENING)
        sm.transition_to(VoiceTransportState.LISTENING)
        assert sm.current_state == VoiceTransportState.LISTENING

        # 2. Speech detected by audio heuristic
        assert sm.can_transition_to(VoiceTransportState.SPEECH_DETECTED)
        sm.transition_to(VoiceTransportState.SPEECH_DETECTED)

        # 3. Speech finished / pause detected
        assert sm.can_transition_to(VoiceTransportState.WAITING_FOR_END_OF_SPEECH)
        sm.transition_to(VoiceTransportState.WAITING_FOR_END_OF_SPEECH)

        # 4. Processing audio (VAD)
        assert sm.can_transition_to(VoiceTransportState.PROCESSING_AUDIO)
        sm.transition_to(VoiceTransportState.PROCESSING_AUDIO)

        # 5. Transcribing via STT
        assert sm.can_transition_to(VoiceTransportState.TRANSCRIBING)
        sm.transition_to(VoiceTransportState.TRANSCRIBING)

        # 6. Processing turn in ConversationManager
        assert sm.can_transition_to(VoiceTransportState.PROCESSING_TURN)
        sm.transition_to(VoiceTransportState.PROCESSING_TURN)

        # 7. Synthesizing TTS
        assert sm.can_transition_to(VoiceTransportState.SYNTHESIZING)
        sm.transition_to(VoiceTransportState.SYNTHESIZING)

        # 8. Speaking (Playback begins)
        assert sm.can_transition_to(VoiceTransportState.SPEAKING)
        sm.transition_to(VoiceTransportState.SPEAKING)

        # 9. Playback ends -> back to READY
        assert sm.can_transition_to(VoiceTransportState.READY)
        sm.transition_to(VoiceTransportState.READY)
        assert sm.current_state == VoiceTransportState.READY

    def test_speaking_to_listening_is_forbidden(self):
        """
        CRITICAL HALF-DUPLEX INVARIANT:
        Microphone MUST NOT be opened directly while SPEAKING.
        """
        sm = VoiceStateMachine(initial_state=VoiceTransportState.SPEAKING)

        assert not sm.can_transition_to(VoiceTransportState.LISTENING)
        with pytest.raises(VoiceStateTransitionError) as exc_info:
            sm.transition_to(VoiceTransportState.LISTENING)

        assert "Illegal voice transport transition" in str(exc_info.value)
        assert "Half-duplex invariants must be respected" in str(exc_info.value)

    def test_speaking_stop_to_ready(self):
        """User taps stop speaking -> transitions to STOPPED or READY."""
        sm = VoiceStateMachine(initial_state=VoiceTransportState.SPEAKING)
        sm.transition_to(VoiceTransportState.STOPPED)
        assert sm.current_state == VoiceTransportState.STOPPED

        sm.transition_to(VoiceTransportState.READY)
        assert sm.current_state == VoiceTransportState.READY

    def test_no_speech_recovery_to_ready(self):
        sm = VoiceStateMachine(initial_state=VoiceTransportState.PROCESSING_AUDIO)
        # VAD detects silence -> transitions back to READY
        sm.transition_to(VoiceTransportState.READY)
        assert sm.current_state == VoiceTransportState.READY

    def test_tts_failure_recovery_to_ready(self):
        sm = VoiceStateMachine(initial_state=VoiceTransportState.SYNTHESIZING)
        # TTS fails -> degraded text mode -> READY
        sm.transition_to(VoiceTransportState.READY)
        assert sm.current_state == VoiceTransportState.READY

    def test_reset_to_ready(self):
        sm = VoiceStateMachine(initial_state=VoiceTransportState.SPEAKING)
        sm.reset_to_ready()
        assert sm.current_state == VoiceTransportState.READY
