"""
Deterministic Hindi/Indian number, currency, scale, and range parsing.
Handles Devanagari numerals, cardinal words (1-100), fractions (डेढ़, ढाई, सवा, पौने, साढ़े),
Indian scales (हजार, लाख, करोड़), approximations, and periodicity.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from app.normalization.numbers import devanagari_to_ascii, parse_indian_number

# Hindi cardinal words 1 to 100
HINDI_CARDINALS: Dict[str, int] = {
    "शून्य": 0, "जीरो": 0, "zero": 0,
    "एक": 1, "ek": 1,
    "दो": 2, "do": 2,
    "तीन": 3, "teen": 3,
    "चार": 4, "chaar": 4, "char": 4,
    "पांच": 5, "पाँच": 5, "panch": 5,
    "छह": 6, "छः": 6, "chhah": 6, "che": 6, "chhe": 6,
    "सात": 7, "saat": 7,
    "आठ": 8, "aath": 8,
    "नौ": 9, "nau": 9,
    "दस": 10, "das": 10,
    "ग्यारह": 11, "gyarah": 11,
    "बारह": 12, "barah": 12,
    "तेरह": 13, "terah": 13,
    "चौदह": 14, "chaudah": 14,
    "पंद्रह": 15, "pandrah": 15,
    "सोलह": 16, "solah": 16,
    "सत्रह": 17, "satrah": 17,
    "अठारह": 18, "atharah": 18,
    "उन्नीस": 19, "unnees": 19,
    "बीस": 20, "bees": 20,
    "इक्कीस": 21, "ikkees": 21,
    "बाईस": 22, "baees": 22,
    "तेईस": 23, "tees": 23,
    "चौबीस": 24, "chaubees": 24,
    "पच्चीस": 25, "pachchees": 25, "pachees": 25,
    "छब्बीस": 26, "chhabbees": 26,
    "सत्ताईस": 27, "sattaees": 27,
    "अट्ठाईस": 28, "atthaees": 28,
    "उनतीस": 29, "unatees": 29,
    "तीस": 30, "tees": 30,
    "इकतीस": 31, "ikatees": 31,
    "बत्तीस": 32, "battees": 32,
    "तैंतीस": 33, "taintees": 33,
    "चौंतीस": 34, "chauntees": 34,
    "पैंतीस": 35, "paintees": 35,
    "छत्तीस": 36, "chhattees": 36,
    "सैंतीस": 37, "saintees": 37,
    "अड़तीस": 38, "adatees": 38,
    "उनतालीस": 39, "unatalees": 39,
    "चालीस": 40, "chalees": 40,
    "इकतालीस": 41, "ikatalees": 41,
    "बयालीस": 42, "bayalees": 42,
    "तैंतालीस": 43, "taintalees": 43,
    "चवालीस": 44, "chawalees": 44,
    "पैंतालीस": 45, "paintalees": 45, "paintalis": 45,
    "छियालीस": 46, "chhiyalees": 46,
    "सैंतालीस": 47, "saintalees": 47,
    "अड़तालीस": 48, "adatalees": 48,
    "उनचास": 49, "unachaas": 49,
    "पचास": 50, "pachaas": 50, "pachas": 50,
    "इक्यावन": 51, "ikyawan": 51,
    "बावन": 52, "baawan": 52,
    "तिरपन": 53, "tirpan": 53,
    "चौवन": 54, "chauwan": 54,
    "पचपन": 55, "बचपन": 55, "pachpan": 55,
    "छप्पन": 56, "chhappan": 56,
    "सत्तावन": 57, "sattawan": 57,
    "अट्ठावन": 58, "atthawan": 58,
    "उनसठ": 59, "unasath": 59,
    "साठ": 60, "saath": 60, "sath": 60,
    "इकसठ": 61, "ikasath": 61, "iksath": 61,
    "बासठ": 62, "baasath": 62, "basath": 62,
    "तिरसठ": 63, "tirasath": 63,
    "चौंसठ": 64, "chaunsath": 64,
    "पैंसठ": 65, "painsath": 65,
    "छियासठ": 66, "chhiyaasath": 66,
    "सरसठ": 67, "sarasath": 67,
    "अड़सठ": 68, "adasath": 68,
    "उनहत्तर": 69, "unahattar": 69,
    "सत्तर": 70, "sattar": 70,
    "इकहत्तर": 71, "ikahattar": 71,
    "बहत्तर": 72, "bahattar": 72,
    "तिहत्तर": 73, "tihattar": 73,
    "चौहत्तर": 74, "chauhattar": 74,
    "पचहत्तर": 75, "pachahattar": 75,
    "छिहत्तर": 76, "chhihattar": 76,
    "सतहत्तर": 77, "satahattar": 77,
    "अठहत्तर": 78, "athahattar": 78,
    "उन्यासी": 79, "uniyasi": 79,
    "अस्सी": 80, "assee": 80, "assi": 80,
    "इक्यासी": 81, "ikyasi": 81,
    "बयासी": 82, "bayasi": 82,
    "तिरासी": 83, "tirasi": 83,
    "चौरासी": 84, "chaurasi": 84,
    "पचासी": 85, "pachasi": 85,
    "छियासी": 86, "chhiyasi": 86,
    "सत्तासी": 87, "sattasi": 87,
    "अट्ठासी": 88, "atthasi": 88,
    "नवासी": 89, "नवाँसी": 89, "nawasi": 89,
    "नब्बे": 90, "nabbe": 90,
    "इक्यानवे": 91, "ikyanwe": 91,
    "बानवे": 92, "बायनवे": 92, "baanwe": 92,
    "तिरानवे": 93, "tiranwe": 93,
    "चौरानवे": 94, "chauranwe": 94,
    "पचानवे": 95, "pachanwe": 95,
    "छियानवे": 96, "chhiyanwe": 96,
    "सत्तानवे": 97, "sattanwe": 97,
    "अट्ठानवे": 98, "atthanwe": 98,
    "निन्यानवे": 99, "ninyanwe": 99,
    "सौ": 100, "sau": 100, "so": 100,
}

# Fractional multipliers
FRACTIONAL_SCALES: Dict[str, float] = {
    "डेढ़": 1.5, "dedh": 1.5, "deedh": 1.5,
    "ढाई": 2.5, "dhai": 2.5,
    "सवा": 1.25, "sawa": 1.25,
    "पौने": 0.75, "paune": 0.75,
}

SCALE_MULTIPLIERS_MAP: Dict[str, int] = {
    "लाख": 100_000, "लाख्स": 100_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000,
    "करोड़": 10_000_000, "करोड": 10_000_000, "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000,
    "हजार": 1_000, "हज़ार": 1_000, "thousand": 1_000, "k": 1_000,
}

APPROX_KEYWORDS = [
    "लगभग", "करीब", "क़रीब", "आसपास", "आस-पास", "अंदाजन", "अनुमानित",
    "approx", "approximately", "around", "nearly", "close to"
]


class HindiNumberParser:
    """
    Parses and normalizes Hindi numbers, Indian financial scales, bounds, and periods.
    """

    @classmethod
    def is_approximate(cls, text: str) -> bool:
        """Returns True if input text indicates an approximate value."""
        lower = text.lower()
        for kw in APPROX_KEYWORDS:
            if kw in lower:
                return True
        return False

    @classmethod
    def detect_periodicity(cls, text: str, default: Optional[str] = None) -> Optional[str]:
        """Detects whether an income expression is MONTHLY or ANNUAL."""
        lower = text.lower()
        if re.search(r'(प्रति\s*माह|प्रतिमाह|मासिक|महीना|महीने|monthly|per\s*month|हर\s*महीने)', lower):
            return "MONTHLY"
        if re.search(r'(वार्षिक|प्रति\s*वर्ष|प्रतिवर्ष|सालाना|annual|per\s*year|हर\s*साल|साल\s*भर)', lower):
            return "ANNUAL"
        return default

    @classmethod
    def detect_income_scope(cls, text: str) -> str:
        """
        Determines whether income text refers to family income or individual/annual income.
        Returns 'family_income' or 'annual_income'.
        """
        lower = text.lower()
        if re.search(r'(परिवार|पारिवारिक|घर|कुल|घरां|household|family)', lower):
            return "family_income"
        return "annual_income"

    @classmethod
    def parse_single_number(cls, text: str) -> Optional[int]:
        """
        Parses a single number word or digit string (e.g. 'बासठ' -> 62, '62' -> 62, 'साठ' -> 60).
        """
        clean = devanagari_to_ascii(text.strip().lower())

        # Check direct digit match
        if re.match(r'^\d+$', clean):
            return int(clean)

        # Check direct cardinal dictionary match
        if clean in HINDI_CARDINALS:
            return HINDI_CARDINALS[clean]

        # Check fractional numbers alone (e.g. डेढ़ -> 1.5 rounded or integer)
        if clean in FRACTIONAL_SCALES:
            return int(FRACTIONAL_SCALES[clean])

        return None

    @classmethod
    def parse_compound_indian_number(cls, text: str) -> Optional[int]:
        """
        Parses complex compound expressions such as:
        - 'डेढ़ लाख' -> 150000
        - 'ढाई लाख' -> 250000
        - 'दो लाख पचास हजार' -> 250000
        - 'एक लाख अस्सी हजार' -> 180000
        - '2 लाख' -> 200000
        - '1.5 lakh' -> 150000
        - 'लगभग दो लाख' -> 200000
        """
        if not text:
            return None

        clean = devanagari_to_ascii(text.strip().lower())

        # Remove currency symbols and noise words
        clean = re.sub(r'[₹$rs\.]', '', clean)
        clean = re.sub(r'(लगभग|करीब|क़रीब|आसपास|आस-पास|अंदाजन|approx|around)', '', clean).strip()

        # Step 1: Check fractional scales (डेढ़ लाख, ढाई लाख, सवा लाख, पौने दो लाख)
        # Regex: (डेढ़|ढाई|सवा) (लाख|हजार|करोड़)
        frac_match = re.search(r'(डेढ़|dedh|ढाई|dhai|सवा|sawa)\s*(लाख|lakhs?|lacs?|हजार|thousand|करोड़|crore)', clean)
        if frac_match:
            frac_word = frac_match.group(1)
            unit_word = frac_match.group(2)
            mult = FRACTIONAL_SCALES.get(frac_word, 1.0)
            unit_scale = SCALE_MULTIPLIERS_MAP.get(unit_word, 100_000)
            return int(mult * unit_scale)

        # "पौने दो लाख" -> 175000, "पौने एक लाख" -> 75000
        paune_match = re.search(r'(पौने|paune)\s*([^\s]+)\s*(लाख|lakhs?|lacs?|हजार|thousand)', clean)
        if paune_match:
            num_word = paune_match.group(2)
            unit_word = paune_match.group(3)
            base_num = cls.parse_single_number(num_word)
            if base_num is not None:
                unit_scale = SCALE_MULTIPLIERS_MAP.get(unit_word, 100_000)
                return int((base_num - 0.25) * unit_scale)

        # "साढ़े तीन लाख" -> 350000
        saadhe_match = re.search(r'(साढ़े|sadhe)\s*([^\s]+)\s*(लाख|lakhs?|lacs?|हजार|thousand)', clean)
        if saadhe_match:
            num_word = saadhe_match.group(2)
            unit_word = saadhe_match.group(3)
            base_num = cls.parse_single_number(num_word)
            if base_num is not None:
                unit_scale = SCALE_MULTIPLIERS_MAP.get(unit_word, 100_000)
                return int((base_num + 0.5) * unit_scale)

        # Step 2: Compound expressions like "दो लाख पचास हजार" or "एक लाख अस्सी हजार"
        # We can parse scale segments sequentially
        total = 0
        found_any = False
        remaining = clean

        for scale_word, multiplier in [("करोड़", 10_000_000), ("crore", 10_000_000),
                                       ("लाख", 100_000), ("lakh", 100_000), ("lac", 100_000),
                                       ("हजार", 1_000), ("हज़ार", 1_000), ("thousand", 1_000)]:
            pat = re.compile(r'([^\s,]+)\s*' + scale_word)
            m = pat.search(remaining)
            if m:
                count_token = m.group(1)
                count_val = cls.parse_single_number(count_token)
                if count_val is None:
                    # Try digit parse
                    try:
                        count_val = float(count_token)
                    except ValueError:
                        count_val = None
                if count_val is not None:
                    total += int(count_val * multiplier)
                    found_any = True
                    remaining = remaining.replace(m.group(0), "")

        if found_any:
            # Check if there is an unscaled trailing remainder number (e.g. "एक लाख पचास")
            trailing = cls.parse_single_number(remaining.strip())
            if trailing is not None:
                total += trailing
            return total

        # Step 3: Fall back to Day 10 parse_indian_number
        parsed = parse_indian_number(text)
        if parsed is not None:
            return int(parsed)

        # Step 4: Fall back to single number word (e.g. "बासठ", "पैंतालीस")
        words = clean.split()
        for w in words:
            single = cls.parse_single_number(w)
            if single is not None:
                return single

        return None

    @classmethod
    def parse_range(cls, text: str) -> Optional[Tuple[int, int]]:
        """
        Parses expressions like 'एक से डेढ़ लाख के बीच' or '1 से 2 लाख' -> (100000, 150000).
        """
        clean = devanagari_to_ascii(text.strip().lower())
        m = re.search(r'([^\s]+)\s*(?:से|to|-)\s*([^\s]+(?:\s+[^\s]+)?)\s*(?:के\s*बीच|between)?', clean)
        if m:
            part1 = m.group(1)
            part2 = m.group(2)
            # If scale word (e.g. लाख) is on part2, carry over to part1 if part1 has no scale
            for scale in ["लाख", "lakh", "हजार", "thousand", "करोड़", "crore"]:
                if scale in part2 and scale not in part1:
                    part1 = f"{part1} {scale}"
            v1 = cls.parse_compound_indian_number(part1)
            v2 = cls.parse_compound_indian_number(part2)
            if v1 is not None and v2 is not None and v1 <= v2:
                return (v1, v2)
        return None

    @classmethod
    def parse_bounds(cls, text: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parses expressions like 'दो लाख से कम' (upper bound = 200000)
        or 'तीन लाख से ज्यादा' (lower bound = 300000).
        Returns (min_val, max_val).
        """
        clean = devanagari_to_ascii(text.strip().lower())
        if re.search(r'(से\s*कम|less\s*than|below|under)', clean):
            val = cls.parse_compound_indian_number(clean)
            return (None, val)
        if re.search(r'(से\s*(?:ज्यादा|अधिक)|more\s*than|above|over)', clean):
            val = cls.parse_compound_indian_number(clean)
            return (val, None)
        return (None, None)

    @classmethod
    def is_approximate(cls, text: str) -> bool:
        """
        Detects if numerical statement contains approximation markers
        such as 'के आसपास', 'लगभग', 'थोड़ा ऊपर', 'around', etc.
        """
        clean = text.strip().lower()
        patterns = [
            r'(आसपास|के\s*आसपास|लगभग|करीब|तकरीबन|थोड़ा\s*ऊपर|थोड़ा\s*कम|से\s*ऊपर|से\s*कम)',
            r'(approx|around|nearly|about|rough|above|below)',
        ]
        for pat in patterns:
            if re.search(pat, clean):
                return True
        return False

    @classmethod
    def detect_periodicity(cls, text: str, default: str = "ANNUAL") -> str:
        """
        Detects frequency: 'महीना' / 'प्रति माह' -> 'MONTHLY', 'सालाना' / 'वार्षिक' -> 'ANNUAL'.
        """
        clean = text.strip().lower()
        if re.search(r'(महीना|माह|प्रति\s*माह|monthly|per\s*month)', clean):
            return "MONTHLY"
        if re.search(r'(साल|सालाना|वार्षिक|प्रति\s*वर्ष|annual|yearly|per\s*annum)', clean):
            return "ANNUAL"
        return default

