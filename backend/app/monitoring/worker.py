import argparse
import asyncio
from datetime import datetime, timezone
import logging
import signal
import sys
from typing import Optional

from app.core.config import settings
from app.database.session import get_db_context
from app.monitoring.service import SourceMonitoringService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("source_monitor_worker")


class SourceMonitorWorker:
    """Background monitoring daemon that polls due sources, claims work via DB locks, and executes checks."""

    def __init__(
        self,
        service: Optional[SourceMonitoringService] = None,
        poll_interval_seconds: int = 10,
        batch_size: int = 5,
    ):
        self.service = service or SourceMonitoringService()
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self._running = True

    def stop(self, *args):
        logger.info("Received stop signal. Shutting down worker gracefully...")
        self._running = False

    async def run_once(self) -> int:
        """Process one batch of due sources. Returns number of checked sources."""
        now = datetime.now(timezone.utc)
        checked_count = 0

        with get_db_context() as db:
            due_items = self.service.repo.get_due_monitoring_sources(
                db, now=now, limit=self.batch_size, lock=True
            )

            if not due_items:
                return 0

            logger.info(f"Worker claimed {len(due_items)} due monitoring target(s)")

            for source_url, state in due_items:
                if not self._running:
                    break

                try:
                    logger.info(f"Checking {source_url.id} -> {source_url.url}")
                    result = await self.service.check_source_url(db, source_url.id)
                    logger.info(
                        f"Completed {source_url.id}: status={result.get('status')} "
                        f"result={result.get('result')} duration={result.get('duration_ms', 0):.1f}ms"
                    )
                    checked_count += 1
                except Exception as e:
                    logger.error(f"Error checking source {source_url.id}: {e}", exc_info=True)

        return checked_count

    async def run_loop(self):
        """Continuous polling loop."""
        logger.info(
            f"Starting JanSetu Source Monitoring Worker "
            f"(poll_interval={self.poll_interval_seconds}s, batch_size={self.batch_size})..."
        )

        while self._running:
            try:
                count = await self.run_once()
                if count == 0:
                    # No work immediately due, sleep for poll interval
                    await asyncio.sleep(self.poll_interval_seconds)
                else:
                    # Small breath before checking next batch if work was available
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval_seconds)

        logger.info("Source Monitoring Worker stopped.")


def main():
    parser = argparse.ArgumentParser(description="JanSetu Source Monitoring Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once over due sources and exit immediately (useful for batch/cron)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds to sleep when idle (default: 10)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Maximum due sources to check in one batch (default: 5)",
    )
    args = parser.parse_args()

    worker = SourceMonitorWorker(
        poll_interval_seconds=args.poll_interval,
        batch_size=args.batch_size,
    )

    # Register signals for clean shutdown
    try:
        signal.signal(signal.SIGINT, worker.stop)
        signal.signal(signal.SIGTERM, worker.stop)
    except Exception:
        pass

    if args.once:
        checked = asyncio.run(worker.run_once())
        logger.info(f"Completed single pass: checked {checked} source(s).")
    else:
        asyncio.run(worker.run_loop())


if __name__ == "__main__":
    main()
