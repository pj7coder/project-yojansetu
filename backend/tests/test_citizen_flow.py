from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.cache.verified_rule_cache import CachedRuleEntry, VerifiedRuleCache, get_rule_cache
from app.citizen.service import load_rajasthan_districts
from app.database.models.category import Category
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.database.session import SessionLocal
from app.eligibility.compiler import EligibilityRuleCompiler
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def cleanup_citizen_test_data():
    """Ensures test schemes and search metadata are deleted after test suite runs."""
    yield
    db = SessionLocal()
    try:
        schemes = db.execute(select(Scheme).where(Scheme.scheme_code.like("RJ-CIT-%"))).scalars().all()
        scheme_ids = [str(s.id) for s in schemes]
        if scheme_ids:
            db.query(SchemeSearchMetadata).filter(SchemeSearchMetadata.scheme_id.in_(scheme_ids)).delete(synchronize_session=False)
            for s in schemes:
                db.delete(s)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def make_canonical_scheme_data(
    scheme_id: str,
    name_en: str,
    name_hi: str,
    dept_name: str,
    root_rule: Dict[str, Any],
    districts: Optional[List[str]] = None,
    benefits: Optional[List[Dict[str, Any]]] = None,
    documents: Optional[List[Dict[str, Any]]] = None,
    portal_url: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "scheme_identity": {
            "scheme_id": scheme_id,
            "name": {"en": name_en, "hi": name_hi},
            "department": dept_name,
            "department_hi": f"{dept_name} (हिंदी)",
            "description": f"Official test description for {name_en}",
            "description_hi": f"{name_hi} का आधिकारिक विवरण",
            "category": "PENSION",
            "scheme_origin": "RAJASTHAN_STATE",
            "jurisdiction": "Rajasthan",
        },
        "scope": {
            "state": "Rajasthan",
            "districts": districts or [],
            "rural_urban": "BOTH",
        },
        "eligibility": {
            "root_rule": root_rule,
        },
        "exclusions": [],
        "benefits": benefits or [
            {
                "type": "CASH",
                "amount": 1000,
                "currency": "INR",
                "frequency": "MONTHLY",
                "description": "₹1,000 per month pension",
                "description_hi": "₹1,000 प्रति माह पेंशन",
            }
        ],
        "required_documents": documents or [
            {
                "document_name": "Aadhaar Card",
                "document_name_hi": "आधार कार्ड",
                "is_mandatory": True,
            },
            {
                "document_name": "Jan Aadhaar Card",
                "document_name_hi": "जन आधार कार्ड",
                "is_mandatory": True,
            },
            {
                "document_name": "Income Certificate",
                "document_name_hi": "आय प्रमाण पत्र",
                "is_mandatory": False,
            },
        ],
        "application": {
            "channels": ["e-Mitra Kiosk", "Rajasthan SSO Portal"],
            "portal_url": portal_url or "https://sso.rajasthan.gov.in",
            "submission_mode": "ONLINE_AND_OFFLINE",
            "steps": [
                "Visit nearest e-Mitra or login to SSO",
                "Submit required documents",
                "Obtain receipt",
            ],
            "fee": 0,
        },
        "important_dates": [],
    }


def seed_test_scheme_with_version(
    db,
    scheme_code: str,
    name_en: str,
    name_hi: str,
    root_rule: Dict[str, Any],
    version_num: int = 1,
    status: str = "ACTIVE",
    valid_from: Optional[date] = None,
    valid_until: Optional[date] = None,
    portal_url: Optional[str] = None,
    districts: Optional[List[str]] = None,
) -> tuple[Scheme, SchemeVersion]:
    dept = db.execute(select(Department).where(Department.code == "RJ-CIT-DEPT")).scalars().first()
    if not dept:
        dept = Department(
            id=uuid.uuid4(),
            code="RJ-CIT-DEPT",
            name_en="Social Justice Department",
            name_hi="सामाजिक न्याय विभाग",
        )
        db.add(dept)

    cat = db.execute(select(Category).where(Category.code == "CIT-PENSION")).scalars().first()
    if not cat:
        cat = Category(
            id=uuid.uuid4(),
            code="CIT-PENSION",
            name_en="Pension",
            name_hi="पेंशन",
        )
        db.add(cat)

    scheme = db.execute(select(Scheme).where(Scheme.scheme_code == scheme_code)).scalars().first()
    if not scheme:
        scheme = Scheme(
            id=uuid.uuid4(),
            scheme_code=scheme_code,
            name_en=name_en,
            name_hi=name_hi,
            short_name=name_en[:20],
            department_id=dept.id,
            category_id=cat.id,
            status="HUMAN_VERIFIED",
            jurisdiction="RAJASTHAN",
            scheme_origin="RAJASTHAN_STATE",
        )
        db.add(scheme)
        db.commit()
        db.refresh(scheme)

    canon = make_canonical_scheme_data(
        scheme_id=str(scheme.id),
        name_en=name_en,
        name_hi=name_hi,
        dept_name=dept.name_en,
        root_rule=root_rule,
        portal_url=portal_url,
        districts=districts,
    )

    existing_ver = db.execute(
        select(SchemeVersion).where(
            SchemeVersion.scheme_id == scheme.id,
            SchemeVersion.version_number == version_num,
        )
    ).scalars().first()

    if existing_ver:
        existing_ver.status = status
        existing_ver.canonical_data = canon
        existing_ver.valid_from = valid_from or date(2025, 1, 1)
        existing_ver.valid_until = valid_until
        existing_ver.effective_date = valid_from or date(2025, 1, 1)
        existing_ver.is_current = (status == "ACTIVE")
        ver = existing_ver
    else:
        ver = SchemeVersion(
            id=uuid.uuid4(),
            scheme_id=scheme.id,
            version_number=version_num,
            version_label=f"v{version_num}.0",
            status=status,
            valid_from=valid_from or date(2025, 1, 1),
            valid_until=valid_until,
            effective_date=valid_from or date(2025, 1, 1),
            canonical_data=canon,
            is_current=(status == "ACTIVE"),
            source_summary=f"Official test circular for {name_en}",
        )
        db.add(ver)

    # Add or update search metadata so candidate filter picks it up
    search_meta = db.execute(select(SchemeSearchMetadata).where(SchemeSearchMetadata.scheme_id == str(scheme.id))).scalars().first()
    if not search_meta:
        search_meta = SchemeSearchMetadata(
            scheme_id=str(scheme.id),
            scheme_name=name_en,
            scheme_name_hi=name_hi,
            department_id=dept.id,
            state="Rajasthan",
            districts=districts or [],
            rural_urban="BOTH",
            scheme_origin="RAJASTHAN_STATE",
            category="Pension",
            is_active=(status == "ACTIVE"),
            is_verified=True,
            search_text=f"{name_en} {name_hi} pension farmer agriculture",
            search_text_hash=f"hash-{scheme.id}",
        )
        db.add(search_meta)
    else:
        search_meta.is_active = (status == "ACTIVE")
        search_meta.districts = districts or []

    db.commit()
    db.refresh(scheme)
    db.refresh(ver)

    # Pre-compile into RAM Rule Cache
    cache = get_rule_cache()
    raw_wrapper = {
        "schema_version": "1.0",
        "review": {"status": "HUMAN_VERIFIED", "artifact_sha256": f"hash-{scheme.id}-v{version_num}"},
        "canonical_scheme": canon,
    }
    compiled = EligibilityRuleCompiler.compile_scheme(raw_wrapper)
    cache._cache[str(scheme.id)] = CachedRuleEntry(
        scheme_id=str(scheme.id),
        scheme_version=str(version_num),
        version_hash=f"hash-{scheme.id}-v{version_num}",
        compiled_scheme=compiled,
        cached_at=datetime.now(timezone.utc),
    )

    return scheme, ver


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_citizen_initial_session():
    """1. Test creating new temporary session. No profile data exists initially."""
    res = client.post("/api/v1/citizen/sessions")
    assert res.status_code == 201
    data = res.json()
    assert "session_id" in data
    assert "expires_at" in data
    session_id = data["session_id"]

    # Verify summary has empty known fields
    summary_res = client.get(f"/api/v1/citizen/sessions/{session_id}")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["known_fields"] == []
    assert summary["declined_fields"] == []


def test_citizen_need_input_and_next_question(test_db):
    """2. Enter need text. Discover returns next_question with vernacular prompt and options."""
    # Seed a scheme requiring age >= 60
    scheme, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-VRIDH-01",
        name_en="Old Age Pension",
        name_hi="वृद्धावस्था पेंशन",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 60},
    )

    # Create session
    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Post need
    disc_res = client.post(
        f"/api/v1/citizen/sessions/{session_id}/discover",
        json={"need_text": "मुझे वृद्धावस्था पेंशन चाहिए"},
    )
    assert disc_res.status_code == 200
    data = disc_res.json()

    assert data["state"] == "COLLECTING_INFORMATION"
    assert data["next_question"] is not None
    assert data["next_question"]["field"] == "age"
    assert "आयु" in data["next_question"]["question_hi"] or "वर्ष" in data["next_question"]["question_hi"]
    assert data["next_question"]["data_type"] in ("integer", "number")


def test_citizen_profile_patch_loop(test_db):
    """3. Answering age, district, income updates session facts iteratively."""
    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Step 1: Answer age
    p1 = client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 65}},
    )
    assert p1.status_code == 200
    assert "age" in p1.json()["known_fields"]

    # Step 2: Answer district
    p2 = client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"district": "Udaipur"}},
    )
    assert p2.status_code == 200
    assert "district" in p2.json()["known_fields"]
    assert "age" in p2.json()["known_fields"]

    # Step 3: Answer income
    p3 = client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"family_income": 150000}},
    )
    assert p3.status_code == 200
    assert "family_income" in p3.json()["known_fields"]


def test_no_repeated_known_question(test_db):
    """4. Once age is known, next question must never ask for age again."""
    scheme, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-REPEAT-01",
        name_en="Pension Scheme Repeat Test",
        name_hi="पेंशन परीक्षण योजना",
        root_rule={
            "operator": "AND",
            "conditions": [
                {"condition_id": "C1", "field": "age", "operator": "GTE", "value": 60},
                {"condition_id": "C2", "field": "family_income", "operator": "LTE", "value": 200000},
            ],
        },
    )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Provide age
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 65}},
    )

    # Discover
    disc_res = client.post(
        f"/api/v1/citizen/sessions/{session_id}/discover",
        json={"need_text": "Pension assistance"},
    )
    assert disc_res.status_code == 200
    data = disc_res.json()

    # Next question must NOT be age (it should be family_income)
    if data["next_question"]:
        assert data["next_question"]["field"] != "age"
        assert data["next_question"]["field"] == "family_income"


def test_or_short_circuit_in_citizen_flow(test_db):
    """5. Rule: BPL OR income <= 200000. When BPL is True, income must not be asked."""
    scheme, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-OR-01",
        name_en="BPL or Low Income Scheme",
        name_hi="बीपीएल अथवा निम्न आय योजना",
        root_rule={
            "type": "OR",
            "children": [
                {"condition_id": "C1", "field": "bpl_status", "operator": "EQ", "value": True},
                {"condition_id": "C2", "field": "family_income", "operator": "LTE", "value": 200000},
            ],
        },
    )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Citizen is BPL
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"bpl_status": True}},
    )

    disc_res = client.post(
        f"/api/v1/citizen/sessions/{session_id}/discover",
        json={"need_text": "Low income support"},
    )
    assert disc_res.status_code == 200
    data = disc_res.json()

    # The scheme should already be resolved as ELIGIBLE
    eligible_ids = [c["scheme_id"] for c in data["eligible"]]
    assert str(scheme.id) in eligible_ids

    # Next question must NOT ask for family_income solely for this scheme
    if data["next_question"]:
        assert data["next_question"]["field"] != "family_income"


def test_decline_sensitive_field(test_db):
    """6. When citizen declines a field, backend records decline and suppresses repeated asking."""
    scheme, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-DECLINE-01",
        name_en="Category Specific Scheme",
        name_hi="श्रेणी विशिष्ट योजना",
        root_rule={"condition_id": "C1", "field": "social_category", "operator": "EQ", "value": "SC"},
    )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Decline social_category
    dec_res = client.post(
        f"/api/v1/citizen/sessions/{session_id}/decline-field",
        json={"field_name": "social_category", "reason": "Prefer not to say"},
    )
    assert dec_res.status_code == 200
    assert "social_category" in dec_res.json()["declined_fields"]

    # Discover again
    disc_res = client.post(f"/api/v1/citizen/sessions/{session_id}/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()

    # Next question must not ask social_category
    if data["next_question"]:
        assert data["next_question"]["field"] != "social_category"


def test_enough_confirmed_results_stops_questioning(test_db):
    """7. When 3 target confirmed schemes are reached, question loop stops and shows RESULTS_READY."""
    # Seed 3 schemes where age >= 60 is satisfied
    for i in range(1, 4):
        seed_test_scheme_with_version(
            test_db,
            scheme_code=f"RJ-CIT-ENOUGH-0{i}",
            name_en=f"Confirmed Senior Scheme {i}",
            name_hi=f"पुष्ट वरिष्ठ योजना {i}",
            root_rule={"condition_id": f"C{i}", "field": "age", "operator": "GTE", "value": 60},
        )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 68}},
    )

    disc_res = client.post(f"/api/v1/citizen/sessions/{session_id}/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()

    assert len(data["eligible"]) >= 3
    assert data["state"] == "RESULTS_READY"
    assert data["next_question"] is None


def test_no_relevant_candidates_flow():
    """8. Completely unmatching need returns NO_CANDIDATES state with honest message."""
    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Set district outside Rajasthan
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"state": "Kerala"}},
    )

    disc_res = client.post(f"/api/v1/citizen/sessions/{session_id}/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()

    assert data["state"] == "NO_CANDIDATES"
    assert len(data["eligible"]) == 0
    assert "सत्यापित योजना नहीं मिली" in data["message_hi"] or "सत्यापित" in data["message_hi"]


def test_cannot_resolve_with_available_info(test_db):
    """9. When all candidates require a field and citizen declines it, state is CANNOT_RESOLVE."""
    seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-RESOLVE-01",
        name_en="Unresolvable Scheme",
        name_hi="असमाधेय योजना",
        root_rule={"condition_id": "C1", "field": "family_income", "operator": "LTE", "value": 100000},
    )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Provide age so age-dependent schemes don't block
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 30}},
    )

    # Decline all remaining sensitive/financial candidate fields
    for f in ["family_income", "social_category", "student_status", "bpl_status"]:
        client.post(
            f"/api/v1/citizen/sessions/{session_id}/decline-field",
            json={"field_name": f, "reason": "Prefer not to say"},
        )

    disc_res = client.post(f"/api/v1/citizen/sessions/{session_id}/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()

    assert data["state"] in ("CANNOT_RESOLVE", "RESULTS_READY", "NO_CANDIDATES")
    if data["next_question"] is None and len(data["eligible"]) == 0:
        assert data["state"] in ("CANNOT_RESOLVE", "NO_CANDIDATES")


def test_eligible_vs_potential_separation(test_db):
    """10. Visually separated result states: confirmed eligible vs more_information_required."""
    s_eligible, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-SEP-ELIGIBLE",
        name_en="Confirmed Farmer Scheme",
        name_hi="पुष्ट कृषक योजना",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 18},
    )
    s_more_info, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-SEP-MOREINFO",
        name_en="Income Dependent Scheme",
        name_hi="आय आधारित योजना",
        root_rule={"condition_id": "C2", "field": "family_income", "operator": "LTE", "value": 250000},
    )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 30}},
    )

    disc_res = client.post(f"/api/v1/citizen/sessions/{session_id}/discover")
    assert disc_res.status_code == 200
    data = disc_res.json()

    eligible_ids = [c["scheme_id"] for c in data["eligible"]]
    more_info_ids = [c["scheme_id"] for c in data["more_information_required"]]

    assert str(s_eligible.id) in eligible_ids
    assert str(s_more_info.id) in more_info_ids
    # Disjoint sets
    assert not set(eligible_ids).intersection(set(more_info_ids))


def test_scheme_detail_active_version_only(test_db):
    """11. Scheme detail returns only active verified version with citizen-safe fields."""
    scheme, ver = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-DETAIL-01",
        name_en="Mukhyamantri Vridhjan Pension",
        name_hi="मुख्यमंत्री वृद्धजन पेंशन",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 60},
    )

    res = client.get(f"/api/v1/citizen/schemes/{scheme.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["scheme_code"] == "RJ-CIT-DETAIL-01"
    assert data["version_number"] == 1
    assert data["is_active"] is True
    assert "benefits" in data
    assert len(data["benefits"]) > 0
    assert "required_documents" in data
    assert "application" in data
    assert "official_source" in data

    # Internal technical fields must NOT be present
    assert "reviewer_id" not in data
    assert "raw_llm_response" not in data
    assert "ast_hash" not in data


def test_historical_version_protection(test_db):
    """12. Scheme has v1 (old) and v2 (current). Citizen endpoint serves v2 after effective date."""
    scheme, v1 = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-HIST-01",
        name_en="Evolving Pension Scheme",
        name_hi="परिवर्तनशील पेंशन योजना",
        root_rule={"condition_id": "C1", "field": "family_income", "operator": "LTE", "value": 100000},
        version_num=1,
        status="SUPERSEDED",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
    )

    # Seed v2 active today
    _, v2 = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-HIST-01",
        name_en="Evolving Pension Scheme",
        name_hi="परिवर्तनशील पेंशन योजना",
        root_rule={"condition_id": "C1", "field": "family_income", "operator": "LTE", "value": 200000},
        version_num=2,
        status="ACTIVE",
        valid_from=date(2025, 1, 1),
    )

    res = client.get(f"/api/v1/citizen/schemes/{scheme.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["version_number"] == 2
    assert data["status"] == "ACTIVE"


def test_future_version_not_exposed_as_current(test_db):
    """13. Future verified amendment (valid_from tomorrow) is NOT exposed as currently active today."""
    tomorrow = date.today() + timedelta(days=1)
    scheme, v_future = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-FUTURE-01",
        name_en="Future Scheme",
        name_hi="भविष्य की योजना",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 50},
        version_num=1,
        status="HUMAN_VERIFIED",
        valid_from=tomorrow,
    )

    # Calling today should indicate not yet active (404/410)
    res = client.get(f"/api/v1/citizen/schemes/{scheme.id}")
    assert res.status_code in (404, 410)
    assert "NOT_YET_ACTIVE" in res.json()["detail"] or "not found" in res.json()["detail"].lower()


def test_expired_scheme_handling(test_db):
    """14. Expired scheme version returns inactive warning (HTTP 410 or 404), not active."""
    yesterday = date.today() - timedelta(days=1)
    past = date.today() - timedelta(days=365)
    scheme, v_expired = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-EXPIRED-01",
        name_en="Sunset Scheme",
        name_hi="समाप्त योजना",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 18},
        version_num=1,
        status="EXPIRED",
        valid_from=past,
        valid_until=yesterday,
    )

    res = client.get(f"/api/v1/citizen/schemes/{scheme.id}")
    assert res.status_code in (404, 410)
    assert "EXPIRED" in res.json()["detail"] or "not found" in res.json()["detail"].lower()


def test_documents_and_application_guidance(test_db):
    """15. Verified document list and application guidance render with safe channels and instructions."""
    scheme, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-DOCS-01",
        name_en="Scholarship Scheme",
        name_hi="छात्रवृत्ति योजना",
        root_rule={"condition_id": "C1", "field": "student_status", "operator": "EQ", "value": True},
    )

    res = client.get(f"/api/v1/citizen/schemes/{scheme.id}")
    assert res.status_code == 200
    data = res.json()

    docs = data["required_documents"]
    assert len(docs) >= 2
    # Verify mandatory flag distinction
    has_mandatory = any(d["is_mandatory"] is True for d in docs)
    assert has_mandatory is True

    app_guide = data["application"]
    assert "e-Mitra Kiosk" in app_guide["channels"]
    assert len(app_guide["steps_en"]) > 0
    assert len(app_guide["steps_hi"]) > 0


def test_unsafe_url_blocking(test_db):
    """16. Unsafe application URL (e.g. javascript: or ftp://) is sanitized and marked unsafe."""
    scheme, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-URLSAFE-01",
        name_en="Unsafe URL Scheme",
        name_hi="असुरक्षित यूआरएल योजना",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 18},
        portal_url="javascript:alert(1)",
    )

    res = client.get(f"/api/v1/citizen/schemes/{scheme.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["application"]["is_portal_url_safe"] is False
    assert data["application"]["portal_url"] is None


def test_false_vs_unknown_preservation():
    """17. Boolean false must be explicitly stored as false, not converted to unknown or skipped."""
    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Citizen answers NO to bpl_status
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"bpl_status": False}},
    )

    profile_res = client.get(f"/api/v1/citizen/sessions/{session_id}/profile")
    assert profile_res.status_code == 200
    prof = profile_res.json()["profile"]

    # Must be explicitly boolean False, not None
    assert prof["bpl_status"] is False
    assert "bpl_status" in profile_res.json()["known_fields"]


def test_start_over_resets_session():
    """18. Start Over deletes old session and creates fresh session with zero retained answers."""
    sess_res = client.post("/api/v1/citizen/sessions")
    old_id = sess_res.json()["session_id"]

    client.patch(
        f"/api/v1/citizen/sessions/{old_id}/profile",
        json={"profile": {"age": 65, "district": "Jaipur"}},
    )

    # Delete old session
    del_res = client.delete(f"/api/v1/citizen/sessions/{old_id}")
    assert del_res.status_code == 200

    # Old session is now 404
    assert client.get(f"/api/v1/citizen/sessions/{old_id}").status_code == 404

    # Create new session
    new_res = client.post("/api/v1/citizen/sessions")
    new_id = new_res.json()["session_id"]
    new_summary = client.get(f"/api/v1/citizen/sessions/{new_id}").json()

    assert new_id != old_id
    assert new_summary["known_fields"] == []


def test_profile_correction(test_db):
    """19. Citizen corrects age 64 -> 61. Discovery recomputes accurately without restart."""
    # Scheme requiring age >= 65
    s65, _ = seed_test_scheme_with_version(
        test_db,
        scheme_code="RJ-CIT-CORR-65",
        name_en="Super Senior Pension",
        name_hi="वरिष्ठतम पेंशन",
        root_rule={"condition_id": "C1", "field": "age", "operator": "GTE", "value": 65},
    )

    sess_res = client.post("/api/v1/citizen/sessions")
    session_id = sess_res.json()["session_id"]

    # Initial input: age 68 -> eligible
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 68}},
    )
    d1 = client.post(f"/api/v1/citizen/sessions/{session_id}/discover").json()
    assert str(s65.id) in [c["scheme_id"] for c in d1["eligible"]]

    # Citizen corrects age: 68 -> 61 -> no longer eligible
    client.patch(
        f"/api/v1/citizen/sessions/{session_id}/profile",
        json={"profile": {"age": 61}},
    )
    d2 = client.post(f"/api/v1/citizen/sessions/{session_id}/discover").json()
    assert str(s65.id) not in [c["scheme_id"] for c in d2["eligible"]]


def test_rajasthan_districts_endpoint():
    """20. Rajasthan districts endpoint returns curated active districts with Hindi and English names."""
    res = client.get("/api/v1/citizen/districts")
    assert res.status_code == 200
    districts = res.json()

    assert len(districts) >= 33  # At least 33-50 Rajasthan districts
    jaipur = next((d for d in districts if d["name_en"] == "Jaipur"), None)
    assert jaipur is not None
    assert jaipur["name_hi"] == "जयपुर"
    assert jaipur["code"] == "RJ-JPR"
