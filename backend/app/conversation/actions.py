"""
Controlled conversation actions for JanSetu response rendering (Day 25).
Directs frontend display and expected interaction without manual client orchestration.
"""

from enum import Enum


class ConversationAction(str, Enum):
    """
    Structured action directives instructing frontend on how to present the response.
    """
    ASK_NEED = "ASK_NEED"
    ASK_PROFILE_FIELD = "ASK_PROFILE_FIELD"
    CONFIRM_PROFILE_VALUE = "CONFIRM_PROFILE_VALUE"
    CLARIFY_PROFILE_VALUE = "CLARIFY_PROFILE_VALUE"
    SHOW_RESULTS = "SHOW_RESULTS"
    SHOW_NO_RESULTS = "SHOW_NO_RESULTS"
    SHOW_CANNOT_RESOLVE = "SHOW_CANNOT_RESOLVE"
    ANSWER_FIELD_HELP = "ANSWER_FIELD_HELP"
    ANSWER_SCHEME_QUERY = "ANSWER_SCHEME_QUERY"
    REPEAT_PROMPT = "REPEAT_PROMPT"
    END_CONVERSATION = "END_CONVERSATION"
    ERROR = "ERROR"
