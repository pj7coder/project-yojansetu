from enum import Enum
import re
from typing import Dict, List, Pattern


class SectionType(str, Enum):
    OVERVIEW = "OVERVIEW"
    DEFINITIONS = "DEFINITIONS"
    ELIGIBILITY = "ELIGIBILITY"
    EXCLUSIONS = "EXCLUSIONS"
    BENEFITS = "BENEFITS"
    DOCUMENTS_REQUIRED = "DOCUMENTS_REQUIRED"
    APPLICATION_PROCESS = "APPLICATION_PROCESS"
    DATES = "DATES"
    FINANCIAL_RULES = "FINANCIAL_RULES"
    CONTACTS = "CONTACTS"
    ANNEXURE = "ANNEXURE"
    AMENDMENT = "AMENDMENT"
    GENERAL = "GENERAL"
    UNKNOWN = "UNKNOWN"


# Bilingual heading patterns mapped to SectionType
# Checked against heading blocks, title blocks, and paragraph lead-in keywords
SECTION_HEADING_PATTERNS: Dict[SectionType, List[Pattern]] = {
    SectionType.ELIGIBILITY: [
        re.compile(r"(?:^|[\s\b])(?:eligibility|eligible|criteria|qualifying\s+conditions?|who\s+can\s+apply)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:पात्रता|योग्यता|पात्रता\s+की\s+शर्तें|कौन\s+पात्र\s+है|पात्रता\s+मापदंड|नियम\s+एवं\s+शर्तें|योजना\s+की\s+शर्तें)"),
    ],
    SectionType.EXCLUSIONS: [
        re.compile(r"(?:^|[\s\b])(?:exclusion|exclusions|ineligible|disqualification|who\s+cannot\s+apply)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:अपात्रता|बहिष्करण|अपात्र|किसे\s+लाभ\s+नहीं\s+मिलेगा|अयोग्यता)"),
    ],
    SectionType.BENEFITS: [
        re.compile(r"(?:^|[\s\b])(?:benefits?|assistance|grant|incentive|scholarship|financial\s+assistance|perks?)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:लाभ|देय\s+लाभ|सहायता\s+राशि|परिलाभ|प्रोत्साहन|अनुदान\s+राशि|छात्रवृत्ति|वित्तीय\s+सहायता)"),
    ],
    SectionType.DOCUMENTS_REQUIRED: [
        re.compile(r"(?:^|[\s\b])(?:required\s+documents?|documents?\s+required|documents?|checklist|attachments?)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:आवश्यक\s+दस्तावेज|दस्तावेज|जरूरी\s+दस्तावेज|संलग्नक|प्रमाण\s+पत्र|दस्तावेजों\s+की\s+सूची)"),
    ],
    SectionType.APPLICATION_PROCESS: [
        re.compile(r"(?:^|[\s\b])(?:application\s+process|how\s+to\s+apply|procedure|application\s+procedure|registration|e-?mitra)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:आवेदन\s+प्रक्रिया|आवेदन\s+कैसे\s+करें|आवेदन\s+का\s+तरीका|पंजीकरण\s+प्रक्रिया|प्रक्रिया)"),
    ],
    SectionType.DEFINITIONS: [
        re.compile(r"(?:^|[\s\b])(?:definitions?|interpretation|meaning\s+of\s+terms)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:परिभाषा|परिभाषाएँ|अर्थ\s+एवं\s+तात्पर्य|परिभाषाएं)"),
    ],
    SectionType.DATES: [
        re.compile(r"(?:^|[\s\b])(?:timeline|schedule|dates?|deadline|last\s+date|validity)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:समय\s+सीमा|महत्वपूर्ण\s+तिथियां|अंतिम\s+तिथि|समयावधि|तिथियाँ)"),
    ],
    SectionType.FINANCIAL_RULES: [
        re.compile(r"(?:^|[\s\b])(?:financial\s+rules?|income\s+limit|funding|budget|ceiling|income\s+criteria)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:वित्तीय\s+प्रावधान|आय\s+सीमा|बजट|वित्तीय\s+नियम|वार्षिक\s+आय)"),
    ],
    SectionType.CONTACTS: [
        re.compile(r"(?:^|[\s\b])(?:contacts?|helpline|nodal\s+officer|helpdesk|support)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:संपर्क|हेल्पलाइन|नोडल\s+अधिकारी|सहायता\s+कक्ष|पता)"),
    ],
    SectionType.ANNEXURE: [
        re.compile(r"(?:^|[\s\b])(?:annexure|appendix|schedule|form|format)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:परिशिष्ट|प्रपत्र|अनुलग्नक|प्रारूप)"),
    ],
    SectionType.AMENDMENT: [
        re.compile(r"(?:^|[\s\b])(?:amendment|corrigendum|addendum|revision|errata)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:संशोधन|शुद्धिपत्र|उपांतरण|संशोधित\s+आदेश)"),
    ],
    SectionType.OVERVIEW: [
        re.compile(r"(?:^|[\s\b])(?:overview|introduction|objective|background|scope|about\s+the\s+scheme)(?:$|[\s\b:\-])", re.I),
        re.compile(r"(?:परिचय|उद्देश्य|संक्षिप्त\s+विवरण|प्रस्तावना|योजना\s+का\s+विवरण)"),
    ],
}

# Legal Proviso and Exception markers that must NOT be cut off from preceding rules
PROVISO_EXCEPTION_REGEX = re.compile(
    r"(?:^|[\s\b])(?:"
    r"provided\s+that|except|however|subject\s+to|notwithstanding|unless|shall\s+not\s+apply|"
    r"परंतु|किन्तु|बशर्ते|अपवाद|लागू\s+नहीं\s+होगा|के\s+अतिरिक्त|बशर्ते\s+कि"
    r")(?:$|[\s\b,:\-])",
    re.IGNORECASE,
)

# Common administrative boilerplate headers/footers to skip from chunk prose
BOILERPLATE_REGEX = re.compile(
    r"(?:^|[\s\b])(?:"
    r"government\s+of\s+rajasthan|rajasthan\s+sarkar|"
    r"राजस्थान\s+सरकार|शासन\s+सचिवालय|"
    r"page\s+\d+\s+of\s+\d+|पृष्ठ\s+\d+\s+का\s+\d+|"
    r"https?://[^\s]+"
    r")(?:$|[\s\b])",
    re.IGNORECASE,
)
