from enum import Enum
from typing import Sequence


class TruthState(str, Enum):
    """
    Three-state internal logic for citizen condition evaluation.
    - TRUE: Condition is definitively satisfied by known citizen data.
    - FALSE: Condition is definitively violated by known citizen data.
    - UNKNOWN: Required citizen data is missing or ambiguous.
    """
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def evaluate_and(states: Sequence[TruthState]) -> TruthState:
    """
    Kleene three-valued logic for AND:
    - FALSE + anything -> FALSE (short-circuit / definitive rejection)
    - TRUE + TRUE -> TRUE
    - TRUE + UNKNOWN -> UNKNOWN
    - UNKNOWN + UNKNOWN -> UNKNOWN
    - UNKNOWN + FALSE -> FALSE
    - Empty sequence -> TRUE (vacuous truth)
    """
    if not states:
        return TruthState.TRUE

    has_unknown = False
    for state in states:
        if state == TruthState.FALSE:
            return TruthState.FALSE
        elif state == TruthState.UNKNOWN:
            has_unknown = True

    return TruthState.UNKNOWN if has_unknown else TruthState.TRUE


def evaluate_or(states: Sequence[TruthState]) -> TruthState:
    """
    Kleene three-valued logic for OR:
    - TRUE + anything -> TRUE (short-circuit / definitive satisfaction)
    - FALSE + FALSE -> FALSE
    - FALSE + UNKNOWN -> UNKNOWN
    - UNKNOWN + UNKNOWN -> UNKNOWN
    - UNKNOWN + TRUE -> TRUE
    - Empty sequence -> FALSE
    """
    if not states:
        return TruthState.FALSE

    has_unknown = False
    for state in states:
        if state == TruthState.TRUE:
            return TruthState.TRUE
        elif state == TruthState.UNKNOWN:
            has_unknown = True

    return TruthState.UNKNOWN if has_unknown else TruthState.FALSE


def evaluate_not(state: TruthState) -> TruthState:
    """
    Three-valued logic for NOT:
    - NOT TRUE -> FALSE
    - NOT FALSE -> TRUE
    - NOT UNKNOWN -> UNKNOWN (missing information remains UNKNOWN)
    """
    if state == TruthState.TRUE:
        return TruthState.FALSE
    elif state == TruthState.FALSE:
        return TruthState.TRUE
    return TruthState.UNKNOWN
