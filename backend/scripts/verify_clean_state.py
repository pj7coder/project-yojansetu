import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from app.database.session import engine

def verify_db():
    print("=== Database Table Verification ===")
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    with engine.connect() as conn:
        for t in tables:
            count = conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
            status = "CLEAN (0 rows)" if count == 0 else f"ACTIVE ({count} rows)"
            if t == "alembic_version":
                status = f"PRESERVED ({count} migration row)"
            print(f"  {t}: {status}")

def verify_storage(storage_path: Path):
    print(f"\n=== Storage Verification: {storage_path} ===")
    if not storage_path.exists():
        print("  Does not exist.")
        return
    for item in sorted(storage_path.iterdir()):
        if item.is_dir():
            if item.name == "models":
                files = [f for _, _, f in os.walk(item)]
                total = sum(len(f) for f in files)
                print(f"  {item.name}/: [PRESERVED MODEL WEIGHTS] ({total} files)")
            else:
                files = [f for _, _, f in os.walk(item)]
                total = sum(len(f) for f in files)
                status = "CLEAN (0 files)" if total == 0 else f"NOT CLEAN ({total} files)"
                print(f"  {item.name}/: {status}")

if __name__ == "__main__":
    repo_root = backend_dir.parent
    verify_db()
    verify_storage(repo_root / "storage")
    verify_storage(backend_dir / "storage")
