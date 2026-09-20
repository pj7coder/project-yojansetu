import re
from typing import Any, List, Optional, Tuple, Union

from app.normalization.numbers import devanagari_to_ascii, parse_indian_number
from app.normalization.schemas import OperatorEnum


def detect_operator_and_value(text: str) -> Tuple[OperatorEnum, Any, Optional[str]]:
    """
    Deterministically extracts the relational operator and numeric/range value from Hindi/English text.
    Handles exact boundary subtleties and Hindi negations accurately.

    Returns:
        (OperatorEnum, normalized_value, unit)
    """
    if not text:
        return OperatorEnum.EQ, None, None

    norm = devanagari_to_ascii(text.strip())
    lower = norm.lower()

    # Determine unit if age or currency
    unit = None
    if re.search(r'(वर्ष|साल|years?|yrs?)', lower):
        unit = "years"
    elif re.search(r'(माह|महीने|months?)', lower):
        unit = "months"
    elif re.search(r'(दिन|days?)', lower):
        unit = "days"
    elif re.search(r'(%|प्रतिशत|percent)', lower):
        unit = "PERCENT"
    elif re.search(r'(₹|rs\.?|rupees?|रुपये|रुपए)', lower):
        unit = "INR"

    # 1. Check for RANGE / BETWEEN: e.g. "18 से 40 वर्ष", "between 18 and 40", "18-40 वर्ष"
    range_pattern = re.compile(
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:से|to|-|and)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:वर्ष|साल|years?|लाख|lakhs?)?',
        re.IGNORECASE,
    )
    m_range = range_pattern.search(lower)
    if m_range and ("से" in lower or "between" in lower or "-" in lower or "to" in lower):
        # ensure it's not a "से अधिक" or "से कम" phrase
        if not re.search(r'से\s*(अधिक|ज्यादा|कम)', lower):
            v1 = float(m_range.group(1))
            v2 = float(m_range.group(2))
            # check if scale like lakh applies
            if "लाख" in lower or "lakh" in lower:
                if v1 < 1000:
                    v1 *= 100000
                if v2 < 1000:
                    v2 *= 100000
            val1 = int(v1) if v1.is_integer() else v1
            val2 = int(v2) if v2.is_integer() else v2
            return OperatorEnum.BETWEEN, [val1, val2], unit

    # 2. Extract primary numeric value
    val = parse_indian_number(norm)

    # 3. Check for NEGATIONS first:
    # "से अधिक नहीं" / "से ज्यादा नहीं" / "not more than" / "not exceeding" -> LTE
    if re.search(r'(से\s*(?:अधिक|ज्यादा)\s*नहीं|not\s*(?:more\s*than|exceeding|greater\s*than))', lower):
        return OperatorEnum.LTE, val, unit

    # "से कम नहीं" / "not less than" -> GTE
    if re.search(r'(से\s*कम\s*नहीं|not\s*less\s*than)', lower):
        return OperatorEnum.GTE, val, unit

    # 4. Check for POSITIVE BOUNDARIES:
    # GTE: "या अधिक", "या उससे अधिक", "पूर्ण कर चुके", "कम से कम", "न्यूनतम", "at least", "minimum", "or more", "and above"
    if re.search(
        r'(या\s*(?:उससे\s*)?अधिक|या\s*ज्यादा|पूर्ण\s*कर\s*चुके|कम\s*से\s*कम|न्यूनतम|at\s*least|minimum|or\s*more|and\s*above)',
        lower,
    ):
        return OperatorEnum.GTE, val, unit

    # GT: "से अधिक", "से ज्यादा", "more than", "greater than", "exceeding", "above"
    if re.search(r'(से\s*(?:अधिक|ज्यादा)|more\s*than|greater\s*than|exceeding|above)', lower):
        return OperatorEnum.GT, val, unit

    # LTE: "तक", "अधिकतम", "not more than", "up to", "maximum"
    if re.search(r'(अधिकतम|तक|up\s*to|maximum)', lower):
        return OperatorEnum.LTE, val, unit

    # LT: "से कम", "less than", "below", "under"
    if re.search(r'(से\s*कम|less\s*than|below|under)', lower):
        return OperatorEnum.LT, val, unit

    # Default if number exists
    if val is not None:
        return OperatorEnum.EQ, val, unit

    return OperatorEnum.EQ, None, unit
