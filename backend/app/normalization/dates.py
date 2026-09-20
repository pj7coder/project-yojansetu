from datetime import datetime
import re
from typing import Any, Dict, Optional, Tuple

from app.normalization.numbers import devanagari_to_ascii, parse_indian_number


def parse_date_expression(text: str) -> Dict[str, Any]:
    """
    Parse a date or timeline expression from English/Hindi government text.

    Supports:
    1. Exact ISO dates (e.g. '2026-03-31')
    2. Indian formatted dates (e.g. '31/03/2026', '31-03-2026')
    3. Relative durations (e.g. 'within 30 days', '30 दिन के भीतर')

    Returns dict with keys:
        - date_type: 'EXACT', 'RELATIVE_DURATION', or 'UNKNOWN'
        - normalized_date: ISO YYYY-MM-DD or None
        - relative_duration: {'value': int, 'unit': str} or None
        - raw_date_text: preserved string
        - parse_method: explanation string
    """
    if not text:
        return {
            "date_type": "UNKNOWN",
            "normalized_date": None,
            "relative_duration": None,
            "raw_date_text": "",
            "parse_method": "EMPTY",
        }

    raw = text.strip()
    norm = devanagari_to_ascii(raw)

    # 1. Check for relative durations: e.g. "within 30 days", "30 दिन के भीतर"
    rel_pattern = re.compile(
        r'([0-9]+)\s*(दिन|माह|महीने|वर्ष|साल|days?|months?|years?)\s*(?:के\s*भीतर|के\s*अंदर|के\s*दौरान|within|from|of)?',
        re.IGNORECASE,
    )
    m_rel = rel_pattern.search(norm)
    if m_rel:
        val = int(m_rel.group(1))
        unit_raw = m_rel.group(2).lower()
        if unit_raw in ["दिन", "day", "days"]:
            unit = "days"
        elif unit_raw in ["माह", "महीने", "month", "months"]:
            unit = "months"
        elif unit_raw in ["वर्ष", "साल", "year", "years"]:
            unit = "years"
        else:
            unit = unit_raw

        return {
            "date_type": "RELATIVE_DURATION",
            "normalized_date": None,
            "relative_duration": {"value": val, "unit": unit},
            "raw_date_text": raw,
            "parse_method": "RELATIVE_DURATION_REGEX",
        }

    # 2. Check for ISO date: YYYY-MM-DD
    iso_pattern = re.compile(r'\b(20[2-3][0-9])[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12][0-9]|3[01])\b')
    m_iso = iso_pattern.search(norm)
    if m_iso:
        y, m, d = m_iso.groups()
        iso_str = f"{y}-{m}-{d}"
        return {
            "date_type": "EXACT",
            "normalized_date": iso_str,
            "relative_duration": None,
            "raw_date_text": raw,
            "parse_method": "ISO_YYYY_MM_DD",
        }

    # 3. Check for Indian standard format: DD/MM/YYYY or DD-MM-YYYY
    in_pattern = re.compile(r'\b(0[1-9]|[12][0-9]|3[01])[-/.](0[1-9]|1[0-2])[-/.](20[2-3][0-9])\b')
    m_in = in_pattern.search(norm)
    if m_in:
        d, m, y = m_in.groups()
        iso_str = f"{y}-{m}-{d}"
        return {
            "date_type": "EXACT",
            "normalized_date": iso_str,
            "relative_duration": None,
            "raw_date_text": raw,
            "parse_method": "INDIAN_DD_MM_YYYY",
        }

    return {
        "date_type": "UNKNOWN",
        "normalized_date": None,
        "relative_duration": None,
        "raw_date_text": raw,
        "parse_method": "UNPARSED",
    }
