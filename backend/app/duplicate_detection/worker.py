import argparse
import logging
import sys
import time
from typing import Optional

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import get_db_context
from app.duplicate_detection.service import DuplicateDetectionService
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger("yojansetu.duplicate_detection.worker")


class DuplicateDetectionWorker:
    """
    Background worker service that polls for documents queued in READY_FOR_DUPLICATE_CHECK,
    classifies them using DuplicateDetectionService, and updates their lifecycle status.
    """

    def __init__(
        self,
        service: Optional[DuplicateDetectionService] = None,
        doc_repo: Optional[DocumentRepository] = None,
    ):
        self.service = service or DuplicateDetectionService()
        self.doc_repo = doc_repo or DocumentRepository()
        self.settings = get_settings()

    def process_batch(self, limit: int = 20) -> int:
        """
        Process a single batch of pending documents.
        Returns the number of documents successfully processed in this batch.
        """
        with get_db_context() as db:
            pending_docs = self.doc_repo.get_pending_duplicate_checks(db, limit=limit)
            if not pending_docs:
                return 0

            logger.info("Found %d pending document(s) for duplicate analysis", len(pending_docs))
            processed_count = 0

            for doc in pending_docs:
                try:
                    logger.info("Processing document %s (%s)...", doc.document_code, doc.original_filename)
                    result = self.service.detect_duplicates(db, doc.id)
                    logger.info(
                        "Classified %s as %s -> status=%s",
                        doc.document_code,
                        result.classification,
                        result.resulting_processing_status,
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error("Error evaluating document %s: %s", doc.document_code, str(e), exc_info=True)

            return processed_count

    def run_loop(self, poll_interval_sec: float = 3.0, batch_size: int = 20) -> None:
        """Run continuous monitoring loop for duplicate detection."""
        logger.info("DuplicateDetectionWorker started. Monitoring for READY_FOR_DUPLICATE_CHECK documents...")
        try:
            while True:
                processed = self.process_batch(limit=batch_size)
                if processed == 0:
                    time.sleep(poll_interval_sec)
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user. Shutting down gracefully...")


def main():
    """CLI entrypoint for running duplicate detection worker."""
    parser = argparse.ArgumentParser(description="YojanSetu Document Duplicate & Version Detection Worker")
    parser.add_argument("--once", action="store_true", help="Process pending batch once and exit")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of documents to process per batch")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds (default 3.0)")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info("=== YOJANSETU DUPLICATE DETECTION WORKER ===")

    worker = DuplicateDetectionWorker()
    if args.once:
        count = worker.process_batch(limit=args.batch_size)
        logger.info("One-shot batch complete: processed %d document(s)", count)
    else:
        worker.run_loop(poll_interval_sec=args.interval, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
