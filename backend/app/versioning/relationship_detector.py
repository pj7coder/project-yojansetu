import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.versioning.reference_extractor import GovernmentReferenceExtractor
from app.versioning.schemas import (
    DetectionMethod,
    DetectedRelationshipResult,
    RelationshipStatus,
    RelationshipType,
)

logger = logging.getLogger("jansetu.versioning.relationship_detector")


class DocumentRelationshipDetector:
    """
    Analyzes legal and semantic relationships between government documents deterministically,
    with explicit evidence grounding and strictly controlled signal strengths.
    """

    def __init__(self, reference_extractor: Optional[GovernmentReferenceExtractor] = None):
        self.extractor = reference_extractor or GovernmentReferenceExtractor()

    def detect_relationship(
        self,
        source_text: str,
        source_filename: Optional[str] = None,
        target_citation: Optional[str] = None,
        target_document_id: Optional[UUID] = None,
        target_scheme_id: Optional[UUID] = None,
        page_number: Optional[int] = None,
        block_ids: Optional[List[str]] = None,
    ) -> DetectedRelationshipResult:
        """
        Detect the legal relationship between source document text and target.
        """
        signals = self.extractor.detect_relationship_signals(source_text)
        eff_date_tuple = self.extractor.extract_effective_date(source_text)
        pub_date_tuple = self.extractor.extract_publication_date(source_text)

        effective_date = eff_date_tuple[0] if eff_date_tuple else None
        publication_date = pub_date_tuple[0] if pub_date_tuple else None

        reason_codes: List[str] = []
        evidence_text: Optional[str] = None

        # Check for explicit citations
        has_explicit_citation = False
        if target_citation and target_citation.lower() in source_text.lower():
            has_explicit_citation = True
            reason_codes.append("EXPLICIT_NOTIFICATION_REFERENCE")

        # 1. Check SUPERSEDES
        if signals["SUPERSEDES"]:
            matched, snippet = signals["SUPERSEDES"][0]
            evidence_text = snippet
            reason_codes.append("EXPLICIT_SUPERSESSION_PHRASE")
            strength = "EXPLICIT" if has_explicit_citation else "STRONG"
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.SUPERSEDES,
                relationship_status=RelationshipStatus.REVIEW_REQUIRED,
                detection_method=DetectionMethod.TEXTUAL_SIGNAL if not has_explicit_citation else DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength=strength,
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=evidence_text,
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        # 2. Check CORRIGENDUM
        if signals["CORRIGENDUM"]:
            matched, snippet = signals["CORRIGENDUM"][0]
            evidence_text = snippet
            reason_codes.append("EXPLICIT_CORRIGENDUM_PHRASE")
            strength = "EXPLICIT" if has_explicit_citation else "STRONG"
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.CORRIGENDUM_TO,
                relationship_status=RelationshipStatus.REVIEW_REQUIRED,
                detection_method=DetectionMethod.TEXTUAL_SIGNAL if not has_explicit_citation else DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength=strength,
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=evidence_text,
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        # 3. Check AMENDS
        if signals["AMENDS"]:
            matched, snippet = signals["AMENDS"][0]
            evidence_text = snippet
            reason_codes.append("EXPLICIT_AMENDMENT_PHRASE")
            strength = "EXPLICIT" if has_explicit_citation else "STRONG"
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.AMENDS,
                relationship_status=RelationshipStatus.REVIEW_REQUIRED,
                detection_method=DetectionMethod.TEXTUAL_SIGNAL if not has_explicit_citation else DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength=strength,
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=evidence_text,
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        # 4. Check ADDENDUM
        if signals["ADDENDUM"]:
            matched, snippet = signals["ADDENDUM"][0]
            evidence_text = snippet
            reason_codes.append("EXPLICIT_ADDENDUM_PHRASE")
            strength = "EXPLICIT" if has_explicit_citation else "STRONG"
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.ADDENDUM_TO,
                relationship_status=RelationshipStatus.REVIEW_REQUIRED,
                detection_method=DetectionMethod.TEXTUAL_SIGNAL if not has_explicit_citation else DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength=strength,
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=evidence_text,
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        # 5. Check CLARIFIES
        if signals["CLARIFIES"]:
            matched, snippet = signals["CLARIFIES"][0]
            evidence_text = snippet
            reason_codes.append("EXPLICIT_CLARIFICATION_PHRASE")
            strength = "EXPLICIT" if has_explicit_citation else "STRONG"
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.CLARIFIES,
                relationship_status=RelationshipStatus.REVIEW_REQUIRED,
                detection_method=DetectionMethod.TEXTUAL_SIGNAL if not has_explicit_citation else DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength=strength,
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=evidence_text,
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        # 6. Check EXTENDS
        if signals["EXTENDS"]:
            matched, snippet = signals["EXTENDS"][0]
            evidence_text = snippet
            reason_codes.append("EXPLICIT_EXTENSION_PHRASE")
            strength = "EXPLICIT" if has_explicit_citation else "STRONG"
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.EXTENDS,
                relationship_status=RelationshipStatus.REVIEW_REQUIRED,
                detection_method=DetectionMethod.TEXTUAL_SIGNAL if not has_explicit_citation else DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength=strength,
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=evidence_text,
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        # 7. Filename-only check: Filename is WEAK signal and NEVER supersedes alone!
        if source_filename:
            fn_lower = source_filename.lower()
            if any(k in fn_lower for k in ["revised", "amend", "corrigendum", "supersed"]):
                reason_codes.append("FILENAME_KEYWORD_ONLY_WEAK")
                return DetectedRelationshipResult(
                    relationship_type=RelationshipType.UNKNOWN_RELATIONSHIP,
                    relationship_status=RelationshipStatus.CANDIDATE,
                    detection_method=DetectionMethod.TEXTUAL_SIGNAL,
                    signal_strength="WEAK",
                    target_document_id=target_document_id,
                    target_scheme_id=target_scheme_id,
                    effective_date=effective_date,
                    publication_date=publication_date,
                    evidence_text=f"Filename signal only: {source_filename}",
                    evidence_page=page_number,
                    evidence_block_ids=block_ids or [],
                    reason_codes=reason_codes,
                )

        # 8. If explicit citation only
        if has_explicit_citation:
            return DetectedRelationshipResult(
                relationship_type=RelationshipType.REFERENCES,
                relationship_status=RelationshipStatus.AUTO_SUPPORTED,
                detection_method=DetectionMethod.EXPLICIT_REFERENCE,
                signal_strength="STRONG",
                target_document_id=target_document_id,
                target_scheme_id=target_scheme_id,
                effective_date=effective_date,
                publication_date=publication_date,
                evidence_text=f"References notification: {target_citation}",
                evidence_page=page_number,
                evidence_block_ids=block_ids or [],
                reason_codes=reason_codes,
            )

        return DetectedRelationshipResult(
            relationship_type=RelationshipType.UNKNOWN_RELATIONSHIP,
            relationship_status=RelationshipStatus.CANDIDATE,
            detection_method=DetectionMethod.DETERMINISTIC_METADATA,
            signal_strength="WEAK",
            target_document_id=target_document_id,
            target_scheme_id=target_scheme_id,
            effective_date=effective_date,
            publication_date=publication_date,
            evidence_text=None,
            evidence_page=page_number,
            evidence_block_ids=block_ids or [],
            reason_codes=["NO_TARGET_REFERENCE"],
        )
