import re
from typing import Optional, Tuple
from app.normalization.schemas import PeriodicityEnum

CURRENCY_SYMBOLS = ["₹", "rs.", "rs", "inr", "rupees", "रुपये", "रुपए", "रु."]

PERIODICITY_PATTERNS = {
    PeriodicityEnum.MONTHLY: [
        r'प्रति\s*माह', r'प्रति\s*महीना', r'मासिक', r'per\s*month', r'monthly', r'/month', r'/माह'
    ],
    PeriodicityEnum.ANNUAL: [
        r'प्रति\s*वर्ष', r'वार्षिक', r'per\s*year', r'annual', r'annually', r'per\s*annum', r'p\.a\.', r'/वर्ष'
    ],
    PeriodicityEnum.ONE_TIME: [
        r'एकमुश्त', r'एक\s*बार', r'one-time', r'one\s*time', r'single\s*installment'
    ],
    PeriodicityEnum.PER_SEMESTER: [
        r'प्रति\s*सत्र', r'per\s*semester', r'per\s*session'
    ],
    PeriodicityEnum.PER_BENEFICIARY: [
        r'प्रति\s*लाभार्थी', r'per\s*beneficiary'
    ],
}


def detect_currency(text: str) -> Optional[str]:
    """Detect if currency terms or symbols are present, returning standard 'INR'."""
    if not text:
        return None
    lower_text = text.lower()
    for sym in CURRENCY_SYMBOLS:
        if sym in lower_text:
            return "INR"
    return None


def detect_periodicity(text: str) -> PeriodicityEnum:
    """Detect periodicity (MONTHLY, ANNUAL, ONE_TIME, etc.) from English/Hindi text."""
    if not text:
        return PeriodicityEnum.UNKNOWN

    lower_text = text.lower()
    for period, patterns in PERIODICITY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower_text):
                return period

    return PeriodicityEnum.UNKNOWN
