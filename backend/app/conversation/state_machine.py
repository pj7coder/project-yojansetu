"""
ConversationStateMachine — Core Deterministic Transition Service (Day 25).
Enforces explicit valid transitions, transition guards, and safe recovery.
Zero LLM involvement in workflow progression.
"""

import logging
from typing import Dict, Optional, Set, Tuple

from app.conversation.events import ConversationEvent
from app.conversation.states import ConversationState
from app.sessions.models import CitizenSession

logger = logging.getLogger("jansetu.conversation.state_machine")


# Explicit Transition Table: (Current State, Event) -> Next State
TRANSITION_TABLE: Dict[Tuple[ConversationState, ConversationEvent], ConversationState] = {
    # 1. NEW_SESSION
    (ConversationState.NEW_SESSION, ConversationEvent.SESSION_STARTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.NEW_SESSION, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,

    # 2. WAITING_FOR_NEED
    (ConversationState.WAITING_FOR_NEED, ConversationEvent.NEED_PROVIDED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.WAITING_FOR_NEED, ConversationEvent.PROFILE_VALUE_EXTRACTED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.WAITING_FOR_NEED, ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED): ConversationState.WAITING_FOR_CONFIRMATION,
    (ConversationState.WAITING_FOR_NEED, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.WAITING_FOR_NEED, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 3. PROCESSING_DISCOVERY
    (ConversationState.PROCESSING_DISCOVERY, ConversationEvent.MORE_INFO_REQUIRED): ConversationState.WAITING_FOR_PROFILE_VALUE,
    (ConversationState.PROCESSING_DISCOVERY, ConversationEvent.ELIGIBLE_RESULTS_FOUND): ConversationState.SHOWING_RESULTS,
    (ConversationState.PROCESSING_DISCOVERY, ConversationEvent.NO_RESULTS_FOUND): ConversationState.NO_RESULTS,
    (ConversationState.PROCESSING_DISCOVERY, ConversationEvent.CANNOT_RESOLVE_MORE): ConversationState.CANNOT_RESOLVE,
    (ConversationState.PROCESSING_DISCOVERY, ConversationEvent.DISCOVERY_COMPLETED): ConversationState.SHOWING_RESULTS,

    # 4. WAITING_FOR_PROFILE_VALUE
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.PROFILE_VALUE_EXTRACTED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED): ConversationState.WAITING_FOR_CONFIRMATION,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.CLARIFICATION_REQUIRED): ConversationState.NEED_CLARIFICATION,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.PROFILE_VALUE_UNKNOWN): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.PROFILE_VALUE_DECLINED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.CITIZEN_QUERY_RECEIVED): ConversationState.HANDLING_CITIZEN_QUERY,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.PROFILE_VALUE_CORRECTED): ConversationState.WAITING_FOR_CONFIRMATION,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.WAITING_FOR_PROFILE_VALUE, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 5. WAITING_FOR_CONFIRMATION
    (ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.PROFILE_VALUE_CONFIRMED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.PROFILE_VALUE_REJECTED): ConversationState.WAITING_FOR_PROFILE_VALUE,
    (ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.PROFILE_VALUE_CORRECTED): ConversationState.WAITING_FOR_CONFIRMATION,
    (ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.CITIZEN_QUERY_RECEIVED): ConversationState.HANDLING_CITIZEN_QUERY,
    (ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.WAITING_FOR_CONFIRMATION, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 6. NEED_CLARIFICATION
    (ConversationState.NEED_CLARIFICATION, ConversationEvent.CLARIFICATION_PROVIDED): ConversationState.WAITING_FOR_PROFILE_VALUE,
    (ConversationState.NEED_CLARIFICATION, ConversationEvent.CITIZEN_QUERY_RECEIVED): ConversationState.HANDLING_CITIZEN_QUERY,
    (ConversationState.NEED_CLARIFICATION, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.NEED_CLARIFICATION, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 7. HANDLING_CITIZEN_QUERY (Resumes previous state via query_answered logic)
    (ConversationState.HANDLING_CITIZEN_QUERY, ConversationEvent.QUERY_ANSWERED): ConversationState.WAITING_FOR_PROFILE_VALUE,  # default fallback
    (ConversationState.HANDLING_CITIZEN_QUERY, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.HANDLING_CITIZEN_QUERY, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 8. SHOWING_RESULTS
    (ConversationState.SHOWING_RESULTS, ConversationEvent.SCHEME_SELECTED): ConversationState.SHOWING_RESULTS,
    (ConversationState.SHOWING_RESULTS, ConversationEvent.CITIZEN_QUERY_RECEIVED): ConversationState.HANDLING_CITIZEN_QUERY,
    (ConversationState.SHOWING_RESULTS, ConversationEvent.CHANGE_NEED_REQUESTED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.SHOWING_RESULTS, ConversationEvent.PROFILE_VALUE_CORRECTED): ConversationState.WAITING_FOR_CONFIRMATION,
    (ConversationState.SHOWING_RESULTS, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.SHOWING_RESULTS, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 9. NO_RESULTS & CANNOT_RESOLVE
    (ConversationState.NO_RESULTS, ConversationEvent.CHANGE_NEED_REQUESTED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.NO_RESULTS, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.NO_RESULTS, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,
    (ConversationState.CANNOT_RESOLVE, ConversationEvent.CHANGE_NEED_REQUESTED): ConversationState.PROCESSING_DISCOVERY,
    (ConversationState.CANNOT_RESOLVE, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.CANNOT_RESOLVE, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,

    # 10. ERROR
    (ConversationState.ERROR, ConversationEvent.START_OVER_REQUESTED): ConversationState.WAITING_FOR_NEED,
    (ConversationState.ERROR, ConversationEvent.END_CONVERSATION_REQUESTED): ConversationState.COMPLETED,
}


class InvalidConversationTransitionError(Exception):
    """Raised when an illegal event transition is attempted on the state machine."""
    pass


class ConversationStateMachine:
    """
    State machine governing conversational turn transitions deterministically.
    """

    @classmethod
    def get_next_state(
        cls,
        current_state: ConversationState,
        event: ConversationEvent,
        session: Optional[CitizenSession] = None,
    ) -> ConversationState:
        """
        Calculates the next state for (current_state, event) pair, verifying transition guards.
        """
        # Global Event Overrides
        if event == ConversationEvent.START_OVER_REQUESTED:
            return ConversationState.WAITING_FOR_NEED

        if event in (ConversationEvent.END_CONVERSATION_REQUESTED, ConversationEvent.MAX_TURNS_REACHED):
            return ConversationState.COMPLETED

        if event in (ConversationEvent.LANGUAGE_CHANGED, ConversationEvent.REPEAT_REQUESTED):
            return current_state

        if event == ConversationEvent.PROCESSING_FAILED:
            return ConversationState.ERROR

        # Resume state override when query answered
        if current_state == ConversationState.HANDLING_CITIZEN_QUERY and event == ConversationEvent.QUERY_ANSWERED:
            if session and session.resume_state:
                try:
                    return ConversationState(session.resume_state)
                except ValueError:
                    pass
            return ConversationState.WAITING_FOR_PROFILE_VALUE

        # Look up transition
        target = TRANSITION_TABLE.get((current_state, event))
        if target is None:
            logger.warning(
                f"Invalid conversation transition attempted: state='{current_state.value}', event='{event.value}'"
            )
            # Safe non-corrupting fallback: maintain current state
            return current_state

        # Verify Transition Guards
        if session:
            target = cls._verify_guards(current_state, target, event, session)

        return target

    @classmethod
    def _verify_guards(
        cls,
        current: ConversationState,
        target: ConversationState,
        event: ConversationEvent,
        session: CitizenSession,
    ) -> ConversationState:
        """
        Enforces state invariants and recovers gracefully if session is missing prerequisite context.
        """
        # Guard: WAITING_FOR_CONFIRMATION requires an active pending confirmation
        if target == ConversationState.WAITING_FOR_CONFIRMATION:
            if not session.pending_confirmation:
                logger.warning(
                    "Guard failure: WAITING_FOR_CONFIRMATION requested without pending_confirmation. "
                    "Recovering state."
                )
                return cls.recover_state(session)

        # Guard: WAITING_FOR_PROFILE_VALUE requires an expected field
        if target == ConversationState.WAITING_FOR_PROFILE_VALUE:
            if not session.expected_field:
                logger.warning(
                    "Guard failure: WAITING_FOR_PROFILE_VALUE requested without expected_field. "
                    "Routing to discovery."
                )
                return ConversationState.PROCESSING_DISCOVERY

        return target

    @classmethod
    def recover_state(cls, session: CitizenSession) -> ConversationState:
        """
        Deterministic recovery logic for inconsistent or corrupt session states.
        """
        try:
            curr = ConversationState(session.conversation_state)
        except ValueError:
            curr = ConversationState.NEW_SESSION

        if curr == ConversationState.WAITING_FOR_CONFIRMATION and not session.pending_confirmation:
            if session.expected_field:
                return ConversationState.WAITING_FOR_PROFILE_VALUE
            return ConversationState.PROCESSING_DISCOVERY

        if curr == ConversationState.WAITING_FOR_PROFILE_VALUE and not session.expected_field:
            return ConversationState.PROCESSING_DISCOVERY

        if curr == ConversationState.HANDLING_CITIZEN_QUERY:
            if session.resume_state:
                try:
                    return ConversationState(session.resume_state)
                except ValueError:
                    pass
            return ConversationState.WAITING_FOR_NEED

        return curr
