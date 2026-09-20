"""
Controlled conversation states for YojanSetu Deterministic State Machine (Day 25).
Represents workflow progress rather than individual fields.
"""

from enum import Enum


class ConversationState(str, Enum):
    """
    Controlled workflow state enum.
    State describes workflow stage; context describes target field.
    """
    NEW_SESSION = "NEW_SESSION"
    WAITING_FOR_NEED = "WAITING_FOR_NEED"
    WAITING_FOR_PROFILE_VALUE = "WAITING_FOR_PROFILE_VALUE"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    PROCESSING_DISCOVERY = "PROCESSING_DISCOVERY"
    SHOWING_RESULTS = "SHOWING_RESULTS"
    WAITING_FOR_RESULT_ACTION = "WAITING_FOR_RESULT_ACTION"
    HANDLING_CITIZEN_QUERY = "HANDLING_CITIZEN_QUERY"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"
    NO_RESULTS = "NO_RESULTS"
    CANNOT_RESOLVE = "CANNOT_RESOLVE"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
