import argparse
import logging
import signal
import sys
import time
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.document import Document
from app.database.session import SessionLocal
from app.parser.service import DocumentParserService

logger = logging.getLogger("yojansetu.parser.worker")


class DocumentParserWorker:
    """
    Background batch worker polling and processing documents in READY_FOR_PARSING state.
    Transitions documents to READY_FOR_OCR_CHECK (or PARSING_FAILED).
    """

    def __init__(self, parser_service: Optional[DocumentParserService] = None):
        self.settings = get_settings()
        self.parser_service = parser_service or DocumentParserService()
        self.running = True

    def process_batch(self, batch_size: int = 10) -> int:
        """
        Poll and parse a batch of documents awaiting structured layout parsing.
        Returns the count of documents parsed in this batch.
        """
        db: Session = SessionLocal()
        processed_count = 0

        try:
            # 1. Reset any stale tasks stuck in PARSING
            self.parser_service.reset_stale_parsing_tasks(db, timeout_minutes=15)

            # 2. Query pending documents in READY_FOR_PARSING state
            stmt = (
                select(Document)
                .where(Document.processing_status == "READY_FOR_PARSING")
                .order_by(Document.created_at.asc())
                .limit(batch_size)
            )
            pending_docs: List[Document] = list(db.execute(stmt).scalars().all())

            if not pending_docs:
                return 0

            logger.info("Found %d document(s) in READY_FOR_PARSING", len(pending_docs))

            for doc in pending_docs:
                if not self.running:
                    break

                try:
                    logger.info("Processing parser job for: %s (%s)", doc.document_code, doc.original_filename)
                    self.parser_service.parse_document(db, doc.id)
                    processed_count += 1
                except Exception as e:
                    logger.error("Failed to parse document %s: %s", doc.document_code, e)

        finally:
            db.close()

        return processed_count

    def run(self, interval_seconds: int = 5, batch_size: int = 10, once: bool = False) -> None:
        """Run worker loop continuously or single-pass."""
        logger.info(
            "Starting DocumentParserWorker (interval=%ds, batch_size=%d, once=%s)",
            interval_seconds,
            batch_size,
            once,
        )

        def handle_signal(sig, frame):
            logger.info("Termination signal received. Shutting down gracefully...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                count = self.process_batch(batch_size=batch_size)
                if once:
                    logger.info("Single-pass execution completed. Processed: %d documents", count)
                    break

                if count == 0:
                    time.sleep(interval_seconds)
            except Exception as e:
                logger.error("Unexpected worker exception: %s", e, exc_info=True)
                if once:
                    break
                time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="YojanSetu Document Parser Worker")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of documents per batch")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    args = parser.parse_args()

    setup_logging()
    worker = DocumentParserWorker()
    worker.run(interval_seconds=args.interval, batch_size=args.batch_size, once=args.once)


if __name__ == "__main__":
    main()
