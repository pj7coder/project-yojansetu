"""
YojanSetu - Day 27: Voice Transport State Machine.

Maintains strict separation between the voice transport layer
(LISTENING, PROCESSING, SPEAKING) and the Day 25 semantic conversation state
(WAITING_FOR_NEED, WAITING_FOR_PROFILE_VALUE, WAITING_FOR_CONFIRMATION, etc.).

Enforces half-duplex rules:
- Microphone is strictly OFF during SPEAKING.
- Transitioning directly from SPEAKING to LISTENING is forbidden without an explicit
  playback-end or user-interrupted event.
"""

from enum import Enum
import logging
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class VoiceTransportState(str, Enum):
    """
    Physical audio transport and turn-taking states for YojanSetu voice loop.
    Strictly orthogonal to semantic ConversationState.
    """
    IDLE = "IDLE"
    READY = "READY"
    LISTENING = "LISTENING"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    WAITING_FOR_END_OF_SPEECH = "WAITING_FOR_END_OF_SPEECH"
    PROCESSING_AUDIO = "PROCESSING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    PROCESSING_TURN = "PROCESSING_TURN"
    SYNTHESIZING = "SYNTHESIZING"
    SPEAKING = "SPEAKING"
    RECOVERABLE_ERROR = "RECOVERABLE_ERROR"
    STOPPED = "STOPPED"


class VoiceStateTransitionError(Exception):
    """Raised when an illegal voice transport state transition is attempted."""
    pass


class VoiceStateMachine:
    """
    Deterministic state machine managing voice transport transitions.
    Guarantees half-duplex safety and prevents acoustic self-transcription.
    """

    # Defined legal state transitions
    VALID_TRANSITIONS: Dict[VoiceTransportState, Set[VoiceTransportState]] = {
        VoiceTransportState.IDLE: {
            VoiceTransportState.READY,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.READY: {
            VoiceTransportState.LISTENING,
            VoiceTransportState.SPEAKING,  # e.g., when initial prompt plays or replay triggered
            VoiceTransportState.PROCESSING_AUDIO,  # e.g., audio upload directly received
            VoiceTransportState.STOPPED,
            VoiceTransportState.RECOVERABLE_ERROR,
        },
        VoiceTransportState.LISTENING: {
            VoiceTransportState.SPEECH_DETECTED,
            VoiceTransportState.PROCESSING_AUDIO,
            VoiceTransportState.READY,  # User canceled or pre-speech timeout
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.SPEECH_DETECTED: {
            VoiceTransportState.WAITING_FOR_END_OF_SPEECH,
            VoiceTransportState.PROCESSING_AUDIO,
            VoiceTransportState.READY,
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.WAITING_FOR_END_OF_SPEECH: {
            VoiceTransportState.PROCESSING_AUDIO,
            VoiceTransportState.READY,
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.PROCESSING_AUDIO: {
            VoiceTransportState.TRANSCRIBING,
            VoiceTransportState.READY,  # No speech detected, recovery prompt
            VoiceTransportState.SPEAKING,  # Fast path retry speech (e.g. no speech prompt)
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.TRANSCRIBING: {
            VoiceTransportState.PROCESSING_TURN,
            VoiceTransportState.READY,  # Empty STT result
            VoiceTransportState.SPEAKING,  # Empty STT spoken retry
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.PROCESSING_TURN: {
            VoiceTransportState.SYNTHESIZING,
            VoiceTransportState.READY,  # TTS failed, degraded text fallback
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.SYNTHESIZING: {
            VoiceTransportState.SPEAKING,
            VoiceTransportState.READY,  # TTS failed, degraded text fallback
            VoiceTransportState.RECOVERABLE_ERROR,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.SPEAKING: {
            VoiceTransportState.READY,  # Audio playback finished
            VoiceTransportState.STOPPED,  # User tapped stop speaking
            VoiceTransportState.RECOVERABLE_ERROR,
            # NOTE: VoiceTransportState.LISTENING is INTENTIONALLY EXCLUDED.
            # You CANNOT transition directly from SPEAKING to LISTENING!
            # Must transition to READY or STOPPED first.
        },
        VoiceTransportState.RECOVERABLE_ERROR: {
            VoiceTransportState.READY,
            VoiceTransportState.STOPPED,
        },
        VoiceTransportState.STOPPED: {
            VoiceTransportState.READY,
            VoiceTransportState.IDLE,
        },
    }

    def __init__(self, initial_state: VoiceTransportState = VoiceTransportState.READY):
        self._current_state = initial_state

    @property
    def current_state(self) -> VoiceTransportState:
        return self._current_state

    def can_transition_to(self, target_state: VoiceTransportState) -> bool:
        """Checks whether transition from current state to target state is legally permissible."""
        allowed = self.VALID_TRANSITIONS.get(self._current_state, set())
        return target_state in allowed

    def transition_to(self, target_state: VoiceTransportState) -> VoiceTransportState:
        """
        Executes transition to target state if legally permissible.
        Raises VoiceStateTransitionError otherwise.
        """
        if target_state == self._current_state:
            return self._current_state

        if not self.can_transition_to(target_state):
            err_msg = (
                f"Illegal voice transport transition from '{self._current_state.value}' "
                f"to '{target_state.value}'. Half-duplex invariants must be respected."
            )
            logger.warning(err_msg)
            raise VoiceStateTransitionError(err_msg)

        old_state = self._current_state
        self._current_state = target_state
        logger.debug(f"Voice state transitioned: {old_state.value} -> {target_state.value}")
        return self._current_state

    def reset_to_ready(self) -> None:
        """Safely returns state machine to READY state from any state."""
        self._current_state = VoiceTransportState.READY
