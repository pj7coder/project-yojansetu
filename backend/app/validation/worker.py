import argparse
import logging
import signal
import sys
import time
from typing import Optional
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.scheme_draft import SchemeDraft
from app.database.session import get_db_context
from app.validation.service import SchemeValidationService

logger = logging.getLogger("jansetu.validation.worker")


class ValidationWorker:
    """Worker process monitoring and executing deterministic validation on scheme drafts."""

    def __init__(self, loop_mode: bool = False, poll_interval: float = 5.0):
        self.loop_mode = loop_mode
        self.poll_interval = poll_interval
        self.running = True
        self.settings = get_settings()

    def handle_signal(self, signum, frame):
        logger.info("Shutdown signal received. Stopping validation worker...")
        self.running = False

    def process_single_draft(self, draft_id: uuid.UUID, force: bool = False) -> bool:
        with get_db_context() as db:
            service = SchemeValidationService(db)
            try:
                logger.info(f"Starting validation for draft {draft_id}")
                report = service.validate_draft(draft_id, force=force)
                logger.info(
                    f"Completed validation for draft {draft_id}: status={report.status.value}, "
                    f"blockers={report.summary.blockers}, errors={report.summary.errors}, "
                    f"warnings={report.summary.warnings}, duration={report.duration_ms}ms"
                )
                return report.status.value != "VALIDATION_FAILED"
            except Exception as ex:
                logger.error(f"Failed to validate scheme draft {draft_id}: {ex}", exc_info=True)
                return False

    def find_next_draft(self) -> Optional[uuid.UUID]:
        with get_db_context() as db:
            stmt = (
                select(SchemeDraft.id)
                .where(SchemeDraft.status == "READY_FOR_VALIDATION")
                .order_by(SchemeDraft.created_at.asc())
                .limit(1)
            )
            return db.execute(stmt).scalar_one_or_none()

    def run(self):
        logger.info(
            f"Validation worker started (loop={self.loop_mode}, poll_interval={self.poll_interval:.1f}s)"
        )

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        while self.running:
            draft_id = self.find_next_draft()
            if draft_id:
                self.process_single_draft(draft_id)
            else:
                if not self.loop_mode:
                    logger.info("No scheme drafts awaiting validation. Exiting.")
                    break
                time.sleep(self.poll_interval)

        logger.info("Validation worker stopped.")


def main():
    parser = argparse.ArgumentParser(description="JanSetu Deterministic Validation Worker")
    parser.add_argument("--draft-id", type=str, help="Specific Scheme Draft UUID to validate")
    parser.add_argument("--all", action="store_true", help="Process all READY_FOR_VALIDATION drafts")
    parser.add_argument("--force", action="store_true", help="Force validation regardless of cache")
    parser.add_argument("--loop", action="store_true", help="Run in continuous polling loop mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds")

    args = parser.parse_args()
    setup_logging()

    if args.draft_id:
        worker = ValidationWorker()
        draft_id = uuid.UUID(args.draft_id)
        success = worker.process_single_draft(draft_id, force=args.force)
        sys.exit(0 if success else 1)
    elif args.all:
        worker = ValidationWorker(loop_mode=False)
        worker.run()
    else:
        worker = ValidationWorker(loop_mode=args.loop, poll_interval=args.interval)
        worker.run()


if __name__ == "__main__":
    main()
