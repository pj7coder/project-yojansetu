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
from app.ocr.service import OCRService

logger = logging.getLogger("jansetu.ocr.worker")


class OCRWorker:
    """
    Background batch worker polling and processing documents in READY_FOR_OCR_CHECK state.
    Transitions documents to READY_FOR_CHUNKING (or OCR_FAILED).
    """

    def __init__(self, ocr_service: Optional[OCRService] = None):
        self.settings = get_settings()
        self.ocr_service = ocr_service or OCRService()
        self.running = True

    def process_batch(self, batch_size: int = 10, force: bool = False) -> int:
        """
        Poll and process a batch of documents awaiting OCR requirement evaluation.
        Returns the count of documents processed in this batch.
        """
        db: Session = SessionLocal()
        processed_count = 0

        try:
            stmt = (
                select(Document)
                .where(Document.processing_status == "READY_FOR_OCR_CHECK")
                .order_by(Document.created_at.asc())
                .limit(batch_size)
            )
            pending_docs: List[Document] = list(db.execute(stmt).scalars().all())

            if not pending_docs:
                return 0

            logger.info("Found %d document(s) in READY_FOR_OCR_CHECK", len(pending_docs))

            for doc in pending_docs:
                if not self.running:
                    break

                try:
                    logger.info(
                        "Processing OCR check for: %s (%s)",
                        doc.document_code,
                        doc.original_filename,
                    )
                    self.ocr_service.process_document(db, doc.id, force=force)
                    processed_count += 1
                except Exception as e:
                    logger.error("Failed to process OCR for document %s: %s", doc.document_code, e)

        finally:
            db.close()

        return processed_count

    def process_single(self, document_id_str: str, force: bool = False) -> bool:
        """Process a specific document by its UUID string."""
        db: Session = SessionLocal()
        try:
            doc_uuid = uuid.UUID(document_id_str)
            logger.info("Processing single document OCR check for %s", doc_uuid)
            self.ocr_service.process_document(db, doc_uuid, force=force)
            return True
        except Exception as e:
            logger.error("Failed to process OCR for document %s: %s", document_id_str, e)
            return False
        finally:
            db.close()

    def run(
        self,
        interval_seconds: int = 5,
        batch_size: int = 10,
        once: bool = False,
        force: bool = False,
    ) -> None:
        """Run worker loop continuously or single-pass."""
        logger.info(
            "Starting OCRWorker (interval=%ds, batch_size=%d, once=%s, concurrency=%d)",
            interval_seconds,
            batch_size,
            once,
            self.settings.ocr_worker_concurrency,
        )

        def handle_signal(sig, frame):
            logger.info("Termination signal received. Shutting down gracefully...")
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        while self.running:
            try:
                count = self.process_batch(batch_size=batch_size, force=force)
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
    parser = argparse.ArgumentParser(description="JanSetu Document OCR Worker")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of documents per batch")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    parser.add_argument("--document-id", type=str, default=None, help="Process a specific document UUID")
    parser.add_argument("--force", action="store_true", help="Force OCR re-processing")
    args = parser.parse_args()

    setup_logging()
    worker = OCRWorker()

    if args.document_id:
        worker.process_single(args.document_id, force=args.force)
    else:
        worker.run(
            interval_seconds=args.interval,
            batch_size=args.batch_size,
            once=args.once,
            force=args.force,
        )


if __name__ == "__main__":
    main()
