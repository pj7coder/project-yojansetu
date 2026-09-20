"""
Watch Folder Service
====================
Monitors a designated hot folder (`storage/watch_folder`) for incoming PDF documents.
Whenever a new document is dropped, it moves it to the ingestion pipeline, runs the
complete extraction & normalization stages, and directly publishes the scheme to
the database without human review.
"""

import asyncio
import logging
import os
from pathlib import Path
import time
from typing import List, Optional
import uuid

from app.core.config import get_settings
from app.database.session import get_db_context
from app.ingestion.service import DocumentIngestionService
from app.pipeline.auto_runner import run_full_pipeline

logger = logging.getLogger("yojansetu.ingestion.folder_watcher")


SUPPORTED_WATCH_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv"}


class FolderWatcherService:
    """Monitors storage/watch_folder and automatically ingests new PDF and Excel files."""

    def __init__(self, watch_dir: Optional[Path] = None):
        self.settings = get_settings()
        self.watch_dir = watch_dir or self.settings.watch_folder_dir
        self.ingestion_service = DocumentIngestionService()
        self._is_running = False

    def ensure_dir(self) -> Path:
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        return self.watch_dir

    def scan_and_process(self) -> List[uuid.UUID]:
        """
        Synchronously scans the watch folder for new PDF and spreadsheet files.
        Moves each detected document into the ingestion pipeline and runs auto-runner.
        Returns the list of ingested Document UUIDs.
        """
        self.ensure_dir()
        ingested_ids: List[uuid.UUID] = []

        try:
            # Find all candidate PDF, XLSX, XLS, CSV files (ignoring temporary lock files like ~$Book.xlsx)
            candidate_files = [
                p for p in self.watch_dir.iterdir()
                if p.is_file()
                and p.suffix.lower() in SUPPORTED_WATCH_EXTENSIONS
                and not p.name.startswith((".", "~", "$"))
                and not p.name.endswith((".tmp", ".part", ".crdownload"))
            ]

            if not candidate_files:
                return ingested_ids

            logger.info("Watch folder scan found %d new document(s) in %s", len(candidate_files), self.watch_dir)

            for file_path in candidate_files:
                try:
                    # Verify file is not still being written (check size stability)
                    initial_size = file_path.stat().st_size
                    if initial_size == 0:
                        logger.warning("Skipping 0-byte file in watch folder: %s", file_path.name)
                        continue

                    # Brief wait to ensure write completes if copied from explorer
                    time.sleep(0.5)
                    current_size = file_path.stat().st_size
                    if initial_size != current_size:
                        logger.info("File '%s' still copying; will retry next cycle", file_path.name)
                        continue

                    original_filename = file_path.name
                    logger.info("Ingesting document from watch folder: '%s'", original_filename)

                    clean_title = Path(original_filename).stem.replace("_", " ").title()

                    with get_db_context() as db:
                        doc = self.ingestion_service.ingest_document(
                            db=db,
                            file_path=file_path,
                            original_filename=original_filename,
                            ingestion_method="FOLDER_WATCHER",
                            title=clean_title,
                            move_file=True,
                        )
                        doc_id = doc.id
                        ingested_ids.append(doc_id)

                    # Trigger full end-to-end auto-pipeline directly into database
                    logger.info("Launching full auto-pipeline for watch folder document %s (%s)", original_filename, doc_id)
                    run_full_pipeline(doc_id, auto_convert=True)
                    logger.info("Auto-pipeline completed for watch folder document %s", original_filename)

                except Exception as e:
                    logger.error("Failed processing file '%s' from watch folder: %s", file_path.name, e, exc_info=True)

        except Exception as e:
            logger.error("Error during watch folder scan: %s", e, exc_info=True)

        return ingested_ids

    def get_status(self) -> dict:
        """Return operational status and metadata of the watch folder."""
        self.ensure_dir()
        try:
            pending_files = [
                p.name for p in self.watch_dir.iterdir()
                if p.is_file()
                and p.suffix.lower() in SUPPORTED_WATCH_EXTENSIONS
                and not p.name.startswith((".", "~", "$"))
            ]
        except Exception:
            pending_files = []

        return {
            "enabled": self.settings.watch_folder_enabled,
            "folder_path": str(self.watch_dir.resolve()),
            "pending_count": len(pending_files),
            "pending_files": pending_files,
            "is_running": self._is_running,
        }

    async def run_loop(self, poll_interval: float = 4.0) -> None:
        """Asynchronous monitoring loop running inside FastAPI lifespan."""
        self._is_running = True
        logger.info("Folder Watcher started on '%s' (poll interval: %.1fs)", self.watch_dir, poll_interval)
        try:
            while self._is_running:
                # Run synchronous scan in thread pool to not block asyncio event loop
                await asyncio.to_thread(self.scan_and_process)
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Folder Watcher loop received cancellation request.")
        finally:
            self._is_running = False
            logger.info("Folder Watcher stopped.")

    def stop(self) -> None:
        self._is_running = False


# Global singleton instance
_folder_watcher_instance: Optional[FolderWatcherService] = None


def get_folder_watcher() -> FolderWatcherService:
    global _folder_watcher_instance
    if _folder_watcher_instance is None:
        _folder_watcher_instance = FolderWatcherService()
    return _folder_watcher_instance
