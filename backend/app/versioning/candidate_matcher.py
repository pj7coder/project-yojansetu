import logging
import uuid
from typing import Dict, List, Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models.document import Document
from app.database.models.scheme import Scheme, SchemeVersion
from app.versioning.reference_extractor import GovernmentReferenceExtractor
from app.versioning.schemas import GovernmentReference

logger = logging.getLogger("jansetu.versioning.candidate_matcher")


class MatchedCandidate:
    def __init__(
        self,
        scheme: Scheme,
        base_version: Optional[SchemeVersion],
        target_document: Optional[Document],
        match_type: str,  # EXPLICIT_CITATION, SCHEME_NAME_EXACT, SCHEME_NAME_FUZZY
        match_reason: str,
        citations: List[GovernmentReference],
    ):
        self.scheme = scheme
        self.base_version = base_version
        self.target_document = target_document
        self.match_type = match_type
        self.match_reason = match_reason
        self.citations = citations


class RelationshipCandidateMatcher:
    """
    Narrows candidate schemes and target documents for a newly analyzed government document
    without full O(N^2) corpus comparisons.
    """

    def __init__(self, reference_extractor: Optional[GovernmentReferenceExtractor] = None):
        self.extractor = reference_extractor or GovernmentReferenceExtractor()

    def find_candidates(
        self,
        db: Session,
        document_text: str,
        document_title: Optional[str] = None,
        department_id: Optional[uuid.UUID] = None,
        source_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[MatchedCandidate], Optional[str]]:
        """
        Identify potential target schemes for the given document text/metadata.
        Returns (candidates, conflict_reason).
        """
        # 1. Extract explicit references
        references = self.extractor.extract_references(document_text)
        notification_numbers = [r.reference_number for r in references if r.reference_number]

        candidates: List[MatchedCandidate] = []
        matched_scheme_ids = set()

        # Step 1: Explicit citation matching against existing schemes / versions / documents
        if notification_numbers:
            # Check if any existing scheme_versions have source_summary or document title matching
            for notif_num in notification_numbers:
                # Query documents with matching title or raw text containing this reference
                stmt = (
                    select(Document)
                    .where(Document.title.ilike(f"%{notif_num}%"))
                )
                matching_docs = db.execute(stmt).scalars().all()
                for doc in matching_docs:
                    # Find scheme associated with this doc via scheme_versions or department
                    v_stmt = select(SchemeVersion).where(SchemeVersion.source_document_id == doc.id)
                    ver = db.execute(v_stmt).scalars().first()
                    if ver and ver.scheme_id not in matched_scheme_ids:
                        scheme = db.get(Scheme, ver.scheme_id)
                        if scheme:
                            # Department guard: check department compatibility
                            if department_id and scheme.department_id != department_id:
                                logger.warning(
                                    f"Citation {notif_num} matches scheme {scheme.scheme_code} but department differs ({scheme.department_id} vs {department_id})"
                                )
                                continue
                            candidates.append(
                                MatchedCandidate(
                                    scheme=scheme,
                                    base_version=ver,
                                    target_document=doc,
                                    match_type="EXPLICIT_CITATION",
                                    match_reason=f"Explicit notification reference matched: {notif_num}",
                                    citations=[r for r in references if r.reference_number == notif_num],
                                )
                            )
                            matched_scheme_ids.add(scheme.id)

        # Step 2: Name-based candidate search (within same department)
        query = select(Scheme)
        if department_id:
            query = query.where(Scheme.department_id == department_id)

        existing_schemes = db.execute(query).scalars().all()

        text_lower = (document_text + " " + (document_title or "")).lower()

        for scheme in existing_schemes:
            if scheme.id in matched_scheme_ids:
                continue

            name_en = (scheme.name_en or "").lower()
            name_hi = (scheme.name_hi or "").lower()
            short_name = (scheme.short_name or "").lower()
            code = (scheme.scheme_code or "").lower()

            matched = False
            reason = ""

            if code and code in text_lower:
                matched = True
                reason = f"Scheme code '{scheme.scheme_code}' found in text"
            elif len(name_en) > 5 and name_en in text_lower:
                matched = True
                reason = f"English scheme name '{scheme.name_en}' found in text"
            elif len(name_hi) > 5 and name_hi in text_lower:
                matched = True
                reason = f"Hindi scheme name '{scheme.name_hi}' found in text"
            elif len(short_name) > 3 and short_name in text_lower:
                matched = True
                reason = f"Short name '{scheme.short_name}' found in text"

            if matched:
                # Find current active version
                active_ver = self._get_latest_version(db, scheme.id)
                candidates.append(
                    MatchedCandidate(
                        scheme=scheme,
                        base_version=active_ver,
                        target_document=None,
                        match_type="SCHEME_NAME_EXACT",
                        match_reason=reason,
                        citations=[],
                    )
                )
                matched_scheme_ids.add(scheme.id)

        # Step 3: Conflict detection
        conflict_reason = None
        if len(candidates) > 1:
            # Check if candidates have equal match_type
            explicit_candidates = [c for c in candidates if c.match_type == "EXPLICIT_CITATION"]
            if len(explicit_candidates) > 1:
                conflict_reason = "MULTIPLE_POSSIBLE_BASE_VERSIONS"
            elif len(explicit_candidates) == 1:
                # One explicit candidate clearly wins
                candidates = explicit_candidates
            else:
                # Multiple name-only candidates
                conflict_reason = "MULTIPLE_POSSIBLE_BASE_VERSIONS"

        return candidates, conflict_reason

    def _get_latest_version(self, db: Session, scheme_id: uuid.UUID) -> Optional[SchemeVersion]:
        stmt = (
            select(SchemeVersion)
            .where(SchemeVersion.scheme_id == scheme_id)
            .order_by(SchemeVersion.version_number.desc())
        )
        return db.execute(stmt).scalars().first()
