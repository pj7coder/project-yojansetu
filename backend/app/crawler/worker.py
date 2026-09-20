import argparse
import logging
import signal
import sys
import time
from typing import Optional

from app.crawler.analysis_service import SourceChangeAnalysisService
from app.database.session import SessionLocal
from app.repositories.change_analysis_repository import ChangeAnalysisRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jansetu.crawler.worker")


class ChangeAnalysisWorker:
    """Background worker daemon consuming PENDING_ANALYSIS change events."""

    def __init__(
        self,
        service: Optional[SourceChangeAnalysisService] = None,
        repository: Optional[ChangeAnalysisRepository] = None,
        poll_interval: float = 5.0,
    ):
        self.service = service or SourceChangeAnalysisService()
        self.repo = repository or ChangeAnalysisRepository()
        self.poll_interval = poll_interval
        self._running = True

    def stop(self, *args):
        logger.info("Stopping change analysis worker...")
        self._running = False

    def process_one(self) -> bool:
        """Claim and process a single pending change event.
        
        Returns True if an event was processed, False if no events were waiting.
        """
        with SessionLocal() as db:
            event = self.repo.claim_next_pending_event(db)
            if not event:
                return False

            logger.info(f"Claimed change event {event.id} for source_url {event.source_url_id}")
            try:
                self.service.analyze_event(db, event)
                return True
            except Exception as e:
                logger.error(f"Analysis worker failed processing event {event.id}: {e}", exc_info=True)
                try:
                    event.processing_status = "ANALYSIS_FAILED"
                    db.commit()
                except Exception as ce:
                    logger.critical(f"Failed to record failure status for event {event.id}: {ce}")
                return True

    def run(self, once: bool = False):
        """Run worker loop."""
        logger.info(f"Starting change analysis worker (poll_interval={self.poll_interval}s, once={once})")
        
        # Setup graceful signal handlers
        try:
            signal.signal(signal.SIGINT, self.stop)
            signal.signal(signal.SIGTERM, self.stop)
        except (ValueError, AttributeError):
            pass  # On non-main threads

        while self._running:
            try:
                processed = self.process_one()
                if once:
                    break
                if not processed:
                    time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Unexpected worker loop exception: {e}", exc_info=True)
                if once:
                    break
                time.sleep(self.poll_interval)

        logger.info("Change analysis worker exited.")


def main():
    parser = argparse.ArgumentParser(description="JanSetu Change Analysis Worker")
    parser.add_argument("--once", action="store_true", help="Process available events and exit")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds")
    args = parser.parse_args()

    worker = ChangeAnalysisWorker(poll_interval=args.interval)
    worker.run(once=args.once)


if __name__ == "__main__":
    main()
