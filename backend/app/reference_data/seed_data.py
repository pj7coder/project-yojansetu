"""
Reference Data Seed for Rajasthan Government Departments and Scheme Categories.
Ensures core government departments and welfare functional categories exist in the database
so foreign keys resolve cleanly during document extraction, normalization, and scheme conversion.
"""
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.department import Department
from app.database.models.category import Category
from app.database.session import get_db_context

logger = logging.getLogger("yojansetu.reference_data.seed")

DEFAULT_DEPARTMENTS = [
    {
        "code": "SJE",
        "name_en": "Social Justice and Empowerment Department",
        "name_hi": "सामाजिक न्याय एवं अधिकारिता विभाग",
        "description": "Nodal department for social security pensions, disability welfare, and disadvantaged empowerment.",
        "official_website": "https://sje.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "AGRI",
        "name_en": "Department of Agriculture",
        "name_hi": "कृषि विभाग",
        "description": "Nodal department for farmer welfare, subsidies, crop insurance, and PM-KUSUM solar schemes.",
        "official_website": "https://agriculture.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "ENERGY",
        "name_en": "Department of Energy & Renewable Resources",
        "name_hi": "ऊर्जा एवं अक्षय ऊर्जा विभाग",
        "description": "Renewable energy, solar pump installations, and electricity subsidies.",
        "official_website": "https://energy.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "TRIBAL",
        "name_en": "Tribal Area Development Department",
        "name_hi": "जनजाति क्षेत्रीय विकास विभाग",
        "description": "Welfare, scholarships, fellowships, and livelihoods for Scheduled Tribes in Rajasthan.",
        "official_website": "https://tad.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "FINANCE",
        "name_en": "Finance Department",
        "name_hi": "वित्त विभाग",
        "description": "Financial planning, MUDRA loans, and economic assistance programs.",
        "official_website": "https://finance.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "HEALTH",
        "name_en": "Medical, Health and Family Welfare Department",
        "name_hi": "चिकित्सा, स्वास्थ्य एवं परिवार कल्याण विभाग",
        "description": "Ayushman Arogya, Chiranjeevi, and universal health coverage.",
        "official_website": "https://health.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "RURAL",
        "name_en": "Rural Development and Panchayati Raj Department",
        "name_hi": "ग्रामीण विकास एवं पंचायती राज विभाग",
        "description": "Rural livelihoods, housing, and MNREGA.",
        "official_website": "https://rdpr.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "EDUCATION",
        "name_en": "School and Higher Education Department",
        "name_hi": "शिक्षा विभाग",
        "description": "Scholarships, coaching schemes, and student support.",
        "official_website": "https://education.rajasthan.gov.in",
        "active": True,
    },
    {
        "code": "MSME",
        "name_en": "Industries and Commerce / MSME Department",
        "name_hi": "उद्योग एवं वाणिज्य विभाग",
        "description": "Support for micro, small, and medium enterprises and industrial subsidies.",
        "official_website": "https://industries.rajasthan.gov.in",
        "active": True,
    },
]

DEFAULT_CATEGORIES = [
    {
        "code": "PENSION",
        "name_en": "Social Security & Old Age Pension",
        "name_hi": "सामाजिक सुरक्षा एवं वृद्धावस्था पेंशन",
        "description": "Old age, widow, and disability pension schemes.",
        "active": True,
    },
    {
        "code": "AGRICULTURE",
        "name_en": "Agriculture, Solar Pumps & Farming Subsidies",
        "name_hi": "कृषि, सौर पम्प एवं कृषक अनुदान",
        "description": "Agricultural equipment, solar pumps, and crop assistance.",
        "active": True,
    },
    {
        "code": "FINANCIAL_LOAN",
        "name_en": "Financial Assistance, Loans & Self-Employment",
        "name_hi": "वित्तीय सहायता, ऋण एवं स्वरोजगार",
        "description": "Subsidized credit, Mudra refinance, and business grants.",
        "active": True,
    },
    {
        "code": "SCHOLARSHIP",
        "name_en": "Scholarships, Fellowships & Education",
        "name_hi": "छात्रवृत्ति, फेलोशिप एवं शिक्षा",
        "description": "Academic assistance, national fellowships, and student grants.",
        "active": True,
    },
    {
        "code": "HEALTHCARE",
        "name_en": "Healthcare, Health Insurance & Medical Relief",
        "name_hi": "स्वास्थ्य, बीमा एवं चिकित्सा सहायता",
        "description": "Hospitalization coverage, health cards, and emergency relief.",
        "active": True,
    },
    {
        "code": "WOMEN_CHILD",
        "name_en": "Women & Child Welfare",
        "name_hi": "महिला एवं बाल विकास",
        "description": "Maternity benefits, girl child education, and women empowerment.",
        "active": True,
    },
    {
        "code": "HOUSING",
        "name_en": "Housing & Urban/Rural Infrastructure",
        "name_hi": "आवास एवं ग्रामीण/शहरी विकास",
        "description": "Affordable housing, sanitation, and pucca house assistance.",
        "active": True,
    },
]


def seed_departments_and_categories(session: Session) -> dict:
    """Idempotently seeds standard departments and categories into PostgreSQL."""
    dept_added = 0
    dept_existing = 0
    for d in DEFAULT_DEPARTMENTS:
        stmt = select(Department).where(Department.code == d["code"])
        existing = session.execute(stmt).scalar_one_or_none()
        if not existing:
            new_dept = Department(**d)
            session.add(new_dept)
            dept_added += 1
        else:
            dept_existing += 1

    cat_added = 0
    cat_existing = 0
    for c in DEFAULT_CATEGORIES:
        stmt = select(Category).where(Category.code == c["code"])
        existing = session.execute(stmt).scalar_one_or_none()
        if not existing:
            new_cat = Category(**c)
            session.add(new_cat)
            cat_added += 1
        else:
            cat_existing += 1

    session.commit()
    logger.info(
        "Seeded departments: %d new, %d existing | categories: %d new, %d existing",
        dept_added, dept_existing, cat_added, cat_existing
    )
    return {
        "departments_added": dept_added,
        "departments_existing": dept_existing,
        "categories_added": cat_added,
        "categories_existing": cat_existing,
    }


if __name__ == "__main__":
    with get_db_context() as db:
        res = seed_departments_and_categories(db)
        print("Reference seed complete:", res)
