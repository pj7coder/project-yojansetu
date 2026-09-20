import argparse
import logging
import signal
import sys
import time
import uuid
from typing import Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.document import Document
from app.database.session import get_db_context
from app.normalization.service import SchemeNormalizationService

logger = logging.getLogger("yojansetu.normalization.worker")


class NormalizationWorker:
    """Worker process monitoring and executing normalization on documents."""

    def __init__(self, loop_mode: bool = False, poll_interval: float = 5.0):
        self.loop_mode = loop_mode
        self.poll_interval = poll_interval
        self.running = True
        self.settings = get_settings()

    def handle_signal(self, signum, frame):
        logger.info("Shutdown signal received. Finishing current task...")
        self.running = False

    def process_single_document(self, doc_id: uuid.UUID, force: bool = False) -> bool:
        with get_db_context() as db:
            service = SchemeNormalizationService(db)
            try:
                logger.info("Starting normalization for document %s", doc_id)
                result = service.normalize_document(doc_id, force=force)
                logger.info(
                    "Completed normalization for %s: status=%s, schemes=%d, duration=%dms",
                    doc_id,
                    result.get("status"),
                    result.get("schemes_detected", 0),
                    result.get("duration_ms", 0),
                )
                return True
            except Exception as e:
                logger.error("Failed to normalize document %s: %s", doc_id, e)
                return False

    def find_next_document(self) -> Optional[uuid.UUID]:
        with get_db_context() as db:
            stmt = (
                select(Document.id)
                .where(Document.processing_status == "READY_FOR_NORMALIZATION")
                .order_by(Document.created_at.asc())
                .limit(1)
            )
            return db.execute(stmt).scalar_one_or_none()

    def run(self):
        logger.info(
            "Normalization worker started (loop=%s, poll_interval=%.1fs)",
            self.loop_mode,
            self.poll_interval,
        )

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        while self.running:
            doc_id = self.find_next_document()
            if doc_id:
                self.process_single_document(doc_id)
            else:
                if not self.loop_mode:
                    logger.info("No documents awaiting normalization. Exiting.")
                    break
                time.sleep(self.poll_interval)

        logger.info("Normalization worker stopped.")


def main():
    parser = argparse.ArgumentParser(description="YojanSetu Normalization Worker")
    parser.add_argument("--document-id", type=str, help="Specific document ID to normalize")
    parser.add_argument("--force", action="store_true", help="Force normalization regardless of status")
    parser.add_argument("--loop", action="store_true", help="Run in continuous polling loop mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds")

    args = parser.parse_args()
    setup_logging()

    if args.document_id:
        worker = NormalizationWorker()
        doc_id = uuid.UUID(args.document_id)
        success = worker.process_single_document(doc_id, force=args.force)
        sys.exit(0 if success else 1)
    else:
        worker = NormalizationWorker(loop_mode=args.loop, poll_interval=args.interval)
        worker.run()


if __name__ == "__main__":
    main()
