import argparse
import logging
import signal
import sys
import time
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chunking.service import DocumentChunkingService
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.document import Document
from app.database.session import SessionLocal

logger = logging.getLogger("yojansetu.chunking.worker")


class ChunkingWorker:
    """
    Background batch worker polling and processing documents in READY_FOR_CHUNKING status.
    Generates structured, page-traceable semantic chunks and transitions documents
    to READY_FOR_EXTRACTION (or CHUNKING_FAILED).
    """

    def __init__(self, chunking_service: Optional[DocumentChunkingService] = None):
        self.settings = get_settings()
        self.chunking_service = chunking_service or DocumentChunkingService()
        self.running = True

    def process_batch(self, batch_size: int = 10, force: bool = False) -> int:
        """
        Poll and process a batch of documents awaiting semantic chunking.
        Returns the count of documents successfully processed in this batch.
        """
        db: Session = SessionLocal()
        processed_count = 0

        try:
            # Pick up both waiting documents AND any stuck in transient CHUNKING state
            # (e.g. backend crashed mid-chunk — they'd be orphaned forever otherwise)
            stmt = (
                select(Document)
                .where(Document.processing_status.in_(["READY_FOR_CHUNKING", "CHUNKING"]))
                .order_by(Document.created_at.asc())
                .limit(batch_size)
            )
            pending_docs: List[Document] = list(db.execute(stmt).scalars().all())

            if not pending_docs:
                return 0

            logger.info("Found %d document(s) in READY_FOR_CHUNKING", len(pending_docs))

            for doc in pending_docs:
                if not self.running:
                    break

                try:
                    logger.info(
                        "Starting chunking for document: %s (%s)",
                        doc.document_code,
                        doc.original_filename,
                    )
                    self.chunking_service.chunk_document(db, doc.id, force=force)
                    processed_count += 1
                except Exception as e:
                    logger.error("Failed to chunk document %s: %s", doc.document_code, e)

        finally:
            db.close()

        return processed_count

    def process_single(self, document_id_str: str, force: bool = False) -> bool:
        """Process a specific document by its UUID string."""
        db: Session = SessionLocal()
        try:
            doc_uuid = uuid.UUID(document_id_str)
            logger.info("Processing single document chunking for %s", doc_uuid)
            self.chunking_service.chunk_document(db, doc_uuid, force=force)
            return True
        except Exception as e:
            logger.error("Failed single document chunking for %s: %s", document_id_str, e)
            return False
        finally:
            db.close()

    def run_loop(self, poll_interval: int = 5, batch_size: int = 10, force: bool = False):
        """Continuously poll for READY_FOR_CHUNKING documents until interrupted."""
        logger.info(
            "Starting ChunkingWorker loop (poll_interval=%ds, batch_size=%d)...",
            poll_interval,
            batch_size,
        )

        def handle_signal(sig, frame):
            logger.info("Shutdown signal received. Stopping ChunkingWorker loop...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                processed = self.process_batch(batch_size=batch_size, force=force)
                if processed == 0:
                    time.sleep(poll_interval)
            except Exception as e:
                logger.error("Error in ChunkingWorker poll cycle: %s", e)
                time.sleep(poll_interval)

        logger.info("ChunkingWorker stopped gracefully.")


def main():
    parser = argparse.ArgumentParser(description="YojanSetu Semantic Document Chunking Worker")
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
        help="Force re-chunking even if document is already READY_FOR_EXTRACTION or CHUNKED",
    )

    args = parser.parse_args()
    setup_logging()

    worker = ChunkingWorker()

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
