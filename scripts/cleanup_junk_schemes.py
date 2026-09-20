"""
Cleanup Junk Schemes
====================
Removes scheme records that were incorrectly generated from bad extraction runs.
Junk schemes have names like "[Section: UNKNOWN]", "[Section: DOCUMENTS_REQUIRED]", etc.
Legitimate schemes are kept.

Run from backend/ directory:
    python ..\scripts\cleanup_junk_schemes.py
"""

import sys
import re
sys.stdout.reconfigure(encoding="utf-8")

from app.database.session import SessionLocal
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.models.scheme_embedding import SchemeEmbedding

# Pattern that identifies junk schemes (section-header extractions, not real schemes)
JUNK_NAME_PATTERNS = [
    r"^\[Section:",       # [Section: UNKNOWN], [Section: ELIGIBILITY], etc.
    r"^\[Section\b",
]

def is_junk_scheme(name_en: str) -> bool:
    if not name_en:
        return False
    for pattern in JUNK_NAME_PATTERNS:
        if re.search(pattern, name_en.strip(), re.IGNORECASE):
            return True
    return False

def main():
    db = SessionLocal()
    try:
        all_schemes = db.query(Scheme).all()
        junk = [s for s in all_schemes if is_junk_scheme(s.name_en or "")]
        keep = [s for s in all_schemes if not is_junk_scheme(s.name_en or "")]

        print("=" * 60)
        print("  JanSetu — Junk Scheme Cleanup")
        print("=" * 60)
        print(f"\n  Total schemes in DB: {len(all_schemes)}")
        print(f"  Legitimate schemes to KEEP: {len(keep)}")
        print(f"  Junk schemes to DELETE: {len(junk)}")
        print()

        if keep:
            print("  KEEPING:")
            for s in keep:
                print(f"    + [{s.scheme_code}] {s.name_en}")
        print()

        if not junk:
            print("  Nothing to delete. DB is already clean.")
            return

        print("  DELETING:")
        for s in junk:
            print(f"    - [{s.scheme_code}] {s.name_en}")

        confirm = input("\n  Proceed with deletion? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("  Aborted.")
            return

        deleted_count = 0
        for s in junk:
            scheme_id_str = str(s.id)

            # 1. Delete embeddings
            emb_deleted = db.query(SchemeEmbedding).filter(
                SchemeEmbedding.scheme_id == scheme_id_str
            ).delete(synchronize_session=False)

            # 2. Delete search metadata
            meta_deleted = db.query(SchemeSearchMetadata).filter(
                SchemeSearchMetadata.scheme_id == scheme_id_str
            ).delete(synchronize_session=False)

            # 3. Delete scheme versions
            ver_deleted = db.query(SchemeVersion).filter(
                SchemeVersion.scheme_id == s.id
            ).delete(synchronize_session=False)

            # 4. Delete scheme itself
            db.delete(s)

            print(f"    Deleted [{s.scheme_code}]: {emb_deleted} embeddings, "
                  f"{meta_deleted} search metadata, {ver_deleted} versions")
            deleted_count += 1

        db.commit()
        print(f"\n  Done. Deleted {deleted_count} junk scheme(s).")
        print(f"  Remaining schemes: {db.query(Scheme).count()}")

    except Exception as e:
        db.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
