"""
Seed script for development and integration test verification.
Populates minimal structural seed records without fake government data.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import logging
from app.core.logging import setup_logging
from app.database.session import SessionLocal
from app.repositories.category_repository import CategoryRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.scheme_repository import SchemeRepository
from app.schemas.category import CategoryCreate
from app.schemas.department import DepartmentCreate
from app.schemas.scheme import SchemeCreate

setup_logging("INFO")
logger = logging.getLogger("jansetu.seed")


def seed_development_data() -> None:
    """Seed test department, category, and draft test scheme."""
    db = SessionLocal()
    dept_repo = DepartmentRepository()
    cat_repo = CategoryRepository()
    scheme_repo = SchemeRepository()

    try:
        # 1. Seed Department
        dept = dept_repo.get_by_code(db, "TEST-DEPT")
        if not dept:
            dept = dept_repo.create(
                db,
                DepartmentCreate(
                    code="TEST-DEPT",
                    name_en="Test Government Department",
                    name_hi="परीक्षण सरकारी विभाग",
                    description="Development testing department placeholder",
                    official_website="https://rajasthan.gov.in",
                    active=True,
                ),
            )
            logger.info("Created test department: %s (%s)", dept.code, dept.id)
        else:
            logger.info("Test department already exists: %s", dept.code)

        # 2. Seed Category
        cat = cat_repo.get_by_code(db, "test-category")
        if not cat:
            cat = cat_repo.create(
                db,
                CategoryCreate(
                    code="test-category",
                    name_en="Test Category",
                    name_hi="परीक्षण श्रेणी",
                    description="Development testing category",
                    active=True,
                ),
            )
            logger.info("Created test category: %s (%s)", cat.code, cat.id)
        else:
            logger.info("Test category already exists: %s", cat.code)

        # 3. Seed Draft Scheme
        scheme = scheme_repo.get_by_code(db, "TEST-SCHEME-001")
        if not scheme:
            scheme = scheme_repo.create(
                db,
                SchemeCreate(
                    scheme_code="TEST-SCHEME-001",
                    name_en="Development Test Scheme",
                    name_hi="परीक्षण योजना",
                    short_name="TEST-SCHEME",
                    department_id=dept.id,
                    category_id=cat.id,
                    short_description="Placeholder draft scheme used to verify database persistence and Hindi Unicode support.",
                    status="DRAFT",
                    jurisdiction="RAJASTHAN",
                    scheme_origin="UNKNOWN",
                    initial_source_summary="Development seed baseline",
                ),
            )
            logger.info("Created test scheme: %s (%s)", scheme.scheme_code, scheme.id)
        else:
            logger.info("Test scheme already exists: %s", scheme.scheme_code)

        logger.info("Development seeding completed successfully.")
    except Exception as e:
        logger.error("Error during development seeding: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_development_data()
