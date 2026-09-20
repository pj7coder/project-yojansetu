from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class FieldMetadata:
    """Vernacular display and privacy metadata for a canonical citizen profile attribute."""
    field_name: str
    display_name_en: str
    display_name_hi: str
    data_type: str
    sensitivity_level: str  # "LOW", "MEDIUM", "HIGH"
    example_question_en: str
    example_question_hi: str


FIELD_METADATA_REGISTRY: Dict[str, FieldMetadata] = {
    "age": FieldMetadata(
        field_name="age",
        display_name_en="Age",
        display_name_hi="आयु",
        data_type="integer",
        sensitivity_level="LOW",
        example_question_en="What is your age in completed years?",
        example_question_hi="आपकी पूर्ण आयु कितने वर्ष है?",
    ),
    "state": FieldMetadata(
        field_name="state",
        display_name_en="State of Residence",
        display_name_hi="निवास का राज्य",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="In which state do you currently reside?",
        example_question_hi="आप वर्तमान में किस राज्य में रहते हैं?",
    ),
    "district": FieldMetadata(
        field_name="district",
        display_name_en="District",
        display_name_hi="जिला",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="Which district in Rajasthan do you reside in?",
        example_question_hi="आप राजस्थान के किस जिले में रहते हैं?",
    ),
    "rural_urban": FieldMetadata(
        field_name="rural_urban",
        display_name_en="Area Type",
        display_name_hi="क्षेत्र का प्रकार",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="Do you live in a rural or urban area?",
        example_question_hi="क्या आप ग्रामीण क्षेत्र में रहते हैं या शहरी?",
    ),
    "gender": FieldMetadata(
        field_name="gender",
        display_name_en="Gender",
        display_name_hi="लिंग",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="What is your gender?",
        example_question_hi="आपका लिंग क्या है?",
    ),
    "occupation": FieldMetadata(
        field_name="occupation",
        display_name_en="Occupation",
        display_name_hi="व्यवसाय",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="What is your primary occupation?",
        example_question_hi="आपका मुख्य व्यवसाय क्या है?",
    ),
    "farmer_category": FieldMetadata(
        field_name="farmer_category",
        display_name_en="Farmer Category",
        display_name_hi="कृषक श्रेणी",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="What is your farmer classification (e.g. Small, Marginal)?",
        example_question_hi="आपकी कृषक श्रेणी क्या है (जैसे लघु, सीमांत)?",
    ),
    "land_holding_acres": FieldMetadata(
        field_name="land_holding_acres",
        display_name_en="Agricultural Land (Acres)",
        display_name_hi="कृषि भूमि (एकड़)",
        data_type="number",
        sensitivity_level="LOW",
        example_question_en="How many acres of agricultural land does your family hold?",
        example_question_hi="आपके परिवार के पास कितने एकड़ कृषि भूमि है?",
    ),
    "land_holding_hectares": FieldMetadata(
        field_name="land_holding_hectares",
        display_name_en="Agricultural Land (Hectares)",
        display_name_hi="कृषि भूमि (हेक्टेयर)",
        data_type="number",
        sensitivity_level="LOW",
        example_question_en="How many hectares of agricultural land does your family hold?",
        example_question_hi="आपके परिवार के पास कितने हेक्टेयर कृषि भूमि है?",
    ),
    "student_status": FieldMetadata(
        field_name="student_status",
        display_name_en="Student Status",
        display_name_hi="विद्यार्थी स्थिति",
        data_type="boolean",
        sensitivity_level="LOW",
        example_question_en="Are you currently enrolled as a student?",
        example_question_hi="क्या आप वर्तमान में एक विद्यार्थी हैं?",
    ),
    "education_level": FieldMetadata(
        field_name="education_level",
        display_name_en="Education Level",
        display_name_hi="शिक्षा का स्तर",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="What is your highest level of completed education?",
        example_question_hi="आपकी उच्चतम शिक्षा का स्तर क्या है?",
    ),
    "marital_status": FieldMetadata(
        field_name="marital_status",
        display_name_en="Marital Status",
        display_name_hi="वैवाहिक स्थिति",
        data_type="select",
        sensitivity_level="LOW",
        example_question_en="What is your marital status?",
        example_question_hi="आपकी वैवाहिक स्थिति क्या है?",
    ),
    "family_income": FieldMetadata(
        field_name="family_income",
        display_name_en="Annual Family Income",
        display_name_hi="वार्षिक पारिवारिक आय",
        data_type="currency",
        sensitivity_level="MEDIUM",
        example_question_en="What is your total annual family income in rupees?",
        example_question_hi="आपके परिवार की कुल वार्षिक आय कितनी है?",
    ),
    "bpl_status": FieldMetadata(
        field_name="bpl_status",
        display_name_en="BPL Status",
        display_name_hi="बीपीएल स्थिति",
        data_type="boolean",
        sensitivity_level="MEDIUM",
        example_question_en="Does your family hold a Below Poverty Line (BPL) card?",
        example_question_hi="क्या आपका परिवार गरीबी रेखा से नीचे (बीपीएल) श्रेणी में है?",
    ),
    "widow_status": FieldMetadata(
        field_name="widow_status",
        display_name_en="Widow Status",
        display_name_hi="विधवा स्थिति",
        data_type="boolean",
        sensitivity_level="MEDIUM",
        example_question_en="Are you a widow?",
        example_question_hi="क्या आप विधवा हैं?",
    ),
    "social_category": FieldMetadata(
        field_name="social_category",
        display_name_en="Social Category",
        display_name_hi="सामाजिक श्रेणी",
        data_type="select",
        sensitivity_level="HIGH",
        example_question_en="What is your social category (e.g. General, SC, ST, OBC)?",
        example_question_hi="आपकी सामाजिक श्रेणी क्या है (जैसे सामान्य, अनुसूचित जाति, जनजाति, ओबीसी)?",
    ),
    "caste": FieldMetadata(
        field_name="caste",
        display_name_en="Caste",
        display_name_hi="जाति",
        data_type="string",
        sensitivity_level="HIGH",
        example_question_en="What is your caste/community?",
        example_question_hi="आपकी जाति/समुदाय क्या है?",
    ),
    "disability_status": FieldMetadata(
        field_name="disability_status",
        display_name_en="Disability Status",
        display_name_hi="दिव्यांगता स्थिति",
        data_type="boolean",
        sensitivity_level="HIGH",
        example_question_en="Do you or a family member have a recognized disability?",
        example_question_hi="क्या आप या परिवार का कोई सदस्य दिव्यांग है?",
    ),
    "disability_percentage": FieldMetadata(
        field_name="disability_percentage",
        display_name_en="Disability Percentage",
        display_name_hi="दिव्यांगता प्रतिशत",
        data_type="integer",
        sensitivity_level="HIGH",
        example_question_en="What is the certified disability percentage (if applicable)?",
        example_question_hi="प्रमाणित दिव्यांगता का प्रतिशत कितना है?",
    ),
}


def get_field_metadata(field_name: str) -> FieldMetadata:
    """Returns metadata for a canonical field or creates a safe fallback."""
    clean_f = field_name.strip()
    if clean_f in FIELD_METADATA_REGISTRY:
        return FIELD_METADATA_REGISTRY[clean_f]
    
    # Sensible fallback for custom or unlisted fields
    words = clean_f.replace("_", " ").title()
    return FieldMetadata(
        field_name=clean_f,
        display_name_en=words,
        display_name_hi=words,
        data_type="string",
        sensitivity_level="MEDIUM",
        example_question_en=f"Please provide your {words.lower()}.",
        example_question_hi=f"कृपया अपनी {words} की जानकारी दें।",
    )
