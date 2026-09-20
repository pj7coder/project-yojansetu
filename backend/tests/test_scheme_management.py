import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.session import get_db_context
from app.database.models.scheme import Scheme
from app.database.models.department import Department
from app.database.models.category import Category


def test_scheme_detail_and_full_update():
    client = TestClient(app)

    # 1. Fetch existing scheme from DB
    with get_db_context() as db:
        scheme = db.query(Scheme).filter(Scheme.scheme_code == "RJ-GEN-PMKUSUM").first()
        if not scheme:
            pytest.skip("PMKUSUM scheme not in DB")
        scheme_id = str(scheme.id)

    # 2. Call GET /api/v1/schemes/{scheme_id}
    res = client.get(f"/api/v1/schemes/{scheme_id}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == scheme_id
    assert "canonical_data" in data
    assert data["canonical_data"] is not None

    # 3. Call PUT /api/v1/schemes/{scheme_id} to edit details
    update_payload = {
        "name_en": "PM-KUSUM Solar Scheme (Updated)",
        "name_hi": "पीएम-कुसुम सौर योजना (संशोधित)",
        "short_description": "Updated solar pump subsidy for Rajasthan farmers.",
        "benefits": [
            {
                "type": "SUBSIDY",
                "amount": 60.0,
                "currency": "PERCENT",
                "frequency": "ONE_TIME",
                "description": "60% capital subsidy for solar pump installation",
                "raw_text": "Up to 60% subsidy provided by central and state government."
            }
        ],
        "eligibility": {
            "simple_fields": {
                "farmer": True,
                "land_holding_min_acres": 0.5
            },
            "conditions": [
                {
                    "condition_id": "COND-SOLAR-001",
                    "field": "farmer_status",
                    "operator": "EQ",
                    "value": True,
                    "raw_text": "Applicant must be a bonafide farmer with agricultural land."
                }
            ],
            "exclusions": [
                {
                    "exclusion_id": "EXCL-001",
                    "field": "prior_subsidy",
                    "raw_text": "Farmers who received solar subsidy in the last 5 years are ineligible."
                }
            ]
        },
        "required_documents": [
            {
                "document_type": "JAN_AADHAAR",
                "name_raw": "Jan Aadhaar Card",
                "mandatory": True,
                "notes": "Mandatory proof of Rajasthan domicile"
            },
            {
                "document_type": "LAND_RECORD",
                "name_raw": "Jamabandi (Khasra/Khatauni)",
                "mandatory": True,
                "notes": "Proof of agricultural land holding"
            }
        ],
        "application": {
            "channels": ["ONLINE", "EMITRA"],
            "portal_url": "https://rajkisan.rajasthan.gov.in",
            "office": "District Agriculture Officer",
            "steps": [
                "1. Apply online via RajKisan Sathi portal or nearest e-Mitra kiosk.",
                "2. Upload Jamabandi and Jan Aadhaar.",
                "3. Site survey by DISCOM engineer.",
                "4. Deposit beneficiary share."
            ]
        }
    }

    put_res = client.put(f"/api/v1/schemes/{scheme_id}", json=update_payload)
    assert put_res.status_code == 200, put_res.text
    updated_data = put_res.json()

    assert updated_data["name_en"] == "PM-KUSUM Solar Scheme (Updated)"
    assert updated_data["canonical_data"]["benefits"][0]["amount"] == 60.0
    assert len(updated_data["canonical_data"]["required_documents"]) == 2
    assert updated_data["canonical_data"]["application"]["portal_url"] == "https://rajkisan.rajasthan.gov.in"


def test_watch_folder_status_endpoint():
    client = TestClient(app)
    res = client.get("/api/v1/documents/watch-folder/status")
    assert res.status_code == 200, res.text
    data = res.json()
    assert "folder_path" in data
    assert "watch_folder" in data["folder_path"]
    assert "pending_count" in data
