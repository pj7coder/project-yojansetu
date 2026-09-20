import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.session import SessionLocal
from app.main import app
from app.normalization.schemas import CanonicalSchemeDraft
from app.normalization.service import SchemeNormalizationService
from app.repositories.document_repository import DocumentRepository
from app.repositories.scheme_draft_repository import SchemeDraftRepository

client = TestClient(app)


@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_document(test_db):
    doc_repo = DocumentRepository()
    doc = Document(
        document_code=f"DOC-TEST-{uuid.uuid4().hex[:6].upper()}",
        source_id=None,
        original_filename="test_pension_order.pdf",
        storage_path="storage/originals/test_pension_order.pdf",
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        file_size_bytes=1024,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_NORMALIZATION",
    )
    saved_doc = doc_repo.create(test_db, doc)
    yield saved_doc
    # Cleanup
    try:
        test_db.delete(saved_doc)
        test_db.commit()
    except Exception:
        test_db.rollback()


def test_multi_scheme_document_separation(test_db, test_document):
    settings = get_settings()
    doc_id = test_document.id
    extracted_doc_dir = settings.extracted_dir / str(doc_id)
    extracted_doc_dir.mkdir(parents=True, exist_ok=True)

    # Prepare extraction containing two distinct schemes
    multi_scheme_data = {
        "document_id": str(doc_id),
        "chunk_extractions": [
            {
                "chunk_id": f"CHUNK-{doc_id}-001",
                "schemes": [
                    {
                        "scheme_name": "मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना",
                        "department": "सामाजिक न्याय एवं अधिकारिता विभाग",
                        "eligibility_conditions": [
                            {
                                "clause": "आयु 60 वर्ष या अधिक",
                                "evidence": {
                                    "evidence_text": "आयु 60 वर्ष या अधिक होनी चाहिए",
                                    "page_numbers": [1],
                                    "source_block_ids": ["BLK-001"],
                                    "chunk_id": f"CHUNK-{doc_id}-001",
                                },
                            }
                        ],
                        "benefits": [
                            {
                                "benefit_type": "pension",
                                "benefit_description": "प्रति माह ₹1,000 पेंशन",
                                "amount": "1000",
                                "frequency": "प्रति माह",
                                "evidence": {
                                    "evidence_text": "प्रति माह ₹1000 पेंशन दी जाएगी",
                                    "page_numbers": [1],
                                    "source_block_ids": ["BLK-002"],
                                    "chunk_id": f"CHUNK-{doc_id}-001",
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "chunk_id": f"CHUNK-{doc_id}-002",
                "schemes": [
                    {
                        "scheme_name": "पालनहार योजना",
                        "department": "सामाजिक न्याय एवं अधिकारिता विभाग",
                        "eligibility_conditions": [
                            {
                                "clause": "अनाथ बालक-बालिकाओं के पालनहार परिवार की वार्षिक आय ₹1.20 लाख से अधिक न हो",
                                "evidence": {
                                    "evidence_text": "वार्षिक आय ₹1.20 लाख से अधिक न हो",
                                    "page_numbers": [2],
                                    "source_block_ids": ["BLK-003"],
                                    "chunk_id": f"CHUNK-{doc_id}-002",
                                },
                            }
                        ],
                        "benefits": [
                            {
                                "benefit_type": "cash",
                                "benefit_description": "मासिक ₹1500 अनुदान",
                                "amount": "1500",
                                "frequency": "मासिक",
                                "evidence": {
                                    "evidence_text": "मासिक ₹1500 अनुदान",
                                    "page_numbers": [2],
                                    "source_block_ids": ["BLK-004"],
                                    "chunk_id": f"CHUNK-{doc_id}-002",
                                },
                            }
                        ],
                    }
                ],
            },
        ],
    }

    with open(extracted_doc_dir / "document_extractions.json", "w", encoding="utf-8") as f:
        json.dump(multi_scheme_data, f, ensure_ascii=False)

    service = SchemeNormalizationService(test_db)
    result = service.normalize_document(doc_id)

    assert result["status"] == "READY_FOR_VALIDATION"
    assert result["schemes_detected"] == 2

    # Verify drafts persisted in DB
    draft_repo = SchemeDraftRepository()
    drafts = draft_repo.get_all_by_document_id(test_db, doc_id)
    assert len(drafts) == 2

    names = {d.detected_name for d in drafts}
    assert "मुख्यमंत्री वृद्धजन सम्मान पेंशन योजना" in names
    assert "पालनहार योजना" in names

    # Verify canonical artifact files exist
    for d in drafts:
        artifact_path = settings.storage_path / d.artifact_path.replace("storage/", "")
        assert artifact_path.exists()
        with open(artifact_path, "r", encoding="utf-8") as f:
            c_json = json.load(f)
            assert c_json["schema_version"] == "1.0"
            assert c_json["document_id"] == str(doc_id)


def test_zero_schemes_document_no_fake_draft(test_db, test_document):
    settings = get_settings()
    doc_id = test_document.id
    extracted_doc_dir = settings.extracted_dir / str(doc_id)
    extracted_doc_dir.mkdir(parents=True, exist_ok=True)

    # Empty extractions (e.g. administrative memo)
    with open(extracted_doc_dir / "document_extractions.json", "w", encoding="utf-8") as f:
        json.dump({"document_id": str(doc_id), "chunk_extractions": []}, f)

    service = SchemeNormalizationService(test_db)
    result = service.normalize_document(doc_id)

    assert result["status"] == "NO_SCHEME_FOUND"
    assert result["schemes_detected"] == 0

    draft_repo = SchemeDraftRepository()
    drafts = draft_repo.get_all_by_document_id(test_db, doc_id)
    assert len(drafts) == 0  # No fake draft created


def test_end_to_end_provenance_chain(test_db, test_document):
    settings = get_settings()
    doc_id = test_document.id
    extracted_doc_dir = settings.extracted_dir / str(doc_id)
    extracted_doc_dir.mkdir(parents=True, exist_ok=True)

    extraction_data = {
        "document_id": str(doc_id),
        "chunk_extractions": [
            {
                "chunk_id": f"CHUNK-{doc_id}-001",
                "schemes": [
                    {
                        "scheme_name": "राजस्थान वृद्धावस्था पेंशन",
                        "eligibility_conditions": [
                            {
                                "clause": "आयु 60 वर्ष या अधिक",
                                "evidence": {
                                    "evidence_text": "आयु 60 वर्ष या अधिक",
                                    "page_numbers": [3],
                                    "source_block_ids": ["BLK-101", "BLK-102"],
                                    "chunk_id": f"CHUNK-{doc_id}-001",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }

    with open(extracted_doc_dir / "document_extractions.json", "w", encoding="utf-8") as f:
        json.dump(extraction_data, f, ensure_ascii=False)

    service = SchemeNormalizationService(test_db)
    result = service.normalize_document(doc_id)

    draft_repo = SchemeDraftRepository()
    drafts = draft_repo.get_all_by_document_id(test_db, doc_id)
    assert len(drafts) == 1

    draft = drafts[0]
    artifact_path = settings.storage_path / draft.artifact_path.replace("storage/", "")
    with open(artifact_path, "r", encoding="utf-8") as f:
        canonical_dict = json.load(f)

    canonical = CanonicalSchemeDraft.model_validate(canonical_dict)

    # 1. Condition has evidence_refs
    root_children = canonical.eligibility.root_rule.children
    assert len(root_children) == 1
    cond = root_children[0]
    assert len(cond.evidence_refs) > 0
    evid_id = cond.evidence_refs[0]

    # 2. Ref resolves in evidence_registry
    assert evid_id in canonical.evidence_registry
    ev_item = canonical.evidence_registry[evid_id]

    # 3. Provenance chain to chunk, source blocks, and page numbers is complete
    assert ev_item.document_id == str(doc_id)
    assert ev_item.chunk_id == f"CHUNK-{doc_id}-001"
    assert ev_item.page_numbers == [3]
    assert ev_item.source_block_ids == ["BLK-101", "BLK-102"]
    assert ev_item.text == "आयु 60 वर्ष या अधिक"


def test_idempotency_clean_rerun(test_db, test_document):
    settings = get_settings()
    doc_id = test_document.id
    extracted_doc_dir = settings.extracted_dir / str(doc_id)
    extracted_doc_dir.mkdir(parents=True, exist_ok=True)

    extraction_data = {
        "document_id": str(doc_id),
        "chunk_extractions": [
            {
                "chunk_id": f"CHUNK-{doc_id}-001",
                "schemes": [
                    {
                        "scheme_name": "परीक्षण योजना",
                        "eligibility_conditions": [
                            {"clause": "राजस्थान का मूल निवासी", "evidence": {"evidence_text": "राजस्थान का मूल निवासी"}}
                        ],
                    }
                ],
            }
        ],
    }
    with open(extracted_doc_dir / "document_extractions.json", "w", encoding="utf-8") as f:
        json.dump(extraction_data, f, ensure_ascii=False)

    service = SchemeNormalizationService(test_db)
    # First run
    res1 = service.normalize_document(doc_id)
    draft_repo = SchemeDraftRepository()
    drafts1 = draft_repo.get_all_by_document_id(test_db, doc_id)
    assert len(drafts1) == 1

    # Second run (idempotent re-run)
    res2 = service.normalize_document(doc_id, force=True)
    drafts2 = draft_repo.get_all_by_document_id(test_db, doc_id)
    assert len(drafts2) == 1  # Still exactly 1 draft, not duplicated!


def test_normalization_api_endpoints(test_db, test_document):
    settings = get_settings()
    doc_id = test_document.id
    extracted_doc_dir = settings.extracted_dir / str(doc_id)
    extracted_doc_dir.mkdir(parents=True, exist_ok=True)

    extraction_data = {
        "document_id": str(doc_id),
        "chunk_extractions": [
            {
                "chunk_id": f"CHUNK-{doc_id}-001",
                "schemes": [
                    {
                        "scheme_name": "एपीआई परीक्षण योजना",
                        "eligibility_conditions": [
                            {"clause": "आयु 60 वर्ष या अधिक", "evidence": {"evidence_text": "आयु 60 वर्ष या अधिक"}}
                        ],
                    }
                ],
            }
        ],
    }
    with open(extracted_doc_dir / "document_extractions.json", "w", encoding="utf-8") as f:
        json.dump(extraction_data, f, ensure_ascii=False)

    # 1. POST /api/v1/documents/{document_id}/normalize
    resp_norm = client.post(f"/api/v1/documents/{doc_id}/normalize?force=true")
    assert resp_norm.status_code == 200
    data_norm = resp_norm.json()
    assert data_norm["schemes_detected"] == 1
    draft_id = data_norm["drafts"][0]["draft_id"]

    # 2. GET /api/v1/documents/{document_id}/scheme-drafts
    resp_list = client.get(f"/api/v1/documents/{doc_id}/scheme-drafts")
    assert resp_list.status_code == 200
    data_list = resp_list.json()
    assert data_list["count"] == 1
    assert data_list["drafts"][0]["id"] == draft_id

    # 3. GET /api/v1/scheme-drafts/{draft_id}
    resp_detail = client.get(f"/api/v1/scheme-drafts/{draft_id}")
    assert resp_detail.status_code == 200
    data_detail = resp_detail.json()
    assert data_detail["id"] == draft_id
    assert data_detail["canonical"] is not None
    assert data_detail["canonical"]["schema_version"] == "1.0"

    # 4. GET /api/v1/scheme-drafts/{draft_id}/conflicts
    resp_conf = client.get(f"/api/v1/scheme-drafts/{draft_id}/conflicts")
    assert resp_conf.status_code == 200
    data_conf = resp_conf.json()
    assert data_conf["draft_id"] == draft_id
    assert "conflict_count" in data_conf
