from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Optional, Sequence, Union
from app.eligibility.truth import TruthState
from app.normalization.schemas import OperatorEnum


def to_comparable_number(val: Any) -> Optional[Decimal]:
    """
    Safely convert an integer, float, string, or Decimal into a Decimal for precise comparison.
    Excludes booleans because bool is a subclass of int in Python.
    Returns None if conversion fails.
    """
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


def op_eq(citizen_val: Any, target_val: Any) -> TruthState:
    """Exact equality check."""
    if citizen_val is None:
        return TruthState.UNKNOWN
    if target_val is None:
        return TruthState.UNKNOWN

    # Boolean check (must precede numeric check because bool subclasses int in Python)
    if isinstance(citizen_val, bool) or isinstance(target_val, bool):
        if isinstance(citizen_val, bool) and isinstance(target_val, bool):
            return TruthState.TRUE if citizen_val is target_val else TruthState.FALSE
        if isinstance(target_val, str):
            t_bool = target_val.lower() in ("true", "1", "yes", "हाँ", "ha")
            return TruthState.TRUE if bool(citizen_val) == t_bool else TruthState.FALSE
        if isinstance(citizen_val, str):
            c_bool = citizen_val.lower() in ("true", "1", "yes", "हाँ", "ha")
            return TruthState.TRUE if c_bool == bool(target_val) else TruthState.FALSE
        return TruthState.TRUE if bool(citizen_val) == bool(target_val) else TruthState.FALSE

    # Numeric check
    c_num = to_comparable_number(citizen_val)
    t_num = to_comparable_number(target_val)
    if c_num is not None and t_num is not None:
        return TruthState.TRUE if c_num == t_num else TruthState.FALSE

    # String check (case-insensitive & whitespace trimmed)
    if isinstance(citizen_val, str) and isinstance(target_val, str):
        return TruthState.TRUE if citizen_val.strip().lower() == target_val.strip().lower() else TruthState.FALSE

    return TruthState.TRUE if citizen_val == target_val else TruthState.FALSE


def op_ne(citizen_val: Any, target_val: Any) -> TruthState:
    """Inequality check."""
    res = op_eq(citizen_val, target_val)
    if res == TruthState.UNKNOWN:
        return TruthState.UNKNOWN
    return TruthState.FALSE if res == TruthState.TRUE else TruthState.TRUE


def op_gt(citizen_val: Any, target_val: Any) -> TruthState:
    """Greater than (>). Strict boundary."""
    if citizen_val is None or target_val is None:
        return TruthState.UNKNOWN
    c_num = to_comparable_number(citizen_val)
    t_num = to_comparable_number(target_val)
    if c_num is None or t_num is None:
        return TruthState.UNKNOWN
    return TruthState.TRUE if c_num > t_num else TruthState.FALSE


def op_gte(citizen_val: Any, target_val: Any) -> TruthState:
    """Greater than or equal to (>=). Inclusive boundary."""
    if citizen_val is None or target_val is None:
        return TruthState.UNKNOWN
    c_num = to_comparable_number(citizen_val)
    t_num = to_comparable_number(target_val)
    if c_num is None or t_num is None:
        return TruthState.UNKNOWN
    return TruthState.TRUE if c_num >= t_num else TruthState.FALSE


def op_lt(citizen_val: Any, target_val: Any) -> TruthState:
    """Less than (<). Strict boundary."""
    if citizen_val is None or target_val is None:
        return TruthState.UNKNOWN
    c_num = to_comparable_number(citizen_val)
    t_num = to_comparable_number(target_val)
    if c_num is None or t_num is None:
        return TruthState.UNKNOWN
    return TruthState.TRUE if c_num < t_num else TruthState.FALSE


def op_lte(citizen_val: Any, target_val: Any) -> TruthState:
    """Less than or equal to (<=). Inclusive boundary."""
    if citizen_val is None or target_val is None:
        return TruthState.UNKNOWN
    c_num = to_comparable_number(citizen_val)
    t_num = to_comparable_number(target_val)
    if c_num is None or t_num is None:
        return TruthState.UNKNOWN
    return TruthState.TRUE if c_num <= t_num else TruthState.FALSE


def op_between(citizen_val: Any, target_val: Any) -> TruthState:
    """
    Between range check: min <= citizen_val <= max (inclusive).
    target_val can be a list/tuple of [min, max] or a dict with {'min': ..., 'max': ...}.
    """
    if citizen_val is None or target_val is None:
        return TruthState.UNKNOWN
    c_num = to_comparable_number(citizen_val)
    if c_num is None:
        return TruthState.UNKNOWN

    low, high = None, None
    if isinstance(target_val, (list, tuple)) and len(target_val) >= 2:
        low = to_comparable_number(target_val[0])
        high = to_comparable_number(target_val[1])
    elif isinstance(target_val, dict):
        low = to_comparable_number(target_val.get("min") or target_val.get("low"))
        high = to_comparable_number(target_val.get("max") or target_val.get("high"))

    if low is None or high is None:
        return TruthState.UNKNOWN

    return TruthState.TRUE if (low <= c_num <= high) else TruthState.FALSE


def op_in(citizen_val: Any, target_val: Any) -> TruthState:
    """
    Membership check: citizen_val IN target_val.
    target_val should be an iterable collection (list, tuple, set).
    """
    if citizen_val is None:
        return TruthState.UNKNOWN
    if target_val is None:
        return TruthState.UNKNOWN

    if not isinstance(target_val, (list, tuple, set)):
        target_val = [target_val]

    # If citizen is string, do case-insensitive comparison against candidates
    if isinstance(citizen_val, str):
        c_str = citizen_val.strip().lower()
        for item in target_val:
            if isinstance(item, str) and item.strip().lower() == c_str:
                return TruthState.TRUE
            elif op_eq(citizen_val, item) == TruthState.TRUE:
                return TruthState.TRUE
        return TruthState.FALSE

    # Numeric or other equality
    for item in target_val:
        if op_eq(citizen_val, item) == TruthState.TRUE:
            return TruthState.TRUE

    return TruthState.FALSE


def op_not_in(citizen_val: Any, target_val: Any) -> TruthState:
    """Negated membership check."""
    res = op_in(citizen_val, target_val)
    if res == TruthState.UNKNOWN:
        return TruthState.UNKNOWN
    return TruthState.FALSE if res == TruthState.TRUE else TruthState.TRUE


def op_exists(citizen_val: Any, target_val: Any = None) -> TruthState:
    """
    Checks whether a citizen value exists / is provided.
    Does NOT mean > 0. A value of 0 or False exists. None does not exist.
    """
    return TruthState.TRUE if citizen_val is not None else TruthState.FALSE


def op_not_exists(citizen_val: Any, target_val: Any = None) -> TruthState:
    """Checks whether citizen value is absent."""
    return TruthState.TRUE if citizen_val is None else TruthState.FALSE


OPERATOR_REGISTRY: Dict[Union[OperatorEnum, str], Callable[[Any, Any], TruthState]] = {
    OperatorEnum.EQ: op_eq,
    OperatorEnum.NE: op_ne,
    OperatorEnum.GT: op_gt,
    OperatorEnum.GTE: op_gte,
    OperatorEnum.LT: op_lt,
    OperatorEnum.LTE: op_lte,
    OperatorEnum.BETWEEN: op_between,
    OperatorEnum.IN: op_in,
    OperatorEnum.NOT_IN: op_not_in,
    OperatorEnum.EXISTS: op_exists,
    OperatorEnum.NOT_EXISTS: op_not_exists,
    # String aliases
    "EQ": op_eq,
    "NE": op_ne,
    "GT": op_gt,
    "GTE": op_gte,
    "LT": op_lt,
    "LTE": op_lte,
    "BETWEEN": op_between,
    "IN": op_in,
    "NOT_IN": op_not_in,
    "EXISTS": op_exists,
    "NOT_EXISTS": op_not_exists,
}


def evaluate_operator(
    operator: Union[OperatorEnum, str],
    citizen_value: Any,
    required_value: Any,
) -> TruthState:
    """
    Deterministically evaluates an operator against citizen value and required rule value.
    Fails safely with UNKNOWN if operator is unrecognized.
    """
    op_func = OPERATOR_REGISTRY.get(operator)
    if not op_func:
        return TruthState.UNKNOWN
    return op_func(citizen_value, required_value)
