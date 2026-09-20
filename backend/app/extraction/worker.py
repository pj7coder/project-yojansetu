import argparse
import logging
import signal
import sys
import time
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.document import Document
from app.database.session import SessionLocal
from app.extraction.aggregator import DocumentExtractionAggregator
from app.extraction.service import SchemeExtractionService
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger("yojansetu.extraction.worker")


class ExtractionWorker:
    """
    Background batch worker polling and processing documents in READY_FOR_EXTRACTION status.
    Runs local LLM evidence-backed extraction across semantic chunks and transitions
    documents to READY_FOR_NORMALIZATION.
    """

    def __init__(
        self,
        extraction_service: Optional[SchemeExtractionService] = None,
        aggregator: Optional[DocumentExtractionAggregator] = None,
    ):
        self.settings = get_settings()
        self.extraction_service = extraction_service or SchemeExtractionService()
        self.aggregator = aggregator or DocumentExtractionAggregator()
        self.chunk_repo = DocumentChunkRepository()
        self.doc_repo = DocumentRepository()
        self.running = True

    def process_document(self, db: Session, document: Document, force: bool = False) -> bool:
        """
        Process all semantic chunks for a single document and aggregate results.
        """
        doc_id = document.id
        chunks = self.chunk_repo.get_by_document_id(db, doc_id)
        if not chunks:
            logger.warning("Document %s has no chunks to extract.", doc_id)
            return False

        logger.info("Extracting %d chunks for document: %s (%s)", len(chunks), document.document_code, doc_id)

        for c in chunks:
            if not self.running:
                break
            try:
                self.extraction_service.extract_chunk(db, c.id, force=force)
            except Exception as e:
                logger.error("Failed extraction on chunk %s: %s", c.chunk_id_str, e)

        # Aggregate document
        try:
            self.aggregator.aggregate_document(db, doc_id)
            return True
        except Exception as e:
            logger.error("Failed to aggregate document %s: %s", doc_id, e)
            return False

    def process_batch(self, batch_size: int = 10, force: bool = False) -> int:
        """
        Poll and process a batch of documents in READY_FOR_EXTRACTION status.
        """
        db: Session = SessionLocal()
        processed_count = 0

        try:
            # Also pick up documents stuck in the transient EXTRACTING state
            # (e.g. backend crashed mid-extraction — they'd be orphaned forever otherwise)
            stmt = (
                select(Document)
                .where(Document.processing_status.in_(["READY_FOR_EXTRACTION", "EXTRACTING"]))
                .order_by(Document.created_at.asc())
                .limit(batch_size)
            )
            pending_docs: List[Document] = list(db.execute(stmt).scalars().all())

            if not pending_docs:
                return 0

            logger.info("Found %d document(s) in READY_FOR_EXTRACTION", len(pending_docs))

            for doc in pending_docs:
                if not self.running:
                    break

                try:
                    success = self.process_document(db, doc, force=force)
                    if success:
                        processed_count += 1
                except Exception as e:
                    logger.error("Failed processing document %s: %s", doc.document_code, e)

        finally:
            db.close()

        return processed_count

    def process_single(self, document_id_str: str, force: bool = False) -> bool:
        """Process a specific document by its UUID string."""
        db: Session = SessionLocal()
        try:
            doc_uuid = uuid.UUID(document_id_str)
            doc = self.doc_repo.get_by_id(db, doc_uuid)
            if not doc:
                logger.error("Document %s not found", document_id_str)
                return False
            return self.process_document(db, doc, force=force)
        except Exception as e:
            logger.error("Failed single document extraction for %s: %s", document_id_str, e)
            return False
        finally:
            db.close()

    def run_loop(self, poll_interval: int = 5, batch_size: int = 10, force: bool = False):
        """Continuously poll for READY_FOR_EXTRACTION documents."""
        logger.info(
            "Starting ExtractionWorker loop (poll_interval=%ds, batch_size=%d)...",
            poll_interval,
            batch_size,
        )

        def handle_signal(sig, frame):
            logger.info("Shutdown signal received. Stopping ExtractionWorker...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                processed = self.process_batch(batch_size=batch_size, force=force)
                if processed == 0:
                    time.sleep(poll_interval)
            except Exception as e:
                logger.error("Error in ExtractionWorker cycle: %s", e)
                time.sleep(poll_interval)

        logger.info("ExtractionWorker stopped gracefully.")


def main():
    parser = argparse.ArgumentParser(description="YojanSetu Local LLM Extraction Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single polling batch and exit immediately",
    )
    parser.add_argument(
        "--document-id",
        type=str,
        default=None,
        help="Process a specific document UUID directly and exit",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of documents to process in each batch",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Seconds to wait between polling cycles when idle",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction even if already EXTRACTED",
    )

    args = parser.parse_args()
    setup_logging()

    worker = ExtractionWorker()

    if args.document_id:
        success = worker.process_single(args.document_id, force=args.force)
        sys.exit(0 if success else 1)

    if args.once:
        count = worker.process_batch(batch_size=args.batch_size, force=args.force)
        logger.info("Batch completed. Processed %d document(s).", count)
        sys.exit(0)

    worker.run_loop(poll_interval=args.interval, batch_size=args.batch_size, force=args.force)


if __name__ == "__main__":
    main()
