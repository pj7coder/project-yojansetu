"""
Pydantic schemas and DTOs for JanSetu Conversation Manager (Day 25).
Provides structured contracts for client turns, responses, and field input descriptors.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.citizen.schemas import CitizenDiscoveryResponse, CitizenSchemeDetailResponse
from app.conversation.actions import ConversationAction
from app.conversation.states import ConversationState


class ConversationInputType(str, Enum):
    """Channel and format of incoming citizen turn input."""
    TEXT = "TEXT"
    STT_TRANSCRIPT = "STT_TRANSCRIPT"
    STRUCTURED_VALUE = "STRUCTURED_VALUE"
    ACTION = "ACTION"
    CONFIRMATION = "CONFIRMATION"


class ConversationInput(BaseModel):
    """
    Unified input payload for a conversation turn.
    Supports typed text, STT transcripts, structured button clicks, and actions.
    """
    type: ConversationInputType = Field(
        default=ConversationInputType.TEXT,
        description="TEXT, STT_TRANSCRIPT, STRUCTURED_VALUE, ACTION, or CONFIRMATION",
    )
    text: Optional[str] = Field(
        default=None,
        description="Verbatim speech transcript or typed text",
    )
    action: Optional[str] = Field(
        default=None,
        description="Structured action code (e.g. START_OVER, END_CONVERSATION, SELECT_SCHEME, CHANGE_LANGUAGE, CHANGE_NEED, CONFIRM_YES, CONFIRM_NO)",
    )
    field: Optional[str] = Field(
        default=None,
        description="Target profile field name if sending structured value",
    )
    value: Optional[Any] = Field(
        default=None,
        description="Typed value if sending structured value",
    )
    client_turn_id: Optional[str] = Field(
        default=None,
        description="Optional client UUID for idempotency on network retries",
    )
    language: Optional[str] = Field(
        default=None,
        description="Optional language preference override ('hi' or 'en')",
    )
    scheme_id: Optional[str] = Field(
        default=None,
        description="Target scheme identifier if selecting a scheme",
    )
    conversation_version: Optional[int] = Field(
        default=None,
        description="Last known conversation version for concurrency conflict detection",
    )


class ExpectedInputOption(BaseModel):
    """Selectable option for structured input card."""
    value: Any
    label_hi: str
    label_en: str


class ExpectedInputDescriptor(BaseModel):
    """
    Metadata informing frontend what input control to render for current turn.
    """
    type: str = Field(
        description="TEXT, NUMBER, CURRENCY, BOOLEAN, SELECT, DISTRICT, CONFIRMATION, ACTION, NONE"
    )
    field: Optional[str] = Field(default=None, description="Profile field key if expecting profile value")
    data_type: Optional[str] = Field(default=None, description="Data type of field: int, decimal, bool, str, select")
    options: Optional[List[Dict[str, Any]]] = Field(default=None, description="Preset choices for select or boolean")
    unit_hi: Optional[str] = Field(default=None, description="Hindi unit label (e.g. वर्ष, ₹/वर्ष, एकड़)")
    unit_en: Optional[str] = Field(default=None, description="English unit label (e.g. Years, ₹/yr, Acres)")
    display_value: Optional[str] = Field(default=None, description="Candidate display value for confirmation")
    allow_decline: bool = Field(default=True, description="Whether citizen can decline answering")
    help_text_hi: Optional[str] = Field(default=None)
    help_text_en: Optional[str] = Field(default=None)


class ConversationMessage(BaseModel):
    """
    Bilingual system message for presentation and Day 26 TTS readiness.
    Free of HTML formatting.
    """
    key: str = Field(description="Message catalog key")
    text_hi: str = Field(description="Hindi plain-text message")
    text_en: str = Field(description="English plain-text message")


class ConversationMeta(BaseModel):
    """Diagnostic and state metadata for the conversation response."""
    turn: int = Field(description="Current conversation turn count")
    version: int = Field(description="Current conversation state version")
    language: str = Field(default="hi", description="Active preferred language")
    resume_state: Optional[str] = Field(default=None, description="Workflow state to resume after query")
    expected_field: Optional[str] = Field(default=None)
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    trace: Optional[List[Dict[str, Any]]] = Field(default=None, description="Debug trace if enabled")


class ConversationResponse(BaseModel):
    """
    Complete structured response returned by ConversationManager.
    Single unified contract powering both text UI and future voice workflows.
    """
    session_id: str
    state: ConversationState
    action: ConversationAction
    message: ConversationMessage
    expected_input: Optional[ExpectedInputDescriptor] = None
    results: Optional[CitizenDiscoveryResponse] = None
    focused_scheme: Optional[CitizenSchemeDetailResponse] = None
    meta: ConversationMeta
