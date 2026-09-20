import argparse
import logging
import sys
import time
from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.document_relationship import DocumentRelationship
from app.database.models.scheme import SchemeVersion
from app.database.session import SessionLocal
from app.versioning.candidate_matcher import RelationshipCandidateMatcher
from app.versioning.relationship_detector import DocumentRelationshipDetector
from app.versioning.service import SchemeVersionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("yojansetu.versioning.worker")


class SchemeVersioningWorker:
    """
    Background worker that scans for candidate amendment, corrigendum,
    or supersession documents, matches target schemes, detects legal relationships,
    and builds proposed ChangeSets for human review.
    """

    def __init__(
        self,
        matcher: Optional[RelationshipCandidateMatcher] = None,
        detector: Optional[DocumentRelationshipDetector] = None,
        version_service: Optional[SchemeVersionService] = None,
    ):
        self.matcher = matcher or RelationshipCandidateMatcher()
        self.detector = detector or DocumentRelationshipDetector()
        self.version_service = version_service or SchemeVersionService()

    def run_cycle(self, db: Session, batch_size: int = 10, document_id: Optional[uuid.UUID] = None) -> int:
        """
        Run one processing cycle over candidate documents.
        Returns number of change sets created.
        """
        stmt = (
            select(Document)
            .where(
                Document.processing_status.in_(["EXTRACTION_COMPLETED", "NORMALIZED", "VERIFIED", "DUPLICATE_CHECK_COMPLETED"])
            )
            .order_by(Document.created_at.desc())
        )
        if document_id:
            stmt = stmt.where(Document.id == document_id)
        else:
            stmt = stmt.limit(batch_size)

        documents = db.execute(stmt).scalars().all()
        created_count = 0

        for doc in documents:
            try:
                # Load text from document chunks or title
                c_stmt = (
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == doc.id)
                    .order_by(DocumentChunk.chunk_index.asc())
                    .limit(5)
                )
                chunks = db.execute(c_stmt).scalars().all()
                chunk_titles = [c.chunk_title for c in chunks if c.chunk_title]
                full_text = (" ".join(chunk_titles) + " " + (doc.title or "")).strip()

                if not full_text.strip():
                    continue

                # Match candidates
                candidates, conflict = self.matcher.find_candidates(
                    db=db,
                    document_text=full_text,
                    document_title=doc.title,
                )

                if not candidates:
                    continue

                for cand in candidates:
                    scheme = cand.scheme
                    base_ver = cand.base_version
                    if not base_ver:
                        continue

                    # Detect relationship
                    rel_result = self.detector.detect_relationship(
                        source_text=full_text,
                        source_filename=doc.original_filename,
                        target_citation=cand.citations[0].reference_number if cand.citations else None,
                        target_document_id=cand.target_document.id if cand.target_document else None,
                        target_scheme_id=scheme.id,
                    )

                    # Determine if it's an amendment/corrigendum/supersession
                    is_rel = rel_result.relationship_type.value in ["AMENDS", "SUPERSEDES", "CORRIGENDUM_TO", "ADDENDUM_TO", "EXTENDS"]
                    if not is_rel:
                        continue

                    # Check if changeset already exists for this doc + base_ver
                    from app.database.models.scheme_change_set import SchemeChangeSet
                    cs_stmt = select(SchemeChangeSet).where(
                        SchemeChangeSet.scheme_id == scheme.id,
                        SchemeChangeSet.base_version_id == base_ver.id,
                        SchemeChangeSet.source_document_id == doc.id,
                    )
                    existing_cs = db.execute(cs_stmt).scalars().first()
                    if existing_cs:
                        logger.info(f"ChangeSet already exists for doc {doc.id} on scheme {scheme.id}; skipping (idempotent)")
                        continue

                    # Build changeset
                    candidate_canonical = base_ver.canonical_data or {}
                    # Build and persist changeset
                    cs = self.version_service.build_change_set_for_document(
                        db=db,
                        scheme_id=scheme.id,
                        base_version_id=base_ver.id,
                        source_document_id=doc.id,
                        candidate_canonical=candidate_canonical,
                        relationship_id=None,
                        effective_date=rel_result.effective_date,
                        publication_date=rel_result.publication_date,
                        is_partial_amendment=(rel_result.relationship_type.value == "AMENDS"),
                        evidence_refs=[{"text": rel_result.evidence_text}] if rel_result.evidence_text else [],
                        conflict_reason=conflict,
                    )
                    created_count += 1
                    logger.info(f"Worker generated SchemeChangeSet {cs.id} for scheme {scheme.scheme_code}")

            except Exception as e:
                logger.error(f"Error processing document {doc.id} in versioning worker: {e}", exc_info=True)

        return created_count

    def run_loop(self, poll_interval: int = 10, batch_size: int = 10, once: bool = False) -> None:
        logger.info(f"Starting SchemeVersioningWorker (poll_interval={poll_interval}s, batch_size={batch_size}, once={once})")
        while True:
            with SessionLocal() as db:
                count = self.run_cycle(db, batch_size=batch_size)
                if count > 0:
                    logger.info(f"Processed cycle: {count} change sets created")

            if once:
                break
            time.sleep(poll_interval)


def main():
    parser = argparse.ArgumentParser(description="YojanSetu Scheme Versioning & Amendment Worker")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    parser.add_argument("--poll-interval", type=int, default=10, help="Polling interval in seconds")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size per cycle")
    args = parser.parse_args()

    worker = SchemeVersioningWorker()
    worker.run_loop(poll_interval=args.poll_interval, batch_size=args.batch_size, once=args.once)


if __name__ == "__main__":
    main()
