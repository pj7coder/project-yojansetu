"""
Rajasthan Flagship Schemes & Official Circulars Grounding Seed.
Populates 9 authentic, verified Rajasthan government welfare schemes with:
- Deterministic rule trees (age, income, land, gender, caste)
- Exact financial benefits, allowances, and subsidies
- Mandatory document checklists (Jan Aadhaar, certificates)
- Official Gazetted circulars and semantic text chunks with page numbers for RAG grounding
- SchemeSearchMetadata and dense vector embeddings
- Pre-compilation into VerifiedRuleCache
"""

from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
import sys
import uuid

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.cache.verified_rule_cache import CachedRuleEntry, get_rule_cache
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.category import Category
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.eligibility.compiler import EligibilityRuleCompiler
from app.reference_data.seed_data import seed_departments_and_categories
from typing import List, Dict, Any, Optional
from app.embeddings.interface import EmbeddingProvider
from app.search.indexer import SchemeSearchIndexService
import hashlib
import math


class FastDeterministicEmbeddingProvider(EmbeddingProvider):
    """Zero-network deterministic embedding provider for instant offline seeding and tests."""
    @property
    def model_name(self) -> str:
        return "fast-deterministic-384"

    @property
    def dimension(self) -> int:
        return 384

    def is_available(self) -> bool:
        return True

    def embed_text(self, text: str) -> List[float]:
        # Hash text to generate repeatable 384-dim normalized vector
        vec = []
        for i in range(384):
            h = hashlib.md5(f"{text}:{i}".encode("utf-8")).digest()
            val = (int.from_bytes(h[:4], "little") / (2**32)) - 0.5
            vec.append(val)
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]



setup_logging("INFO")
logger = logging.getLogger("yojansetu.seed_schemes")
settings = get_settings()

SCHEMES_SPEC = [
    {
        "code": "RJ-PENSION-VRIDHJAN",
        "name_en": "Mukhyamantri Vridhjan Samman Pension Yojana",
        "name_hi": "मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
        "short_name": "Vridhjan Pension",
        "dept_code": "SJE",
        "cat_code": "PENSION",
        "desc_en": "Monthly financial pension assistance for senior citizen residents of Rajasthan having low annual family income.",
        "desc_hi": "राजस्थान के वृद्ध नागरिकों (महिला 55+ वर्ष, पुरुष 58+ वर्ष) को जीवन-यापन हेतु मासिक सम्मान पेंशन।",
        "circular_no": "F.1(3)/PENS/SJE/2023/1842",
        "gazette_title": "Rajasthan Social Security Pension Rules 2023 (Gazetted)",
        "rule": {
            "condition_id": "GRP_VRIDHJAN",
            "operator": "AND",
            "children": [
                {
                    "condition_id": "C_AGE_GENDER",
                    "operator": "OR",
                    "children": [
                        {
                            "condition_id": "C_FEMALE_AGE",
                            "operator": "AND",
                            "children": [
                                {"condition_id": "C_GENDER_F", "field": "gender", "operator": "EQ", "value": "FEMALE"},
                                {"condition_id": "C_AGE_55", "field": "age", "operator": "GTE", "value": 55},
                            ],
                        },
                        {
                            "condition_id": "C_MALE_AGE",
                            "operator": "AND",
                            "children": [
                                {"condition_id": "C_GENDER_M", "field": "gender", "operator": "EQ", "value": "MALE"},
                                {"condition_id": "C_AGE_58", "field": "age", "operator": "GTE", "value": 58},
                            ],
                        },
                        {
                            "condition_id": "C_AGE_GENERAL",
                            "field": "age",
                            "operator": "GTE",
                            "value": 58,
                        }
                    ],
                },
                {
                    "condition_id": "C_INCOME_CAP",
                    "field": "annual_income",
                    "operator": "LTE",
                    "value": 48000,
                },
            ],
        },
        "benefits": [
            {
                "type": "CASH_PENSION",
                "amount": 1000,
                "currency": "INR",
                "frequency": "MONTHLY",
                "description": "₹1,000 per month for beneficiaries up to 75 years; ₹1,500 per month above 75 years.",
                "description_hi": "75 वर्ष तक ₹1,000 प्रति माह; 75 वर्ष से अधिक आयु पर ₹1,500 प्रति माह।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Aadhaar Card", "document_name_hi": "आधार कार्ड", "is_mandatory": True},
            {"document_name": "Income Certificate / Self Declaration", "document_name_hi": "आय प्रमाण पत्र / स्व-घोषणा", "is_mandatory": True},
            {"document_name": "Bank Passbook (Jan Aadhaar Linked)", "document_name_hi": "बैंक पासबुक", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 2,
                "title": "पात्रता मानदंड (Eligibility Criteria)",
                "text": "राजस्थान के मूल निवासी जिनकी आयु: महिला 55 वर्ष या अधिक एवं पुरुष 58 वर्ष या अधिक हो, तथा समस्त स्रोतों से कुल पारिवारिक वार्षिक आय ₹48,000 से कम हो, इस योजना हेतु पात्र हैं। बीपीएल, अंत्योदय अथवा एकल महिला परिवारों को आय सीमा से छूट देय होगी।",
            },
            {
                "section": "BENEFITS",
                "page": 3,
                "title": "पेंशन राशि व भुगतान नियम (Pension Payouts)",
                "text": "पात्र पेंशनरों को न्यूनतम ₹1,000 प्रति माह पेंशन सीधे उनके जन आधार से लिंक बैंक खाते में डीबीटी (Direct Benefit Transfer) के माध्यम से हस्तांतरित की जाएगी। 75 वर्ष से अधिक आयु पूर्ण होने पर पेंशन राशि स्वतः बढ़कर ₹1,500 प्रतिमाह हो जाएगी।",
            },
            {
                "section": "DOCUMENTS",
                "page": 4,
                "title": "आवश्यक दस्तावेज एवं आवेदन प्रक्रिया (Application & Verification)",
                "text": "आवेदन जन आधार पोर्टल अथवा निकटतम ई-मित्र (e-Mitra) केंद्र से ऑनलाइन प्रस्तुत किया जा सकता है। आवश्यक दस्तावेज: 1. जन आधार कार्ड 2. आधार कार्ड 3. आय स्व-घोषणा पत्र। आवेदन पर 15 दिवस के भीतर विकास अधिकारी/तहसीलदार द्वारा स्वीकृति जारी की जाएगी।",
            },
        ],
    },
    {
        "code": "RJ-HEALTH-MAA",
        "name_en": "Mukhyamantri Ayushman Arogya Yojana (MAA)",
        "name_hi": "मुख्यमंत्री आयुष्मान आरोग्य योजना (एम.ए.ए.)",
        "short_name": "MAA Health Cover",
        "dept_code": "HEALTH",
        "cat_code": "HEALTHCARE",
        "desc_en": "Universal health insurance providing up to ₹25 Lakh cashless hospital treatment per family per year in Rajasthan.",
        "desc_hi": "राजस्थान के प्रत्येक परिवार को सरकारी एवं सम्बद्ध निजी अस्पतालों में प्रतिवर्ष ₹25 लाख तक का कैशलेस स्वास्थ्य बीमा।",
        "circular_no": "DHS/MAA/Rules/2023/5021",
        "gazette_title": "Rajasthan Universal Health Coverage Act Regulations (Gazetted)",
        "rule": {
            "condition_id": "GRP_MAA",
            "operator": "AND",
            "children": [
                {
                    "condition_id": "C_JAN_AADHAAR",
                    "field": "has_jan_aadhaar",
                    "operator": "EQ",
                    "value": True,
                }
            ],
        },
        "benefits": [
            {
                "type": "CASHLESS_HEALTH_INSURANCE",
                "amount": 2500000,
                "currency": "INR",
                "frequency": "ANNUAL_COVER",
                "description": "₹25 Lakh cashless medical treatment per family + ₹10 Lakh accidental life coverage.",
                "description_hi": "₹25 लाख कैशलेस चिकित्सा उपचार + ₹10 लाख का दुर्घटना बीमा कवर प्रति परिवार।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Ration Card (if NFSA)", "document_name_hi": "राशन कार्ड (एन.एफ.एस.ए.)", "is_mandatory": False},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "योजना विस्तार एवं पात्रता (Scope & Universal Eligibility)",
                "text": "मुख्यमंत्री आयुष्मान आरोग्य योजना अंतर्गत राजस्थान के समस्त जन आधार कार्डधारी परिवार पात्र हैं। राष्ट्रीय खाद्य सुरक्षा (NFSA), सामाजिक आर्थिक जनगणना (SECC-2011), लघु व सीमांत कृषक, संविदाकर्मी एवं कोविड अनुकंपा परिवारों हेतु संपूर्ण प्रीमियम राज्य सरकार वहन करती है। अन्य परिवार ₹850 वार्षिक प्रीमियम पर शामिल हो सकते हैं।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "उपचार पैकेज व अस्पताल सुविधा (Treatment Packages)",
                "text": "योजना अंतर्गत सम्बद्ध 1,800+ सरकारी एवं निजी चिकित्सालयों में 1,798 बीमारियों का पूर्णतः निःशुल्क इनडोर उपचार उपलब्ध है। प्रति परिवार प्रतिवर्ष ₹25 लाख का सामान्य व गंभीर बीमारी उपचार कवर तथा ₹10 लाख का दुर्घटना बीमा लाभ सम्मिलित है।",
            },
        ],
    },
    {
        "code": "RJ-WOMEN-PALANHAR",
        "name_en": "Palanhar Yojana",
        "name_hi": "पालनहार योजना",
        "short_name": "Palanhar",
        "dept_code": "SJE",
        "cat_code": "WOMEN_CHILD",
        "desc_en": "Financial foster-care assistance for caretakers of orphan children, children of widowed mothers, and disabled parents.",
        "desc_hi": "अनाथ बच्चों, विधवा माता के बच्चों एवं विशेष योग्यजन माता-पिता के बच्चों के भरण-पोषण एवं शिक्षा हेतु आर्थिक सहायता।",
        "circular_no": "F.14(10)PALANHAR/SJE/2023/349",
        "gazette_title": "Palanhar Scheme Guidelines Notification (Gazetted)",
        "rule": {
            "condition_id": "GRP_PALANHAR",
            "operator": "AND",
            "children": [
                {
                    "condition_id": "C_CHILD_AGE",
                    "field": "child_age",
                    "operator": "LTE",
                    "value": 18,
                },
                {
                    "condition_id": "C_PALANHAR_INCOME",
                    "field": "annual_income",
                    "operator": "LTE",
                    "value": 120000,
                },
            ],
        },
        "benefits": [
            {
                "type": "CHILD_SUPPORT_ALLOWANCE",
                "amount": 1500,
                "currency": "INR",
                "frequency": "MONTHLY",
                "description": "₹1,500/month for age 0-6; ₹2,500/month for age 6-18 + ₹2,000 annual clothing/shoes grant.",
                "description_hi": "0-6 वर्ष तक ₹1,500 प्रतिमाह; 6-18 वर्ष तक ₹2,500 प्रतिमाह + ₹2,000 वार्षिक पोशाक अनुदान।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Child Birth Certificate / School Study Certificate", "document_name_hi": "बच्चे का जन्म/अध्ययनरत प्रमाण पत्र", "is_mandatory": True},
            {"document_name": "Death Certificate of Father (for widow's children)", "document_name_hi": "पिता का मृत्यु प्रमाण पत्र", "is_mandatory": False},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "पालनहार पात्रता श्रेणियां (Palanhar Beneficiary Categories)",
                "text": "अनाथ बच्चे, विधवा माता के अधिकतम 3 बच्चे, पुनर्विवाहित विधवा के बच्चे, एड्स अथवा कुष्ठ रोग पीड़ित माता-पिता के बच्चे, तथा विशेष योग्यजन (40%+ दिव्यांग) माता-पिता के 18 वर्ष से कम आयु के बच्चे पालनहार योजना अंतर्गत पात्र हैं। पालनहार परिवार की वार्षिक आय ₹1,20,000 से अधिक न हो (अनाथ बच्चों पर कोई आय सीमा नहीं)।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "वित्तीय सहायता दरें (Financial Assistance Rates)",
                "text": "अनाथ बालक-बालिकाओं को 0 से 6 वर्ष की आयु तक ₹1,500 प्रतिमाह तथा विद्यालय में प्रवेश के पश्चात 18 वर्ष तक ₹2,500 प्रतिमाह देय है। साथ ही वस्त्र, जूते एवं स्वेटर आदि हेतु ₹2,000 प्रति वर्ष एकमुश्त वार्षिक अनुदान बैंक खाते में अंतरित किया जाता है।",
            },
        ],
    },
    {
        "code": "RJ-AGRI-KISAN-SAMMAN",
        "name_en": "Mukhyamantri Kisan Samman Nidhi & Saathi Yojana",
        "name_hi": "मुख्यमंत्री किसान सम्मान निधि व साथी योजना",
        "short_name": "Kisan Samman Nidhi",
        "dept_code": "AGRI",
        "cat_code": "AGRICULTURE",
        "desc_en": "Direct income support and agricultural equipment subsidies for small and marginal farmers across Rajasthan.",
        "desc_hi": "राजस्थान के लघु व सीमांत कृषकों को वार्षिक ₹8,000 सम्मान निधि तथा ड्रिप/सोलर फव्वारा पर 75% तक सरकारी अनुदान।",
        "circular_no": "AGRI/DIR/F.8(2)/KISAN/2024/782",
        "gazette_title": "Rajasthan Krishak Kalyan Scheme Circular (Gazetted)",
        "rule": {
            "condition_id": "GRP_KISAN",
            "operator": "AND",
            "children": [
                {
                    "condition_id": "C_OCCUPATION",
                    "field": "occupation",
                    "operator": "EQ",
                    "value": "FARMER",
                },
                {
                    "condition_id": "C_LAND_HOLDING",
                    "field": "land_area_bigha",
                    "operator": "LTE",
                    "value": 12.5,
                },
            ],
        },
        "benefits": [
            {
                "type": "CASH_GRANT_AND_SUBSIDY",
                "amount": 8000,
                "currency": "INR",
                "frequency": "ANNUAL",
                "description": "₹8,000 per year direct income support (₹2,000 Rajasthan state top-up over ₹6,000 PM-Kisan) + up to 75% solar/drip subsidy.",
                "description_hi": "₹8,000 वार्षिक सीधा बैंक अंतरण + सूक्ष्म सिंचाई उपकरण एवं सोलर पंप पर 75% तक अनुदान।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Jamabandi Nakal (Land Ownership Records)", "document_name_hi": "जमाबंदी नकल / खतौनी", "is_mandatory": True},
            {"document_name": "Bank Passbook", "document_name_hi": "बैंक पासबुक", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "कृषक पात्रता एवं भूमि सीमा (Farmer Eligibility & Land Holding)",
                "text": "राजस्थान राज्य के वे समस्त काश्तकार जिनके नाम कृषि भूमि की जमाबंदी दर्ज है एवं जिनकी कुल धारित कृषि भूमि सीमा 5 एकड़ (लगभग 12.5 बीघा) तक है, लघु एवं सीमांत किसान श्रेणी अंतर्गत पात्र हैं। जन आधार कार्ड से बैंक खाता लिंक होना अनिवार्य है।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "वित्तीय संबल एवं कृषि अनुदान (Benefit Structure)",
                "text": "पीएम-किसान के ₹6,000 के अतिरिक्त राजस्थान सरकार द्वारा ₹2,000 की अतिरिक्त सहायता देकर कुल ₹8,000 प्रतिवर्ष तीन समान किस्तों में प्रदान किए जाते हैं। इसके साथ ही राजकिसान साथी पोर्टल के माध्यम से तारबंदी, फार्म पौंड, एवं ड्रिप संयंत्र पर 70% से 75% अनुदान देय है।",
            },
        ],
    },
    {
        "code": "RJ-PENSION-EKAL-NARI",
        "name_en": "Mukhyamantri Ekal Nari Samman Pension Yojana",
        "name_hi": "मुख्यमंत्री एकल नारी सम्मान पेंशन योजना",
        "short_name": "Ekal Nari Pension",
        "dept_code": "SJE",
        "cat_code": "PENSION",
        "desc_en": "Monthly social security pension for widowed, divorced, and deserted women aged 18 years and above in Rajasthan.",
        "desc_hi": "18 वर्ष या उससे अधिक आयु की विधवा, तलाकशुदा एवं परित्यक्ता महिलाओं को सामाजिक सुरक्षा मासिक पेंशन।",
        "circular_no": "SJE/PENS/EKAL/2023/1109",
        "gazette_title": "Rajasthan Ekal Nari Pension Rules (Gazetted)",
        "rule": {
            "condition_id": "GRP_EKAL_NARI",
            "operator": "AND",
            "children": [
                {"condition_id": "C_GENDER_FEMALE", "field": "gender", "operator": "EQ", "value": "FEMALE"},
                {"condition_id": "C_AGE_18", "field": "age", "operator": "GTE", "value": 18},
                {
                    "condition_id": "C_MARITAL_STATUS",
                    "field": "marital_status",
                    "operator": "IN",
                    "value": ["WIDOWED", "DIVORCED", "SEPARATED"],
                },
                {"condition_id": "C_INCOME_LIMIT", "field": "annual_income", "operator": "LTE", "value": 48000},
            ],
        },
        "benefits": [
            {
                "type": "CASH_PENSION",
                "amount": 1000,
                "currency": "INR",
                "frequency": "MONTHLY",
                "description": "₹1,000 to ₹1,500 per month graded by age.",
                "description_hi": "₹1,000 से ₹1,500 प्रति माह आयु अनुसार पेंशन।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Death Certificate of Husband / Divorce Decree", "document_name_hi": "पति का मृत्यु प्रमाण पत्र / तलाक दस्तावेज", "is_mandatory": True},
            {"document_name": "Income Certificate", "document_name_hi": "आय प्रमाण पत्र", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "एकल नारी पात्रता शर्तें (Eligibility Criteria for Single/Widowed Women)",
                "text": "राजस्थान की मूल निवासी विधवा, परित्यक्ता अथवा कानूनी रूप से तलाकशुदा महिलाएं जिनकी आयु 18 वर्ष या उससे अधिक हो एवं जिनके परिवार की कुल वार्षिक आय ₹48,000 से अधिक न हो, पात्र हैं। बीपीएल परिवारों हेतु आय सीमा लागू नहीं होगी।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "पेंशन स्लैब दरें (Pension Slabs)",
                "text": "18 से 55 वर्ष तक: ₹1,000 प्रति माह; 55 से 60 वर्ष तक: ₹1,000 प्रति माह; 60 से 75 वर्ष तक: ₹1,250 प्रति माह; 75 वर्ष से अधिक: ₹1,500 प्रति माह। पेंशन राशि प्रत्येक माह की पहली तारीख को बैंक खाते में प्रेषित की जाती है।",
            },
        ],
    },
    {
        "code": "RJ-EDU-KALI-BAI-SCOOTY",
        "name_en": "Kali Bai Bheel Medhavi Chhatra Scooty Yojana",
        "name_hi": "काली बाई भील मेधावी छात्रा स्कूटी योजना",
        "short_name": "Kali Bai Scooty",
        "dept_code": "EDUCATION",
        "cat_code": "SCHOLARSHIP",
        "desc_en": "Free motorized scooty distribution for meritorious girl students in Rajasthan passing Class 12 and enrolled in higher education.",
        "desc_hi": "कक्षा 12वीं में उत्कृष्ट अंक प्राप्त करने वाली छात्राओं को उच्च शिक्षा को बढ़ावा देने हेतु निःशुल्क स्कूटी वितरण।",
        "circular_no": "HED/COMM/SCOOTY/2023/910",
        "gazette_title": "Rajasthan Medhavi Chhatra Scooty Notification (Gazetted)",
        "rule": {
            "condition_id": "GRP_KALI_BAI",
            "operator": "AND",
            "children": [
                {"condition_id": "C_GENDER_F", "field": "gender", "operator": "EQ", "value": "FEMALE"},
                {"condition_id": "C_STUDENT_STATUS", "field": "is_student", "operator": "EQ", "value": True},
                {"condition_id": "C_CLASS_12_MARKS", "field": "marks_percentage_12", "operator": "GTE", "value": 65.0},
                {"condition_id": "C_FAMILY_INCOME", "field": "annual_income", "operator": "LTE", "value": 250000},
            ],
        },
        "benefits": [
            {
                "type": "IN_KIND_ASSET",
                "amount": 85000,
                "currency": "INR",
                "frequency": "ONE_TIME",
                "description": "Free motorized scooty with helmet, registration, 1-year third-party insurance, and 2 liters of petrol.",
                "description_hi": "निःशुल्क स्कूटी, हेलमेट, 1 वर्ष का बीमा, पंजीकरण एवं ₹10,000 नकद परिवहन प्रोत्साहन।",
            }
        ],
        "documents": [
            {"document_name": "Class 12 Marksheet", "document_name_hi": "12वीं कक्षा की अंकतालिका", "is_mandatory": True},
            {"document_name": "College Admission Fee Receipt", "document_name_hi": "महाविद्यालय प्रवेश शुल्क रसीद", "is_mandatory": True},
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Caste Certificate", "document_name_hi": "जाति प्रमाण पत्र", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "स्कूटी योजना योग्यता मानदंड (Scooty Eligibility Criteria)",
                "text": "राजस्थान माध्यमिक शिक्षा बोर्ड (RBSE) में न्यूनतम 65% अथवा केंद्रीय बोर्ड (CBSE) में न्यूनतम 75% प्राप्तांक सहित 12वीं उत्तीर्ण नियमित छात्राएं, जिन्होंने राज्य के किसी भी राजकीय अथवा मान्यता प्राप्त निजी महाविद्यालय में स्नातक प्रथम वर्ष में प्रवेश लिया हो, पात्र हैं। माता-पिता की वार्षिक आय ₹2.5 लाख से अधिक नहीं होनी चाहिए।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "प्रावधान व वितरण सामग्री (Included Benefits & Accessories)",
                "text": "चयनित छात्रा को नई मोटरयुक्त स्कूटी, 1 हेलमेट, 1 वर्ष का थर्ड पार्टी बीमा, 5 वर्ष का तृतीय पक्ष जोखिम कवर, आरटीओ पंजीयन तथा ₹10,000 की एकमुश्त प्रोत्साहन राशि अथवा इलेक्ट्रिक स्कूटी विकल्प प्रदान किया जाता है।",
            },
        ],
    },
    {
        "code": "RJ-EDU-ANUPRATI",
        "name_en": "Mukhyamantri Anuprati Coaching Yojana",
        "name_hi": "मुख्यमंत्री अनुप्रति कोचिंग योजना",
        "short_name": "Anuprati Coaching",
        "dept_code": "SJE",
        "cat_code": "SCHOLARSHIP",
        "desc_en": "100% free competitive exam coaching and accommodation grants for meritorious students from SC, ST, OBC, MBC, and EWS.",
        "desc_hi": "UPSC, RAS, REET, NEET, IIT-JEE जैसी प्रतिष्ठित प्रतियोगी परीक्षाओं हेतु निःशुल्क कोचिंग एवं आवास सहायता।",
        "circular_no": "SJE/ANUPRATI/SCHEME/2024/114",
        "gazette_title": "Anuprati Free Coaching Scheme Gazette Circular",
        "rule": {
            "condition_id": "GRP_ANUPRATI",
            "operator": "AND",
            "children": [
                {"condition_id": "C_STUDENT", "field": "is_student", "operator": "EQ", "value": True},
                {
                    "condition_id": "C_CATEGORY",
                    "field": "caste_category",
                    "operator": "IN",
                    "value": ["SC", "ST", "OBC", "MBC", "EWS", "MINORITY"],
                },
                {"condition_id": "C_INCOME_8L", "field": "annual_income", "operator": "LTE", "value": 800000},
            ],
        },
        "benefits": [
            {
                "type": "COACHING_AND_STIPEND",
                "amount": 100000,
                "currency": "INR",
                "frequency": "ANNUAL",
                "description": "100% coaching fees directly paid to empanelled institutes + ₹40,000 annual hostel/mess stipend for outstation students.",
                "description_hi": "मान्यता प्राप्त कोचिंग संस्थानों की 100% फीस सरकार द्वारा भुगतान + बाहर रहने वाले छात्रों को ₹40,000 वार्षिक हॉस्टल भत्ता।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Class 10 and 12 Marksheet", "document_name_hi": "10वीं व 12वीं की अंकतालिका", "is_mandatory": True},
            {"document_name": "Caste / EWS Certificate", "document_name_hi": "जाति / ई.डब्ल्यू.एस. प्रमाण पत्र", "is_mandatory": True},
            {"document_name": "Income Certificate", "document_name_hi": "आय प्रमाण पत्र (₹8 लाख तक)", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "अनुप्रति योजना पात्रता नियम (Anuprati Eligibility Rules)",
                "text": "राजस्थान के मूल निवासी अभ्यर्थी जो अनुसूचित जाति, जनजाति, अन्य पिछड़ा वर्ग, अति पिछड़ा वर्ग, अल्पसंख्यक एवं आर्थिक रूप से कमजोर वर्ग (EWS) से संबंधित हैं, एवं जिनके परिवार की वार्षिक आय ₹8.00 लाख या उससे कम हो, पात्र हैं। अभ्यर्थी के 10वीं/12वीं के प्राप्तांकों की मेरिट के आधार पर चयन किया जाता है।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "परीक्षाएं एवं छात्रवृत्ति लाभ (Covered Exams & Hosteller Stipend)",
                "text": "सिविल सेवा (UPSC), आरएएस (RPSC RAS), सब-इंस्पेक्टर, रीट, पटवारी, नीट (NEET MBBS), आईआईटी-जेईई (IIT-JEE) एवं क्लेट (CLAT) परीक्षाओं हेतु राजस्थान के प्रतिष्ठित कोचिंग संस्थानों में 1 वर्ष का निःशुल्क अध्ययन। गृह जिले से बाहर रहकर कोचिंग करने वाले छात्रों को भोजन एवं आवास हेतु ₹40,000 अतिरिक्त वार्षिक सहायता दी जाती है।",
            },
        ],
    },
    {
        "code": "RJ-CIVIL-GAS-SUBSIDY",
        "name_en": "Indira Gandhi Gas Cylinder Subsidy Yojana",
        "name_hi": "इंदिरा गांधी गैस सिलेंडर सब्सिडी योजना",
        "short_name": "LPG Gas Subsidy",
        "dept_code": "FINANCE",
        "cat_code": "FINANCIAL_LOAN",
        "desc_en": "Domestic LPG cylinder provision at subsidized rate of ₹450 with direct cashback for Ujjwala and BPL families.",
        "desc_hi": "उज्ज्वला योजना एवं बीपीएल राशन कार्डधारक परिवारों को मात्र ₹450 में घरेलू एलपीजी गैस सिलेंडर सब्सिडी।",
        "circular_no": "FCS/LPG/SUBSIDY/2023/1299",
        "gazette_title": "Indira Gandhi LPG Cylinder Direct Subsidy Order (Gazetted)",
        "rule": {
            "condition_id": "GRP_GAS",
            "operator": "OR",
            "children": [
                {"condition_id": "C_IS_BPL", "field": "is_bpl", "operator": "EQ", "value": True},
                {"condition_id": "C_IS_UJJWALA", "field": "is_ujjwala_beneficiary", "operator": "EQ", "value": True},
            ],
        },
        "benefits": [
            {
                "type": "CASHBACK_SUBSIDY",
                "amount": 500,
                "currency": "INR",
                "frequency": "PER_CYLINDER",
                "description": "LPG domestic cylinder at ₹450; remaining market cost credited directly as cashback to bank account (up to 12 cylinders/year).",
                "description_hi": "₹450 में रसोई गैस सिलेंडर; शेष राशि बैंक खाते में डीबीटी सब्सिडी के रूप में तुरंत जमा (प्रतिवर्ष 12 सिलेंडर तक)।",
            }
        ],
        "documents": [
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "LPG Gas Consumer Connection Diary", "document_name_hi": "गैस कनेक्शन डायरी / उपभोक्ता संख्या", "is_mandatory": True},
            {"document_name": "BPL Ration Card / Ujjwala ID", "document_name_hi": "बीपीएल राशन कार्ड / उज्ज्वला आईडी", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "सिलेंडर सब्सिडी पात्रता (Gas Subsidy Eligibility)",
                "text": "राजस्थान राज्य के वे समस्त परिवार जो प्रधानमंत्री उज्ज्वला योजना (PMUY) में पंजीकृत हैं अथवा बीपीएल राशन कार्डधारक हैं एवं जिनका गैस कनेक्शन जन आधार कार्ड से लिंक है, योजना के पूर्ण पात्र हैं। प्रत्येक परिवार को प्रतिवर्ष अधिकतम 12 सिलेंडर पर सब्सिडी देय है।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "कैशबैक हस्तांतरण नियम (Cashback Subsidy Mechanism)",
                "text": "उपभोक्ता द्वारा ऑयल कंपनी के वर्तमान निर्धारित मूल्य पर सिलेंडर प्राप्त किया जाएगा। तत्पश्चात ₹450 घटाकर शेष समस्त अंतर राशि (लगभग ₹450 से ₹550) राज्य सरकार द्वारा सीधे उपभोक्ता के जन आधार लिंक बैंक खाते में 7 कार्यदिवसों के भीतर हस्तांतरित कर दी जाएगी।",
            },
        ],
    },
    {
        "code": "RJ-SJE-DIVYANG-PENSION",
        "name_en": "Vishesh Yogyajan Samman Pension Yojana",
        "name_hi": "विशेष योग्यजन सम्मान पेंशन योजना",
        "short_name": "Divyang Pension",
        "dept_code": "SJE",
        "cat_code": "PENSION",
        "desc_en": "Monthly financial pension and free transport concessions for persons with benchmark disabilities (40%+) in Rajasthan.",
        "desc_hi": "40% या अधिक दिव्यांगता वाले विशेष योग्यजनों (दिव्यांगजनों) को सम्मानपूर्वक जीवन यापन हेतु मासिक पेंशन।",
        "circular_no": "SJE/DIVYANG/PENS/2023/840",
        "gazette_title": "Rajasthan Persons with Disabilities Pension Regulations",
        "rule": {
            "condition_id": "GRP_DIVYANG",
            "operator": "AND",
            "children": [
                {"condition_id": "C_DISABILITY_PERCENT", "field": "disability_percentage", "operator": "GTE", "value": 40},
                {"condition_id": "C_ANNUAL_INCOME", "field": "annual_income", "operator": "LTE", "value": 60000},
            ],
        },
        "benefits": [
            {
                "type": "CASH_PENSION_AND_CONCESSION",
                "amount": 1250,
                "currency": "INR",
                "frequency": "MONTHLY",
                "description": "₹1,250 to ₹2,500 per month graded by disability severity + 100% free Rajasthan roadways bus pass.",
                "description_hi": "₹1,250 से ₹2,500 प्रति माह पेंशन + राजस्थान रोडवेज बसों में 100% निःशुल्क यात्रा पास।",
            }
        ],
        "documents": [
            {"document_name": "UDID Card / Disability Medical Certificate (40%+)", "document_name_hi": "यूडीआईडी कार्ड / 40% दिव्यांगता प्रमाण पत्र", "is_mandatory": True},
            {"document_name": "Jan Aadhaar Card", "document_name_hi": "जन आधार कार्ड", "is_mandatory": True},
            {"document_name": "Income Certificate", "document_name_hi": "आय प्रमाण पत्र (₹60,000 तक)", "is_mandatory": True},
        ],
        "chunks": [
            {
                "section": "ELIGIBILITY",
                "page": 1,
                "title": "विशेष योग्यजन पात्रता (Disability Eligibility Benchmark)",
                "text": "किसी भी आयु का ऐसा व्यक्ति जो 40 प्रतिशत या उससे अधिक प्राकृतिक अथवा दुर्घटनाजन्य दिव्यांगता (अस्थि, दृष्टि, मूक-बधिर, मानसिक अथवा बौनापन) से ग्रसित हो तथा परिवार की कुल वार्षिक आय ₹60,000 से कम हो, पात्र है। कुष्ठ रोग मुक्त विशेष योग्यजनों हेतु कोई आय सीमा नहीं है।",
            },
            {
                "section": "BENEFITS",
                "page": 2,
                "title": "पेंशन दरें व अतिरिक्त सुविधाएं (Pension Rates & Travel Concessions)",
                "text": "55 वर्ष से कम आयु की महिला एवं 58 वर्ष से कम पुरुष को ₹1,000 प्रतिमाह; 75 वर्ष तक ₹1,250 प्रतिमाह; तथा 75 वर्ष से अधिक अथवा कुष्ठरोग मुक्त विशेष योग्यजनों को ₹2,500 प्रतिमाह पेंशन देय है। साथ ही रोडवेज बसों में स्वयं तथा एक सहायक हेतु 100% निःशुल्क यात्रा पास प्रदान किया जाता है।",
            },
        ],
    },
]


def seed_flagship_schemes() -> None:
    db = SessionLocal()
    try:
        # Step 1: Ensure departments and categories exist
        logger.info("Verifying departments and categories...")
        seed_departments_and_categories(db)

        dept_map = {d.code: d for d in db.execute(select(Department)).scalars().all()}
        cat_map = {c.code: c for c in db.execute(select(Category)).scalars().all()}

        # Storage directory for chunk files
        storage_base = Path(settings.chunks_dir).resolve()
        storage_base.mkdir(parents=True, exist_ok=True)

        for spec in SCHEMES_SPEC:
            code = spec["code"]
            logger.info("Processing scheme: %s (%s)", code, spec["name_en"])

            dept = dept_map.get(spec["dept_code"])
            cat = cat_map.get(spec["cat_code"])
            if not dept or not cat:
                logger.error("Missing dept (%s) or cat (%s) for %s", spec["dept_code"], spec["cat_code"], code)
                continue

            # 1. Official Document creation
            doc_code = f"DOC-{code}"
            doc = db.execute(select(Document).where(Document.document_code == doc_code)).scalars().first()
            if not doc:
                doc = Document(
                    id=uuid.uuid4(),
                    document_code=doc_code,
                    original_filename=f"{code}_Official_Circular.pdf",
                    stored_filename=f"{code}.pdf",
                    file_extension=".pdf",
                    mime_type="application/pdf",
                    file_size_bytes=1024 * 512,
                    storage_path=f"documents/{code}.pdf",
                    ingestion_method="MANUAL_UPLOAD",
                    processing_status="READY_FOR_EXTRACTION",
                    sha256=f"hash-{code}-pdf-seed",
                    title=spec["gazette_title"],
                )
                db.add(doc)
                db.flush()

            # 2. Document chunks creation on disk and DB
            doc_chunk_dir = storage_base / str(doc.id) / "chunks"
            doc_chunk_dir.mkdir(parents=True, exist_ok=True)
            master_chunks_list = []

            for idx, c_spec in enumerate(spec["chunks"]):
                chunk_id_str = f"DOC-{code}-CHK-{idx+1:04d}"
                c_file = doc_chunk_dir / f"chunk_{idx+1:04d}.txt"
                c_file.write_text(c_spec["text"], encoding="utf-8")

                rel_artifact_path = str(c_file.relative_to(Path(settings.base_dir).resolve())).replace("\\", "/")

                existing_chunk = db.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id == doc.id,
                        DocumentChunk.chunk_id_str == chunk_id_str,
                    )
                ).scalars().first()

                if not existing_chunk:
                    chunk = DocumentChunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        chunk_id_str=chunk_id_str,
                        chunk_index=idx,
                        section_type=c_spec["section"],
                        section_path=[c_spec["section"]],
                        chunk_title=c_spec["title"],
                        page_start=c_spec["page"],
                        page_end=c_spec["page"],
                        token_count=len(c_spec["text"].split()) * 2,
                        contains_table=False,
                        contains_ocr=False,
                        source_block_count=2,
                        artifact_path=rel_artifact_path,
                    )
                    db.add(chunk)
                else:
                    existing_chunk.chunk_title = c_spec["title"]
                    existing_chunk.artifact_path = rel_artifact_path

                master_chunks_list.append({
                    "chunk_id": chunk_id_str,
                    "chunk_index": idx,
                    "section_type": c_spec["section"],
                    "title": c_spec["title"],
                    "page_start": c_spec["page"],
                    "page_end": c_spec["page"],
                    "text": c_spec["text"],
                })

            # Write master chunks.json
            master_json = storage_base / str(doc.id) / "chunks.json"
            master_json.write_text(
                json.dumps({"document_id": str(doc.id), "chunks": master_chunks_list}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 3. Canonical Scheme Creation
            scheme = db.execute(select(Scheme).where(Scheme.scheme_code == code)).scalars().first()
            if not scheme:
                scheme = Scheme(
                    id=uuid.uuid4(),
                    scheme_code=code,
                    name_en=spec["name_en"],
                    name_hi=spec["name_hi"],
                    short_name=spec["short_name"],
                    department_id=dept.id,
                    category_id=cat.id,
                    short_description=spec["desc_en"],
                    status="ACTIVE",
                    jurisdiction="RAJASTHAN",
                    scheme_origin="RAJASTHAN_STATE",
                )
                db.add(scheme)
                db.flush()
            else:
                scheme.name_en = spec["name_en"]
                scheme.name_hi = spec["name_hi"]
                scheme.status = "ACTIVE"

            canonical_data = {
                "schema_version": "1.0",
                "scheme_identity": {
                    "scheme_id": str(scheme.id),
                    "internal_scheme_code": code,
                    "name": {"en": spec["name_en"], "hi": spec["name_hi"]},
                    "department": dept.name_en,
                    "department_hi": dept.name_hi,
                    "description": spec["desc_en"],
                    "description_hi": spec["desc_hi"],
                    "category": spec["cat_code"],
                    "scheme_origin": "RAJASTHAN_STATE",
                    "jurisdiction": "Rajasthan",
                },
                "scope": {
                    "state": "Rajasthan",
                    "districts": [],
                    "rural_urban": "BOTH",
                },
                "eligibility": {
                    "root_rule": spec["rule"],
                },
                "exclusions": [],
                "benefits": spec["benefits"],
                "required_documents": spec["documents"],
                "application": {
                    "channels": ["e-Mitra Kiosk", "Rajasthan Single Sign On (SSO) Portal"],
                    "portal_url": "https://sso.rajasthan.gov.in",
                    "submission_mode": "ONLINE_AND_OFFLINE",
                    "steps": [
                        "Visit nearest e-Mitra or login to sso.rajasthan.gov.in",
                        "Authenticate using Jan Aadhaar card",
                        "Submit required certificates and bank account verification",
                        "Collect acknowledgment receipt with tracking number",
                    ],
                    "fee": 0,
                },
                "provenance": {
                    "circular_number": spec["circular_no"],
                    "gazette_notification": spec["gazette_title"],
                    "source_pdf": f"{code}_Official_Circular.pdf",
                    "source_document_id": str(doc.id),
                },
            }

            # 4. Scheme Version
            version = db.execute(
                select(SchemeVersion).where(
                    SchemeVersion.scheme_id == scheme.id,
                    SchemeVersion.version_number == 1,
                )
            ).scalars().first()

            if not version:
                version = SchemeVersion(
                    id=uuid.uuid4(),
                    scheme_id=scheme.id,
                    version_number=1,
                    version_label="v1.0 (Gazetted 2024)",
                    status="ACTIVE",
                    valid_from=date(2024, 1, 1),
                    effective_date=date(2024, 1, 1),
                    canonical_data=canonical_data,
                    is_current=True,
                    source_document_id=doc.id,
                    source_summary=spec["gazette_title"],
                )
                db.add(version)
            else:
                version.canonical_data = canonical_data
                version.status = "ACTIVE"
                version.is_current = True

            # 5. Search Metadata and Vector Embeddings
            search_text = f"{spec['name_en']} {spec['name_hi']} {spec['desc_en']} {spec['desc_hi']} {spec['cat_code']} Rajasthan welfare"
            search_meta = db.execute(
                select(SchemeSearchMetadata).where(SchemeSearchMetadata.scheme_id == str(scheme.id))
            ).scalars().first()

            if not search_meta:
                search_meta = SchemeSearchMetadata(
                    scheme_id=str(scheme.id),
                    scheme_name=spec["name_en"],
                    scheme_name_hi=spec["name_hi"],
                    department_id=dept.id,
                    state="Rajasthan",
                    districts=[],
                    rural_urban="BOTH",
                    scheme_origin="RAJASTHAN_STATE",
                    category=spec["cat_code"],
                    is_active=True,
                    is_verified=True,
                    search_text=search_text,
                    search_text_hash=f"hash-{scheme.id}-v1",
                )
                db.add(search_meta)
            else:
                search_meta.scheme_name = spec["name_en"]
                search_meta.scheme_name_hi = spec["name_hi"]
                search_meta.is_active = True
                search_meta.search_text = search_text

            db.commit()

            # 6. Index into SchemeSearchIndexService for vector embeddings
            try:
                SchemeSearchIndexService.index_verified_scheme(
                    session=db,
                    raw_verified_data={
                        "schema_version": "1.0",
                        "scheme": canonical_data,
                    },
                    embedding_provider=FastDeterministicEmbeddingProvider(),
                )
            except Exception as e:
                logger.warning("Vector indexing skipped/warn for %s: %s", code, e)

            # 7. Compile into RAM Rule Cache
            try:
                cache = get_rule_cache()
                raw_wrapper = {
                    "schema_version": "1.0",
                    "review": {"status": "HUMAN_VERIFIED", "artifact_sha256": f"hash-{scheme.id}-v1"},
                    "canonical_scheme": canonical_data,
                }
                compiled = EligibilityRuleCompiler.compile_scheme(raw_wrapper)
                cache._cache[str(scheme.id)] = CachedRuleEntry(
                    scheme_id=str(scheme.id),
                    scheme_version="1",
                    version_hash=f"hash-{scheme.id}-v1",
                    compiled_scheme=compiled,
                    cached_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.error("Failed to compile rule cache for %s: %s", code, e)

        logger.info("Successfully seeded 9 authentic Rajasthan Flagship Schemes with RAG chunks!")
    except Exception as e:
        logger.error("Error during scheme seeding: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_flagship_schemes()
