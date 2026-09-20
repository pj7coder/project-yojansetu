import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.versioning.schemas import GovernmentReference


class GovernmentReferenceExtractor:
    """
    Deterministic extractor for official Rajasthan government citations,
    notification/order/circular numbers, clause references, dates, and relationship phrases.
    """

    # 1. Official Document Numbers
    NOTIFICATION_PATTERNS = [
        # Hindi: अधिसूचना / आदेश / परिपत्र क्रमांक
        re.compile(r"(?:अधिसूचना|शासनादेश|आदेश|परिपत्र|विज्ञप्ति)\s*(?:क्रमांक|संख्या|क्र\.)\s*[:\.]?\s*([A-Za-z0-9\/\-\.\(\)\_\s]+?)(?=\s+(?:दिनांक|dated|द्वारा|\n|$))", re.IGNORECASE),
        re.compile(r"(?:फा\.|प\.)\s*\d+\s*\([^\)]+\)\s*[^\n,]+", re.IGNORECASE),
        # English: Notification No., Order No., Circular No., F. No.
        re.compile(r"(?:Notification|Order|Circular|Gazette\s+Notification|F\.?\s*No\.?)\s*(?:No\.?|Number|Ref\.?)?\s*[:\.]?\s*([A-Za-z0-9\/\-\.\(\)\_\s]+?)(?=\s+(?:dated|दिनांक|dt\.|\n|$))", re.IGNORECASE),
        re.compile(r"(?:No\.|Ref\.)\s*[:\.]?\s*([A-Z0-9]+[\/\-][A-Za-z0-9\/\-\.]+)", re.IGNORECASE),
    ]

    # 2. Relationship / Action Signals
    SUPERSEDES_PATTERNS = [
        re.compile(r"in\s+supersession\s+of(?:\s+all\s+previous\s+orders)?", re.IGNORECASE),
        re.compile(r"(?:पूर्व\s+आदेश|पूर्व\s+अधिसूचना)\s*(?:के\s+)?अधिक्रमण\s+में", re.IGNORECASE),
        re.compile(r"(?:के\s+)?अधिक्रमण\s+में\s+प्रत्यादिष्ट", re.IGNORECASE),
        re.compile(r"supersed(?:es|ed|ing)\s+(?:order|notification)?", re.IGNORECASE),
    ]

    CORRIGENDUM_PATTERNS = [
        re.compile(r"(?:shall\s+be\s+read\s+as|to\s+be\s+read\s+as)", re.IGNORECASE),
        re.compile(r"(?:शुद्धिपत्र|शुद्धि-पत्र|corrigendum|erratum)", re.IGNORECASE),
        re.compile(r"के\s+स्थान\s+पर\s+(?:पढ़ा|समझा)\s+जावे", re.IGNORECASE),
    ]

    AMENDMENT_PATTERNS = [
        re.compile(r"(?:amendment|amended|hereby\s+amends?|partial\s+modification)", re.IGNORECASE),
        re.compile(r"(?:संशोधन|संशोधित|आंशिक\s+संशोधन)", re.IGNORECASE),
        re.compile(r"shall\s+be\s+substituted", re.IGNORECASE),
        re.compile(r"(?:प्रतिस्थापित\s+किया\s+जाता\s+है|प्रतिस्थापित\s+करते\s+हुए)", re.IGNORECASE),
        re.compile(r"के\s+स्थान\s+पर\s+प्रतिस्थापित", re.IGNORECASE),
    ]

    ADDENDUM_PATTERNS = [
        re.compile(r"(?:addendum|supplementary\s+guideline|addition\s+to)", re.IGNORECASE),
        re.compile(r"(?:परिशिष्ट|अनुपूरक|अतिरिक्त\s+दिशा-निर्देश)", re.IGNORECASE),
        re.compile(r"shall\s+be\s+inserted", re.IGNORECASE),
        re.compile(r"के\s+पश्चात\s+जोड़ा\s+जाता\s+है", re.IGNORECASE),
    ]

    CLARIFICATION_PATTERNS = [
        re.compile(r"(?:clarification|clarified|for\s+the\s+removal\s+of\s+doubt)", re.IGNORECASE),
        re.compile(r"(?:स्पष्टीकरण|स्थिति\s+स्पष्ट\s+की\s+जाती\s+है|संशय\s+निवारण)", re.IGNORECASE),
    ]

    EXTENDS_PATTERNS = [
        re.compile(r"(?:deadline\s+extended|validity\s+extended|last\s+date\s+is\s+extended|extended\s+up\s+to|extended\s+from)", re.IGNORECASE),
        re.compile(r"(?:अंतिम\s+तिथि\s+बढ़ाई\s+जाती\s+है|अवधि\s+विस्तार|तिथि\s+विस्तार|बढ़ाकर)", re.IGNORECASE),
    ]

    # 3. Clause / Rule references
    CLAUSE_PATTERNS = [
        re.compile(r"(?:Clause|Rule|Section|Para|Paragraph|Annexure|कंडिका|पैरा|नियम|धारा|बिंदु\s*संख्या)\s*[:\.]?\s*([0-9]+(?:\([a-zA-Z0-9ivxLCDM]+\))*)", re.IGNORECASE),
    ]

    # 4. Effective Date Patterns
    EFFECTIVE_DATE_PATTERNS = [
        re.compile(r"(?:with\s+effect\s+from|effective\s+from|w\.e\.f\.?)\s*[:\.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})", re.IGNORECASE),
        re.compile(r"दिनांक\s*[:\.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\s*से\s+प्रभावी", re.IGNORECASE),
        re.compile(r"प्रभावी\s+दिनांक\s*[:\.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", re.IGNORECASE),
        re.compile(r"(?:shall\s+come\s+into\s+force\s+on|takes\s+effect\s+on)\s*[:\.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})", re.IGNORECASE),
    ]

    # 5. Publication / Document Date Patterns
    PUB_DATE_PATTERNS = [
        re.compile(r"(?:दिनांक|दि\.|Dated?|Dt\.?)\s*[:\.]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", re.IGNORECASE),
        re.compile(r"(?:Dated?|Dt\.?)\s*[:\.]?\s*(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})", re.IGNORECASE),
    ]

    def extract_references(
        self,
        text: str,
        page_number: Optional[int] = None,
        chunk_id: Optional[str] = None,
        block_id: Optional[str] = None,
    ) -> List[GovernmentReference]:
        """
        Extract all structured government references from a text block.
        """
        results: List[GovernmentReference] = []
        seen_numbers = set()

        # 1. Notification / Order numbers
        for pattern in self.NOTIFICATION_PATTERNS:
            for match in pattern.finditer(text):
                raw_ref = match.group(1).strip() if match.groups() else match.group(0).strip()
                # Clean up punctuation and trailing whitespace
                clean_ref = re.sub(r"[\s\:\,\.]+$", "", raw_ref).strip()
                if len(clean_ref) >= 3 and clean_ref not in seen_numbers:
                    seen_numbers.add(clean_ref)
                    results.append(
                        GovernmentReference(
                            reference_type="NOTIFICATION",
                            reference_number=clean_ref,
                            raw_text=match.group(0).strip(),
                            page_number=page_number,
                            chunk_id=chunk_id,
                            block_id=block_id,
                        )
                    )

        # 2. Clause references
        for pattern in self.CLAUSE_PATTERNS:
            for match in pattern.finditer(text):
                clause_num = match.group(1).strip()
                results.append(
                    GovernmentReference(
                        reference_type="CLAUSE",
                        clause_reference=clause_num,
                        raw_text=match.group(0).strip(),
                        page_number=page_number,
                        chunk_id=chunk_id,
                        block_id=block_id,
                    )
                )

        return results

    def detect_relationship_signals(self, text: str) -> Dict[str, List[Tuple[str, str]]]:
        """
        Detect relationship signal occurrences:
        Returns mapping of signal_type -> list of (matched_text, snippet).
        """
        signals: Dict[str, List[Tuple[str, str]]] = {
            "SUPERSEDES": [],
            "CORRIGENDUM": [],
            "AMENDS": [],
            "ADDENDUM": [],
            "CLARIFIES": [],
            "EXTENDS": [],
        }

        def _check(patterns, signal_key):
            for pat in patterns:
                for match in pat.finditer(text):
                    start = max(0, match.start() - 40)
                    end = min(len(text), match.end() + 40)
                    snippet = text[start:end].replace("\n", " ").strip()
                    signals[signal_key].append((match.group(0), snippet))

        _check(self.SUPERSEDES_PATTERNS, "SUPERSEDES")
        _check(self.CORRIGENDUM_PATTERNS, "CORRIGENDUM")
        _check(self.AMENDMENT_PATTERNS, "AMENDS")
        _check(self.ADDENDUM_PATTERNS, "ADDENDUM")
        _check(self.CLARIFICATION_PATTERNS, "CLARIFIES")
        _check(self.EXTENDS_PATTERNS, "EXTENDS")

        return signals

    def extract_effective_date(self, text: str) -> Optional[Tuple[date, str]]:
        """
        Extract legal effective date and the evidence text.
        """
        for pat in self.EFFECTIVE_DATE_PATTERNS:
            match = pat.search(text)
            if match:
                raw_date = match.group(1).strip()
                parsed = self._parse_date_string(raw_date)
                if parsed:
                    return parsed, match.group(0).strip()
        return None

    def extract_publication_date(self, text: str) -> Optional[Tuple[date, str]]:
        """
        Extract publication/issuance date and evidence text.
        """
        for pat in self.PUB_DATE_PATTERNS:
            match = pat.search(text)
            if match:
                raw_date = match.group(1).strip()
                parsed = self._parse_date_string(raw_date)
                if parsed:
                    return parsed, match.group(0).strip()
        return None

    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """Parse various Indian date formats (DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY)."""
        clean_str = re.sub(r"(st|nd|rd|th)", "", date_str).replace(".", "/").replace("-", "/").strip()
        clean_str = re.sub(r"\s+", " ", clean_str)

        formats = [
            "%d/%m/%Y",
            "%d/%m/%y",
            "%Y/%m/%d",
            "%d %B %Y",
            "%d %b %Y",
            "%B %d, %Y",
            "%b %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(clean_str, fmt).date()
            except ValueError:
                continue
        return None
