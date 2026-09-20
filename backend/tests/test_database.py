import uuid
import pytest
from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.repositories.category_repository import CategoryRepository
from app.repositories.department_repository import DepartmentRepository
from app.schemas.category import CategoryCreate
from app.schemas.department import DepartmentCreate

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_test_dept_and_cat():
    """Ensure a baseline department and category exist for testing."""
    db = SessionLocal()
    dept_repo = DepartmentRepository()
    cat_repo = CategoryRepository()

    dept = dept_repo.get_by_code(db, "TEST-UNIT-DEPT")
    if not dept:
        dept = dept_repo.create(
            db,
            DepartmentCreate(
                code="TEST-UNIT-DEPT",
                name_en="Test Unit Department",
                name_hi="परीक्षण इकाई विभाग",
                description="Unit test department",
                active=True,
            ),
        )

    cat = cat_repo.get_by_code(db, "test-unit-cat")
    if not cat:
        cat = cat_repo.create(
            db,
            CategoryCreate(
                code="test-unit-cat",
                name_en="Test Unit Category",
                name_hi="परीक्षण इकाई श्रेणी",
                description="Unit test category",
                active=True,
            ),
        )

    dept_id = dept.id
    cat_id = cat.id
    db.close()
    return {"department_id": str(dept_id), "category_id": str(cat_id)}


def test_health_check_day1_regression():
    """Verify Day 1 health check still works without error."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "jansetu-backend"


def test_database_health_check():
    """Verify GET /api/v1/health/database returns operational status."""
    response = client.get("/api/v1/health/database")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_create_scheme_success(setup_test_dept_and_cat):
    """Verify creating a scheme persists record and initializes Version 1."""
    unique_code = f"TEST-SCHEME-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "scheme_code": unique_code,
        "name_en": "Test Welfare Scheme",
        "name_hi": "परीक्षण कल्याण योजना",
        "short_name": "TWS",
        "department_id": setup_test_dept_and_cat["department_id"],
        "category_id": setup_test_dept_and_cat["category_id"],
        "short_description": "Test scheme for automated testing.",
        "status": "DRAFT",
        "jurisdiction": "RAJASTHAN",
        "scheme_origin": "RAJASTHAN_STATE",
        "initial_source_summary": "Initial baseline gazette notification",
    }

    response = client.post("/api/v1/schemes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["scheme_code"] == unique_code
    assert data["name_en"] == "Test Welfare Scheme"
    assert data["name_hi"] == "परीक्षण कल्याण योजना"
    assert data["status"] == "DRAFT"
    assert "id" in data
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version_number"] == 1
    assert data["versions"][0]["is_current"] is True


def test_create_scheme_duplicate_rejected(setup_test_dept_and_cat):
    """Verify duplicate scheme_code returns HTTP 409 Conflict."""
    unique_code = f"TEST-DUP-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "scheme_code": unique_code,
        "name_en": "Duplicate Scheme Test",
        "department_id": setup_test_dept_and_cat["department_id"],
        "category_id": setup_test_dept_and_cat["category_id"],
        "status": "DRAFT",
    }

    # First attempt should succeed
    res1 = client.post("/api/v1/schemes", json=payload)
    assert res1.status_code == 201

    # Second attempt with identical code must fail with 409
    res2 = client.post("/api/v1/schemes", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_create_scheme_invalid_relations():
    """Verify invalid foreign keys return clean HTTP 400."""
    fake_uuid = str(uuid.uuid4())
    payload = {
        "scheme_code": f"TEST-INV-{uuid.uuid4().hex[:6].upper()}",
        "name_en": "Invalid FK Scheme",
        "department_id": fake_uuid,
        "category_id": fake_uuid,
        "status": "DRAFT",
    }

    response = client.post("/api/v1/schemes", json=payload)
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_list_schemes_pagination_and_filter(setup_test_dept_and_cat):
    """Verify GET /api/v1/schemes supports pagination and status filters."""
    response = client.get("/api/v1/schemes?page=1&page_size=5&status=DRAFT")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert "total_pages" in data
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert isinstance(data["items"], list)


def test_get_scheme_by_id(setup_test_dept_and_cat):
    """Verify fetching existing scheme by UUID and 404 for missing scheme."""
    unique_code = f"TEST-GET-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "scheme_code": unique_code,
        "name_en": "Get Scheme By ID Test",
        "department_id": setup_test_dept_and_cat["department_id"],
        "category_id": setup_test_dept_and_cat["category_id"],
        "status": "DRAFT",
    }

    res_create = client.post("/api/v1/schemes", json=payload)
    scheme_id = res_create.json()["id"]

    # Fetch existing
    res_get = client.get(f"/api/v1/schemes/{scheme_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == scheme_id
    assert res_get.json()["scheme_code"] == unique_code

    # Fetch missing
    res_missing = client.get(f"/api/v1/schemes/{uuid.uuid4()}")
    assert res_missing.status_code == 404


def test_update_scheme_fields(setup_test_dept_and_cat):
    """Verify PATCH /api/v1/schemes/{id} updates allowed fields."""
    unique_code = f"TEST-UPD-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "scheme_code": unique_code,
        "name_en": "Pre-update Scheme Name",
        "department_id": setup_test_dept_and_cat["department_id"],
        "category_id": setup_test_dept_and_cat["category_id"],
        "status": "DRAFT",
    }

    res_create = client.post("/api/v1/schemes", json=payload)
    scheme_id = res_create.json()["id"]

    # Update title and status
    update_payload = {
        "name_en": "Post-update Scheme Name",
        "status": "REVIEW_REQUIRED",
    }
    res_update = client.patch(f"/api/v1/schemes/{scheme_id}", json=update_payload)
    assert res_update.status_code == 200
    data = res_update.json()
    assert data["name_en"] == "Post-update Scheme Name"
    assert data["status"] == "REVIEW_REQUIRED"


def test_hindi_unicode_persistence(setup_test_dept_and_cat):
    """Verify Hindi Unicode text persists and retrieves accurately without corruption."""
    unique_code = f"TEST-HI-{uuid.uuid4().hex[:6].upper()}"
    hindi_title = "मुख्यमंत्री अनुप्रति कोचिंग योजना"
    hindi_desc = "राजस्थान के प्रतिभावान विद्यार्थियों को प्रतियोगी परीक्षाओं की उत्कृष्ट तैयारी हेतु आर्थिक सहायता।"

    payload = {
        "scheme_code": unique_code,
        "name_en": "Mukhyamantri Anuprati Coaching Yojana",
        "name_hi": hindi_title,
        "short_description": hindi_desc,
        "department_id": setup_test_dept_and_cat["department_id"],
        "category_id": setup_test_dept_and_cat["category_id"],
        "status": "DRAFT",
    }

    res_create = client.post("/api/v1/schemes", json=payload)
    assert res_create.status_code == 201
    scheme_id = res_create.json()["id"]

    res_get = client.get(f"/api/v1/schemes/{scheme_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["name_hi"] == hindi_title
    assert data["short_description"] == hindi_desc


def test_departments_api():
    """Verify GET and POST /api/v1/departments endpoints."""
    unique_code = f"DEPT-{uuid.uuid4().hex[:4].upper()}"
    dept_payload = {
        "code": unique_code,
        "name_en": "Department of Animal Husbandry",
        "name_hi": "पशुपालन विभाग",
        "official_website": "https://animalhusbandry.rajasthan.gov.in",
        "active": True,
    }

    res_create = client.post("/api/v1/departments", json=dept_payload)
    assert res_create.status_code == 201
    assert res_create.json()["code"] == unique_code

    res_list = client.get("/api/v1/departments")
    assert res_list.status_code == 200
    assert "items" in res_list.json()
    assert any(d["code"] == unique_code for d in res_list.json()["items"])
