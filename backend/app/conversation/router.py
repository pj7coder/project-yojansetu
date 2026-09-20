"""
CitizenInputRouter — Deterministic Conversational Input Routing (Day 25).
Orchestrates turn priority:
1. Structured Actions
2. Active Confirmation Context
3. Structured UI Input
4. Expected Field Processing via Day 24 Extractor
5. Need / Query / Open Utterance Routing
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.conversation.actions import ConversationAction
from app.conversation.events import ConversationEvent
from app.conversation.messages import ConversationMessageCatalog
from app.conversation.query_handler import CitizenQueryHandler
from app.conversation.schemas import ConversationInput, ConversationInputType, ConversationMessage
from app.conversation.states import ConversationState
from app.profile_extraction.boolean_parser import BooleanAndStatusParser
from app.profile_extraction.schemas import (
    CandidateProfileUpdate,
    CandidateStatus,
    InputSource,
    IntentType,
    ProfileExtractionResult,
)
from app.profile_extraction.service import CitizenProfileExtractionService, get_profile_extraction_service
from app.sessions.models import CitizenSession, FieldValueState

logger = logging.getLogger("jansetu.conversation.router")

# Ordinal patterns for scheme selection from results list
ORDINAL_MAP = {
    "first": 0, "1st": 0, "एक": 0, "पहली": 0, "पहला": 0, "पहला वाला": 0,
    "second": 1, "2nd": 1, "दो": 1, "दूसरी": 1, "दूसरा": 1, "दूसरा वाला": 1,
    "third": 2, "3rd": 2, "तीन": 2, "तीसरी": 2, "तीसरा": 2, "तीसरा वाला": 2,
    "fourth": 3, "4th": 3, "चार": 3, "चौथी": 3, "चौथा": 3,
    "fifth": 4, "5th": 4, "पांच": 4, "पाँचवीं": 4, "पाँचवाँ": 4,
}

COMPLETION_PATTERNS = [
    r"^धन्यवाद$",
    r"^बस$",
    r"^ठीक है धन्यवाद$",
    r"^that'?s all$",
    r"^thank you$",
    r"^thanks$",
]


class CitizenInputRouter:
    """
    Decoupled deterministic router mapping citizen turn input into a validated state-machine event.
    """

    def __init__(self, extractor: Optional[CitizenProfileExtractionService] = None):
        self.extractor = extractor or get_profile_extraction_service()

    def route_input(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """
        Main routing method returning (event, payload_context).
        Payload context holds extracted values, confirmation decisions, or query messages.
        """
        curr_state = ConversationState(session.conversation_state)

        # -------------------------------------------------------------
        # PRIORITY 1: Explicit Structured Action
        # -------------------------------------------------------------
        if inp.type == ConversationInputType.ACTION or inp.action:
            action_code = (inp.action or "").upper().strip()

            if action_code == "START_OVER":
                return (ConversationEvent.START_OVER_REQUESTED, {})
            if action_code == "END_CONVERSATION":
                return (ConversationEvent.END_CONVERSATION_REQUESTED, {})
            if action_code == "CHANGE_LANGUAGE":
                return (ConversationEvent.LANGUAGE_CHANGED, {"language": inp.language or "hi"})
            if action_code == "CHANGE_NEED":
                return (ConversationEvent.CHANGE_NEED_REQUESTED, {"need_text": inp.text or ""})
            if action_code == "SELECT_SCHEME":
                return (ConversationEvent.SCHEME_SELECTED, {"scheme_id": inp.scheme_id})
            if action_code == "REPEAT_QUESTION":
                return (ConversationEvent.REPEAT_REQUESTED, {})
            if action_code == "CONFIRM_YES":
                return (ConversationEvent.PROFILE_VALUE_CONFIRMED, {"decision": "YES"})
            if action_code == "CONFIRM_NO":
                return (ConversationEvent.PROFILE_VALUE_REJECTED, {"decision": "NO"})

        # -------------------------------------------------------------
        # PRIORITY 2: Pending Confirmation Interpretation
        # -------------------------------------------------------------
        if curr_state == ConversationState.WAITING_FOR_CONFIRMATION:
            return self._route_confirmation_turn(inp, session)

        # -------------------------------------------------------------
        # PRIORITY 3: Structured UI Value
        # -------------------------------------------------------------
        if inp.type == ConversationInputType.STRUCTURED_VALUE:
            return self._route_structured_value(inp, session)

        # -------------------------------------------------------------
        # PRIORITY 4: Expected Field Processing
        # -------------------------------------------------------------
        if curr_state == ConversationState.WAITING_FOR_PROFILE_VALUE:
            return self._route_expected_field(inp, session)

        # -------------------------------------------------------------
        # PRIORITY 5: Need Collection
        # -------------------------------------------------------------
        if curr_state in (ConversationState.WAITING_FOR_NEED, ConversationState.NEW_SESSION):
            return self._route_need_input(inp, session)

        # -------------------------------------------------------------
        # PRIORITY 6: Clarification Turn
        # -------------------------------------------------------------
        if curr_state == ConversationState.NEED_CLARIFICATION:
            return self._route_clarification_turn(inp, session)

        # -------------------------------------------------------------
        # PRIORITY 7: Results or Open Utterance State
        # -------------------------------------------------------------
        return self._route_open_turn(inp, session)

    def _route_confirmation_turn(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """
        Evaluates input strictly within confirmation context:
        'हाँ' -> confirms pending fact
        'नहीं' -> rejects pending fact (does NOT set boolean to False)
        Interruption query -> temporarily answers query, preserves confirmation
        Correction statement -> updates pending fact
        """
        text = (inp.text or "").strip()
        if not text and inp.action:
            if inp.action.upper() in ("YES", "CONFIRM_YES"):
                return (ConversationEvent.PROFILE_VALUE_CONFIRMED, {"decision": "YES"})
            if inp.action.upper() in ("NO", "CONFIRM_NO"):
                return (ConversationEvent.PROFILE_VALUE_REJECTED, {"decision": "NO"})

        # Check for citizen help interruption query
        if CitizenQueryHandler.is_query(text):
            return (ConversationEvent.CITIZEN_QUERY_RECEIVED, {"query_text": text})

        # Check for explicit YES
        if BooleanAndStatusParser.is_affirmative(text):
            return (ConversationEvent.PROFILE_VALUE_CONFIRMED, {"decision": "YES"})

        # Check for explicit NO
        if BooleanAndStatusParser.is_negative(text):
            return (ConversationEvent.PROFILE_VALUE_REJECTED, {"decision": "NO"})

        # Check if citizen provides a correction text ("मेरी उम्र 61 है")
        pending = session.pending_confirmation or {}
        pending_field = pending.get("field")
        res = self.extractor.process_citizen_input(
            text=text,
            input_source=InputSource.STT_TRANSCRIPT if inp.type == ConversationInputType.STT_TRANSCRIPT else InputSource.TEXT_INPUT,
            expected_field=pending_field,
            existing_profile=session.profile,
        )

        if res.candidates:
            cand = res.candidates[0]
            if cand.status in (CandidateStatus.ACCEPTED, CandidateStatus.CONFIRMATION_REQUIRED, CandidateStatus.CONFLICT_WITH_EXISTING_VALUE):
                return (
                    ConversationEvent.PROFILE_VALUE_CORRECTED,
                    {"candidate": cand, "confirmation": res.pending_confirmation},
                )

        # Fallback: clarify confirmation
        return (ConversationEvent.CLARIFICATION_REQUIRED, {"field": pending_field, "raw_text": text})

    def _route_structured_value(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """
        Handles pre-validated UI button selections.
        Verifies target field matches expected field to prevent workflow bypass.
        """
        field_name = inp.field
        expected = session.expected_field

        if expected and field_name != expected:
            logger.warning(f"Structured value field '{field_name}' mismatched expected '{expected}'")
            return (
                ConversationEvent.CLARIFICATION_REQUIRED,
                {"field": expected, "hint": "कृपया पूछे गए प्रश्न का उत्तर दें"},
            )

        target = field_name or expected
        if not target:
            return (ConversationEvent.CLARIFICATION_REQUIRED, {})

        val = inp.value
        return (
            ConversationEvent.PROFILE_VALUE_EXTRACTED,
            {"field": target, "value": val, "source": "STRUCTURED_UI_INPUT"},
        )

    def _route_expected_field(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """
        Routes natural language text/speech transcript when waiting for an expected profile field.
        """
        text = (inp.text or "").strip()
        expected = session.expected_field

        # Interruption check: citizen asking why or what
        if CitizenQueryHandler.is_query(text):
            return (ConversationEvent.CITIZEN_QUERY_RECEIVED, {"query_text": text})

        source = InputSource.STT_TRANSCRIPT if inp.type == ConversationInputType.STT_TRANSCRIPT else InputSource.TEXT_INPUT
        res = self.extractor.process_citizen_input(
            text=text,
            input_source=source,
            expected_field=expected,
            existing_profile=session.profile,
        )

        # Intent handling
        if res.intent == IntentType.USER_QUERY:
            return (ConversationEvent.CITIZEN_QUERY_RECEIVED, {"query_text": text})

        if res.intent == IntentType.DECLINE:
            return (ConversationEvent.PROFILE_VALUE_DECLINED, {"field": expected})

        if res.intent == IntentType.UNKNOWN_RESPONSE:
            return (ConversationEvent.PROFILE_VALUE_UNKNOWN, {"field": expected})

        # Ambiguous candidate (Range, approximation, or unmapped expressions -> clarification)
        ambiguous = [c for c in res.candidates if c.status == CandidateStatus.AMBIGUOUS]
        if ambiguous:
            return (
                ConversationEvent.CLARIFICATION_REQUIRED,
                {"field": expected, "reason": "AMBIGUOUS_VALUE", "raw_text": text},
            )

        # Pending confirmation required (STT critical value or explicit correction)
        if res.pending_confirmation:
            return (
                ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED,
                {
                    "confirmation": res.pending_confirmation,
                    "candidates": res.candidates,
                },
            )

        # Direct safe candidates
        accepted_candidates = [c for c in res.candidates if c.status == CandidateStatus.ACCEPTED]
        if accepted_candidates:
            # Check if any candidate was an explicit correction
            if any(c.is_correction for c in accepted_candidates):
                return (
                    ConversationEvent.PROFILE_VALUE_CORRECTED,
                    {"candidates": accepted_candidates},
                )
            return (
                ConversationEvent.PROFILE_VALUE_EXTRACTED,
                {"candidates": accepted_candidates},
            )

        # No facts extracted from answer
        return (
            ConversationEvent.CLARIFICATION_REQUIRED,
            {"field": expected, "reason": "NO_PROFILE_FACT_EXTRACTED", "raw_text": text},
        )

    def _route_need_input(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """
        Processes initial citizen need statement (e.g. 'मुझे पेंशन चाहिए' or 'मैं 65 वर्ष का किसान हूँ').
        Extracts need text and any open multi-fact demographic facts provided simultaneously.
        """
        text = (inp.text or "").strip()
        source = InputSource.STT_TRANSCRIPT if inp.type == ConversationInputType.STT_TRANSCRIPT else InputSource.TEXT_INPUT

        res = self.extractor.process_citizen_input(
            text=text,
            input_source=source,
            expected_field=None,
            existing_profile=session.profile,
        )

        need_text = res.need_text or text

        # If citizen provided critical facts requiring confirmation alongside need
        if res.pending_confirmation:
            return (
                ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED,
                {
                    "need_text": need_text,
                    "confirmation": res.pending_confirmation,
                    "candidates": res.candidates,
                },
            )

        return (
            ConversationEvent.NEED_PROVIDED,
            {
                "need_text": need_text,
                "candidates": [c for c in res.candidates if c.status == CandidateStatus.ACCEPTED],
            },
        )

    def _route_clarification_turn(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """Handles response to a clarification prompt."""
        text = (inp.text or "").strip()
        if CitizenQueryHandler.is_query(text):
            return (ConversationEvent.CITIZEN_QUERY_RECEIVED, {"query_text": text})

        return (ConversationEvent.CLARIFICATION_PROVIDED, {"text": text})

    def _route_open_turn(
        self,
        inp: ConversationInput,
        session: CitizenSession,
    ) -> Tuple[ConversationEvent, Dict[str, Any]]:
        """
        Handles conversational turns while viewing results or in general non-question states:
        - Ordinal scheme selection ('पहली योजना', 'दूसरा')
        - Need change ('अब खेती की योजना देखनी है')
        - Correction ('मेरी उम्र 61 है')
        - End conversation ('धन्यवाद', 'बस')
        - Informational queries
        """
        text = (inp.text or "").strip()
        clean = text.lower()

        # 1. Natural end phrase check
        if any(re.match(pat, clean) for pat in COMPLETION_PATTERNS):
            return (ConversationEvent.END_CONVERSATION_REQUESTED, {})

        # 2. Ordinal scheme selection
        for ord_word, idx in ORDINAL_MAP.items():
            if ord_word in clean:
                if session.result_order and 0 <= idx < len(session.result_order):
                    scheme_id = session.result_order[idx]
                    return (ConversationEvent.SCHEME_SELECTED, {"scheme_id": scheme_id})

        # 3. Query check
        if CitizenQueryHandler.is_query(text):
            return (ConversationEvent.CITIZEN_QUERY_RECEIVED, {"query_text": text})

        # 4. Correction or Need change check via Day 24 extractor
        source = InputSource.STT_TRANSCRIPT if inp.type == ConversationInputType.STT_TRANSCRIPT else InputSource.TEXT_INPUT
        res = self.extractor.process_citizen_input(
            text=text,
            input_source=source,
            expected_field=None,
            existing_profile=session.profile,
        )

        if res.candidates:
            cand = res.candidates[0]
            if cand.is_correction or cand.field in session.profile:
                return (
                    ConversationEvent.PROFILE_VALUE_CORRECTED,
                    {"candidate": cand, "confirmation": res.pending_confirmation},
                )

        # 5. Treat as Need Change
        return (ConversationEvent.CHANGE_NEED_REQUESTED, {"need_text": text})
