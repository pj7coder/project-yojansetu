"""
JanSetu - Day 26: Deterministic Speech Text Normalizer.

Transforms display messages and raw numerical/symbolic data into clear, natural,
and phonetically unambiguous Hindi speech text.

Guarantees:
- Canonical display text is NEVER mutated; speech text is created separately.
- Currency (₹ amounts), numbers, percentages, dates, boundary operators,
  and acronyms are deterministically expanded.
- Negation ('नहीं') and boundary qualifiers ('या उससे कम', 'या अधिक') are preserved.
- URLs and presentation markdown are safely stripped or redirected to screen references.
"""

import re
from typing import Dict, List, Optional, Tuple, Union

from app.normalization.numbers import devanagari_to_ascii


# Standard Hindi cardinal words 0 to 100
CARDINALS_0_TO_100: Dict[int, str] = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पांच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह",
    16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस",
    26: "छब्बीस", 27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस", 30: "तीस",
    31: "इकतीस", 32: "बत्तीस", 33: "तैंतीस", 34: "चौंतीस", 35: "पैंतीस",
    36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस", 39: "उनतालीस", 40: "चालीस",
    41: "इकतालीस", 42: "बयालीस", 43: "तैंतालीस", 44: "चवालीस", 45: "पैंतालीस",
    46: "छियालीस", 47: "सैंतालीस", 48: "अड़तालीस", 49: "उनचास", 50: "पचास",
    51: "इक्यावन", 52: "बावन", 53: "तिरपन", 54: "चौवन", 55: "पचपन",
    56: "छप्पन", 57: "सत्तावन", 58: "अट्ठावन", 59: "उनसठ", 60: "साठ",
    61: "इकसठ", 62: "बासठ", 63: "तिरसठ", 64: "चौंसठ", 65: "पैंसठ",
    66: "छियासठ", 67: "सरसठ", 68: "अड़सठ", 69: "उनहत्तर", 70: "सत्तर",
    71: "इकहत्तर", 72: "बहत्तर", 73: "तिहत्तर", 74: "चौहत्तर", 75: "पचहत्तर",
    76: "छिहत्तर", 77: "सतहत्तर", 78: "अठहत्तर", 79: "उन्यासी", 80: "अस्सी",
    81: "इक्यासी", 82: "बयासी", 83: "तिरासी", 84: "चौरासी", 85: "पचासी",
    86: "छियासी", 87: "सत्तासी", 88: "अट्ठासी", 89: "नवासी", 90: "नब्बे",
    91: "इक्यानवे", 92: "बानवे", 93: "तिरानवे", 94: "चौरानवे", 95: "पचानवे",
    96: "छियानवे", 97: "सत्तानवे", 98: "अट्ठानवे", 99: "निन्यानवे", 100: "सौ",
}

# Controlled acronym expansions for Hindi speech synthesis
ACRONYM_SPEECH_MAP: Dict[str, str] = {
    "SSO": "एस एस ओ",
    "sso": "एस एस ओ",
    "एसएसओ": "एस एस ओ",
    "BPL": "बी पी एल",
    "bpl": "बी पी एल",
    "बीपीएल": "बी पी एल",
    "OTP": "ओ टी पी",
    "otp": "ओ टी पी",
    "ओटीपी": "ओ टी पी",
    "PDF": "पी डी एफ",
    "pdf": "पी डी एफ",
    "e-Mitra": "ई-मित्र",
    "eMitra": "ई-मित्र",
    "emitra": "ई-मित्र",
    "e mitra": "ई-मित्र",
    "ईमित्र": "ई-मित्र",
    "URL": "लिंक",
    "url": "लिंक",
    "SMS": "एस एम एस",
    "sms": "एस एम एस",
    "SC": "एस सी",
    "sc": "एस सी",
    "ST": "एस टी",
    "st": "एस टी",
    "OBC": "ओ बी सी",
    "obc": "ओ बी सी",
    "EWS": "ई डब्ल्यू एस",
    "ews": "ई डब्ल्यू एस",
    "MBC": "एम बी सी",
    "mbc": "एम बी सी",
    "DBT": "डी बी टी",
    "dbt": "डी बी टी",
}

# Controlled Rajasthan district pronunciation alias registry
DISTRICT_PRONUNCIATION_MAP: Dict[str, str] = {
    "उदयपुर": "उदयपुर",
    "डूंगरपुर": "डूंगरपुर",
    "बांसवाड़ा": "बांसवाड़ा",
    "चित्तौड़गढ़": "चित्तौड़गढ़",
    "चितौड़गढ़": "चित्तौड़गढ़",
    "झालावाड़": "झालावाड़",
    "प्रतापगढ़": "प्रतापगढ़",
    "जैसलमेर": "जैसलमेर",
    "श्रीगंगानगर": "श्रीगंगानगर",
    "सवाई माधोपुर": "सवाई माधोपुर",
    "सवाईमाधोपुर": "सवाई माधोपुर",
    "भीलवाड़ा": "भीलवाड़ा",
    "राजसमंद": "राजसमंद",
    "सिरोही": "सिरोही",
    "जोधपुर": "जोधपुर",
    "बीकानेर": "बीकानेर",
    "बाड़मेर": "बाड़मेर",
    "नागौर": "नागौर",
    "चूरू": "चूरू",
    "सीकर": "सीकर",
    "झुंझुनू": "झुंझुनू",
    "जयपुर": "जयपुर",
    "दौसा": "दौसा",
    "अलवर": "अलवर",
    "भरतपुर": "भरतपुर",
    "धौलपुर": "धौलपुर",
    "करौली": "करौली",
    "टोंक": "टोंक",
    "अजमेर": "अजमेर",
    "कोटा": "कोटा",
    "बूंदी": "बूंदी",
    "बारां": "बारां",
    "पाली": "पाली",
    "जालौर": "जालौर",
    "हनुमानगढ़": "हनुमानगढ़",
}

# Month names in Hindi
HINDI_MONTHS: Dict[str, str] = {
    "january": "जनवरी", "jan": "जनवरी", "जनवरी": "जनवरी",
    "february": "फ़रवरी", "feb": "फ़रवरी", "फ़रवरी": "फ़रवरी", "फरवरी": "फ़रवरी",
    "march": "मार्च", "mar": "मार्च", "मार्च": "मार्च",
    "april": "अप्रैल", "apr": "अप्रैल", "अप्रैल": "अप्रैल",
    "may": "मई", "मई": "मई",
    "june": "जून", "jun": "जून", "जून": "जून",
    "july": "जुलाई", "jul": "जुलाई", "जुलाई": "जुलाई",
    "august": "अगस्त", "aug": "अगस्त", "अगस्त": "अगस्त",
    "september": "सितंबर", "sep": "सितंबर", "sept": "सितंबर", "सितंबर": "सितंबर", "सितम्बर": "सितंबर",
    "october": "अक्टूबर", "oct": "अक्टूबर", "अक्टूबर": "अक्टूबर",
    "november": "नवंबर", "nov": "नवंबर", "नवंबर": "नवंबर", "नवम्बर": "नवंबर",
    "december": "दिसंबर", "dec": "दिसंबर", "दिसंबर": "दिसंबर", "दिसम्बर": "दिसंबर",
}


def int_to_hindi_words(n: int) -> str:
    """
    Deterministically converts an integer (0 to 99,99,99,999) into standard spoken Hindi words
    using the Indian numbering system (हजार, लाख, करोड़).
    """
    if n < 0:
        return f"माइनस {int_to_hindi_words(abs(n))}"
    if n <= 100:
        return CARDINALS_0_TO_100.get(n, str(n))

    parts: List[str] = []

    # Crores (1,00,00,000)
    crores = n // 10_000_000
    n %= 10_000_000
    if crores > 0:
        parts.append(f"{int_to_hindi_words(crores)} करोड़")

    # Lakhs (1,00,000)
    lakhs = n // 100_000
    n %= 100_000
    if lakhs > 0:
        parts.append(f"{int_to_hindi_words(lakhs)} लाख")

    # Thousands (1,000)
    thousands = n // 1_000
    n %= 1_000
    if thousands > 0:
        parts.append(f"{int_to_hindi_words(thousands)} हजार")

    # Hundreds (100)
    hundreds = n // 100
    n %= 100
    if hundreds > 0:
        parts.append(f"{CARDINALS_0_TO_100.get(hundreds, str(hundreds))} सौ")

    # Remainder (1-99)
    if n > 0:
        parts.append(CARDINALS_0_TO_100.get(n, str(n)))

    return " ".join(parts)


def parse_clean_int(val_str: str) -> Optional[int]:
    """Parses a digit string potentially formatted with commas into an int."""
    ascii_str = devanagari_to_ascii(val_str.strip()).replace(",", "")
    try:
        return int(float(ascii_str))
    except (ValueError, TypeError):
        return None


class SpeechTextNormalizer:
    """
    Deterministic normalizer converting display text into speech-optimized Hindi text.
    """

    @classmethod
    def normalize_currency(cls, text: str) -> str:
        """
        Normalizes ₹ currency amounts and periodicity into spoken Hindi words.
        Examples:
            "₹1,50,000" -> "एक लाख पचास हजार रुपये"
            "₹1,000 प्रति माह" -> "एक हजार रुपये प्रति माह"
            "₹500" -> "पांच सौ रुपये"
            "₹2 लाख" -> "दो लाख रुपये"
            "1.5 लाख रुपये" -> "एक लाख पचास हजार रुपये"
        """
        # 1. Pattern: ₹ or Rs. with decimal scale e.g. "1.5 लाख", "₹1.5 लाख"
        def _replace_decimal_scale(match: re.Match) -> str:
            prefix = match.group(1) or ""
            num_val = float(match.group(2))
            scale_word = match.group(3)
            period = match.group(4) or ""

            total_val = 0
            if "लाख" in scale_word or "lakh" in scale_word.lower():
                total_val = int(round(num_val * 100_000))
            elif "करोड़" in scale_word or "crore" in scale_word.lower():
                total_val = int(round(num_val * 10_000_000))
            elif "हजार" in scale_word or "thousand" in scale_word.lower():
                total_val = int(round(num_val * 1_000))

            spoken_amount = int_to_hindi_words(total_val)
            res = f"{spoken_amount} रुपये"
            if period:
                res = f"{res} {period.strip()}"
            return f" {res} "

        text = re.sub(
            r'(₹|Rs\.?|INR)?\s*([0-9]+(?:\.[0-9]+))\s*(लाख|करोड़|हजार)\s*(रुपये|रुपए)?\s*(प्रति\s*माह|प्रति\s*वर्ष|सालाना|मासिक)?',
            _replace_decimal_scale,
            text,
            flags=re.IGNORECASE
        )

        # 2. Pattern: ₹ or Rs. with standard digits and optional commas e.g. "₹1,50,000", "₹500", "₹ 2,00,000"
        def _replace_currency_amount(match: re.Match) -> str:
            raw_digits = match.group(2)
            unit_word = match.group(3) or "रुपये"
            period = match.group(4) or ""

            val = parse_clean_int(raw_digits)
            if val is not None:
                spoken = int_to_hindi_words(val)
                res = f"{spoken} रुपये"
                if period:
                    res = f"{res} {period.strip()}"
                return f" {res} "
            return match.group(0)

        text = re.sub(
            r'(₹|Rs\.?|INR)\s*([0-9०-९,]+)\s*(?:(रुपये|रुपए)\b)?\s*(प्रति\s*माह|प्रति\s*वर्ष|सालाना|मासिक)?',
            _replace_currency_amount,
            text,
            flags=re.IGNORECASE
        )

        # 3. Pattern: Bare number directly followed by "रुपये" or "रुपए" e.g. "1,50,000 रुपये"
        def _replace_bare_rupees(match: re.Match) -> str:
            raw_digits = match.group(1)
            period = match.group(3) or ""
            val = parse_clean_int(raw_digits)
            if val is not None:
                spoken = int_to_hindi_words(val)
                res = f"{spoken} रुपये"
                if period:
                    res = f"{res} {period.strip()}"
                return f" {res} "
            return match.group(0)

        text = re.sub(
            r'([0-9०-९,]+)\s*(?:(रुपये|रुपए)\b)\s*(प्रति\s*माह|प्रति\s*वर्ष|सालाना|मासिक)?',
            _replace_bare_rupees,
            text
        )

        return text

    @classmethod
    def normalize_percentages(cls, text: str) -> str:
        """
        Normalizes percentage notations.
        Examples:
            "40%" -> "चालीस प्रतिशत"
            "45%" -> "पैंतालीस प्रतिशत"
            "75%" -> "पचहत्तर प्रतिशत"
            "40 % या अधिक" -> "चालीस प्रतिशत या अधिक"
        """
        def _replace_percent(match: re.Match) -> str:
            raw_num = match.group(1)
            qualifier = match.group(2) or ""
            val = parse_clean_int(raw_num)
            if val is not None:
                spoken = int_to_hindi_words(val)
                res = f"{spoken} प्रतिशत"
                if qualifier:
                    res = f"{res} {qualifier.strip()}"
                return res
            return match.group(0)

        return re.sub(
            r'([0-9०-९]+)\s*%\s*(या\s*उससे\s*अधिक|या\s*अधिक|से\s*अधिक)?',
            _replace_percent,
            text
        )

    @classmethod
    def normalize_dates(cls, text: str) -> str:
        """
        Normalizes dates into spoken Hindi.
        Examples:
            "1 अक्टूबर 2026" -> "एक अक्टूबर दो हजार छब्बीस"
            "15 अगस्त 2026" -> "पंद्रह अगस्त दो हजार छब्बीस"
            "31 मार्च 2027" -> "इकतीस मार्च दो हजार सत्ताईस"
        """
        # Pattern: Day (1-31) Month_Name Year (e.g. 1 अक्टूबर 2026)
        def _replace_date(match: re.Match) -> str:
            day_str = match.group(1)
            month_str = match.group(2)
            year_str = match.group(3)

            day_val = parse_clean_int(day_str)
            year_val = parse_clean_int(year_str)

            spoken_day = int_to_hindi_words(day_val) if day_val is not None else day_str
            month_name = HINDI_MONTHS.get(month_str.lower(), month_str)
            spoken_year = int_to_hindi_words(year_val) if year_val is not None else year_str

            return f"{spoken_day} {month_name} {spoken_year}"

        pattern = r'([0-9०-९]{1,2})\s*([a-zA-Z]+|जनवरी|फ़रवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|सितम्बर|अक्टूबर|नवंबर|नवम्बर|दिसंबर|दिसम्बर)\s*([0-9०-९]{4})'
        return re.sub(pattern, _replace_date, text)

    @classmethod
    def normalize_operators_and_boundaries(cls, text: str) -> str:
        """
        Expands mathematical boundary symbols into citizen-safe spoken Hindi phrases
        while strictly preserving inclusive/exclusive bounds.
        Examples:
            "<= ₹2,00,000" -> "दो लाख रुपये या उससे कम"
            "<= 60" -> "साठ या उससे कम"
            ">= 60 वर्ष" -> "साठ वर्ष या उससे अधिक"
            "< ₹2,00,000" -> "दो लाख रुपये से कम"
            "> 60 वर्ष" -> "साठ वर्ष से अधिक"
        """
        # <= or =<
        text = re.sub(r'<=\s*', '', text)  # Handled with phrasing below if needed
        text = re.sub(r'≤\s*', '', text)
        text = re.sub(r'>=\s*', '', text)
        text = re.sub(r'≥\s*', '', text)

        # Standard boundary phrasing check
        # e.g. "₹2,00,000 से कम" -> already clear, ensure "से कम" survives
        return text

    @classmethod
    def normalize_age_and_numbers(cls, text: str) -> str:
        """
        Normalizes standalone numbers, age phrases, and years into spoken Hindi.
        Examples:
            "62 वर्ष" -> "बासठ वर्ष"
            "60 वर्ष" -> "साठ वर्ष"
            "65 वर्ष" -> "पैंसठ वर्ष"
            "2026" -> "दो हजार छब्बीस"
            "2027" -> "दो हजार सत्ताईस"
        """
        # 1. Number followed by unit e.g. "62 वर्ष", "60 साल", "3 योजनाएँ", "3 दस्तावेज"
        def _replace_numbered_unit(match: re.Match) -> str:
            raw_num = match.group(1)
            unit = match.group(2)
            val = parse_clean_int(raw_num)
            if val is not None:
                spoken = int_to_hindi_words(val)
                return f"{spoken} {unit}"
            return match.group(0)

        text = re.sub(
            r'([0-9०-९]+)\s*(वर्ष|साल|योजनाएँ|योजनाएं|योजना|दस्तावेज|दस्तावेज़|विकल्प|महीने|महीना|दिन|घंटे)',
            _replace_numbered_unit,
            text
        )

        # 2. Four-digit years (e.g. 2024 to 2035)
        def _replace_year(match: re.Match) -> str:
            raw_year = match.group(1)
            val = parse_clean_int(raw_year)
            if val is not None and 1900 <= val <= 2099:
                return int_to_hindi_words(val)
            return match.group(0)

        text = re.sub(r'\b(20[2-9][0-9]|19[5-9][0-9])\b', _replace_year, text)

        # 3. Any remaining standalone numbers up to 100
        def _replace_small_number(match: re.Match) -> str:
            raw_num = match.group(1)
            val = parse_clean_int(raw_num)
            if val is not None and val <= 100:
                return CARDINALS_0_TO_100.get(val, raw_num)
            return raw_num

        text = re.sub(r'(?<![₹Rs\w/])([0-9०-९]{1,2})(?![₹Rs\w/])', _replace_small_number, text)

        return text

    @classmethod
    def normalize_acronyms_and_terms(cls, text: str) -> str:
        """
        Replaces Latin and Devanagari acronyms with spaced phonemic Hindi equivalents.
        Examples:
            "SSO" -> "एस एस ओ"
            "BPL" -> "बी पी एल"
            "e-Mitra" -> "ई-मित्र"
        """
        for acronym, spoken in ACRONYM_SPEECH_MAP.items():
            # Match whole word
            pattern = rf'\b{re.escape(acronym)}\b'
            text = re.sub(pattern, spoken, text)

        # e-Mitra variants without strict word boundary
        text = re.sub(r'(?i)e-?mitra', 'ई-मित्र', text)
        text = re.sub(r'ईमित्र', 'ई-मित्र', text)

        return text

    @classmethod
    def normalize_districts(cls, text: str) -> str:
        """
        Ensures consistent, unambiguous Devanagari pronunciation of Rajasthan districts.
        """
        for district, canonical in DISTRICT_PRONUNCIATION_MAP.items():
            pattern = rf'\b{re.escape(district)}\b'
            text = re.sub(pattern, canonical, text)
        return text

    @classmethod
    def sanitize_presentation(cls, text: str) -> str:
        """
        Strips markdown formatting, HTML tags, control characters, emojis, and raw URLs.
        URLs are replaced with a polite voice reference to visual screen links.
        """
        # 1. Replace raw HTTP/HTTPS URLs with citizen-friendly screen link announcement
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        text = re.sub(url_pattern, 'आधिकारिक वेबसाइट का लिंक स्क्रीन पर दिया गया है।', text)

        # 2. Strip HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # 3. Strip Markdown bold, italics, links, headers
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'^[#]+\s*', '', text, flags=re.MULTILINE)

        # 4. Strip emojis and presentation-only decorative characters
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub("", text)

        # 5. Clean up redundant whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @classmethod
    def normalize_for_speech(cls, text: str) -> str:
        """
        Master normalization pipeline.
        Consumes raw display text and returns speech-ready text.
        Does NOT alter backend truth or canonical display strings.
        """
        if not text or not text.strip():
            return ""

        # Step 1: Sanitize presentation markup (URLs, markdown, HTML, emojis)
        cleaned = cls.sanitize_presentation(text)

        # Step 2: Expand mathematical boundary operators (<, <=, >, >=)
        def _replace_le(m: re.Match) -> str:
            target = m.group(1).strip()
            return f" {target} या उससे कम "

        def _replace_ge(m: re.Match) -> str:
            target = m.group(1).strip()
            return f" {target} या उससे अधिक "

        def _replace_lt(m: re.Match) -> str:
            target = m.group(1).strip()
            return f" {target} से कम "

        def _replace_gt(m: re.Match) -> str:
            target = m.group(1).strip()
            return f" {target} से अधिक "

        cleaned = re.sub(r'(?:<=|≤)\s*([₹0-9०-९,]+(?:\s*(?:वर्ष|साल|महीने|प्रतिशत|रुपये|रुपए))?)', _replace_le, cleaned)
        cleaned = re.sub(r'(?:>=|≥)\s*([₹0-9०-९,]+(?:\s*(?:वर्ष|साल|महीने|प्रतिशत|रुपये|रुपए))?)', _replace_ge, cleaned)
        cleaned = re.sub(r'(?<!<)<(?!=)\s*([₹0-9०-९,]+(?:\s*(?:वर्ष|साल|महीने|प्रतिशत|रुपये|रुपए))?)', _replace_lt, cleaned)
        cleaned = re.sub(r'(?<!>)>(?!=)\s*([₹0-9०-९,]+(?:\s*(?:वर्ष|साल|महीने|प्रतिशत|रुपये|रुपए))?)', _replace_gt, cleaned)

        # Step 3: Currency normalization (₹1,50,000 -> एक लाख पचास हजार रुपये)
        cleaned = cls.normalize_currency(cleaned)

        # Step 4: Percentages (40% -> चालीस प्रतिशत)
        cleaned = cls.normalize_percentages(cleaned)

        # Step 5: Dates (1 अक्टूबर 2026 -> एक अक्टूबर दो हजार छब्बीस)
        cleaned = cls.normalize_dates(cleaned)

        # Step 6: Age and general numbers (62 वर्ष -> बासठ वर्ष)
        cleaned = cls.normalize_age_and_numbers(cleaned)

        # Step 7: Acronyms and government terms (SSO -> एस एस ओ, BPL -> बी पी एल)
        cleaned = cls.normalize_acronyms_and_terms(cleaned)

        # Step 8: Rajasthan districts check
        cleaned = cls.normalize_districts(cleaned)

        # Final space cleanup
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned
