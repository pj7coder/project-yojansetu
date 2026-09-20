import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Set
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.database.session import get_db_context
from app.ingestion.service import DocumentIngestionError, DocumentIngestionService
from app.ingestion.storage import StorageManager

logger = logging.getLogger("jansetu.ingestion.watcher")


class IncomingFolderHandler(FileSystemEventHandler):
    """Event handler for detecting new or moved files in the incoming storage directory."""

    def __init__(
        self,
        ingestion_service: DocumentIngestionService,
        stability_interval_sec: float = 1.0,
        max_stability_checks: int = 10,
    ):
        super().__init__()
        self.ingestion_service = ingestion_service
        self.stability_interval_sec = stability_interval_sec
        self.max_stability_checks = max_stability_checks
        self._processing_files: Set[str] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._handle_candidate_file(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        # If moved into incoming folder
        dest_path = getattr(event, "dest_path", None)
        if dest_path:
            self._handle_candidate_file(Path(dest_path))

    def _wait_for_file_stability(self, file_path: Path) -> bool:
        """
        Poll the file until its size stabilizes and it is no longer being actively written.

        :param file_path: Path to the file being copied or written.
        :return: True if file is stable and readable, False if timed out or vanished.
        """
        if not file_path.exists():
            return False

        last_size = -1
        checks = 0

        while checks < self.max_stability_checks:
            try:
                if not file_path.exists():
                    return False
                current_size = file_path.stat().st_size
                if current_size > 0 and current_size == last_size:
                    # Size hasn't changed over the interval; try opening in read mode
                    try:
                        with open(file_path, "rb") as f:
                            f.read(1024)
                        logger.debug("File '%s' is stable at %d bytes", file_path.name, current_size)
                        return True
                    except OSError:
                        # File is locked by writing process
                        pass
                last_size = current_size
            except OSError as e:
                logger.debug("Transient error inspecting '%s': %s", file_path.name, e)

            time.sleep(self.stability_interval_sec)
            checks += 1

        logger.warning("File '%s' failed to stabilize after %d checks", file_path.name, checks)
        return False

    def _handle_candidate_file(self, file_path: Path) -> None:
        """Process a candidate file with stability checks and duplicate event prevention."""
        abs_str = str(file_path.resolve())

        # Ignore hidden files or .gitkeep
        if file_path.name.startswith("."):
            return

        if abs_str in self._processing_files:
            return

        self._processing_files.add(abs_str)
        try:
            logger.info("New incoming file detected: %s", file_path.name)

            if not self._wait_for_file_stability(file_path):
                logger.warning("Skipping unstable or missing file: %s", file_path.name)
                return

            # Open a fresh database session and ingest
            with get_db_context() as db:
                try:
                    self.ingestion_service.ingest_document(
                        db=db,
                        file_path=file_path,
                        original_filename=file_path.name,
                        ingestion_method="FOLDER_WATCHER",
                        move_file=True,
                    )
                    logger.info("Watcher successfully processed: %s", file_path.name)
                except DocumentIngestionError as e:
                    logger.warning("Watcher document ingestion rejected '%s': %s", file_path.name, e.message)
                except Exception as e:
                    logger.error("Unexpected error during watcher ingestion for '%s': %s", file_path.name, str(e), exc_info=True)
        finally:
            self._processing_files.discard(abs_str)


class FolderWatcher:
    """
    Automatic watcher monitoring storage/incoming/ for new Rajasthan government documents.

    Includes:
    - Startup scanning of existing incoming files.
    - Filesystem event observer using watchdog.
    - File stability polling before ingestion.
    """

    def __init__(
        self,
        watch_dir: Optional[Path] = None,
        ingestion_service: Optional[DocumentIngestionService] = None,
    ):
        settings = get_settings()
        self.watch_dir = (watch_dir or settings.incoming_dir).resolve()
        self.ingestion_service = ingestion_service or DocumentIngestionService()
        self.event_handler = IncomingFolderHandler(self.ingestion_service)
        self.observer = Observer()

    def scan_existing_files(self) -> int:
        """
        Scan and process any files already present in the incoming folder at startup.
        Returns the number of files discovered.
        """
        if not self.watch_dir.exists():
            self.watch_dir.mkdir(parents=True, exist_ok=True)
            return 0

        existing_files = [
            f for f in self.watch_dir.iterdir()
            if f.is_file() and not f.name.startswith(".")
        ]

        if not existing_files:
            logger.info("Startup scan: No pending files found in incoming directory (%s)", self.watch_dir)
            return 0

        logger.info("Startup scan: Found %d existing file(s) to process in %s", len(existing_files), self.watch_dir)
        processed_count = 0
        for f in existing_files:
            try:
                self.event_handler._handle_candidate_file(f)
                processed_count += 1
            except Exception as e:
                logger.error("Error processing existing file '%s': %s", f.name, str(e))

        return processed_count

    def start(self) -> None:
        """Start the startup scan and launch the background filesystem watcher observer."""
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Starting FolderWatcher on directory: %s", self.watch_dir)

        # 1. Process backlog files on startup
        self.scan_existing_files()

        # 2. Schedule and start filesystem observer
        self.observer.schedule(self.event_handler, str(self.watch_dir), recursive=False)
        self.observer.start()
        logger.info("FolderWatcher active and monitoring for incoming PDF files")

    def stop(self) -> None:
        """Gracefully stop the folder watcher observer."""
        logger.info("Stopping FolderWatcher...")
        self.observer.stop()
        self.observer.join()
        logger.info("FolderWatcher stopped successfully")


def run_watcher() -> None:
    """CLI entrypoint for running the folder watcher process standalone."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info("=== JANSETU AUTOMATIC FOLDER WATCHER ===")

    # Ensure storage directories exist
    settings.ensure_storage_dirs()

    watcher = FolderWatcher()
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received; exiting watcher...")
    finally:
        watcher.stop()


if __name__ == "__main__":
    run_watcher()
