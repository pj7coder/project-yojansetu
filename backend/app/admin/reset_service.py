import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict
from fastapi import HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.cache.verified_rule_cache import get_rule_cache
from app.core.config import get_settings
from app.database.session import engine
from app.sessions.manager import get_session_manager

logger = logging.getLogger("yojansetu.admin.reset")

TABLES_TO_TRUNCATE = [
    # Search & Embeddings
    "scheme_embeddings",
    "scheme_search_metadata",
    # Scheme Changes & Drafts
    "scheme_change_items",
    "scheme_change_sets",
    "scheme_document_links",
    "scheme_drafts",
    "scheme_versions",
    "schemes",
    # Review & Audit
    "human_review_items",
    "human_review_sessions",
    "review_audit_events",
    # Verification & Validation
    "fact_verifications",
    "evidence_verification_runs",
    "validation_issues",
    "validation_runs",
    # Pipeline Runs & Chunks
    "normalization_runs",
    "extraction_runs",
    "document_chunks",
    "ocr_runs",
    "parsed_documents",
    "document_relationships",
    "documents",
    # Sources & Crawling
    "web_content_artifacts",
    "discovered_resources",
    "source_change_analyses",
    "source_change_events",
    "source_monitor_runs",
    "source_monitor_states",
    "source_urls",
    "sources",
    # Admin Operations
    "admin_operation_events",
    "worker_heartbeats",
    # Generated Catalog Reference Data
    "departments",
    "categories",
]

STORAGE_SUBDIRS = [
    "incoming",
    "originals",
    "failed",
    "fingerprints",
    "parsed",
    "ocr",
    "chunks",
    "extracted",
    "normalized",
    "validation",
    "verification",
    "verified",
    "archived",
    "monitoring",
    "schemes",
    "audio",
    "benchmarks",
]


class AdminResetService:
    """Service to execute an authorized, complete system purge and factory reset."""

    def __init__(self):
        self.settings = get_settings()

    def reset_all_data(self, confirmation: str) -> Dict[str, Any]:
        """
        Executes complete wipe of database records, storage files, and caches.
        Requires exact confirmation string 'DELETE'.
        """
        if not confirmation or confirmation.strip() != "DELETE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation phrase mismatch. You must type 'DELETE' in all caps to confirm this operation.",
            )

        logger.warning("AUTHORIZED PLATFORM RESET INITIATED: Purging all database tables and storage artifacts.")

        # 1. Truncate Database Tables
        tables_cleared = 0
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        with engine.begin() as conn:
            for table in TABLES_TO_TRUNCATE:
                if table in existing_tables:
                    conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE;'))
                    tables_cleared += 1

        # 2. Clean Filesystem Storage (both project root storage and backend storage)
        files_removed = 0
        repo_root = self.settings.base_dir.parent

        for storage_root in [repo_root / "storage", self.settings.base_dir / "storage"]:
            if not storage_root.exists():
                continue

            for subdir_name in STORAGE_SUBDIRS:
                target_dir = storage_root / subdir_name
                if target_dir.exists():
                    for item in target_dir.iterdir():
                        if item.is_file() or item.is_symlink():
                            item.unlink()
                            files_removed += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            files_removed += 1
                else:
                    target_dir.mkdir(parents=True, exist_ok=True)

        # Ensure all directories exist cleanly
        self.settings.ensure_storage_dirs()

        # 3. Clean in-memory caches
        try:
            rule_cache = get_rule_cache()
            rule_cache.clear()
        except Exception as e:
            logger.warning(f"Error clearing rule cache: {e}")

        try:
            session_mgr = get_session_manager()
            with session_mgr._lock:
                session_mgr._sessions.clear()
        except Exception as e:
            logger.warning(f"Error clearing session manager: {e}")

        logger.info(
            f"PLATFORM RESET COMPLETE: Cleared {tables_cleared} tables, removed {files_removed} files."
        )

        return {
            "status": "success",
            "message": "All platform data (schemes, documents, sources, pipeline runs, and review records) has been completely reset to a clean state.",
            "tables_cleared": tables_cleared,
            "files_removed": files_removed,
        }
