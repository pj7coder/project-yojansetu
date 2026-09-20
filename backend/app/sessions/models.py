from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class FieldValueState(str, Enum):
    """Lifecycle state of a citizen profile field in the session."""
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    DECLINED = "DECLINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class FieldRecord:
    """Audit and provenance record for a specific profile field."""
    field_name: str
    value: Any
    state: FieldValueState
    source: str = "USER_INPUT"
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CitizenSession:
    """
    Ephemeral in-memory citizen session state.
    Holds structured profile facts collected across multi-turn interactions.
    Never persisted to permanent database tables; automatically expires after TTL.
    """
    session_id: str
    profile: Dict[str, Any] = field(default_factory=dict)
    field_states: Dict[str, FieldValueState] = field(default_factory=dict)
    field_records: Dict[str, FieldRecord] = field(default_factory=dict)
    need_text: Optional[str] = None
    asked_fields: List[str] = field(default_factory=list)
    field_ask_counts: Dict[str, int] = field(default_factory=dict)
    candidate_scheme_ids: List[str] = field(default_factory=list)
    eligible_scheme_ids: List[str] = field(default_factory=list)
    more_info_scheme_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    profile_version: int = 1
    discovery_version: int = 0
    pending_profile_updates: List[Dict[str, Any]] = field(default_factory=list)
    pending_confirmation: Optional[Dict[str, Any]] = None
    update_history: List[Dict[str, Any]] = field(default_factory=list)
    # Day 25: Deterministic Conversation Manager extensions
    conversation_state: str = "NEW_SESSION"
    expected_field: Optional[str] = None
    resume_state: Optional[str] = None
    resume_expected_field: Optional[str] = None
    current_need_text: Optional[str] = None
    focused_scheme_id: Optional[str] = None
    result_order: List[str] = field(default_factory=list)
    result_version: int = 0
    conversation_version: int = 1
    conversation_turn_count: int = 0
    processed_turn_ids: List[str] = field(default_factory=list)
    preferred_language: str = "hi"
    clarification_attempts: Dict[str, int] = field(default_factory=dict)
    last_system_action: Optional[str] = None
    last_user_input_type: Optional[str] = None
    conversation_started_at: Optional[datetime] = None
    debug_trace: List[Dict[str, Any]] = field(default_factory=list)
    # Day 27: Voice Mode & Transport Extensions
    voice_mode_enabled: bool = False
    voice_turn_active: bool = False
    voice_transport_state: str = "READY"
    last_voice_error: Optional[str] = None
    last_voice_response_id: Optional[str] = None

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Returns True if the session has exceeded its configured TTL."""
        now = current_time or datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return now >= self.expires_at

    def get_known_field_names(self) -> List[str]:
        """Returns list of field names that are currently confirmed/known."""
        return [
            f for f, s in self.field_states.items()
            if s == FieldValueState.KNOWN and self.profile.get(f) is not None
        ]

    def get_declined_field_names(self) -> List[str]:
        """Returns list of field names that citizen has declined to answer."""
        return [
            f for f, s in self.field_states.items()
            if s == FieldValueState.DECLINED
        ]

    def is_field_known(self, field_name: str) -> bool:
        """Checks if a field is known and present."""
        return (
            self.field_states.get(field_name) == FieldValueState.KNOWN
            and self.profile.get(field_name) is not None
        )

    def is_field_declined(self, field_name: str) -> bool:
        """Checks if citizen previously declined to answer this field."""
        return self.field_states.get(field_name) == FieldValueState.DECLINED

    def invalidate_results(self) -> None:
        """Invalidates discovery results cache and ordinal list when profile changes."""
        self.focused_scheme_id = None
        self.result_order = []
        self.result_version += 1

    def reset_conversation(self) -> None:
        """Completely clears conversational state and profile facts for START_OVER."""
        self.profile = {}
        self.field_states = {}
        self.field_records = {}
        self.need_text = None
        self.current_need_text = None
        self.asked_fields = []
        self.field_ask_counts = {}
        self.candidate_scheme_ids = []
        self.eligible_scheme_ids = []
        self.more_info_scheme_ids = []
        self.pending_profile_updates = []
        self.pending_confirmation = None
        self.update_history = []
        self.conversation_state = "WAITING_FOR_NEED"
        self.expected_field = None
        self.resume_state = None
        self.resume_expected_field = None
        self.focused_scheme_id = None
        self.result_order = []
        self.result_version = 0
        self.conversation_version += 1
        self.conversation_turn_count = 0
        self.clarification_attempts = {}
        self.last_system_action = None
        self.last_user_input_type = None

    def record_trace(self, turn: int, old_state: str, event: str, new_state: str, action: str) -> None:
        """Records a privacy-safe state machine transition trace without citizen data."""
        self.debug_trace.append({
            "turn": turn,
            "old_state": old_state,
            "event": event,
            "new_state": new_state,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Bound trace history to last 50 transitions
        if len(self.debug_trace) > 50:
            self.debug_trace = self.debug_trace[-50:]

