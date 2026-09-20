import re
from typing import Optional, Tuple, Union

DEVANAGARI_DIGITS_MAP = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
}

SCALE_MULTIPLIERS = {
    'लाख': 100_000,
    'lakh': 100_000,
    'lakhs': 100_000,
    'lac': 100_000,
    'lacs': 100_000,
    'करोड़': 10_000_000,
    'करोड': 10_000_000,
    'crore': 10_000_000,
    'crores': 10_000_000,
    'cr': 10_000_000,
    'हजार': 1_000,
    'हज़ार': 1_000,
    'thousand': 1_000,
    'k': 1_000,
    'अरब': 1_000_000_000,
    'arab': 1_000_000_000,
}


def devanagari_to_ascii(text: str) -> str:
    """Translate all Devanagari numerals (०-९) to ASCII numerals (0-9)."""
    if not text:
        return ""
    result = []
    for ch in text:
        result.append(DEVANAGARI_DIGITS_MAP.get(ch, ch))
    return "".join(result)


def parse_indian_number(text: str) -> Optional[Union[int, float]]:
    """
    Parse a numeric expression from English/Hindi text into an int or float,
    correctly handling Indian scales (lakh, crore, thousand), comma formatting,
    Devanagari numerals, and decimal multipliers.

    Examples:
        "₹2 लाख" -> 200000
        "₹2,00,000" -> 200000
        "1.5 लाख" -> 150000
        "२ लाख" -> 200000
        "६० वर्ष" -> 60
        "40 प्रतिशत" -> 40
        "₹1000 प्रति माह" -> 1000
    """
    if not text:
        return None

    # Step 1: Normalize Devanagari numerals to ASCII digits
    normalized = devanagari_to_ascii(text.strip().lower())

    # Step 2: Look for patterns with explicit scale words (e.g. 1.5 लाख, 2 crore, 50 हजार)
    # Regex: number (int or float) possibly followed by scale word
    scale_pattern = re.compile(
        r'([0-9]+(?:\.[0-9]+)?)\s*(लाख|lakhs?|lacs?|करोड़|करोड|crores?|cr|हजार|हज़ार|thousand|k|अरब|arab)',
        re.IGNORECASE,
    )
    match = scale_pattern.search(normalized)
    if match:
        num_part = float(match.group(1))
        unit_word = match.group(2).lower()
        multiplier = SCALE_MULTIPLIERS.get(unit_word, 1)
        val = num_part * multiplier
        return int(val) if val.is_integer() else val

    # Step 3: Check for comma-formatted or standard digits (e.g. "2,00,000", "200000", "60", "1.5")
    # Clean out currency symbols and whitespace around numbers
    comma_pattern = re.compile(r'([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)')
    match_comma = comma_pattern.search(normalized)
    if match_comma:
        raw_num = match_comma.group(1).replace(",", "")
        try:
            val = float(raw_num)
            return int(val) if val.is_integer() else val
        except ValueError:
            return None

    return None


def parse_percentage(text: str) -> Optional[Tuple[float, str]]:
    """
    Extract percentage value if present in text.
    Examples:
        "40%" -> (40.0, "PERCENT")
        "40 प्रतिशत" -> (40.0, "PERCENT")
        "४०%" -> (40.0, "PERCENT")
    """
    if not text:
        return None

    normalized = devanagari_to_ascii(text.strip().lower())
    percent_pattern = re.compile(
        r'([0-9]+(?:\.[0-9]+)?)\s*(%|प्रतिशत|percent|percentage)',
        re.IGNORECASE,
    )
    match = percent_pattern.search(normalized)
    if match:
        try:
            val = float(match.group(1))
            return val, "PERCENT"
        except ValueError:
            return None

    return None
