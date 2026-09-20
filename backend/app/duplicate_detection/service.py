import datetime
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.document_relationship import DocumentRelationship
from app.duplicate_detection.diff import analyze_document_diff
from app.duplicate_detection.fingerprint import TextFingerprint, extract_text_fingerprint
from app.duplicate_detection.similarity import calculate_jaccard_similarity
from app.ingestion.storage import StorageManager
from app.repositories.document_relationship_repository import DocumentRelationshipRepository
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger("yojansetu.duplicate_detection.service")


@dataclass
class DuplicateDetectionResult:
    """Structured result returned by DuplicateDetectionService."""

    document_id: uuid.UUID
    classification: str  # NEW_DOCUMENT, EXACT_DUPLICATE, CONTENT_DUPLICATE, POSSIBLE_VERSION, POSSIBLE_NEAR_DUPLICATE
    matched_document_id: Optional[uuid.UUID] = None
    canonical_document_id: Optional[uuid.UUID] = None
    similarity_score: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    diff_summary: Optional[str] = None
    resulting_processing_status: str = "READY_FOR_PARSING"


class DuplicateDetectionService:
    """
    Central multi-tier duplicate detection and version identification service.

    Execution Flow:
    1. Exact binary SHA-256 hash lookup (Stage 1)
    2. Normalized rough text extraction & SHA-256 fingerprint (Stage 2)
    3. Scanned PDF conservative handling (if text < 50 chars)
    4. Content-level hash comparison (Stage 3)
    5. Candidate narrowing by department, source, page count, and title tokens (Stage 4)
    6. Shingle Jaccard similarity & text diff with version keyword detection (Stage 5)
    7. Canonical root resolution (flattening chains: D3 -> D1 instead of D3 -> D2 -> D1)
    8. Idempotent persistence of status and audit relationships
    """

    def __init__(
        self,
        document_repo: Optional[DocumentRepository] = None,
        relationship_repo: Optional[DocumentRelationshipRepository] = None,
        storage_manager: Optional[StorageManager] = None,
    ):
        self.doc_repo = document_repo or DocumentRepository()
        self.rel_repo = relationship_repo or DocumentRelationshipRepository()
        self.storage = storage_manager or StorageManager()
        self.settings = get_settings()

    def resolve_canonical_root(self, db: Session, initial_doc_id: uuid.UUID) -> uuid.UUID:
        """
        Recursively resolve the root canonical document ID to avoid duplicate chains.
        E.g. if Doc C is duplicate of Doc B, and Doc B is duplicate of Doc A -> returns Doc A.
        """
        current_id = initial_doc_id
        visited = set()

        while current_id not in visited:
            visited.add(current_id)
            doc = self.doc_repo.get_by_id(db, current_id)
            if not doc:
                break

            # If document itself points to another canonical or duplicate parent
            if doc.canonical_document_id and doc.canonical_document_id != current_id:
                current_id = doc.canonical_document_id
            elif doc.duplicate_of_document_id and doc.duplicate_of_document_id != current_id:
                current_id = doc.duplicate_of_document_id
            else:
                break

        return current_id

    def detect_duplicates(
        self,
        db: Session,
        document_id: uuid.UUID,
        force_recheck: bool = False,
    ) -> DuplicateDetectionResult:
        """
        Run the complete multi-tier duplicate detection pipeline on a document.

        :param db: Active SQLAlchemy database session.
        :param document_id: Primary UUID of candidate document to evaluate.
        :param force_recheck: Whether to re-run check even if already completed.
        :return: DuplicateDetectionResult with classification, matched canonical, and reasons.
        """
        doc = self.doc_repo.get_by_id(db, document_id)
        if not doc:
            raise ValueError(f"Document with ID '{document_id}' not found")

        # Idempotency check: skip if already classified and not forcing recheck
        if (
            not force_recheck
            and doc.duplicate_status is not None
            and doc.processing_status not in ["READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING"]
        ):
            logger.info("Document %s already processed for duplicates (%s); skipping", doc.document_code, doc.duplicate_status)
            return DuplicateDetectionResult(
                document_id=doc.id,
                classification=doc.duplicate_status,
                matched_document_id=doc.duplicate_of_document_id or doc.possible_version_of_document_id,
                canonical_document_id=doc.canonical_document_id,
                similarity_score=doc.similarity_score,
                reasons=[doc.duplicate_check_reason or "Previously evaluated"],
                resulting_processing_status=doc.processing_status,
            )

        logger.info("Starting duplicate check for document: %s (%s)", doc.document_code, doc.original_filename)

        # Mark in progress
        doc.processing_status = "DUPLICATE_CHECKING"
        db.commit()

        resolved_file = self.storage.resolve_storage_path(doc.storage_path)
        if not resolved_file or not resolved_file.exists():
            error_reason = f"Document file not found at storage path: {doc.storage_path}"
            logger.error(error_reason)
            doc.processing_status = "DUPLICATE_CHECK_FAILED"
            doc.failure_reason = error_reason
            db.commit()
            return DuplicateDetectionResult(
                document_id=doc.id,
                classification="FAILED",
                reasons=[error_reason],
                resulting_processing_status="DUPLICATE_CHECK_FAILED",
            )

        # ---------------------------------------------------------------------
        # STAGE 1: Exact Binary Check (SHA-256)
        # ---------------------------------------------------------------------
        if doc.sha256:
            exact_match = self.doc_repo.find_exact_sha256_match(
                db, doc.sha256, exclude_id=doc.id, created_before=doc.created_at
            )
            if exact_match:
                canonical_id = self.resolve_canonical_root(db, exact_match.id)
                canonical_doc = self.doc_repo.get_by_id(db, canonical_id) or exact_match
                reason = f"Exact SHA-256 byte digest matched canonical document {canonical_doc.document_code}"
                logger.info("EXACT_DUPLICATE found: %s matches %s", doc.document_code, canonical_doc.document_code)

                # Record audit relationship
                self.rel_repo.create(
                    db,
                    DocumentRelationship(
                        document_id=doc.id,
                        related_document_id=canonical_id,
                        relationship_type="EXACT_DUPLICATE_OF",
                        similarity_score=1.0,
                        reason=reason,
                    ),
                )

                # Update document entity
                doc.duplicate_status = "EXACT_DUPLICATE"
                doc.canonical_document_id = canonical_id
                doc.duplicate_of_document_id = exact_match.id
                doc.similarity_score = 1.0
                doc.duplicate_checked_at = datetime.datetime.now(datetime.timezone.utc)
                doc.duplicate_check_reason = reason
                doc.processing_status = "DUPLICATE"
                db.commit()

                return DuplicateDetectionResult(
                    document_id=doc.id,
                    classification="EXACT_DUPLICATE",
                    matched_document_id=exact_match.id,
                    canonical_document_id=canonical_id,
                    similarity_score=1.0,
                    reasons=[reason],
                    resulting_processing_status="DUPLICATE",
                )

        # ---------------------------------------------------------------------
        # STAGE 2: Extract Rough Text Fingerprint
        # ---------------------------------------------------------------------
        fingerprint: TextFingerprint = extract_text_fingerprint(
            file_path=resolved_file,
            document_id=str(doc.id),
        )

        # Update document text metadata
        doc.page_count = fingerprint.page_count
        doc.text_length = fingerprint.text_length
        doc.normalized_text_sha256 = fingerprint.normalized_hash
        db.commit()

        # Handle Scanned / Image-Only PDFs (text length < 50)
        if fingerprint.is_scanned_or_empty:
            reason = "Scanned or image-only PDF without extractable rough text; proceeding conservatively as new document"
            logger.info("Scanned document detected for %s; advancing to READY_FOR_PARSING", doc.document_code)

            doc.duplicate_status = "NEW_DOCUMENT"
            doc.processing_status = "READY_FOR_PARSING"
            doc.duplicate_checked_at = datetime.datetime.now(datetime.timezone.utc)
            doc.duplicate_check_reason = reason
            db.commit()

            return DuplicateDetectionResult(
                document_id=doc.id,
                classification="NEW_DOCUMENT",
                reasons=[reason],
                resulting_processing_status="READY_FOR_PARSING",
            )

        # ---------------------------------------------------------------------
        # STAGE 3: Content Duplicate Check (Normalized Text SHA-256)
        # ---------------------------------------------------------------------
        if fingerprint.normalized_hash:
            content_match = self.doc_repo.find_content_hash_match(
                db,
                fingerprint.normalized_hash,
                exclude_id=doc.id,
                created_before=doc.created_at,
            )
            if content_match:
                canonical_id = self.resolve_canonical_root(db, content_match.id)
                canonical_doc = self.doc_repo.get_by_id(db, canonical_id) or content_match
                reason = f"Normalized rough text hash matched canonical document {canonical_doc.document_code} (different packaging or PDF producer)"
                logger.info("CONTENT_DUPLICATE found: %s matches %s", doc.document_code, canonical_doc.document_code)

                self.rel_repo.create(
                    db,
                    DocumentRelationship(
                        document_id=doc.id,
                        related_document_id=canonical_id,
                        relationship_type="CONTENT_DUPLICATE_OF",
                        similarity_score=1.0,
                        reason=reason,
                    ),
                )

                doc.duplicate_status = "CONTENT_DUPLICATE"
                doc.canonical_document_id = canonical_id
                doc.duplicate_of_document_id = content_match.id
                doc.similarity_score = 1.0
                doc.duplicate_checked_at = datetime.datetime.now(datetime.timezone.utc)
                doc.duplicate_check_reason = reason
                doc.processing_status = "DUPLICATE"
                db.commit()

                return DuplicateDetectionResult(
                    document_id=doc.id,
                    classification="CONTENT_DUPLICATE",
                    matched_document_id=content_match.id,
                    canonical_document_id=canonical_id,
                    similarity_score=1.0,
                    reasons=[reason],
                    resulting_processing_status="DUPLICATE",
                )

        # ---------------------------------------------------------------------
        # ---------------------------------------------------------------------
        # STAGE 4: Candidate Narrowing & Shingle Similarity / Diff Analysis
        # ---------------------------------------------------------------------
        candidates = self.doc_repo.find_candidates_for_comparison(db, doc, limit=25)
        logger.debug("Evaluating %d similarity candidates for document %s", len(candidates), doc.document_code)

        best_version_match: Optional[Document] = None
        best_version_similarity: float = 0.0
        best_version_diff: Optional[object] = None

        best_near_match: Optional[Document] = None
        best_near_similarity: float = 0.0
        best_near_diff: Optional[object] = None

        for candidate in candidates:
            cand_path = self.storage.resolve_storage_path(candidate.storage_path)
            if not cand_path or not cand_path.exists():
                continue

            # Extract or load cached candidate fingerprint
            cand_fingerprint = extract_text_fingerprint(cand_path, document_id=str(candidate.id))
            if cand_fingerprint.is_scanned_or_empty:
                continue

            similarity = calculate_jaccard_similarity(
                text1=fingerprint.normalized_text,
                text2=cand_fingerprint.normalized_text,
                shingle_size=3,
            )

            if similarity >= self.settings.version_candidate_threshold:
                # Perform deep text diff analysis
                diff_analysis = analyze_document_diff(
                    text_old=cand_fingerprint.normalized_text,
                    text_new=fingerprint.normalized_text,
                    title_old=candidate.original_filename,
                    title_new=doc.original_filename,
                )

                # Check if this candidate is an amendment/version of the old document
                is_version = diff_analysis.is_probable_version or bool(diff_analysis.version_keywords_found)
                if is_version and similarity > best_version_similarity:
                    best_version_similarity = similarity
                    best_version_match = candidate
                    best_version_diff = diff_analysis

                # Track highest similarity candidate overall
                if similarity > best_near_similarity:
                    best_near_similarity = similarity
                    best_near_match = candidate
                    best_near_diff = diff_analysis

        # Evaluate version finding first (high-signal legal amendments/rules revisions)
        if best_version_match and best_version_diff:
            diff_obj = best_version_diff
            diff_summary = getattr(diff_obj, "diff_summary", "")
            keywords_found = getattr(diff_obj, "version_keywords_found", [])

            reason = (
                f"Possible amended version of {best_version_match.document_code} (similarity: {best_version_similarity:.2%}). "
                f"Version markers: {', '.join(keywords_found) if keywords_found else 'Text diff identified'}"
            )
            logger.info("POSSIBLE_VERSION identified: %s of %s", doc.document_code, best_version_match.document_code)

            self.rel_repo.create(
                db,
                DocumentRelationship(
                    document_id=doc.id,
                    related_document_id=best_version_match.id,
                    relationship_type="POSSIBLE_VERSION_OF",
                    similarity_score=best_version_similarity,
                    reason=f"{reason}\nDiff Summary:\n{diff_summary}",
                ),
            )

            doc.duplicate_status = "POSSIBLE_VERSION"
            doc.possible_version_of_document_id = best_version_match.id
            doc.similarity_score = best_version_similarity
            doc.duplicate_checked_at = datetime.datetime.now(datetime.timezone.utc)
            doc.duplicate_check_reason = reason
            doc.processing_status = "VERSION_REVIEW_REQUIRED"
            db.commit()

            return DuplicateDetectionResult(
                document_id=doc.id,
                classification="POSSIBLE_VERSION",
                matched_document_id=best_version_match.id,
                similarity_score=best_version_similarity,
                reasons=[reason],
                diff_summary=diff_summary,
                resulting_processing_status="VERSION_REVIEW_REQUIRED",
            )

        # Very high similarity (>= 0.98) without explicit amendment markers -> POSSIBLE_NEAR_DUPLICATE
        if best_near_match and best_near_similarity >= self.settings.duplicate_high_similarity_threshold:
            diff_obj = best_near_diff
            diff_summary = getattr(diff_obj, "diff_summary", "") if diff_obj else ""
            reason = f"High textual similarity ({best_near_similarity:.2%}) to {best_near_match.document_code} without explicit amendment keywords"
            logger.info("POSSIBLE_NEAR_DUPLICATE identified: %s to %s", doc.document_code, best_near_match.document_code)

            self.rel_repo.create(
                db,
                DocumentRelationship(
                    document_id=doc.id,
                    related_document_id=best_near_match.id,
                    relationship_type="POSSIBLE_NEAR_DUPLICATE_OF",
                    similarity_score=best_near_similarity,
                    reason=f"{reason}\nDiff Summary:\n{diff_summary}",
                ),
            )

            doc.duplicate_status = "POSSIBLE_NEAR_DUPLICATE"
            doc.duplicate_of_document_id = best_near_match.id
            doc.similarity_score = best_near_similarity
            doc.duplicate_checked_at = datetime.datetime.now(datetime.timezone.utc)
            doc.duplicate_check_reason = reason
            doc.processing_status = "VERSION_REVIEW_REQUIRED"
            db.commit()

            return DuplicateDetectionResult(
                document_id=doc.id,
                classification="POSSIBLE_NEAR_DUPLICATE",
                matched_document_id=best_near_match.id,
                similarity_score=best_near_similarity,
                reasons=[reason],
                diff_summary=diff_summary,
                resulting_processing_status="VERSION_REVIEW_REQUIRED",
            )

        # ---------------------------------------------------------------------
        # STAGE 5: Genuine New Document
        # ---------------------------------------------------------------------
        reason = "No matching binary, content, or version candidates detected; verified as new document"
        logger.info("NEW_DOCUMENT confirmed for %s -> READY_FOR_PARSING", doc.document_code)

        doc.duplicate_status = "NEW_DOCUMENT"
        doc.processing_status = "READY_FOR_PARSING"
        doc.duplicate_checked_at = datetime.datetime.now(datetime.timezone.utc)
        doc.duplicate_check_reason = reason
        db.commit()

        return DuplicateDetectionResult(
            document_id=doc.id,
            classification="NEW_DOCUMENT",
            reasons=[reason],
            resulting_processing_status="READY_FOR_PARSING",
        )
