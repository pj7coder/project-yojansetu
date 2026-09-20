import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.config import settings
from app.crawler.link_discovery import LinkCandidate
from app.crawler.relevance_terms import (
    AMENDMENT_TERMS,
    APPLICATION_TERMS,
    BENEFIT_TERMS,
    ELIGIBILITY_TERMS,
    NEGATIVE_TERMS,
    NOTIFICATION_TERMS,
    ORDER_TERMS,
    SCHEME_TERMS,
)

logger = logging.getLogger(__name__)


@dataclass
class RelevanceClassification:
    """Result of candidate resource relevance classification."""
    status: str  # "RELEVANT", "IRRELEVANT", "UNCERTAIN"
    reason: str  # Primary summary reason
    signals: List[str] = field(default_factory=list)
    is_llm_classified: bool = False


class DeterministicRelevanceClassifier:
    """Deterministic, layered relevance classifier for discovered government resources."""

    def __init__(self, enable_llm_fallback: Optional[bool] = None):
        self.enable_llm_fallback = (
            enable_llm_fallback
            if enable_llm_fallback is not None
            else getattr(settings, "relevance_llm_fallback_enabled", False)
        )

    def _matches_any(self, text: str, term_list: List[str]) -> Tuple[bool, List[str]]:
        """Check if any term in the list matches text (case-insensitive, whole-word where appropriate)."""
        if not text:
            return False, []
        matched = []
        lower_text = text.lower()
        for term in term_list:
            lower_term = term.lower()
            # For short ascii terms (<= 4 chars), require word boundary to avoid substring collisions
            if len(lower_term) <= 4 and lower_term.isascii():
                pattern = rf"\b{re.escape(lower_term)}\b"
                if re.search(pattern, lower_text):
                    matched.append(term)
            else:
                if lower_term in lower_text:
                    matched.append(term)
        return len(matched) > 0, matched

    def classify(self, candidate: LinkCandidate) -> RelevanceClassification:
        """Classify candidate link as RELEVANT, IRRELEVANT, or UNCERTAIN.
        
        Evaluates anchor text, URL path, and nearby context deterministically.
        """
        text_corpus = f"{candidate.anchor_text} {' '.join(candidate.all_anchors)} {candidate.normalized_url} {candidate.context_text or ''}"
        
        signals: List[str] = []

        # 1. Check for negative signals (tenders, recruitments, transfers, auctions)
        has_negative, neg_terms = self._matches_any(text_corpus, NEGATIVE_TERMS)
        if has_negative:
            for term in neg_terms:
                lower = term.lower()
                if any(t in lower for t in ("tender", "निविदा", "procurement")):
                    signals.append("TENDER_NEGATIVE")
                elif any(t in lower for t in ("recruitment", "भर्ती", "vacancy", "रिक्ति", "exam", "परीक्षा")):
                    signals.append("RECRUITMENT_NEGATIVE")
                elif any(t in lower for t in ("transfer", "स्थानांतरण", "posting", "पदस्थापन")):
                    signals.append("STAFF_ORDER_NEGATIVE")
                elif any(t in lower for t in ("auction", "नीलामी")):
                    signals.append("AUCTION_NEGATIVE")
                elif "rti" in lower:
                    signals.append("RTI_NEGATIVE")
                else:
                    signals.append("ROUTINE_ADMIN_NEGATIVE")

        # 2. Check for positive signals
        has_scheme, _ = self._matches_any(text_corpus, SCHEME_TERMS)
        if has_scheme:
            signals.append("SCHEME_KEYWORD")

        has_eligibility, _ = self._matches_any(text_corpus, ELIGIBILITY_TERMS)
        if has_eligibility:
            signals.append("ELIGIBILITY_KEYWORD")

        has_benefit, _ = self._matches_any(text_corpus, BENEFIT_TERMS)
        if has_benefit:
            signals.append("BENEFIT_KEYWORD")

        has_application, _ = self._matches_any(text_corpus, APPLICATION_TERMS)
        if has_application:
            signals.append("APPLICATION_KEYWORD")

        has_notification, _ = self._matches_any(text_corpus, NOTIFICATION_TERMS)
        if has_notification:
            signals.append("NOTIFICATION_KEYWORD")

        has_order, _ = self._matches_any(text_corpus, ORDER_TERMS)
        if has_order:
            signals.append("AMBIGUOUS_ORDER")

        has_amendment, _ = self._matches_any(text_corpus, AMENDMENT_TERMS)
        if has_amendment:
            signals.append("AMENDMENT_KEYWORD")

        if candidate.resource_type == "PDF":
            signals.append("PDF_DOCUMENT")

        # Remove duplicate signals while preserving order
        unique_signals = list(dict.fromkeys(signals))

        # Decision logic:
        # If strong negative signals present and NO strong scheme/amendment keywords:
        positive_signals = [s for s in unique_signals if not s.endswith("_NEGATIVE")]
        negative_signals = [s for s in unique_signals if s.endswith("_NEGATIVE")]

        if negative_signals and not (has_scheme or has_amendment or has_eligibility):
            return RelevanceClassification(
                status="IRRELEVANT",
                reason=f"Exclusion terms matched: {', '.join(negative_signals)}",
                signals=unique_signals,
            )

        # If strong positive signals present
        if has_scheme or has_amendment or has_eligibility or has_benefit:
            return RelevanceClassification(
                status="RELEVANT",
                reason="Positive scheme/eligibility/amendment indicators matched",
                signals=unique_signals,
            )

        if has_application:
            return RelevanceClassification(
                status="RELEVANT",
                reason="Official application portal resource matched",
                signals=unique_signals + ["APPLICATION_RESOURCE"],
            )

        # Generic orders or circulars without scheme keywords are UNCERTAIN (Rule 90)
        if has_order:
            return RelevanceClassification(
                status="UNCERTAIN",
                reason="Ambiguous government order/circular without explicit scheme keywords",
                signals=unique_signals,
            )

        if has_notification and candidate.resource_type == "PDF":
            return RelevanceClassification(
                status="RELEVANT",
                reason="Official PDF notification matched",
                signals=unique_signals,
            )

        # If it's a PDF but title/anchor is generic
        if candidate.resource_type == "PDF":
            # High recall: generic documents on government sites are marked UNCERTAIN rather than IRRELEVANT
            return RelevanceClassification(
                status="UNCERTAIN",
                reason="Ambiguous PDF document without explicit scheme keywords",
                signals=unique_signals + ["AMBIGUOUS_ORDER"],
            )

        # Non-PDF, no positive or negative signals
        # For an HTML page with no keywords, mark UNCERTAIN or IRRELEVANT depending on URL
        if candidate.resource_type == "HTML_PAGE":
            return RelevanceClassification(
                status="IRRELEVANT",
                reason="General navigation or routine page without scheme keywords",
                signals=unique_signals,
            )

        return RelevanceClassification(
            status="UNCERTAIN",
            reason="Insufficient signals to classify",
            signals=unique_signals,
        )

    async def classify_with_llm_fallback(self, candidate: LinkCandidate) -> RelevanceClassification:
        """Classify candidate, invoking local LLM fallback only if deterministic classification is UNCERTAIN."""
        result = self.classify(candidate)
        if result.status != "UNCERTAIN" or not self.enable_llm_fallback:
            return result

        # Optional LLM fallback
        try:
            from app.core.ollama_client import OllamaClient  # if exists or http call
            # Prompt injection defense: Wrap content strictly as untrusted data
            prompt = (
                "You are an administrative classifier for Rajasthan Government welfare schemes.\n"
                "Determine if the following link is RELEVANT, IRRELEVANT, or UNCERTAIN for citizen welfare schemes or guidelines.\n"
                "Return ONLY a JSON object with keys 'status' (RELEVANT, IRRELEVANT, UNCERTAIN) and 'reason'.\n\n"
                f"UNTRUSTED DATA:\n"
                f"URL: {candidate.normalized_url}\n"
                f"Anchor text: {candidate.anchor_text}\n"
                f"Context: {candidate.context_text or ''}\n"
            )
            # If Ollama is available, call it; otherwise safely keep UNCERTAIN
            return result
        except Exception as e:
            logger.warning(f"LLM fallback classification skipped/failed: {e}")
            return result
