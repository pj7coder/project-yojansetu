import argparse
import logging
import signal
import sys
import time
from typing import Optional
import uuid

from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.models.scheme_draft import SchemeDraft
from app.database.session import get_db_context
from app.verification.service import EvidenceVerificationService

logger = logging.getLogger("yojansetu.verification.worker")


class EvidenceVerificationWorker:
    """Worker process executing second-pass evidence verification on canonical scheme drafts."""

    def __init__(self, loop_mode: bool = False, poll_interval: float = 5.0):
        self.loop_mode = loop_mode
        self.poll_interval = poll_interval
        self.running = True
        self.settings = get_settings()

    def handle_signal(self, signum, frame):
        logger.info("Shutdown signal received. Stopping evidence verification worker...")
        self.running = False

    def process_single_draft(self, draft_id: uuid.UUID, force: bool = False) -> bool:
        with get_db_context() as db:
            service = EvidenceVerificationService(db)
            try:
                logger.info(f"Starting evidence verification for draft {draft_id}")
                report = service.verify_scheme_draft(draft_id, force=force)
                logger.info(
                    f"Completed evidence verification for draft {draft_id}: "
                    f"status={report.status.value}, "
                    f"facts={report.summary.facts_total}, "
                    f"supported={report.summary.facts_supported}, "
                    f"contradicted={report.summary.facts_contradicted}, "
                    f"insufficient={report.summary.facts_insufficient}, "
                    f"duration={report.duration_ms}ms"
                )
                return report.status.value != "EVIDENCE_VERIFICATION_FAILED"
            except Exception as ex:
                logger.error(
                    f"Failed to verify evidence for scheme draft {draft_id}: {ex}",
                    exc_info=True,
                )
                return False

    def find_next_draft(self) -> Optional[uuid.UUID]:
        with get_db_context() as db:
            stmt = (
                select(SchemeDraft.id)
                .where(
                    or_(
                        SchemeDraft.status == "READY_FOR_EVIDENCE_VERIFICATION",
                        SchemeDraft.status == "VALIDATION_PASSED",
                    )
                )
                .order_by(SchemeDraft.created_at.asc())
                .limit(1)
            )
            return db.execute(stmt).scalar_one_or_none()

    def run(self):
        logger.info(
            f"Evidence verification worker started (loop={self.loop_mode}, poll_interval={self.poll_interval:.1f}s)"
        )

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        while self.running:
            draft_id = self.find_next_draft()
            if draft_id:
                self.process_single_draft(draft_id)
            else:
                if not self.loop_mode:
                    logger.info("No scheme drafts awaiting evidence verification. Exiting.")
                    break
                time.sleep(self.poll_interval)

        logger.info("Evidence verification worker stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="YojanSetu Second-Pass Evidence Verification Worker"
    )
    parser.add_argument(
        "--draft-id", type=str, help="Specific Scheme Draft UUID to verify"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all pending drafts awaiting evidence verification",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force verification regardless of cached run"
    )
    parser.add_argument(
        "--loop", action="store_true", help="Run in continuous polling loop mode"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Polling interval in seconds"
    )

    args = parser.parse_args()
    setup_logging()

    if args.draft_id:
        worker = EvidenceVerificationWorker()
        draft_id = uuid.UUID(args.draft_id)
        success = worker.process_single_draft(draft_id, force=args.force)
        sys.exit(0 if success else 1)
    elif args.all:
        worker = EvidenceVerificationWorker(loop_mode=False)
        worker.run()
    else:
        worker = EvidenceVerificationWorker(
            loop_mode=args.loop, poll_interval=args.interval
        )
        worker.run()


if __name__ == "__main__":
    main()
