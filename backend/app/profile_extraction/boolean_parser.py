"""
Boolean, negation, unknown, and decline parser for vernacular citizen inputs.
Strictly safeguards against negation inversion (never treats 'बीपीएल में नहीं हूँ' as true).
"""

import re
from typing import Optional, Tuple
from app.profile_extraction.schemas import IntentType
from app.sessions.models import FieldValueState

YES_TOKENS = {
    "हाँ", "हां", "हा",  # हा = Whisper tiny often drops chandrabindu (ँ) from हाँ
    "जी हाँ", "जी हां", "जी हा",
    "yes", "y", "haan", "ha", "haa",
    "bilkul", "sahi", "sahi hai", "true", "हूँ", "हूँ जी"
}

NO_TOKENS = {
    "नहीं", "नही", "जी नहीं", "जी नही", "no", "n", "nahi", "na", "false",
    "galat", "कोनी", "कोनी है", "ना", "नहीं हूँ"
}

UNKNOWN_PATTERNS = [
    r'(पता\s*नहीं|मालूम\s*नहीं|नहीं\s*पता|जानकारी\s*नहीं|याद\s*नहीं)',
    r'(don\'?t\s*know|dont\s*know|not\s*sure|no\s*idea|unknown)',
]

DECLINE_PATTERNS = [
    r'(नहीं\s*बताना|बताना\s*नहीं\s*चाहता|नहीं\s*बताऊंगा|शेयर\s*नहीं\s*करना)',
    r'(prefer\s*not\s*to\s*say|decline|won\'?t\s*say|private)',
]

QUERY_PATTERNS = [
    r'(कितना\s*पैसा|कितने\s*पैसे|कब\s*मिलेगा|कैसे\s*मिलेगा|क्या\s*मिलेगा)',
    r'(योजना\s*क्या\s*है|कौन\s*सी\s*योजना|पात्रता\s*क्या\s*है|जानकारी\s*दीजिए|फॉर्म\s*कैसे)',
    r'(how\s*much|when\s*will|which\s*scheme|what\s*scheme)',
    r'\?\s*$',
]

CORRECTION_PATTERNS = [
    r'(पहले\s*गलत\s*बताया|सुधार\s*करो|सुधारो|गलत\s*हो\s*गया|बदलना\s*है|change\s*it|correct\s*it)',
    r'^(नहीं|no),\s*(मेरी|मेरा|आय|उम्र|district)',
]


class BooleanAndStatusParser:
    """
    Parses truth values, negations, non-responses, declines, and high-level utterance intents.
    """

    @classmethod
    def detect_intent(cls, text: str) -> IntentType:
        """Classifies high-level user intent from surface text."""
        clean = text.strip().lower()

        # Check for user query first
        for pat in QUERY_PATTERNS:
            if re.search(pat, clean):
                return IntentType.USER_QUERY

        # Check for explicit correction
        for pat in CORRECTION_PATTERNS:
            if re.search(pat, clean):
                return IntentType.CORRECTION

        # Check for decline
        for pat in DECLINE_PATTERNS:
            if re.search(pat, clean):
                return IntentType.DECLINE

        # Check for unknown
        for pat in UNKNOWN_PATTERNS:
            if re.search(pat, clean):
                return IntentType.UNKNOWN_RESPONSE

        return IntentType.PROFILE_INFORMATION

    @classmethod
    def is_unknown(cls, text: str) -> bool:
        """Returns True if the user indicates they do not know the answer."""
        clean = text.strip().lower()
        for pat in UNKNOWN_PATTERNS:
            if re.search(pat, clean):
                return True
        return False

    @classmethod
    def is_decline(cls, text: str) -> bool:
        """Returns True if the user declines to answer."""
        clean = text.strip().lower()
        for pat in DECLINE_PATTERNS:
            if re.search(pat, clean):
                return True
        return False

    @classmethod
    def parse_direct_boolean(cls, text: str) -> Optional[bool]:
        """
        Parses direct single-token or short affirmative/negative answers.
        Returns True, False, or None if ambiguous.
        """
        clean = text.strip().lower().rstrip(".!,।")
        if clean in YES_TOKENS:
            return True
        if clean in NO_TOKENS:
            return False
        return None

    @classmethod
    def is_affirmative(cls, text: str) -> bool:
        """Returns True if text expresses an affirmative / confirmation response."""
        return cls.parse_direct_boolean(text) is True

    @classmethod
    def is_negative(cls, text: str) -> bool:
        """Returns True if text expresses a negative / rejection response."""
        return cls.parse_direct_boolean(text) is False

    @classmethod
    def detect_negation(cls, text: str, concept: Optional[str] = None) -> bool:
        """
        Returns True if the text contains a negative assertion.
        Example: 'मैं बीपीएल में नहीं हूँ' -> True.
        """
        clean = text.strip().lower()
        has_negative_word = bool(re.search(r'(नहीं|नही|कोनी|ना|not|no|neither|never)', clean))
        if not has_negative_word:
            return False

        if concept:
            # Verify the negation is within proximity of the concept
            pat = rf'{re.escape(concept)}.*?(नहीं|कोनी|not)'
            return bool(re.search(pat, clean)) or bool(re.search(rf'(नहीं|कोनी|not).*?{re.escape(concept)}', clean))

        return True
