"""
ConversationManager — Main Deterministic Conversational Brain (Day 25).
Orchestrates turn intake, concurrency, idempotency, input routing, state transitions,
session updates, candidate discovery, and structured action responses.
Zero LLM workflow control.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.citizen.questions import CitizenQuestionBuilder
from app.citizen.schemas import (
    CitizenDiscoveryResponse,
    CitizenQuestionDisplay,
    CitizenSchemeDetailResponse,
)
from app.citizen.service import CitizenDiscoveryFacade
from app.core.config import get_settings
from app.conversation.actions import ConversationAction
from app.conversation.events import ConversationEvent
from app.conversation.messages import ConversationMessageCatalog
from app.conversation.query_handler import CitizenQueryHandler
from app.conversation.router import CitizenInputRouter
from app.conversation.schemas import (
    ConversationInput,
    ConversationInputType,
    ConversationMessage,
    ConversationMeta,
    ConversationResponse,
    ExpectedInputDescriptor,
)
from app.conversation.state_machine import ConversationStateMachine
from app.conversation.states import ConversationState
from app.discovery.session_discovery_service import SessionDiscoveryService
from app.questioning.field_metadata import get_field_metadata
from app.questioning.schemas import QuestionReasonCode
from app.sessions.manager import CitizenSessionManager, SessionNotFoundError, get_session_manager
from app.sessions.models import CitizenSession, FieldValueState

logger = logging.getLogger("yojansetu.conversation.manager")


class ConversationManager:
    """
    Unified conversation manager driving both text UI and future voice workflows deterministically.
    """

    def __init__(
        self,
        session_manager: Optional[CitizenSessionManager] = None,
        router: Optional[CitizenInputRouter] = None,
    ):
        self.settings = get_settings()
        self.session_mgr = session_manager or get_session_manager()
        self.router = router or CitizenInputRouter()

    def handle_input(
        self,
        session_id: str,
        inp: ConversationInput,
        db_session: Session,
    ) -> ConversationResponse:
        """
        Executes a single conversational turn:
        1. Validates session existence and concurrency.
        2. Enforces idempotency via client_turn_id.
        3. Routes input to a validated state machine event.
        4. Calculates state transition.
        5. Performs deterministic session updates and discovery.
        6. Constructs and returns structured response action.
        """
        start_time = time.perf_counter()
        session = self.session_mgr.require_session(session_id)

        # Update language preference if provided
        if inp.language:
            session.preferred_language = inp.language.lower().strip()

        # Idempotency check: Ignore duplicate submissions of the same turn ID
        if inp.client_turn_id:
            is_new = self.session_mgr.record_turn_processed(session_id, inp.client_turn_id)
            if not is_new:
                logger.info(f"Duplicate client_turn_id '{inp.client_turn_id}' detected. Returning current state.")
                return self.get_current_state(session_id, db_session=db_session)

        # Optimistic concurrency version check
        if inp.conversation_version is not None and inp.conversation_version < session.conversation_version:
            logger.warning(
                f"Concurrency conflict: client version={inp.conversation_version}, "
                f"server version={session.conversation_version}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conversation state version mismatch (client: {inp.conversation_version}, server: {session.conversation_version}). Please refresh.",
            )

        # Max conversation turns safeguard
        if session.conversation_turn_count >= self.settings.max_conversation_turns:
            logger.info(f"Session '{session_id[:8]}' reached MAX_CONVERSATION_TURNS ({self.settings.max_conversation_turns})")
            session.conversation_state = ConversationState.COMPLETED.value
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.COMPLETED,
                action=ConversationAction.END_CONVERSATION,
                message=ConversationMessageCatalog.max_turns(),
                expected_input=ExpectedInputDescriptor(type="ACTION"),
                meta=self._build_meta(session, start_time),
            )

        # Increment turn count
        session.conversation_turn_count += 1
        session.last_user_input_type = inp.type.value

        old_state_enum = ConversationState(session.conversation_state)

        # If currently in HANDLING_CITIZEN_QUERY, resume to previous state prior to routing
        if old_state_enum == ConversationState.HANDLING_CITIZEN_QUERY:
            resumed_state = session.resume_state or ConversationState.WAITING_FOR_NEED.value
            session.conversation_state = resumed_state
            session.expected_field = session.resume_expected_field
            session.resume_state = None
            session.resume_expected_field = None
            old_state_enum = ConversationState(session.conversation_state)

        # Route input to event
        event, payload = self.router.route_input(inp, session)

        # Handle global action START_OVER immediately
        if event == ConversationEvent.START_OVER_REQUESTED:
            session = self.session_mgr.reset_session_conversation(session_id)
            session.record_trace(
                turn=session.conversation_turn_count,
                old_state=old_state_enum.value,
                event=event.value,
                new_state=ConversationState.WAITING_FOR_NEED.value,
                action=ConversationAction.ASK_NEED.value,
            )
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.WAITING_FOR_NEED,
                action=ConversationAction.ASK_NEED,
                message=ConversationMessageCatalog.start_over(),
                expected_input=ExpectedInputDescriptor(type="TEXT"),
                meta=self._build_meta(session, start_time),
            )

        # Handle global action END_CONVERSATION immediately
        if event == ConversationEvent.END_CONVERSATION_REQUESTED:
            session.conversation_state = ConversationState.COMPLETED.value
            session.record_trace(
                turn=session.conversation_turn_count,
                old_state=old_state_enum.value,
                event=event.value,
                new_state=ConversationState.COMPLETED.value,
                action=ConversationAction.END_CONVERSATION.value,
            )
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.COMPLETED,
                action=ConversationAction.END_CONVERSATION,
                message=ConversationMessageCatalog.completed(),
                expected_input=ExpectedInputDescriptor(type="NONE"),
                meta=self._build_meta(session, start_time),
            )

        # Handle Query Interruption
        if event == ConversationEvent.CITIZEN_QUERY_RECEIVED:
            query_text = payload.get("query_text", inp.text or "")
            # Preserve return path
            session.resume_state = old_state_enum.value
            session.resume_expected_field = session.expected_field
            session.conversation_state = ConversationState.HANDLING_CITIZEN_QUERY.value

            msg, act = CitizenQueryHandler.handle_query(query_text, session, db_session)
            session.record_trace(
                turn=session.conversation_turn_count,
                old_state=old_state_enum.value,
                event=event.value,
                new_state=ConversationState.HANDLING_CITIZEN_QUERY.value,
                action=act.value,
            )
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.HANDLING_CITIZEN_QUERY,
                action=act,
                message=msg,
                expected_input=self._build_resume_input_descriptor(session),
                meta=self._build_meta(session, start_time),
            )


        # Handle Confirmation Decisions (YES / NO)
        if event == ConversationEvent.PROFILE_VALUE_CONFIRMED:
            return self._handle_confirm_yes(session, db_session, start_time, old_state_enum)

        if event == ConversationEvent.PROFILE_VALUE_REJECTED:
            return self._handle_confirm_no(session, db_session, start_time, old_state_enum)

        # Handle Profile Value Extracted with Confirmation Required
        if event == ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED:
            return self._handle_pending_confirmation_queued(session, payload, start_time, old_state_enum)

        # Handle Direct Profile Value Extraction
        if event == ConversationEvent.PROFILE_VALUE_EXTRACTED:
            return self._handle_profile_value_extracted(session, payload, db_session, start_time, old_state_enum)

        # Handle Profile Value Unknown ("पता नहीं")
        if event == ConversationEvent.PROFILE_VALUE_UNKNOWN:
            return self._handle_profile_unknown(session, payload, db_session, start_time, old_state_enum)

        # Handle Profile Value Declined ("नहीं बताना चाहता")
        if event == ConversationEvent.PROFILE_VALUE_DECLINED:
            return self._handle_profile_declined(session, payload, db_session, start_time, old_state_enum)

        # Handle Clarification Required (Ambiguous / Range / No match)
        if event == ConversationEvent.CLARIFICATION_REQUIRED:
            return self._handle_clarification_required(session, payload, db_session, start_time, old_state_enum)

        # Handle Clarification Provided
        if event == ConversationEvent.CLARIFICATION_PROVIDED:
            # Re-evaluate clarified answer as expected field
            inp.text = payload.get("text", inp.text)
            return self._route_and_process_expected_field_again(session, inp, db_session, start_time, old_state_enum)

        # Handle Need Provided / Change Need
        if event in (ConversationEvent.NEED_PROVIDED, ConversationEvent.CHANGE_NEED_REQUESTED):
            return self._handle_need_provided(session, payload, db_session, start_time, old_state_enum)

        # Handle Scheme Selected
        if event == ConversationEvent.SCHEME_SELECTED:
            return self._handle_scheme_selected(session, payload, db_session, start_time, old_state_enum)

        # Handle Profile Value Corrected
        if event == ConversationEvent.PROFILE_VALUE_CORRECTED:
            return self._handle_profile_corrected(session, payload, db_session, start_time, old_state_enum)

        # Fallback default: Return current state
        return self.get_current_state(session_id, db_session=db_session)

    # -------------------------------------------------------------------------
    # ACTION HANDLERS
    # -------------------------------------------------------------------------

    def _handle_confirm_yes(
        self,
        session: CitizenSession,
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Citizen confirmed the pending fact with 'हाँ' or 'YES'."""
        _, accepted, field_name = self.session_mgr.confirm_pending(session.session_id, decision="YES")
        session.conversation_version += 1

        # Re-run discovery with updated profile
        discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
        return self._transition_after_discovery(
            session=session,
            discovery=discovery,
            start_time=start_time,
            old_state=old_state,
            event=ConversationEvent.PROFILE_VALUE_CONFIRMED,
        )

    def _handle_confirm_no(
        self,
        session: CitizenSession,
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Citizen rejected the pending fact with 'नहीं' or 'NO'."""
        pending = session.pending_confirmation or {}
        rejected_field = pending.get("field") or session.expected_field or "value"
        self.session_mgr.confirm_pending(session.session_id, decision="NO")

        # Stay in WAITING_FOR_PROFILE_VALUE and ask for the value again
        session.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
        session.expected_field = rejected_field
        session.conversation_version += 1

        session.record_trace(
            turn=session.conversation_turn_count,
            old_state=old_state.value,
            event=ConversationEvent.PROFILE_VALUE_REJECTED.value,
            new_state=ConversationState.WAITING_FOR_PROFILE_VALUE.value,
            action=ConversationAction.ASK_PROFILE_FIELD.value,
        )

        f_meta = get_field_metadata(rejected_field)
        msg = ConversationMessageCatalog.confirm_rejected(rejected_field)
        return ConversationResponse(
            session_id=session.session_id,
            state=ConversationState.WAITING_FOR_PROFILE_VALUE,
            action=ConversationAction.ASK_PROFILE_FIELD,
            message=msg,
            expected_input=ExpectedInputDescriptor(
                type="NUMBER" if f_meta.data_type in ("integer", "decimal") else ("BOOLEAN" if f_meta.data_type == "boolean" else "TEXT"),
                field=rejected_field,
                data_type=f_meta.data_type,
            ),
            meta=self._build_meta(session, start_time),
        )

    def _handle_pending_confirmation_queued(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Queues a pending confirmation candidate requiring citizen verification."""
        conf = payload["confirmation"]
        candidates = payload.get("candidates", [])

        if payload.get("need_text"):
            self.session_mgr.set_need_text(session.session_id, payload["need_text"])

        self.session_mgr.set_pending_confirmation(
            session_id=session.session_id,
            confirmation=conf.model_dump(),
            pending_updates=[c.model_dump() for c in candidates],
        )

        session.conversation_state = ConversationState.WAITING_FOR_CONFIRMATION.value
        session.expected_field = conf.field
        session.conversation_version += 1

        session.record_trace(
            turn=session.conversation_turn_count,
            old_state=old_state.value,
            event=ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED.value,
            new_state=ConversationState.WAITING_FOR_CONFIRMATION.value,
            action=ConversationAction.CONFIRM_PROFILE_VALUE.value,
        )

        is_correction = conf.is_correction
        msg = ConversationMessageCatalog.confirm_value(
            field_name=conf.field,
            display_value=conf.display_value,
            is_correction=is_correction,
        )

        return ConversationResponse(
            session_id=session.session_id,
            state=ConversationState.WAITING_FOR_CONFIRMATION,
            action=ConversationAction.CONFIRM_PROFILE_VALUE,
            message=msg,
            expected_input=ExpectedInputDescriptor(
                type="CONFIRMATION",
                field=conf.field,
                display_value=conf.display_value,
                options=[
                    {"value": "YES", "label_hi": "हाँ, यह सही है", "label_en": "Yes, correct"},
                    {"value": "NO", "label_hi": "नहीं, यह गलत है", "label_en": "No, incorrect"},
                ],
            ),
            meta=self._build_meta(session, start_time),
        )

    def _handle_profile_value_extracted(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Direct safe profile value accepted without confirmation."""
        patch: Dict[str, Any] = {}

        if "field" in payload and "value" in payload:
            patch[payload["field"]] = payload["value"]
        elif "candidates" in payload:
            for c in payload["candidates"]:
                patch[c.field] = c.value
                if getattr(c, "frequency", None) and c.field in ("annual_income", "family_income"):
                    patch[f"{c.field}_frequency"] = c.frequency

        if patch:
            self.session_mgr.update_profile(session.session_id, patch=patch, source="CITIZEN_CONVERSATION")

        session.conversation_version += 1
        discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
        return self._transition_after_discovery(
            session=session,
            discovery=discovery,
            start_time=start_time,
            old_state=old_state,
            event=ConversationEvent.PROFILE_VALUE_EXTRACTED,
        )

    def _handle_profile_unknown(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Citizen stated 'पता नहीं' for the active field."""
        field_name = payload.get("field") or session.expected_field
        if field_name:
            session.field_states[field_name] = FieldValueState.UNKNOWN

        session.conversation_version += 1
        discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
        return self._transition_after_discovery(
            session=session,
            discovery=discovery,
            start_time=start_time,
            old_state=old_state,
            event=ConversationEvent.PROFILE_VALUE_UNKNOWN,
        )

    def _handle_profile_declined(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Citizen explicitly declined to provide the active field."""
        field_name = payload.get("field") or session.expected_field
        if field_name:
            self.session_mgr.decline_field(session.session_id, field_name)

        session.conversation_version += 1
        discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
        return self._transition_after_discovery(
            session=session,
            discovery=discovery,
            start_time=start_time,
            old_state=old_state,
            event=ConversationEvent.PROFILE_VALUE_DECLINED,
        )

    def _handle_clarification_required(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Input was ambiguous, approximate, or unparseable. Requests clarification."""
        target_field = payload.get("field") or session.expected_field or "information"
        attempts = session.clarification_attempts.get(target_field, 0) + 1
        session.clarification_attempts[target_field] = attempts

        # If citizen exceeded maximum clarification attempts, fall back to avoid infinite loops
        if attempts >= self.settings.max_clarification_attempts:
            logger.info(
                f"Field '{target_field}' exceeded max clarification attempts ({attempts}). "
                "Marking UNKNOWN and advancing."
            )
            session.field_states[target_field] = FieldValueState.UNKNOWN
            session.conversation_version += 1
            discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
            return self._transition_after_discovery(
                session=session,
                discovery=discovery,
                start_time=start_time,
                old_state=old_state,
                event=ConversationEvent.PROFILE_VALUE_UNKNOWN,
            )

        session.conversation_state = ConversationState.NEED_CLARIFICATION.value
        session.expected_field = target_field
        session.conversation_version += 1

        session.record_trace(
            turn=session.conversation_turn_count,
            old_state=old_state.value,
            event=ConversationEvent.CLARIFICATION_REQUIRED.value,
            new_state=ConversationState.NEED_CLARIFICATION.value,
            action=ConversationAction.CLARIFY_PROFILE_VALUE.value,
        )

        hint = payload.get("hint")
        msg = ConversationMessageCatalog.clarify_value(target_field, hint=hint)
        f_meta = get_field_metadata(target_field)

        return ConversationResponse(
            session_id=session.session_id,
            state=ConversationState.NEED_CLARIFICATION,
            action=ConversationAction.CLARIFY_PROFILE_VALUE,
            message=msg,
            expected_input=ExpectedInputDescriptor(
                type="CURRENCY" if target_field in ("family_income", "annual_income") else "TEXT",
                field=target_field,
                data_type=f_meta.data_type,
            ),
            meta=self._build_meta(session, start_time),
        )

    def _route_and_process_expected_field_again(
        self,
        session: CitizenSession,
        inp: ConversationInput,
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Re-evaluates clarified input as expected field."""
        session.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
        event, payload = self.router.route_input(inp, session)

        if event == ConversationEvent.PROFILE_VALUE_EXTRACTED:
            return self._handle_profile_value_extracted(session, payload, db_session, start_time, old_state)
        if event == ConversationEvent.PROFILE_VALUE_EXTRACTED_CONFIRMATION_REQUIRED:
            return self._handle_pending_confirmation_queued(session, payload, start_time, old_state)

        # If still ambiguous, ask clarification again (counter tracked)
        return self._handle_clarification_required(session, payload, db_session, start_time, old_state)

    def _handle_need_provided(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Processes initial need expression and executes discovery."""
        need_text = payload.get("need_text", session.need_text)
        if need_text:
            self.session_mgr.set_need_text(session.session_id, need_text)

        # If any safe candidates were recognized alongside need, apply them
        patch: Dict[str, Any] = {}
        for c in payload.get("candidates", []):
            patch[c.field] = c.value
        if patch:
            self.session_mgr.update_profile(session.session_id, patch=patch, source="CITIZEN_NEED_STATEMENT")

        session.conversation_version += 1
        discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
        return self._transition_after_discovery(
            session=session,
            discovery=discovery,
            start_time=start_time,
            old_state=old_state,
            event=ConversationEvent.NEED_PROVIDED,
        )

    def _handle_scheme_selected(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Citizen clicks or selects a specific scheme card."""
        scheme_id = payload.get("scheme_id")
        if not scheme_id:
            return self.get_current_state(session.session_id, db_session=db_session)

        # Validate that the selected scheme exists in current eligible or more_info results
        all_ids = set(session.eligible_scheme_ids + session.more_info_scheme_ids)
        if all_ids and scheme_id not in all_ids:
            logger.warning(f"Scheme ID '{scheme_id}' not found in active session candidates.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme '{scheme_id}' is not in the current active discovery results.",
            )

        session.focused_scheme_id = scheme_id
        detail = CitizenDiscoveryFacade.get_citizen_scheme_detail(scheme_id, db_session)

        session.conversation_state = ConversationState.SHOWING_RESULTS.value
        session.record_trace(
            turn=session.conversation_turn_count,
            old_state=old_state.value,
            event=ConversationEvent.SCHEME_SELECTED.value,
            new_state=ConversationState.SHOWING_RESULTS.value,
            action=ConversationAction.SHOW_RESULTS.value,
        )

        name = detail.name_hi or detail.name_en
        return ConversationResponse(
            session_id=session.session_id,
            state=ConversationState.SHOWING_RESULTS,
            action=ConversationAction.SHOW_RESULTS,
            message=ConversationMessage(
                key="SCHEME_DETAIL_VIEW",
                text_hi=f"{name} का विवरण खोला गया है।",
                text_en=f"Opened details for {detail.name_en}.",
            ),
            focused_scheme=detail,
            meta=self._build_meta(session, start_time),
        )

    def _handle_profile_corrected(
        self,
        session: CitizenSession,
        payload: Dict[str, Any],
        db_session: Session,
        start_time: float,
        old_state: ConversationState,
    ) -> ConversationResponse:
        """Citizen corrects an existing profile fact (e.g. 'मेरी उम्र 61 है')."""
        conf = payload.get("confirmation")
        candidate = payload.get("candidate")

        if conf:
            return self._handle_pending_confirmation_queued(
                session=session,
                payload={"confirmation": conf, "candidates": [candidate] if candidate else []},
                start_time=start_time,
                old_state=old_state,
            )

        # Direct correction
        if candidate:
            patch = {candidate.field: candidate.value}
            self.session_mgr.update_profile(session.session_id, patch=patch, source="CITIZEN_CORRECTION")

        session.invalidate_results()
        discovery = CitizenDiscoveryFacade.discover_for_citizen(session.session_id, db_session)
        return self._transition_after_discovery(
            session=session,
            discovery=discovery,
            start_time=start_time,
            old_state=old_state,
            event=ConversationEvent.PROFILE_VALUE_CORRECTED,
        )

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS AFTER DISCOVERY
    # -------------------------------------------------------------------------

    def _transition_after_discovery(
        self,
        session: CitizenSession,
        discovery: CitizenDiscoveryResponse,
        start_time: float,
        old_state: ConversationState,
        event: ConversationEvent,
    ) -> ConversationResponse:
        """
        Determines the next conversation state and action after executing discovery.
        1. If sufficient eligible schemes found -> SHOWING_RESULTS
        2. If next question selected -> WAITING_FOR_PROFILE_VALUE (expected_field set)
        3. If cannot resolve -> CANNOT_RESOLVE
        4. If 0 candidates -> NO_RESULTS
        """
        # Store result order for ordinal resolution
        session.result_order = [s.scheme_id for s in discovery.eligible]

        # Scenario 1: Results ready (target reached or questions finished with eligible results)
        if discovery.state == "RESULTS_READY" or (
            len(discovery.eligible) >= self.settings.target_confirmed_schemes
            or (len(discovery.eligible) > 0 and not discovery.next_question)
        ):
            session.conversation_state = ConversationState.SHOWING_RESULTS.value
            session.expected_field = None
            session.record_trace(
                turn=session.conversation_turn_count,
                old_state=old_state.value,
                event=event.value,
                new_state=ConversationState.SHOWING_RESULTS.value,
                action=ConversationAction.SHOW_RESULTS.value,
            )
            return ConversationResponse(
                session_id=session.session_id,
                state=ConversationState.SHOWING_RESULTS,
                action=ConversationAction.SHOW_RESULTS,
                message=ConversationMessageCatalog.show_results(len(discovery.eligible)),
                results=discovery,
                expected_input=ExpectedInputDescriptor(type="ACTION"),
                meta=self._build_meta(session, start_time),
            )

        # Scenario 2: Next question selected to resolve remaining schemes
        if discovery.next_question and discovery.next_question.field:
            next_f = discovery.next_question.field
            session.conversation_state = ConversationState.WAITING_FOR_PROFILE_VALUE.value
            session.expected_field = next_f
            session.record_trace(
                turn=session.conversation_turn_count,
                old_state=old_state.value,
                event=event.value,
                new_state=ConversationState.WAITING_FOR_PROFILE_VALUE.value,
                action=ConversationAction.ASK_PROFILE_FIELD.value,
            )

            q_hi = discovery.next_question.question_hi
            q_en = discovery.next_question.question_en
            return ConversationResponse(
                session_id=session.session_id,
                state=ConversationState.WAITING_FOR_PROFILE_VALUE,
                action=ConversationAction.ASK_PROFILE_FIELD,
                message=ConversationMessage(
                    key=f"ASK_{next_f.upper()}",
                    text_hi=q_hi,
                    text_en=q_en,
                ),
                expected_input=self._build_field_input_descriptor(discovery.next_question),
                results=discovery,
                meta=self._build_meta(session, start_time),
            )

        # Scenario 3: Cannot resolve remaining candidates with available questions
        if discovery.state == "CANNOT_RESOLVE":
            session.conversation_state = ConversationState.CANNOT_RESOLVE.value
            session.expected_field = None
            session.record_trace(
                turn=session.conversation_turn_count,
                old_state=old_state.value,
                event=event.value,
                new_state=ConversationState.CANNOT_RESOLVE.value,
                action=ConversationAction.SHOW_CANNOT_RESOLVE.value,
            )
            return ConversationResponse(
                session_id=session.session_id,
                state=ConversationState.CANNOT_RESOLVE,
                action=ConversationAction.SHOW_CANNOT_RESOLVE,
                message=ConversationMessageCatalog.show_cannot_resolve(),
                results=discovery,
                expected_input=ExpectedInputDescriptor(type="ACTION"),
                meta=self._build_meta(session, start_time),
            )

        # Scenario 4: No matching candidates found
        session.conversation_state = ConversationState.NO_RESULTS.value
        session.expected_field = None
        session.record_trace(
            turn=session.conversation_turn_count,
            old_state=old_state.value,
            event=event.value,
            new_state=ConversationState.NO_RESULTS.value,
            action=ConversationAction.SHOW_NO_RESULTS.value,
        )
        return ConversationResponse(
            session_id=session.session_id,
            state=ConversationState.NO_RESULTS,
            action=ConversationAction.SHOW_NO_RESULTS,
            message=ConversationMessageCatalog.show_no_results(),
            results=discovery,
            expected_input=ExpectedInputDescriptor(type="ACTION"),
            meta=self._build_meta(session, start_time),
        )

    # -------------------------------------------------------------------------
    # STATE RESTORATION & HELPERS
    # -------------------------------------------------------------------------

    def get_current_state(
        self,
        session_id: str,
        db_session: Optional[Session] = None,
    ) -> ConversationResponse:
        """
        Restores full conversational prompt and action during browser refresh or GET requests.
        """
        start_time = time.perf_counter()
        session = self.session_mgr.require_session(session_id)
        state = ConversationState(session.conversation_state)

        # 1. Waiting for Confirmation
        if state == ConversationState.WAITING_FOR_CONFIRMATION and session.pending_confirmation:
            conf = session.pending_confirmation
            field_name = conf.get("field", "value")
            disp_val = conf.get("display_value", "")
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.WAITING_FOR_CONFIRMATION,
                action=ConversationAction.CONFIRM_PROFILE_VALUE,
                message=ConversationMessageCatalog.confirm_value(field_name, disp_val),
                expected_input=ExpectedInputDescriptor(
                    type="CONFIRMATION",
                    field=field_name,
                    display_value=disp_val,
                    options=[
                        {"value": "YES", "label_hi": "हाँ, यह सही है", "label_en": "Yes, correct"},
                        {"value": "NO", "label_hi": "नहीं, यह गलत है", "label_en": "No, incorrect"},
                    ],
                ),
                meta=self._build_meta(session, start_time),
            )

        # 2. Waiting for Profile Value
        if state == ConversationState.WAITING_FOR_PROFILE_VALUE and session.expected_field:
            f_name = session.expected_field
            f_meta = get_field_metadata(f_name)
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.WAITING_FOR_PROFILE_VALUE,
                action=ConversationAction.ASK_PROFILE_FIELD,
                message=ConversationMessage(
                    key=f"ASK_{f_name.upper()}",
                    text_hi=f_meta.example_question_hi or f"आपकी {f_meta.display_name_hi} क्या है?",
                    text_en=f_meta.example_question_en or f"What is your {f_meta.display_name_en}?",
                ),
                expected_input=ExpectedInputDescriptor(
                    type="NUMBER" if f_meta.data_type in ("integer", "decimal") else ("BOOLEAN" if f_meta.data_type == "boolean" else "TEXT"),
                    field=f_name,
                    data_type=f_meta.data_type,
                ),
                meta=self._build_meta(session, start_time),
            )

        # 3. Showing Results
        if state == ConversationState.SHOWING_RESULTS and db_session:
            discovery = CitizenDiscoveryFacade.discover_for_citizen(session_id, db_session)
            return ConversationResponse(
                session_id=session_id,
                state=ConversationState.SHOWING_RESULTS,
                action=ConversationAction.SHOW_RESULTS,
                message=ConversationMessageCatalog.show_results(len(discovery.eligible)),
                results=discovery,
                expected_input=ExpectedInputDescriptor(type="ACTION"),
                meta=self._build_meta(session, start_time),
            )

        # 4. Default: Waiting for Need
        return ConversationResponse(
            session_id=session_id,
            state=ConversationState.WAITING_FOR_NEED,
            action=ConversationAction.ASK_NEED,
            message=ConversationMessageCatalog.ask_need(),
            expected_input=ExpectedInputDescriptor(type="TEXT"),
            meta=self._build_meta(session, start_time),
        )

    def initialize_session(
        self,
        session_id: str,
        language: str = "hi",
    ) -> ConversationResponse:
        """Initializes conversation state machine for a newly created session."""
        start_time = time.perf_counter()
        session = self.session_mgr.require_session(session_id)
        session.conversation_state = ConversationState.WAITING_FOR_NEED.value
        session.preferred_language = language.lower().strip()
        session.conversation_started_at = datetime.now(timezone.utc)

        return ConversationResponse(
            session_id=session_id,
            state=ConversationState.WAITING_FOR_NEED,
            action=ConversationAction.ASK_NEED,
            message=ConversationMessageCatalog.ask_need(),
            expected_input=ExpectedInputDescriptor(type="TEXT"),
            meta=self._build_meta(session, start_time),
        )

    def _build_meta(self, session: CitizenSession, start_time: float) -> ConversationMeta:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return ConversationMeta(
            turn=session.conversation_turn_count,
            version=session.conversation_version,
            language=session.preferred_language,
            resume_state=session.resume_state,
            expected_field=session.expected_field,
            timings_ms={"total_ms": duration_ms},
            trace=session.debug_trace if self.settings.conversation_debug_trace else None,
        )

    def _build_field_input_descriptor(
        self,
        q_display: CitizenQuestionDisplay,
    ) -> ExpectedInputDescriptor:
        """Converts CitizenQuestionDisplay into ExpectedInputDescriptor."""
        input_type = "TEXT"
        if q_display.data_type in ("integer", "decimal"):
            input_type = "CURRENCY" if "income" in q_display.field else "NUMBER"
        elif q_display.data_type == "boolean":
            input_type = "BOOLEAN"
        elif q_display.data_type == "select":
            input_type = "DISTRICT" if q_display.field == "district" else "SELECT"

        opts = None
        if q_display.options:
            opts = [
                {"value": o.value, "label_hi": o.label_hi, "label_en": o.label_en}
                for o in q_display.options
            ]

        return ExpectedInputDescriptor(
            type=input_type,
            field=q_display.field,
            data_type=q_display.data_type,
            options=opts,
            unit_hi=q_display.unit_hi,
            unit_en=q_display.unit_en,
            allow_decline=q_display.allow_decline,
            help_text_hi=q_display.help_text_hi,
            help_text_en=q_display.help_text_en,
        )

    def _build_resume_input_descriptor(self, session: CitizenSession) -> ExpectedInputDescriptor:
        """Builds expected input descriptor when resuming from query handling."""
        if session.resume_state == ConversationState.WAITING_FOR_CONFIRMATION.value:
            return ExpectedInputDescriptor(
                type="CONFIRMATION",
                field=session.expected_field,
                options=[
                    {"value": "YES", "label_hi": "हाँ, यह सही है", "label_en": "Yes, correct"},
                    {"value": "NO", "label_hi": "नहीं, यह गलत है", "label_en": "No, incorrect"},
                ],
            )
        if session.expected_field:
            f_meta = get_field_metadata(session.expected_field)
            return ExpectedInputDescriptor(
                type="NUMBER" if f_meta.data_type in ("integer", "decimal") else ("BOOLEAN" if f_meta.data_type == "boolean" else "TEXT"),
                field=session.expected_field,
                data_type=f_meta.data_type,
            )
        return ExpectedInputDescriptor(type="TEXT")


# Process-level singleton instance
_CONVERSATION_MANAGER_INSTANCE: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """Returns the singleton ConversationManager instance."""
    global _CONVERSATION_MANAGER_INSTANCE
    if _CONVERSATION_MANAGER_INSTANCE is None:
        _CONVERSATION_MANAGER_INSTANCE = ConversationManager()
    return _CONVERSATION_MANAGER_INSTANCE
