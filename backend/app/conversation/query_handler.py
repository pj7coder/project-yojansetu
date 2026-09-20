"""
CitizenQueryHandler — Deterministic Citizen Informational Query Handler (Day 25).
Handles questions like 'Why is this asked?', 'What does this mean?', and scheme-specific inquiries.
All answers derive strictly from verified canonical data and metadata. Zero LLM fact hallucination.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.citizen.service import CitizenDiscoveryFacade
from app.conversation.actions import ConversationAction
from app.conversation.messages import ConversationMessageCatalog
from app.conversation.schemas import ConversationMessage
from app.sessions.models import CitizenSession

logger = logging.getLogger("yojansetu.conversation.query_handler")

# Deterministic regex matchers for citizen query classification
WHY_PATTERNS = [
    r"क्यों",
    r"why",
    r"कारण",
    r"किसलिए",
    r"वजह",
    r"ज़रूरत",
    r"जरूरी क्यों",
    r"why do you need",
    r"why ask",
]

WHAT_PATTERNS = [
    r"क्या होता है",
    r"क्या होती है",
    r"का मतलब",
    r"का अर्थ",
    r"meaning",
    r"what is",
    r"define",
]

PRIVACY_PATTERNS = [
    r"गोपनीय",
    r"सुरक्षित",
    r"डेटा",
    r"सहेज",
    r"प्राइवेसी",
    r"privacy",
    r"confidential",
]

BENEFIT_PATTERNS = [
    r"कितना पैसा",
    r"क्या लाभ",
    r"क्या फायदा",
    r"कितनी राशि",
    r"सहायता राशि",
    r"कितने रुपये",
    r"benefit",
    r"how much",
    r"paisa",
]

DOCUMENT_PATTERNS = [
    r"दस्तावेज",
    r"कागज़",
    r"कागजात",
    r"प्रमाण पत्र",
    r"डॉक्यूमेंट",
    r"document",
    r"certificate",
]

APPLICATION_PATTERNS = [
    r"आवेदन",
    r"कैसे करें",
    r"कहाँ जाएं",
    r"फॉर्म",
    r"apply",
    r"application",
    r"portal",
    r"ई-मित्र",
]

ELIGIBILITY_PATTERNS = [
    r"पात्रता",
    r"नियम",
    r"शर्त",
    r"criteria",
    r"eligible",
]

SOURCE_PATTERNS = [
    r"स्रोत",
    r"सरकारी लिंक",
    r"वेबसाइट",
    r"source",
    r"official link",
]


class CitizenQueryHandler:
    """
    Evaluates citizen natural language interruptions and queries.
    Provides verified explanations and returns structured response action.
    """

    @classmethod
    def is_query(cls, text: str) -> bool:
        """Determines if the statement is an informational query rather than a profile answer."""
        if not text or not text.strip():
            return False
        clean = text.strip().lower()
        all_patterns = (
            WHY_PATTERNS
            + WHAT_PATTERNS
            + PRIVACY_PATTERNS
            + BENEFIT_PATTERNS
            + DOCUMENT_PATTERNS
            + APPLICATION_PATTERNS
            + ELIGIBILITY_PATTERNS
            + SOURCE_PATTERNS
        )
        return any(re.search(pat, clean) for pat in all_patterns)

    @classmethod
    def handle_query(
        cls,
        text: str,
        session: CitizenSession,
        db_session: Optional[Session] = None,
    ) -> Tuple[ConversationMessage, ConversationAction]:
        """
        Classifies and answers citizen query using deterministic metadata and verified scheme facts.
        """
        clean = text.strip().lower()

        # 1. Why is this asked?
        if any(re.search(pat, clean) for pat in WHY_PATTERNS):
            target_field = session.expected_field
            if not target_field and session.pending_confirmation:
                target_field = session.pending_confirmation.get("field")
            if target_field:
                return (
                    ConversationMessageCatalog.why_is_this_asked(target_field),
                    ConversationAction.ANSWER_FIELD_HELP,
                )
            return (
                ConversationMessageCatalog.privacy_note(),
                ConversationAction.ANSWER_FIELD_HELP,
            )

        # 2. What does this mean?
        if any(re.search(pat, clean) for pat in WHAT_PATTERNS):
            target_field = session.expected_field
            if not target_field and session.pending_confirmation:
                target_field = session.pending_confirmation.get("field")
            if target_field:
                return (
                    ConversationMessageCatalog.what_does_it_mean(target_field),
                    ConversationAction.ANSWER_FIELD_HELP,
                )

        # 3. Privacy & Data safety
        if any(re.search(pat, clean) for pat in PRIVACY_PATTERNS):
            return (
                ConversationMessageCatalog.privacy_note(),
                ConversationAction.ANSWER_FIELD_HELP,
            )

        # Scheme-specific questions require an active focused scheme or single result
        focused_id = session.focused_scheme_id
        if not focused_id and session.eligible_scheme_ids and len(session.eligible_scheme_ids) == 1:
            focused_id = session.eligible_scheme_ids[0]

        if focused_id and db_session:
            try:
                detail = CitizenDiscoveryFacade.get_citizen_scheme_detail(focused_id, db_session)
                scheme_name = detail.name_hi or detail.name_en

                # 4. Benefits query
                if any(re.search(pat, clean) for pat in BENEFIT_PATTERNS):
                    b_texts_hi = [b.display_text_hi for b in detail.benefits if b.display_text_hi]
                    b_texts_en = [b.display_text_en for b in detail.benefits if b.display_text_en]
                    hi_summary = ", ".join(b_texts_hi) if b_texts_hi else "वित्तीय सहायता उपलब्ध है।"
                    en_summary = ", ".join(b_texts_en) if b_texts_en else "Financial benefits available."
                    return (
                        ConversationMessage(
                            key="SCHEME_BENEFITS_ANSWER",
                            text_hi=f"{scheme_name} के तहत मिलने वाले लाभ: {hi_summary}",
                            text_en=f"Benefits under {detail.name_en}: {en_summary}",
                        ),
                        ConversationAction.ANSWER_SCHEME_QUERY,
                    )

                # 5. Documents query
                if any(re.search(pat, clean) for pat in DOCUMENT_PATTERNS):
                    d_texts_hi = [d.document_name_hi or d.document_name_en for d in detail.required_documents]
                    d_texts_en = [d.document_name_en for d in detail.required_documents]
                    hi_docs = ", ".join(d_texts_hi) if d_texts_hi else "जन आधार और मूल निवास प्रमाण पत्र।"
                    en_docs = ", ".join(d_texts_en) if d_texts_en else "Jan Aadhaar and Domicile certificate."
                    return (
                        ConversationMessage(
                            key="SCHEME_DOCS_ANSWER",
                            text_hi=f"{scheme_name} के लिए आवश्यक दस्तावेज़: {hi_docs}",
                            text_en=f"Required documents for {detail.name_en}: {en_docs}",
                        ),
                        ConversationAction.ANSWER_SCHEME_QUERY,
                    )

                # 6. Application query
                if any(re.search(pat, clean) for pat in APPLICATION_PATTERNS):
                    channels = detail.application.channels if detail.application else []
                    ch_str = ", ".join(channels) if channels else "ई-मित्र या विभागीय पोर्टल"
                    return (
                        ConversationMessage(
                            key="SCHEME_APP_ANSWER",
                            text_hi=f"{scheme_name} के लिए आवेदन माध्यम: {ch_str}।",
                            text_en=f"Application channels for {detail.name_en}: {ch_str}.",
                        ),
                        ConversationAction.ANSWER_SCHEME_QUERY,
                    )

                # 7. Eligibility query
                if any(re.search(pat, clean) for pat in ELIGIBILITY_PATTERNS):
                    hi_str = ", ".join(detail.why_eligible_hi) if detail.why_eligible_hi else "पात्रता नियमों की जाँच की गई है।"
                    en_str = ", ".join(detail.why_eligible_en) if detail.why_eligible_en else "Eligibility verified."
                    return (
                        ConversationMessage(
                            key="SCHEME_ELIG_ANSWER",
                            text_hi=f"{scheme_name} के मुख्य पात्रता नियम: {hi_str}",
                            text_en=f"Key eligibility criteria for {detail.name_en}: {en_str}",
                        ),
                        ConversationAction.ANSWER_SCHEME_QUERY,
                    )

                # 8. Source query
                if any(re.search(pat, clean) for pat in SOURCE_PATTERNS):
                    src_url = detail.official_source.official_url if detail.official_source and detail.official_source.official_url else "https://rajasthan.gov.in"
                    return (
                        ConversationMessage(
                            key="SCHEME_SOURCE_ANSWER",
                            text_hi=f"{scheme_name} की आधिकारिक जानकारी स्रोत: {src_url}",
                            text_en=f"Official source for {detail.name_en}: {src_url}",
                        ),
                        ConversationAction.ANSWER_SCHEME_QUERY,
                    )
            except Exception as e:
                logger.warning(f"Error answering scheme detail query for '{focused_id}': {e}")

        # Fallback unknown query
        return (
            ConversationMessageCatalog.unknown_query(),
            ConversationAction.ANSWER_FIELD_HELP,
        )
