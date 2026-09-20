"""
Deterministic Bilingual Message Catalog for YojanSetu Conversation Manager (Day 25).
Pure plain text; no HTML. Standardized for presentation and Day 26 TTS generation.
"""

from typing import Any, Dict, Optional
from app.conversation.schemas import ConversationMessage


FIELD_GLOSSARY: Dict[str, Dict[str, str]] = {
    "age": {
        "name_hi": "आयु",
        "name_en": "Age",
        "why_hi": "वृद्धावस्था पेंशन, छात्रवृत्ति और युवा रोजगार जैसी कई योजनाओं में आयु सीमा की शर्त होती है।",
        "why_en": "Many schemes like old age pension, scholarships, and youth schemes have specific age criteria.",
        "definition_hi": "आयु का अर्थ है आपकी पूर्ण हो चुकी आयु वर्षों में।",
        "definition_en": "Age refers to your completed years of age.",
    },
    "family_income": {
        "name_hi": "वार्षिक पारिवारिक आय",
        "name_en": "Annual Family Income",
        "why_hi": "कल्याणकारी योजनाओं में आर्थिक सीमा निर्धारित होती है ताकि जरूरतमंद परिवारों को लाभ मिल सके।",
        "why_en": "Welfare schemes define income limits to target benefits to families in financial need.",
        "definition_hi": "परिवार के सभी कमाने वाले सदस्यों की सभी स्रोतों से कुल वार्षिक आय।",
        "definition_en": "Total combined annual income of all earning family members from all sources.",
    },
    "district": {
        "name_hi": "जिला",
        "name_en": "District",
        "why_hi": "कुछ योजनाएं विशेष रूप से विशिष्ट जिलों या आदिवासी/मरुस्थलीय क्षेत्रों के लिए होती हैं।",
        "why_en": "Certain schemes are specifically targeted to particular districts or tribal/desert areas.",
        "definition_hi": "राजस्थान का वह जिला जहाँ आपका स्थायी निवास है।",
        "definition_en": "The district in Rajasthan where you permanently reside.",
    },
    "bpl_status": {
        "name_hi": "बीपीएल स्थिति",
        "name_en": "BPL Status",
        "why_hi": "बीपीएल परिवारों को कई सरकारी योजनाओं में प्राथमिकता या विशेष सहायता दी जाती है।",
        "why_en": "Below Poverty Line (BPL) families receive prioritized or specialized welfare assistance.",
        "definition_hi": "क्या आपका परिवार राज्य सरकार द्वारा जारी बीपीएल सूची या राशन कार्ड में शामिल है।",
        "definition_en": "Whether your family holds a valid Below Poverty Line (BPL) card/status.",
    },
    "social_category": {
        "name_hi": "सामाजिक श्रेणी (जाति वर्ग)",
        "name_en": "Social Category",
        "why_hi": "अनुसूचित जाति (SC), जनजाति (ST), अन्य पिछड़ा वर्ग (OBC) और EWS के लिए विशेष कल्याण योजनाएं हैं।",
        "why_en": "Special welfare schemes exist for SC, ST, OBC, MBC, and EWS categories.",
        "definition_hi": "आपकी संवैधानिक सामाजिक श्रेणी जैसे सामान्य, ओबीसी, एससी, एसटी या ईडब्ल्यूएस।",
        "definition_en": "Your official social category such as General, OBC, SC, ST, MBC, or EWS.",
    },
    "gender": {
        "name_hi": "लिंग",
        "name_en": "Gender",
        "why_hi": "महिला सशक्तिकरण, कन्या विवाह और प्रसूति सहायता योजनाएं विशेष रूप से महिलाओं के लिए हैं।",
        "why_en": "Schemes for women empowerment, marriage assistance, and maternity benefits require gender information.",
        "definition_hi": "महिला, पुरुष या अन्य।",
        "definition_en": "Female, Male, or Other.",
    },
    "occupation": {
        "name_hi": "व्यवसाय / कार्य",
        "name_en": "Occupation",
        "why_hi": "किसान, निर्माण श्रमिक, बुनकर और विद्यार्थियों के लिए अलग-अलग विशिष्ट योजनाएं उपलब्ध हैं।",
        "why_en": "Distinct welfare schemes are tailored specifically for farmers, daily-wage labourers, artisans, and students.",
        "definition_hi": "आपकी आजीविका का मुख्य कार्य जैसे खेती, मजदूरी, व्यापार या अध्ययन।",
        "definition_en": "Your primary livelihood activity such as farming, labour, business, or studies.",
    },
    "disability_status": {
        "name_hi": "दिव्यांगता स्थिति",
        "name_en": "Disability Status",
        "why_hi": "विशेष योग्यजन पेंशन, सहायक उपकरण और आरक्षण लाभ के लिए दिव्यांगता की जानकारी आवश्यक है।",
        "why_en": "Disability pension, assistive equipment, and special benefits require disability verification.",
        "definition_hi": "क्या आपके पास 40% या अधिक का सक्षम प्राधिकारी द्वारा जारी दिव्यांगता प्रमाण पत्र है।",
        "definition_en": "Whether you hold a recognized disability certificate of 40% or higher.",
    },
    "land_holding": {
        "name_hi": "कृषि भूमि",
        "name_en": "Agricultural Land Holding",
        "why_hi": "लघु और सीमांत कृषक सहायता योजनाओं में भूमि सीमा की शर्त होती है।",
        "why_en": "Small and marginal farmer subsidy schemes depend on the extent of agricultural land owned.",
        "definition_hi": "आपके परिवार के स्वामित्व वाली कुल कृषि योग्य भूमि का आकार।",
        "definition_en": "Total size of cultivable agricultural land owned by your family.",
    },
}

DEFAULT_PRIVACY_NOTE_HI = "यह जानकारी केवल इस अस्थायी सत्र में योजनाओं की पात्रता जाँचने के लिए उपयोग की जाती है और इसे स्थायी रूप से सहेजा नहीं जाता।"
DEFAULT_PRIVACY_NOTE_EN = "This information is used strictly within this temporary session to evaluate scheme eligibility and is never permanently stored."


class ConversationMessageCatalog:
    """
    Central repository of plain-text vernacular system prompts and messages.
    """

    @classmethod
    def get_field_info(cls, field_name: str) -> Dict[str, str]:
        """Retrieves localized display names and explanations for a profile field."""
        clean = field_name.strip().lower() if field_name else ""
        if clean in FIELD_GLOSSARY:
            return FIELD_GLOSSARY[clean]
        return {
            "name_hi": field_name,
            "name_en": field_name,
            "why_hi": f"{field_name} की जानकारी कुछ योजनाओं की पात्रता नियम जाँचने के लिए आवश्यक है।",
            "why_en": f"{field_name} is required to check eligibility criteria for schemes.",
            "definition_hi": f"{field_name} से संबंधित विवरण।",
            "definition_en": f"Details regarding {field_name}.",
        }

    @classmethod
    def ask_need(cls) -> ConversationMessage:
        return ConversationMessage(
            key="ASK_NEED",
            text_hi="नमस्ते! आपको किस प्रकार की सहायता या सरकारी योजना चाहिए? जैसे: पेंशन, छात्रवृत्ति, कृषि सहायता, या राशन।",
            text_en="Hello! What kind of assistance or government scheme are you looking for? For example: pension, scholarship, farming aid, or ration.",
        )

    @classmethod
    def confirm_value(
        cls,
        field_name: str,
        display_value: str,
        is_correction: bool = False,
        old_value: Optional[str] = None,
    ) -> ConversationMessage:
        f_info = cls.get_field_info(field_name)
        hi_name = f_info.get("name_hi", field_name)
        en_name = f_info.get("name_en", field_name)

        if is_correction and old_value:
            return ConversationMessage(
                key="CONFIRM_CORRECTION",
                text_hi=f"आपने पहले {hi_name} {old_value} बताई थी। क्या इसे बदलकर {display_value} करना है?",
                text_en=f"You previously stated {en_name} as {old_value}. Would you like to change it to {display_value}?",
            )
        return ConversationMessage(
            key="CONFIRM_PROFILE_VALUE",
            text_hi=f"आपने अपनी {hi_name} {display_value} बताई है। क्या यह सही है?",
            text_en=f"You stated your {en_name} as {display_value}. Is this correct?",
        )

    @classmethod
    def confirm_rejected(cls, field_name: str) -> ConversationMessage:
        f_info = cls.get_field_info(field_name)
        hi_name = f_info.get("name_hi", field_name)
        en_name = f_info.get("name_en", field_name)
        return ConversationMessage(
            key="CONFIRM_REJECTED",
            text_hi=f"ठीक है, इसे दर्ज नहीं किया गया है। कृपया अपनी सही {hi_name} बताएं।",
            text_en=f"Understood, this was not recorded. Please provide your correct {en_name}.",
        )

    @classmethod
    def clarify_value(cls, field_name: str, hint: Optional[str] = None) -> ConversationMessage:
        f_info = cls.get_field_info(field_name)
        hi_name = f_info.get("name_hi", field_name)
        en_name = f_info.get("name_en", field_name)

        if field_name in ("family_income", "annual_income"):
            return ConversationMessage(
                key="CLARIFY_RANGE_INCOME",
                text_hi="आपने आय का अनुमान बताया है। कृपया लगभग कुल वार्षिक राशि बताएं (जैसे: ₹1,50,000)।",
                text_en="You provided an estimated range. Please specify an approximate total annual amount (e.g. ₹1,50,000).",
            )

        hint_hi = f" (जैसे: {hint})" if hint else ""
        hint_en = f" (e.g. {hint})" if hint else ""
        return ConversationMessage(
            key="CLARIFY_PROFILE_VALUE",
            text_hi=f"कृपया {hi_name} की स्पष्ट जानकारी दें{hint_hi}।",
            text_en=f"Please provide a clearer answer for {en_name}{hint_en}.",
        )

    @classmethod
    def show_results(cls, count: int) -> ConversationMessage:
        return ConversationMessage(
            key="SHOW_RESULTS",
            text_hi=f"आपकी जानकारी के आधार पर आपके लिए {count} योजनाएँ उपयुक्त मिली हैं।",
            text_en=f"Based on your information, {count} eligible schemes were found for you.",
        )

    @classmethod
    def show_no_results(cls) -> ConversationMessage:
        return ConversationMessage(
            key="SHOW_NO_RESULTS",
            text_hi="दी गई जानकारी के आधार पर अभी कोई सत्यापित योजना नहीं मिली। आप अपनी आवश्यकता बदलकर फिर से खोज सकते हैं।",
            text_en="No verified schemes matching your criteria were found. You can try adjusting your stated need.",
        )

    @classmethod
    def show_cannot_resolve(cls) -> ConversationMessage:
        return ConversationMessage(
            key="SHOW_CANNOT_RESOLVE",
            text_hi="कुछ योजनाओं की पात्रता जाँचने के लिए आवश्यक जानकारी उपलब्ध नहीं हो पाई।",
            text_en="Additional required information was not available to determine eligibility for remaining schemes.",
        )

    @classmethod
    def why_is_this_asked(cls, field_name: str) -> ConversationMessage:
        f_info = cls.get_field_info(field_name)
        return ConversationMessage(
            key="FIELD_WHY_ASKED",
            text_hi=f"{f_info['why_hi']} {DEFAULT_PRIVACY_NOTE_HI}",
            text_en=f"{f_info['why_en']} {DEFAULT_PRIVACY_NOTE_EN}",
        )

    @classmethod
    def what_does_it_mean(cls, field_name: str) -> ConversationMessage:
        f_info = cls.get_field_info(field_name)
        return ConversationMessage(
            key="FIELD_WHAT_IT_MEANS",
            text_hi=f"{f_info['name_hi']}: {f_info['definition_hi']}",
            text_en=f"{f_info['name_en']}: {f_info['definition_en']}",
        )

    @classmethod
    def privacy_note(cls) -> ConversationMessage:
        return ConversationMessage(
            key="PRIVACY_NOTE",
            text_hi=DEFAULT_PRIVACY_NOTE_HI,
            text_en=DEFAULT_PRIVACY_NOTE_EN,
        )

    @classmethod
    def start_over(cls) -> ConversationMessage:
        return ConversationMessage(
            key="START_OVER",
            text_hi="सत्र पुनः प्रारंभ कर दिया गया है। आपको किस प्रकार की योजना या सहायता चाहिए?",
            text_en="Session has been reset. What kind of scheme or assistance are you looking for?",
        )

    @classmethod
    def completed(cls) -> ConversationMessage:
        return ConversationMessage(
            key="COMPLETED",
            text_hi="योजनसेतु का उपयोग करने के लिए धन्यवाद! आपकी बातचीत समाप्त हो गई है।",
            text_en="Thank you for using YojanSetu! Your conversation is completed.",
        )

    @classmethod
    def max_turns(cls) -> ConversationMessage:
        return ConversationMessage(
            key="MAX_TURNS",
            text_hi="बातचीत की अधिकतम सीमा पूरी हो गई है। कृपया नई खोज के लिए पुनः प्रारंभ करें।",
            text_en="Maximum conversation turns reached. Please start over to begin a new search.",
        )

    @classmethod
    def unknown_query(cls) -> ConversationMessage:
        return ConversationMessage(
            key="UNKNOWN_QUERY",
            text_hi="मैं इस प्रश्न का उत्तर देने में असमर्थ हूँ। कृपया चल रही प्रक्रिया से संबंधित जानकारी दें।",
            text_en="I could not answer that query. Please continue with the ongoing question.",
        )

    @classmethod
    def processing_error(cls, message_en: Optional[str] = None) -> ConversationMessage:
        return ConversationMessage(
            key="PROCESSING_ERROR",
            text_hi="तकनीकी समस्या के कारण यह प्रक्रिया पूर्ण नहीं हो सकी। कृपया पुनः प्रयास करें।",
            text_en=message_en or "A temporary processing issue occurred. Please try again.",
        )
