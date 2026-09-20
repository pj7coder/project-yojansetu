"""
Vernacular question catalog and dynamic builder for YojanSetu Citizen Interface.
Enforces deterministic question mapping, units, sensitivity, and option translation.
"""

from typing import Dict, List, Optional

from app.citizen.schemas import CitizenQuestionDisplay, QuestionOption
from app.questioning.field_metadata import FIELD_METADATA_REGISTRY, get_field_metadata
from app.questioning.schemas import NextQuestionResult


# Predefined canonical options for select fields
FIELD_OPTIONS_MAP: Dict[str, List[QuestionOption]] = {
    "gender": [
        QuestionOption(value="MALE", label_en="Male", label_hi="पुरुष"),
        QuestionOption(value="FEMALE", label_en="Female", label_hi="महिला"),
        QuestionOption(value="TRANSGENDER", label_en="Transgender", label_hi="ट्रांसजेंडर"),
        QuestionOption(value="OTHER", label_en="Other", label_hi="अन्य"),
    ],
    "rural_urban": [
        QuestionOption(value="RURAL", label_en="Rural", label_hi="ग्रामीण"),
        QuestionOption(value="URBAN", label_en="Urban", label_hi="शहरी"),
    ],
    "social_category": [
        QuestionOption(value="GENERAL", label_en="General", label_hi="सामान्य (General)"),
        QuestionOption(value="OBC", label_en="OBC (Other Backward Class)", label_hi="ओबीसी (अन्य पिछड़ा वर्ग)"),
        QuestionOption(value="SC", label_en="SC (Scheduled Caste)", label_hi="अनुसूचित जाति (SC)"),
        QuestionOption(value="ST", label_en="ST (Scheduled Tribe)", label_hi="अनुसूचित जनजाति (ST)"),
        QuestionOption(value="MBC", label_en="MBC (Most Backward Class)", label_hi="एमबीसी (अति पिछड़ा वर्ग)"),
        QuestionOption(value="EWS", label_en="EWS (Economically Weaker Section)", label_hi="ईडब्ल्यूएस (आर्थिक रूप से कमजोर)"),
    ],
    "occupation": [
        QuestionOption(value="FARMER", label_en="Farmer / Cultivator", label_hi="किसान / काश्तकार"),
        QuestionOption(value="LABOURER", label_en="Labourer / Daily Wage Worker", label_hi="श्रमिक / दैनिक वेतनभोगी"),
        QuestionOption(value="STUDENT", label_en="Student", label_hi="विद्यार्थी / छात्र"),
        QuestionOption(value="SELF_EMPLOYED", label_en="Self Employed / Business", label_hi="स्वरोजगार / छोटा व्यवसाय"),
        QuestionOption(value="ARTISAN", label_en="Artisan / Craftsman", label_hi="दस्तकार / कारीगर"),
        QuestionOption(value="UNEMPLOYED", label_en="Unemployed", label_hi="बेरोजगार"),
        QuestionOption(value="OTHER", label_en="Other Occupation", label_hi="अन्य कार्य"),
    ],
    "farmer_category": [
        QuestionOption(value="MARGINAL", label_en="Marginal Farmer (Up to 1 Hectare)", label_hi="सीमांत किसान (1 हेक्टेयर तक)"),
        QuestionOption(value="SMALL", label_en="Small Farmer (1 to 2 Hectares)", label_hi="लघु किसान (1 से 2 हेक्टेयर)"),
        QuestionOption(value="MEDIUM", label_en="Semi-Medium / Medium Farmer", label_hi="अर्ध-मध्यम / मध्यम किसान"),
        QuestionOption(value="LARGE", label_en="Large Farmer (> 10 Hectares)", label_hi="बड़ा किसान"),
    ],
    "marital_status": [
        QuestionOption(value="SINGLE", label_en="Unmarried / Single", label_hi="अविवाहित"),
        QuestionOption(value="MARRIED", label_en="Married", label_hi="विवाहित"),
        QuestionOption(value="WIDOWED", label_en="Widowed", label_hi="विधवा / विधुर"),
        QuestionOption(value="DIVORCED", label_en="Divorced / Separated", label_hi="तलाकशुदा / परित्यक्ता"),
    ],
    "education_level": [
        QuestionOption(value="ILLITERATE", label_en="No formal schooling", label_hi="औपचारिक शिक्षा नहीं"),
        QuestionOption(value="PRIMARY", label_en="Primary School (up to Class 5)", label_hi="प्राथमिक (5वीं तक)"),
        QuestionOption(value="SECONDARY", label_en="Secondary (10th Pass)", label_hi="माध्यमिक (10वीं पास)"),
        QuestionOption(value="HIGHER_SECONDARY", label_en="Senior Secondary (12th Pass)", label_hi="उच्च माध्यमिक (12वीं पास)"),
        QuestionOption(value="GRADUATE", label_en="Graduate (Degree)", label_hi="स्नातक (Graduate)"),
        QuestionOption(value="POST_GRADUATE", label_en="Post Graduate / Higher", label_hi="स्नातकोत्तर या उच्च"),
    ],
}

# Boolean field custom options
BOOLEAN_OPTIONS_MAP: Dict[str, List[QuestionOption]] = {
    "bpl_status": [
        QuestionOption(value="true", label_en="Yes, family has BPL card", label_hi="हाँ, परिवार बीपीएल श्रेणी में है"),
        QuestionOption(value="false", label_en="No, not BPL", label_hi="नहीं, बीपीएल नहीं है"),
    ],
    "disability_status": [
        QuestionOption(value="true", label_en="Yes, has recognized disability", label_hi="हाँ, दिव्यांगता है"),
        QuestionOption(value="false", label_en="No disability", label_hi="नहीं, दिव्यांगता नहीं है"),
    ],
    "widow_status": [
        QuestionOption(value="true", label_en="Yes, widow", label_hi="हाँ, विधवा हूँ"),
        QuestionOption(value="false", label_en="No", label_hi="नहीं"),
    ],
    "student_status": [
        QuestionOption(value="true", label_en="Yes, currently enrolled student", label_hi="हाँ, वर्तमान में विद्यार्थी हूँ"),
        QuestionOption(value="false", label_en="No, not a student", label_hi="नहीं, विद्यार्थी नहीं हूँ"),
    ],
}

DEFAULT_BOOLEAN_OPTIONS: List[QuestionOption] = [
    QuestionOption(value="true", label_en="Yes", label_hi="हाँ"),
    QuestionOption(value="false", label_en="No", label_hi="नहीं"),
]

# Field units and formatting guidance
FIELD_EXTRA_METADATA: Dict[str, Dict[str, str]] = {
    "age": {
        "unit_en": "Years",
        "unit_hi": "वर्ष",
        "help_text_en": "Enter age in completed years (e.g. 45)",
        "help_text_hi": "अपनी पूर्ण आयु दर्ज करें (जैसे 45)",
    },
    "family_income": {
        "unit_en": "₹ / year",
        "unit_hi": "₹ प्रति वर्ष",
        "help_text_en": "Approximate annual income of all family members combined",
        "help_text_hi": "परिवार के सभी सदस्यों की कुल वार्षिक आय (जैसे 150000 या 1.5 लाख)",
    },
    "land_holding_acres": {
        "unit_en": "Acres",
        "unit_hi": "एकड़",
        "help_text_en": "Total agricultural land held in acres",
        "help_text_hi": "कुल कृषि भूमि एकड़ में",
    },
    "land_holding_hectares": {
        "unit_en": "Hectares",
        "unit_hi": "हेक्टेयर",
        "help_text_en": "Total agricultural land held in hectares",
        "help_text_hi": "कुल कृषि भूमि हेक्टेयर में",
    },
    "disability_percentage": {
        "unit_en": "%",
        "unit_hi": "%",
        "help_text_en": "Percentage from disability certificate (e.g. 40)",
        "help_text_hi": "दिव्यांगता प्रमाण पत्र के अनुसार प्रतिशत (जैसे 40)",
    },
}


class CitizenQuestionBuilder:
    """
    Constructs bilingual presentation questions from Day 16 NextQuestionResult.
    """

    @classmethod
    def build_question_display(cls, next_q: NextQuestionResult) -> Optional[CitizenQuestionDisplay]:
        if not next_q.field:
            return None

        field_name = next_q.field
        field_meta = get_field_metadata(field_name)

        data_type = field_meta.data_type
        options = None

        if data_type == "select":
            options = FIELD_OPTIONS_MAP.get(field_name)
        elif data_type == "boolean":
            options = BOOLEAN_OPTIONS_MAP.get(field_name, DEFAULT_BOOLEAN_OPTIONS)

        extra = FIELD_EXTRA_METADATA.get(field_name, {})

        return CitizenQuestionDisplay(
            field=field_name,
            reason_code=next_q.reason_code,
            affected_scheme_count=next_q.affected_scheme_count,
            data_type=data_type,
            display_name_en=field_meta.display_name_en,
            display_name_hi=field_meta.display_name_hi,
            question_en=next_q.example_question_en or field_meta.example_question_en,
            question_hi=next_q.example_question_hi or field_meta.example_question_hi,
            options=options,
            unit_en=extra.get("unit_en"),
            unit_hi=extra.get("unit_hi"),
            sensitivity_level=field_meta.sensitivity_level,
            allow_decline=True,
            help_text_en=extra.get("help_text_en"),
            help_text_hi=extra.get("help_text_hi"),
        )
