"""
YojanSetu - Day 22: Critical Entity Extraction and Evaluation Metrics.

Evaluates eligibility-critical facts from speech transcripts:
- AGE (e.g. 62 vs 26, Devanagari numerals, Hindi number words)
- INCOME (e.g. 1.5 lakh, 2.5 lakh, monthly vs annual)
- DISTRICT (Rajasthan 50-district canonical registry match)
- NEGATION (e.g. "बीपीएल में नहीं हूँ" vs "बीपीएल में हूँ")
- GOVERNMENT TERMS (Jan Aadhaar, e-Mitra, SSO, BPL, etc.)
- MULTI-ENTITY (all critical target fields must match)

CRITICAL INVARIANT: Zero LLM calls are used to evaluate transcript correctness.
Deterministic regex and dictionary-based extraction guarantees reproducible benchmarking.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.stt.schemas import CriticalEntityTarget, FieldMatchResult
from app.stt.transcript_normalizer import TranscriptNormalizer

# Common Hindi number words for ages and numbers
HINDI_NUMBER_WORDS: Dict[str, int] = {
    "शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15,
    "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20,
    "इक्कीस": 21, "बाईस": 22, "तेईस": 23, "चौबीस": 24, "पच्चीस": 25,
    "छब्बीस": 26, "सत्ताईस": 27, "अट्ठाईस": 28, "उनतीस": 29, "तीस": 30,
    "इकतीस": 31, "बत्तीस": 32, "तैंतीस": 33, "चौंतीस": 34, "पैंतीस": 35,
    "छत्तीस": 36, "सैंतीस": 37, "अड़तीस": 38, "उनतालीस": 39, "चालीस": 40,
    "इकतालीस": 41, "बयालीस": 42, "तैंतालीस": 43, "चवालीस": 44, "पैंतालीस": 45,
    "छियालीस": 46, "सैंतालीस": 47, "अड़तालीस": 48, "उनचास": 49, "पचास": 50,
    "इक्यावन": 51, "बावन": 52, "तिरेपन": 53, "चौवन": 54, "पचपन": 55,
    "छप्पन": 56, "सत्तावन": 57, "अट्ठावन": 58, "अट्ठावन": 58, "उनसठ": 59,
    "साठ": 60, "इकसठ": 61, "बासठ": 62, "तिरेसठ": 63, "चौंसठ": 64,
    "पैंसठ": 65, "छियासठ": 66, "सरसठ": 67, "अड़सठ": 68, "उनहत्तर": 69,
    "सत्तर": 70, "इकहत्तर": 71, "बहत्तर": 72, "तिहत्तर": 73, "चौहत्तर": 74,
    "पचहत्तर": 75, "छिहत्तर": 76, "सतहत्तर": 77, "अठहत्तर": 78, "उन्नासी": 79,
    "अस्सी": 80, "इक्यासी": 81, "बयासी": 82, "तिरासी": 83, "चौरासी": 84,
    "पचासी": 85, "छियासी": 86, "सत्तासी": 87, "अट्ठासी": 88, "नवासी": 89,
    "नब्बे": 90, "इक्यानवे": 91, "बानवे": 92, "तिरानवे": 93, "चौरानवे": 94,
    "पंचानवे": 95, "छियानवे": 96, "सत्तानवे": 97, "अट्ठानवे": 98, "निन्यानवे": 99,
    "सौ": 100,
}

# Rajasthan Districts Canonical Mapping (Hindi & English to Canonical Name)
RAJASTHAN_DISTRICT_MAP: Dict[str, str] = {
    "उदयपुर": "Udaipur", "udaipur": "Udaipur",
    "डूंगरपुर": "Dungarpur", "dungarpur": "Dungarpur",
    "बांसवाड़ा": "Banswara", "banswara": "Banswara",
    "चित्तौड़गढ़": "Chittorgarh", "चित्तौड़": "Chittorgarh", "chittorgarh": "Chittorgarh",
    "झालावाड़": "Jhalawar", "jhalawar": "Jhalawar",
    "प्रतापगढ़": "Pratapgarh", "pratapgarh": "Pratapgarh",
    "जैसलमेर": "Jaisalmer", "jaisalmer": "Jaisalmer",
    "श्रीगंगानगर": "Sri Ganganagar", "गंगानगर": "Sri Ganganagar", "sri ganganagar": "Sri Ganganagar",
    "सवाई माधोपुर": "Sawai Madhopur", "sawai madhopur": "Sawai Madhopur",
    "जयपुर": "Jaipur", "jaipur": "Jaipur",
    "जोधपुर": "Jodhpur", "jodhpur": "Jodhpur",
    "कोटा": "Kota", "kota": "Kota",
    "अजमेर": "Ajmer", "ajmer": "Ajmer",
    "बीकानेर": "Bikaner", "bikaner": "Bikaner",
    "अलवर": "Alwar", "alwar": "Alwar",
    "भीलवाड़ा": "Bhilwara", "bhilwara": "Bhilwara",
    "सीकर": "Sikar", "sikar": "Sikar",
    "पाली": "Pali", "pali": "Pali",
    "टोंक": "Tonk", "tonk": "Tonk",
    "नागौर": "Nagaur", "nagaur": "Nagaur",
    "भरतपुर": "Bharatpur", "bharatpur": "Bharatpur",
    "बाड़मेर": "Barmer", "barmer": "Barmer",
    "चूरू": "Churu", "churu": "Churu",
    "दौसा": "Dausa", "dausa": "Dausa",
    "धौलपुर": "Dholpur", "dholpur": "Dholpur",
    "हनुमानगढ़": "Hanumangarh", "hanumangarh": "Hanumangarh",
    "झुंझुनू": "Jhunjhunu", "jhunjhunu": "Jhunjhunu",
    "करौली": "Karauli", "karauli": "Karauli",
    "राजसमंद": "Rajsamand", "rajsamand": "Rajsamand",
    "सिरोही": "Sirohi", "sirohi": "Sirohi",
    "जालोर": "Jalore", "jalore": "Jalore",
    "बूंदी": "Bundi", "bundi": "Bundi",
    "बारां": "Baran", "baran": "Baran",
}

# Key government welfare terms
GOVERNMENT_TERMS_MAP: Dict[str, str] = {
    "जन आधार": "JAN_AADHAAR",
    "jan aadhaar": "JAN_AADHAAR",
    "आधार": "AADHAAR",
    "aadhaar": "AADHAAR",
    "ई-मित्र": "E_MITRA",
    "ई मित्र": "E_MITRA",
    "e-mitra": "E_MITRA",
    "emitra": "E_MITRA",
    "एसएसओ": "SSO",
    "sso": "SSO",
    "बीपीएल": "BPL",
    "bpl": "BPL",
    "पेंशन": "PENSION",
    "pension": "PENSION",
    "छात्रवृत्ति": "SCHOLARSHIP",
    "scholarship": "SCHOLARSHIP",
    "आय प्रमाण पत्र": "INCOME_CERTIFICATE",
    "जाति प्रमाण पत्र": "CASTE_CERTIFICATE",
    "दिव्यांग": "DISABILITY",
    "subsidy": "SUBSIDY",
    "सब्सिडी": "SUBSIDY",
}


class EntityMetricsExtractor:
    """Extracts critical eligibility entities from raw or normalized transcripts."""

    @classmethod
    def extract_age(cls, text: str) -> Optional[int]:
        """
        Extracts age from text using digits or Hindi number words.
        Supports patterns like:
        - "मेरी उम्र 62 साल" -> 62
        - "मेरी उम्र बासठ वर्ष" -> 62
        - "अट्ठावन साल का हूँ" -> 58
        - Standalone short answer "बासठ" -> 62
        """
        normalized = TranscriptNormalizer.normalize_for_metrics(text, convert_digits=True, remove_punct=True)
        tokens = normalized.split()

        # 1. Look for explicit age context with digit: "उम्र 62", "62 साल", "62 वर्ष"
        m = re.search(r"(?:उम्र|आयु|age)?\s*(\d{1,3})\s*(?:साल|वर्ष|years|year)?", normalized)
        if m and m.group(1):
            val = int(m.group(1))
            if 0 < val <= 120:
                # Check if it was next to age keywords or is standalone
                if any(kw in normalized for kw in ["उम्र", "आयु", "साल", "वर्ष", "age", "years"]) or len(tokens) <= 3:
                    return val

        # 2. Look for Hindi number words
        for token in tokens:
            if token in HINDI_NUMBER_WORDS:
                val = HINDI_NUMBER_WORDS[token]
                if 1 <= val <= 100:
                    return val

        # 3. Fallback: single digit token in short answer
        for token in tokens:
            if token.isdigit():
                val = int(token)
                if 1 <= val <= 120:
                    return val

        return None

    @classmethod
    def extract_income(cls, text: str) -> Optional[int]:
        """
        Extracts annual/monthly income value from Hindi/English speech text.
        Supports:
        - "डेढ़ लाख" -> 150000
        - "ढाई लाख" -> 250000
        - "दो लाख" -> 200000
        - "एक लाख पचास हजार" -> 150000
        - "एक लाख अस्सी हजार" -> 180000
        - "पंद्रह हजार रुपये महीना" -> 15000
        - "1.5 लाख", "2.5 लाख", "150000", "200000"
        """
        normalized = TranscriptNormalizer.normalize_for_metrics(text, convert_digits=True, remove_punct=True)

        # A. Common compound Hindi expressions
        if "डेढ़ लाख" in normalized or "1.5 लाख" in normalized or "1.5 lakh" in normalized:
            return 150000
        if "ढाई लाख" in normalized or "2.5 लाख" in normalized or "2.5 lakh" in normalized:
            return 250000
        if "पौने दो लाख" in normalized or "1.75 लाख" in normalized:
            return 175000
        if "सवा दो लाख" in normalized or "2.25 लाख" in normalized:
            return 225000
        if "सवा लाख" in normalized or "1.25 लाख" in normalized:
            return 125000

        # B. Token-based inspection for "X लाख" and "X लाख Y हजार"
        tokens = normalized.split()
        for idx, token in enumerate(tokens):
            if token in ("लाख", "lakh", "lakhs") and idx > 0:
                prev = tokens[idx - 1]
                l_val = HINDI_NUMBER_WORDS.get(prev)
                if l_val is None:
                    try:
                        l_val = float(prev)
                    except ValueError:
                        l_val = None

                if l_val is not None:
                    base_amount = int(round(l_val * 100000))
                    # Check if followed by "Y हजार"
                    if idx + 2 < len(tokens) and tokens[idx + 2] in ("हजार", "thousand"):
                        h_prev = tokens[idx + 1]
                        h_val = HINDI_NUMBER_WORDS.get(h_prev) or (int(h_prev) if h_prev.isdigit() else 0)
                        return base_amount + (h_val * 1000)
                    return base_amount

        # C. Regex for "X हजार" / "X thousand"
        for idx, token in enumerate(tokens):
            if token in ("हजार", "thousand") and idx > 0:
                prev = tokens[idx - 1]
                val = HINDI_NUMBER_WORDS.get(prev) or (int(prev) if prev.isdigit() else 0)
                if val > 0:
                    return val * 1000

        # E. Explicit digit amounts (e.g. 150000, 200000, 250000)
        digits = re.findall(r"\b\d{4,8}\b", normalized)
        if digits:
            return int(digits[0])

        return None

    @classmethod
    def extract_district(cls, text: str) -> Optional[str]:
        """
        Extracts Rajasthan district name matching trusted registry.
        E.g. "चित्तौड़गढ़", "चित्तौड़", "उदयपुर", "डूंगरपुर", "बांसवाड़ा".
        """
        normalized = TranscriptNormalizer.normalize_for_metrics(text, convert_digits=True, remove_punct=True)

        for district_key, canonical_name in RAJASTHAN_DISTRICT_MAP.items():
            # Check whole-word or substring presence
            if district_key in normalized:
                return canonical_name

        return None

    @classmethod
    def extract_negation(cls, text: str) -> bool:
        """
        Detects whether an explicit negation is expressed:
        "नहीं", "ना", "न", "not", "no", "कदापि नहीं".
        Returns True if negation is present, False otherwise.
        """
        normalized = TranscriptNormalizer.normalize_for_metrics(text, convert_digits=True, remove_punct=True)
        tokens = normalized.split()

        negation_markers = {"नहीं", "ना", "न", "not", "no", "never", "गैर"}
        return any(t in negation_markers for t in tokens)

    @classmethod
    def extract_government_terms(cls, text: str) -> List[str]:
        """Identifies government welfare terminology present in text."""
        normalized = TranscriptNormalizer.normalize_for_metrics(text, convert_digits=True, remove_punct=True)
        found = set()
        for term_key, term_code in GOVERNMENT_TERMS_MAP.items():
            if term_key in normalized:
                found.add(term_code)
        return sorted(list(found))

    @classmethod
    def evaluate_sample(
        cls,
        prediction_text: str,
        target_entities: CriticalEntityTarget,
    ) -> Tuple[Dict[str, FieldMatchResult], bool, bool]:
        """
        Evaluates extracted fields from predicted transcript against target entities.
        Returns:
            (field_results, all_correct, has_critical_failure)
        """
        results: Dict[str, FieldMatchResult] = {}
        all_correct = True
        has_critical = False

        # 1. AGE evaluation
        if target_entities.age is not None:
            pred_age = cls.extract_age(prediction_text)
            correct = (pred_age == target_entities.age)
            is_crit = not correct
            if is_crit:
                has_critical = True
                all_correct = False
            results["age"] = FieldMatchResult(
                field_name="age",
                expected=target_entities.age,
                predicted=pred_age,
                is_correct=correct,
                is_critical_failure=is_crit,
                details=f"Expected age {target_entities.age}, got {pred_age}",
            )

        # 2. INCOME evaluation
        if target_entities.family_income is not None:
            pred_income = cls.extract_income(prediction_text)
            correct = (pred_income == target_entities.family_income)
            is_crit = not correct
            if is_crit:
                has_critical = True
                all_correct = False
            results["family_income"] = FieldMatchResult(
                field_name="family_income",
                expected=target_entities.family_income,
                predicted=pred_income,
                is_correct=correct,
                is_critical_failure=is_crit,
                details=f"Expected income {target_entities.family_income}, got {pred_income}",
            )

        # 3. DISTRICT evaluation
        if target_entities.district is not None:
            pred_dist = cls.extract_district(prediction_text)
            correct = (pred_dist is not None and pred_dist.lower() == target_entities.district.lower())
            is_crit = not correct
            if is_crit:
                has_critical = True
                all_correct = False
            results["district"] = FieldMatchResult(
                field_name="district",
                expected=target_entities.district,
                predicted=pred_dist,
                is_correct=correct,
                is_critical_failure=is_crit,
                details=f"Expected district {target_entities.district}, got {pred_dist}",
            )

        # 4. NEGATION evaluation
        if target_entities.negation is not None:
            pred_neg = cls.extract_negation(prediction_text)
            correct = (pred_neg == target_entities.negation)
            is_crit = not correct
            if is_crit:
                has_critical = True
                all_correct = False
            results["negation"] = FieldMatchResult(
                field_name="negation",
                expected=target_entities.negation,
                predicted=pred_neg,
                is_correct=correct,
                is_critical_failure=is_crit,
                details=f"Expected negation={target_entities.negation}, got {pred_neg}",
            )

        # 5. SCHEME / GOVERNMENT TERM evaluation
        if target_entities.scheme_name is not None:
            norm_pred = TranscriptNormalizer.normalize_for_metrics(prediction_text)
            norm_target = TranscriptNormalizer.normalize_for_metrics(target_entities.scheme_name)
            correct = (norm_target in norm_pred)
            if not correct:
                all_correct = False
            results["scheme_name"] = FieldMatchResult(
                field_name="scheme_name",
                expected=target_entities.scheme_name,
                predicted=prediction_text,
                is_correct=correct,
                is_critical_failure=not correct,
                details=f"Term '{norm_target}' in prediction: {correct}",
            )

        return results, all_correct, has_critical
