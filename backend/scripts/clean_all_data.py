"""
JanSetu - Maintenance Utility: Complete Data Clean & Reset.

Purges:
- All database records across schemes, documents, sources, reviews, runs, and pipeline data.
- All files in storage/ and backend/storage/ (preserving models/).
- Scratch temporary files.
- In-memory rule caches.
"""

import os
import shutil
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from app.core.config import settings
from app.database.session import engine


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
    # Reference catalog data (test departments and test categories)
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


def clean_database():
    print("\n--- 1. Resetting PostgreSQL Database ---")
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in TABLES_TO_TRUNCATE:
            if table in existing_tables:
                print(f"  Truncating table: {table}")
                conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE;'))
            else:
                print(f"  Table not found (skipping): {table}")

    print("Database truncation complete.")


def clean_storage_directory(storage_root_path: Path):
    print(f"\n--- Cleaning storage root: {storage_root_path} ---")
    if not storage_root_path.exists():
        print(f"  Directory does not exist: {storage_root_path}")
        return

    for subdir_name in STORAGE_SUBDIRS:
        target_dir = storage_root_path / subdir_name
        if target_dir.exists():
            deleted_count = 0
            for item in target_dir.iterdir():
                if item.is_file() or item.is_symlink():
                    item.unlink()
                    deleted_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_count += 1
            print(f"  Cleaned {subdir_name}/: removed {deleted_count} items")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Created empty {subdir_name}/")

    # Ensure models dir is kept untouched if inside storage
    models_dir = storage_root_path / "models"
    if models_dir.exists():
        model_count = sum(len(files) for _, _, files in os.walk(models_dir))
        print(f"  [PRESERVED] models/: {model_count} model files preserved")


def clean_scratch_files(repo_root: Path):
    print("\n--- 3. Cleaning Temporary Scratch Files ---")
    scratch_files = [
        repo_root / "temp.file",
        repo_root / "backend" / "scratch_catalog_check.py",
        repo_root / "backend" / "scratch_inspect_db.py",
    ]
    for sf in scratch_files:
        if sf.exists():
            sf.unlink()
            print(f"  Removed scratch file: {sf.name}")


def main():
    repo_root = backend_dir.parent
    clean_database()

    # Clean both storage locations (root and backend)
    clean_storage_directory(repo_root / "storage")
    clean_storage_directory(backend_dir / "storage")

    clean_scratch_files(repo_root)

    print("\n[SUCCESS] Cleanup completed successfully.")


if __name__ == "__main__":
    main()
