import re
from typing import List, Set

# Granular category term lists for deterministic classification
SCHEME_TERMS: List[str] = [
    "योजना",
    "scheme",
    "yojana",
    "guideline",
    "guidelines",
    "दिशा-निर्देश",
    "दिशा निर्देश",
    "गाइडलाइन",
    "welfare",
    "sop",
    "instruction",
    "instructions",
    "नियम",
]

ELIGIBILITY_TERMS: List[str] = [
    "पात्रता",
    "eligibility",
    "criteria",
    "आयु",
    "age",
    "आय",
    "income",
    "दस्तावेज",
    "documents",
    "निवास",
    "domicile",
    "certificate",
]

BENEFIT_TERMS: List[str] = [
    "लाभ",
    "लाभार्थी",
    "benefit",
    "benefits",
    "beneficiary",
    "पेंशन",
    "pension",
    "अनुदान",
    "subsidy",
    "छात्रवृत्ति",
    "scholarship",
    "सहायता",
    "assistance",
]

APPLICATION_TERMS: List[str] = [
    "आवेदन",
    "application",
    "apply",
    "e-mitra",
    "emitra",
    "sso",
    "पंजीकरण",
    "registration",
    "portal",
    "form",
]

NOTIFICATION_TERMS: List[str] = [
    "अधिसूचना",
    "notification",
    "notifications",
    "विज्ञप्ति",
]

ORDER_TERMS: List[str] = [
    "आदेश",
    "order",
    "orders",
    "कार्यालय आदेश",
    "परिपत्र",
    "circular",
    "circulars",
]

AMENDMENT_TERMS: List[str] = [
    "संशोधन",
    "amendment",
    "amendments",
    "संशोधित",
    "amended",
    "विस्तार",
    "extension",
    "शुद्धिपत्र",
    "corrigendum",
]

# Exclusion / Negative Terms (Tenders, Jobs, Staffing, Routine Admin)
NEGATIVE_TERMS: List[str] = [
    "निविदा",
    "भर्ती",
    "रिक्ति",
    "परीक्षा",
    "नीलामी",
    "स्थानांतरण",
    "पदस्थापना",
    "कोटेशन",
    "प्रवेश पत्र",
    "उत्तर कुंजी",
    "परिणाम",
    "पाठ्यक्रम",
    "निविदा सूचना",
    "बोली",
    "tender",
    "tenders",
    "e-tender",
    "etender",
    "recruitment",
    "recruitments",
    "vacancy",
    "vacancies",
    "exam",
    "examination",
    "auction",
    "auctions",
    "transfer",
    "transfers",
    "posting",
    "postings",
    "quotation",
    "quotations",
    "eoi",
    "rfp",
    "procurement",
    "admit card",
    "answer key",
    "syllabus",
    "curriculum",
    "deputation",
    "rti",
    "right to information",
    "staff",
]

# Sets for quick lookup & backward compatibility
POSITIVE_HINDI_TERMS: Set[str] = {
    "योजना", "पात्रता", "लाभ", "लाभार्थी", "दस्तावेज", "आवेदन", "दिशा-निर्देश",
    "दिशा निर्देश", "अधिसूचना", "संशोधन", "परिपत्र", "आदेश", "अनुदान",
    "छात्रवृत्ति", "पेंशन", "सहायता", "नियम", "गाइडलाइन", "विस्तार", "पंजीकरण",
    "स्वीकृति", "कार्यालय आदेश", "विज्ञप्ति",
}

POSITIVE_ENGLISH_TERMS: Set[str] = {
    "scheme", "yojana", "guideline", "guidelines", "circular", "circulars",
    "order", "orders", "notification", "notifications", "amendment", "amendments",
    "eligibility", "criteria", "benefit", "benefits", "beneficiary", "subsidy",
    "pension", "scholarship", "assistance", "application", "rule", "rules",
    "directive", "welfare", "sop", "instruction", "instructions",
}

NEGATIVE_HINDI_TERMS: Set[str] = {
    "निविदा", "भर्ती", "रिक्ति", "परीक्षा", "नीलामी", "स्थानांतरण", "पदस्थापना",
    "कोटेशन", "प्रवेश पत्र", "उत्तर कुंजी", "परिणाम", "पाठ्यक्रम", "निविदा सूचना", "बोली",
}

NEGATIVE_ENGLISH_TERMS: Set[str] = {
    "tender", "tenders", "e-tender", "etender", "recruitment", "recruitments",
    "vacancy", "vacancies", "exam", "examination", "auction", "auctions",
    "transfer", "transfers", "posting", "postings", "quotation", "quotations",
    "eoi", "rfp", "procurement", "corrigendum", "admit card", "answer key",
    "syllabus", "curriculum", "deputation", "rti",
}

# Regex patterns for detecting numeric changes in text (Currency, ages, percentages, dates)
NUMERIC_PATTERNS: List[re.Pattern] = [
    re.compile(r"₹\s*[\d,]+"),                                  # Currency ₹ 2,00,000
    re.compile(r"(?:rs\.?|inr)\s*[\d,]+", re.IGNORECASE),       # Rs. 50000
    re.compile(r"\b\d+\s*(?:%|प्रतिशत|percent)\b", re.IGNORECASE), # 50% / प्रतिशत
    re.compile(r"\b\d{1,2}\s*(?:वर्ष|साल|years?|yrs?)\b", re.IGNORECASE), # Age: 60 years / 60 वर्ष
    re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})\b", re.IGNORECASE), # Dates
    re.compile(r"\b\d+\s*(?:लाख|करोड़|lakh|crore)\b", re.IGNORECASE), # 2 लाख / 5 crore
]


def contains_numeric_change_indicators(text: str) -> bool:
    """Check if text contains financial, age, percentage, or date expressions."""
    if not text:
        return False
    for pat in NUMERIC_PATTERNS:
        if pat.search(text):
            return True
    return False
