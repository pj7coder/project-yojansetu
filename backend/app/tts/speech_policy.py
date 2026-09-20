"""
YojanSetu - Day 26: Conversation Speech Policy.

Transforms structured Day 25 ConversationResponse objects into concise,
citizen-friendly speakable text according to action types and privacy policies.

Guarantees:
- Conversation action, state machine, and response DTO are NEVER altered.
- Long scheme/document lists are never spoken in full; concise summaries are voiced.
- Distinguishes generic prompts (cacheable) from sensitive profile messages (never cached).
"""

from typing import Optional
from pydantic import BaseModel, Field

from app.conversation.actions import ConversationAction
from app.conversation.schemas import ConversationResponse
from app.tts.speech_normalizer import SpeechTextNormalizer


class SpeakableTurn(BaseModel):
    """
    Representation of text ready for speech rendering.
    Maintains clean separation between visual presentation and acoustic output.
    """
    display_text: str = Field(description="Raw canonical display text shown on citizen screen")
    speech_text: str = Field(description="Phonetically normalized text to be spoken by TTS")
    language: str = Field(default="hi", description="Spoken language ('hi' or 'en')")
    is_generic: bool = Field(default=False, description="True if prompt is generic and safe for disk cache")
    action: ConversationAction = Field(description="Source conversation action")


# Set of generic prompt keys from ConversationMessageCatalog that are static and non-sensitive
GENERIC_MESSAGE_KEYS = {
    "WELCOME_GREETING",
    "ASK_NEED",
    "RECONFIRM_PROMPT",
    "REPEAT_PROMPT",
    "DEFAULT_PRIVACY_NOTE",
    "NO_RESULTS",
    "CANNOT_RESOLVE",
    "GENERIC_ERROR",
    "NETWORK_ERROR",
    "FALLBACK_RECOVERY",
}


class ConversationSpeechPolicy:
    """
    Orchestrates the conversion of Day 25 ConversationResponse into speakable turns.
    """

    @classmethod
    def get_speakable_turn(
        cls,
        response: ConversationResponse,
        preferred_language: Optional[str] = None
    ) -> SpeakableTurn:
        """
        Extracts and prepares speakable text from a ConversationResponse without mutating it.
        """
        lang = preferred_language or response.meta.language or "hi"
        action = response.action

        # Extract base display text
        if lang == "en":
            raw_display = response.message.text_en or response.message.text_hi
        else:
            raw_display = response.message.text_hi

        # Determine caching eligibility
        # Only static prompts with no citizen-specific values can be cached
        is_generic = (
            response.message.key in GENERIC_MESSAGE_KEYS
            or action in {ConversationAction.ASK_NEED, ConversationAction.REPEAT_PROMPT}
        )

        # Policy by action
        if action == ConversationAction.SHOW_RESULTS:
            # Rule 31: Do NOT dump exhaustive scheme details into TTS.
            # Speak a concise overview summary.
            is_generic = False
            results = response.results
            schemes_list = []
            if results:
                if hasattr(results, "eligible") and results.eligible:
                    schemes_list = results.eligible
                elif hasattr(results, "schemes") and getattr(results, "schemes"):
                    schemes_list = results.schemes
                elif hasattr(results, "more_information_required") and results.more_information_required:
                    schemes_list = results.more_information_required

            total = len(schemes_list)

            if lang == "en":
                if total == 1:
                    first_title = getattr(schemes_list[0], "name_en", None) or getattr(schemes_list[0], "scheme_name", "Scheme")
                    speakable = f"Based on your details, 1 eligible scheme was found: {first_title}. Details are on your screen."
                elif total > 1:
                    first_title = getattr(schemes_list[0], "name_en", None) or getattr(schemes_list[0], "scheme_name", "Scheme")
                    speakable = f"Based on your details, {total} eligible schemes were found. The first scheme is {first_title}. Full details are displayed on screen."
                else:
                    speakable = raw_display
            else:
                if total == 1:
                    first_title = getattr(schemes_list[0], "name_hi", None) or getattr(schemes_list[0], "scheme_name_hi", None) or getattr(schemes_list[0], "name_en", "योजना")
                    speakable = f"आपकी जानकारी के आधार पर 1 उपयुक्त योजना मिली है: {first_title}। विवरण स्क्रीन पर उपलब्ध है।"
                elif total > 1:
                    first_title = getattr(schemes_list[0], "name_hi", None) or getattr(schemes_list[0], "scheme_name_hi", None) or getattr(schemes_list[0], "name_en", "योजना")
                    speakable = f"आपकी जानकारी के आधार पर {total} उपयुक्त योजनाएँ मिली हैं। पहली योजना {first_title} से संबंधित है। पूरी सूची स्क्रीन पर उपलब्ध है।"
                else:
                    speakable = raw_display

            display_text = raw_display
            speech_text = SpeechTextNormalizer.normalize_for_speech(speakable)

        elif action == ConversationAction.CONFIRM_PROFILE_VALUE:
            # Rule 61, 62: Confirmation messages contain sensitive numbers/values.
            # Must NEVER be cached in generic cache.
            is_generic = False
            display_text = raw_display
            speech_text = SpeechTextNormalizer.normalize_for_speech(raw_display)

        elif action == ConversationAction.ASK_PROFILE_FIELD:
            # Questions may be generic if they don't include dynamic personalized values
            display_text = raw_display
            speech_text = SpeechTextNormalizer.normalize_for_speech(raw_display)
            # If the question does not contain citizen specific values, it can be cached
            if not any(token in raw_display for token in ["₹", "वर्ष बताई", "आय बताई"]):
                is_generic = True

        else:
            # Default policy: Speak message directly with deterministic normalization
            display_text = raw_display
            speech_text = SpeechTextNormalizer.normalize_for_speech(raw_display)

        return SpeakableTurn(
            display_text=display_text,
            speech_text=speech_text,
            language=lang,
            is_generic=is_generic,
            action=action,
        )
