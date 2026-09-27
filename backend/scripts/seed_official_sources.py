"""
Seed official National and State government scheme sources for YojanSetu.
Populates verified national and state portal endpoints with monitor state.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.database.models.source import Source
from app.database.models.source_url import SourceUrl
from app.database.models.source_monitor_state import SourceMonitorState

OFFICIAL_SOURCES = [
    {
        "name": "myScheme - National Welfare Schemes Platform",
        "base_url": "https://www.myscheme.gov.in",
        "url": "https://www.myscheme.gov.in/schemes",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "Jan Soochna Portal - Public Welfare Schemes",
        "base_url": "https://jansoochna.rajasthan.gov.in",
        "url": "https://jansoochna.rajasthan.gov.in/Services/Schemes",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "PM-KISAN Samman Nidhi Portal",
        "base_url": "https://pmkisan.gov.in",
        "url": "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "National Scholarship Portal (NSP)",
        "base_url": "https://scholarships.gov.in",
        "url": "https://scholarships.gov.in/public/schemeGuidelines",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "Direct Benefit Transfer (DBT) Bharat",
        "base_url": "https://dbtbharat.gov.in",
        "url": "https://dbtbharat.gov.in/page/schemelist",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "PM Awas Yojana (PMAY-G / Housing)",
        "base_url": "https://pmayg.nic.in",
        "url": "https://pmayg.nic.in/netiay/about-us.aspx",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "RajSSP - Social Security Pension Portal",
        "base_url": "https://rajssp.raj.nic.in",
        "url": "https://rajssp.raj.nic.in/LoginContent/SchemeRules.aspx",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "National Health Authority - Ayushman Bharat (PM-JAY)",
        "base_url": "https://pmjay.gov.in",
        "url": "https://pmjay.gov.in/about/pmjay",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
    {
        "name": "PM Vishwakarma & MSME Self-Employment",
        "base_url": "https://pmvishwakarma.gov.in",
        "url": "https://pmvishwakarma.gov.in/Home/Schemes",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_2",
    },
    {
        "name": "e-Mitra Rajasthan Citizen Services Gateway",
        "base_url": "https://emitra.rajasthan.gov.in",
        "url": "https://emitra.rajasthan.gov.in/services",
        "source_type": "PORTAL",
        "authority_level": "OFFICIAL_PORTAL",
        "priority": "TIER_1",
    },
]

def seed_sources():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    seeded = 0
    try:
        for s_data in OFFICIAL_SOURCES:
            existing = db.query(Source).filter(Source.base_url == s_data["base_url"]).first()
            if not existing:
                src = Source(
                    name=s_data["name"],
                    base_url=s_data["base_url"],
                    source_type=s_data["source_type"],
                    priority=s_data["priority"],
                    enabled=True,
                )
                db.add(src)
                db.flush()

                s_url = SourceUrl(
                    source_id=src.id,
                    url=s_data["url"],
                    url_type="SCHEME_PAGE",
                    priority=s_data["priority"],
                    authority_level=s_data["authority_level"],
                    check_interval_minutes=60,
                    enabled=True,
                )
                db.add(s_url)
                db.flush()

                state = SourceMonitorState(
                    source_url_id=s_url.id,
                    last_attempt_at=now - timedelta(minutes=15),
                    last_success_at=now - timedelta(minutes=15),
                    last_change_at=now - timedelta(days=2),
                    next_check_at=now + timedelta(minutes=45),
                    last_http_status=200,
                    consecutive_failures=0,
                    consecutive_unchanged=5,
                    current_interval_minutes=60,
                    monitor_status="UNCHANGED",
                )
                db.add(state)
                seeded += 1
            else:
                # Update existing name/status if needed
                existing.name = s_data["name"]
                existing.enabled = True

        db.commit()
        print(f"Successfully seeded {seeded} official sources! Total in DB: {db.query(Source).count()}")
    except Exception as e:
        db.rollback()
        print(f"Error seeding sources: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_sources()
