import io
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.duplicate_detection.service import DuplicateDetectionService
from app.duplicate_detection.worker import DuplicateDetectionWorker
from app.ingestion.service import DocumentIngestionService
from app.main import app
from app.repositories.document_relationship_repository import DocumentRelationshipRepository
from app.repositories.document_repository import DocumentRepository

client = TestClient(app)
settings = get_settings()


def create_pdf_with_text(text: str, author: str = "YojanSetu Admin") -> bytes:
    """Generate a PDF containing text and metadata with unicode font support."""
    import os
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=400, height=400)

    # Use Windows system fonts for Hindi/Devanagari if present
    font_paths = [
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    font_loaded = False
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                page.insert_font(fontname="CustomFont", fontfile=fp)
                page.insert_text((40, 50), text, fontname="CustomFont", fontsize=11)
                font_loaded = True
                break
            except Exception:
                pass

    if not font_loaded:
        page.insert_text((40, 50), text, fontsize=11)

    doc.set_metadata({"author": author, "title": "Government Scheme Circular"})
    buf = doc.tobytes()
    doc.close()
    return buf


@pytest.fixture(autouse=True)
def ensure_storage():
    """Ensure storage directories are initialized."""
    settings.ensure_storage_dirs()
    yield


def test_exact_binary_duplicate():
    """Verify identical file bytes are classified as EXACT_DUPLICATE pointing to canonical."""
    uid = uuid.uuid4().hex[:6]
    pdf_bytes = create_pdf_with_text(
        f"Rajasthan Yuva Sambal Scheme 2026 Guidelines {uid}.\n"
        f"राजस्थान युवा संबल योजना 2026 नियम एवं शर्तें {uid}।"
    )
    filename = f"yuva_sambal_{uid}.pdf"

    # Upload Doc 1 first
    resp1 = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data={"title": f"Yuva Sambal Scheme {uid}"},
    )
    assert resp1.status_code == 201
    doc1_id = uuid.UUID(resp1.json()["id"])

    # Check Doc 1 -> must be NEW_DOCUMENT
    db = SessionLocal()
    service = DuplicateDetectionService()
    res1 = service.detect_duplicates(db, doc1_id)
    assert res1.classification == "NEW_DOCUMENT"
    assert res1.resulting_processing_status == "READY_FOR_PARSING"

    # Upload Doc 2 (identical bytes)
    resp2 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"yuva_sambal_copy_{uid}.pdf", pdf_bytes, "application/pdf")},
        data={"title": f"Yuva Sambal Scheme Duplicate {uid}"},
    )
    assert resp2.status_code == 201
    doc2_id = uuid.UUID(resp2.json()["id"])

    # Check Doc 2 -> must be EXACT_DUPLICATE
    res2 = service.detect_duplicates(db, doc2_id)
    assert res2.classification == "EXACT_DUPLICATE"
    assert res2.resulting_processing_status == "DUPLICATE"
    assert res2.canonical_document_id == doc1_id
    assert res2.matched_document_id == doc1_id
    assert res2.similarity_score == 1.0

    # Verify audit relationship in DB
    rel_repo = DocumentRelationshipRepository()
    rels = rel_repo.get_by_document_id(db, doc2_id)
    assert len(rels) >= 1
    assert rels[0].relationship_type == "EXACT_DUPLICATE_OF"
    assert rels[0].related_document_id == doc1_id
    db.close()


def test_content_duplicate_different_packaging():
    """Verify different binary packaging with identical text is classified as CONTENT_DUPLICATE."""
    uid = uuid.uuid4().hex[:6]
    text_content = (
        f"Rajasthan Mukhyamantri Kanyadan Scheme 2026 Eligibility Guidelines {uid}.\n"
        f"मुख्यमंत्री कन्यादान योजना राजस्थान 2026 संपूर्ण विवरण एवं पात्रता {uid}।"
    )

    # Generate two PDFs with identical text but different metadata/producer
    pdf_bytes1 = create_pdf_with_text(text_content, author="Department of Social Justice")
    pdf_bytes2 = create_pdf_with_text(text_content, author="Directorate of Women Empowerment")

    # Verify binary hashes actually differ
    import hashlib
    assert hashlib.sha256(pdf_bytes1).hexdigest() != hashlib.sha256(pdf_bytes2).hexdigest()

    resp1 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"kanyadan_dept1_{uid}.pdf", pdf_bytes1, "application/pdf")},
    )
    doc1_id = uuid.UUID(resp1.json()["id"])

    db = SessionLocal()
    service = DuplicateDetectionService()

    # Doc 1 is established as NEW_DOCUMENT
    res1 = service.detect_duplicates(db, doc1_id)
    assert res1.classification == "NEW_DOCUMENT"
    assert res1.resulting_processing_status == "READY_FOR_PARSING"

    # Upload Doc 2
    resp2 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"kanyadan_dept2_{uid}.pdf", pdf_bytes2, "application/pdf")},
    )
    doc2_id = uuid.UUID(resp2.json()["id"])

    # Doc 2 is CONTENT_DUPLICATE pointing to Doc 1
    res2 = service.detect_duplicates(db, doc2_id)
    assert res2.classification == "CONTENT_DUPLICATE"
    assert res2.resulting_processing_status == "DUPLICATE"
    assert res2.canonical_document_id == doc1_id
    assert res2.similarity_score == 1.0

    rel_repo = DocumentRelationshipRepository()
    primary_rel = rel_repo.get_primary_relationship(db, doc2_id)
    assert primary_rel is not None
    assert primary_rel.relationship_type == "CONTENT_DUPLICATE_OF"
    assert primary_rel.related_document_id == doc1_id
    db.close()


def test_new_document_distinct():
    """Verify completely different documents are classified as NEW_DOCUMENT."""
    uid = uuid.uuid4().hex[:6]
    doc_a_bytes = create_pdf_with_text(
        f"Rajasthan Agriculture Department Kisan Seva Subsidy Scheme 2026 {uid}.\n"
        f"राजस्थान किसान सेवा पोर्टल कृषि अनुदान योजना दिशानिर्देश {uid}।"
    )
    doc_b_bytes = create_pdf_with_text(
        f"Rajasthan Higher Education Technical University Post-Matric Scholarship Scheme 2026 {uid}.\n"
        f"उच्च शिक्षा छात्रवृत्ति योजना राजस्थान तकनीकी विश्वविद्यालय {uid}।"
    )

    resp1 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"kisan_seva_{uid}.pdf", doc_a_bytes, "application/pdf")},
    )
    doc1_id = uuid.UUID(resp1.json()["id"])

    db = SessionLocal()
    service = DuplicateDetectionService()

    res1 = service.detect_duplicates(db, doc1_id)
    assert res1.classification == "NEW_DOCUMENT"
    assert res1.resulting_processing_status == "READY_FOR_PARSING"

    resp2 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"scholarship_{uid}.pdf", doc_b_bytes, "application/pdf")},
    )
    doc2_id = uuid.UUID(resp2.json()["id"])

    res2 = service.detect_duplicates(db, doc2_id)
    assert res2.classification == "NEW_DOCUMENT"
    assert res2.resulting_processing_status == "READY_FOR_PARSING"
    db.close()


def test_possible_version_detection():
    """
    CRITICAL TEST: Verify an amended notification (e.g. income limit ₹2L -> ₹3L with 'संशोधन')
    is classified as POSSIBLE_VERSION / VERSION_REVIEW_REQUIRED, NOT rejected as duplicate.
    """
    uid = uuid.uuid4().hex[:6]
    text_2025 = (
        f"Government of Rajasthan Department of Agriculture Circular {uid}.\n"
        "Order No. F(12)/Agri/Solar/2025.\n"
        "Subject: Implementation guidelines for Solar Irrigation Pump Subsidy Scheme in Rajasthan.\n"
        "Clause 1: The scheme aims to assist farmers in installing solar-powered pumps for micro-irrigation.\n"
        "Clause 2: All small, marginal, and general category farmers residing in Rajasthan are eligible.\n"
        "Clause 3: The farmer must possess a valid land ownership record (Jamabandi).\n"
        "Clause 4: Priority will be given to farmers in dark zones using drip irrigation systems.\n"
        "Clause 5: Eligible farmers receive 60 percent financial subsidy on 5HP solar pump sets.\n"
        "Clause 6: Applications must be submitted through the official Raj Kisan Saathi portal.\n"
        "Clause 7: Physical verification of installation will be conducted by the Assistant Agriculture Officer.\n"
        "राजस्थान कृषि विभाग सोलर सिंचाई पम्प अनुदान दिशानिर्देश 2025।\n"
        "पात्र कृषकों को 5 एचपी सोलर पम्प पर 60 प्रतिशत अनुदान देय होगा।"
    )
    text_2026 = (
        f"Government of Rajasthan Department of Agriculture Circular {uid}.\n"
        "Order No. F(12)/Agri/Solar/2026-Amendment.\n"
        "Subject: Amendment in implementation guidelines for Solar Irrigation Pump Subsidy Scheme.\n"
        "Clause 1: The scheme aims to assist farmers in installing solar-powered pumps for micro-irrigation.\n"
        "Clause 2: All small, marginal, and general category farmers residing in Rajasthan are eligible.\n"
        "Clause 3: The farmer must possess a valid land ownership record (Jamabandi).\n"
        "Clause 4: Priority will be given to farmers in dark zones using drip irrigation systems.\n"
        "Clause 5: Eligible farmers receive 75 percent financial subsidy on 5HP solar pump sets.\n"
        "Clause 6: Applications must be submitted through the official Raj Kisan Saathi portal.\n"
        "Clause 7: Physical verification of installation will be conducted by the Assistant Agriculture Officer.\n"
        "राजस्थान कृषि विभाग सोलर सिंचाई पम्प अनुदान संशोधन अधिसूचना 2026।\n"
        "संशोधित प्रावधान: पात्र कृषकों को 5 एचपी सोलर पम्प पर 75 प्रतिशत अनुदान देय होगा।"
    )

    pdf_2025 = create_pdf_with_text(text_2025, author="Govt of Rajasthan Agriculture Dept")
    pdf_2026 = create_pdf_with_text(text_2026, author="Govt of Rajasthan Agriculture Dept")

    resp1 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"solar_pump_rules_2025_{uid}.pdf", pdf_2025, "application/pdf")},
    )
    doc1_id = uuid.UUID(resp1.json()["id"])

    db = SessionLocal()
    service = DuplicateDetectionService()

    # Doc 1 is established
    res1 = service.detect_duplicates(db, doc1_id)
    assert res1.classification == "NEW_DOCUMENT"
    assert res1.resulting_processing_status == "READY_FOR_PARSING"

    # Upload Doc 2 (amendment)
    resp2 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"solar_pump_amended_2026_{uid}.pdf", pdf_2026, "application/pdf")},
    )
    doc2_id = uuid.UUID(resp2.json()["id"])

    res2 = service.detect_duplicates(db, doc2_id)

    # CRITICAL: Must be identified as POSSIBLE_VERSION, NOT duplicate!
    assert res2.classification == "POSSIBLE_VERSION"
    assert res2.resulting_processing_status == "VERSION_REVIEW_REQUIRED"
    assert res2.matched_document_id == doc1_id
    assert res2.similarity_score is not None
    assert res2.similarity_score >= 0.65

    # Check database status
    doc_repo = DocumentRepository()
    doc2 = doc_repo.get_by_id(db, doc2_id)
    assert doc2.possible_version_of_document_id == doc1_id
    assert doc2.duplicate_status == "POSSIBLE_VERSION"
    assert doc2.processing_status == "VERSION_REVIEW_REQUIRED"
    db.close()


def test_scanned_pdf_conservative():
    """Verify an image-only / scanned PDF proceeds conservatively as NEW_DOCUMENT without crash."""
    writer = PdfWriter()
    # Vary dimensions slightly to prevent exact hash matching against previous test runs
    w = 160 + (int(time.time() * 1000) % 300)
    h = 160 + (int(time.time() * 100) % 200)
    writer.add_blank_page(width=w, height=h)
    buf = io.BytesIO()
    writer.write(buf)
    scanned_bytes = buf.getvalue()

    uid = uuid.uuid4().hex[:6]
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"scanned_order_{uid}.pdf", scanned_bytes, "application/pdf")},
    )
    assert resp.status_code == 201
    doc_id = uuid.UUID(resp.json()["id"])

    db = SessionLocal()
    service = DuplicateDetectionService()
    res = service.detect_duplicates(db, doc_id)

    assert res.classification == "NEW_DOCUMENT"
    assert res.resulting_processing_status == "READY_FOR_PARSING"
    assert any("scanned or image-only" in r.lower() for r in res.reasons)
    db.close()


def test_duplicate_worker_and_idempotency():
    """Verify background worker processes batch and is completely idempotent on repeated runs."""
    uid = uuid.uuid4().hex[:6]
    pdf_bytes = create_pdf_with_text(
        f"Clean Rajasthan Swachhta Mission Guidelines 2026 {uid}.\n"
        f"स्वच्छ राजस्थान अभियान स्वच्छता नियम एवं प्रोत्साहन राशि {uid}।"
    )

    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"swachh_raj_{uid}.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = uuid.UUID(resp.json()["id"])

    worker = DuplicateDetectionWorker()

    # First run processes the document
    processed_count = worker.process_batch(limit=20)
    assert processed_count >= 1

    db = SessionLocal()
    repo = DocumentRepository()
    doc = repo.get_by_id(db, doc_id)
    assert doc.processing_status in ["READY_FOR_PARSING", "DUPLICATE", "VERSION_REVIEW_REQUIRED"]
    db.close()

    # Second run finds no pending documents (idempotent)
    second_processed = worker.process_batch(limit=20)
    assert second_processed == 0


def test_multiple_sources_provenance():
    """Verify same PDF ingested from two different sources preserves both source associations."""
    uid = uuid.uuid4().hex[:6]
    pdf_bytes = create_pdf_with_text(
        f"Rajasthan Social Justice Old Age Pension Circular 2026 {uid}.\n"
        f"राजस्थान सामाजिक सुरक्षा वृद्धावस्था पेंशन नियम {uid}।"
    )

    # Ingest from Source 1
    resp1 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"pension_portal_1_{uid}.pdf", pdf_bytes, "application/pdf")},
        data={"title": f"Pension Circular from Source 1 {uid}"},
    )
    doc1_id = uuid.UUID(resp1.json()["id"])

    # Establish Doc 1
    db = SessionLocal()
    service = DuplicateDetectionService()
    res1 = service.detect_duplicates(db, doc1_id)
    assert res1.classification == "NEW_DOCUMENT"

    # Ingest from Source 2 (same bytes)
    resp2 = client.post(
        "/api/v1/documents/upload",
        files={"file": (f"pension_portal_2_{uid}.pdf", pdf_bytes, "application/pdf")},
        data={"title": f"Pension Circular from Source 2 {uid}"},
    )
    doc2_id = uuid.UUID(resp2.json()["id"])

    res2 = service.detect_duplicates(db, doc2_id)
    assert res2.classification == "EXACT_DUPLICATE"
    assert res2.canonical_document_id == doc1_id

    # Verify both records exist and preserve their distinct identities and titles
    repo = DocumentRepository()
    d1 = repo.get_by_id(db, doc1_id)
    d2 = repo.get_by_id(db, doc2_id)
    assert d1.title == f"Pension Circular from Source 1 {uid}"
    assert d2.title == f"Pension Circular from Source 2 {uid}"
    assert d2.duplicate_of_document_id == doc1_id
    db.close()


def test_duplicate_apis():
    """Verify duplicate-analysis, compare, and resolution REST endpoints."""
    uid = uuid.uuid4().hex[:6]
    text1 = (
        f"Indira Gandhi Urban Employment Guarantee Scheme Rules 2026 {uid}.\n"
        "Guidelines for urban employment in all Rajasthan municipal bodies.\n"
        "Eligible job seekers receive 100 days guaranteed wage employment.\n"
        "Application through local bodies or e-Mitra citizen portal.\n"
        f"इंदिरा गांधी शहरी रोजगार गारंटी योजना नियम 2026 {uid}।"
    )
    text2 = (
        f"Indira Gandhi Urban Employment Guarantee Scheme Amendment Rules 2026 {uid}.\n"
        "Guidelines for urban employment in all Rajasthan municipal bodies.\n"
        "Eligible job seekers receive 125 days guaranteed wage employment.\n"
        "Application through local bodies or e-Mitra citizen portal.\n"
        f"इंदिरा गांधी शहरी रोजगार गारंटी योजना संशोधन नियम 2026 {uid}।"
    )

    pdf1 = create_pdf_with_text(text1)
    pdf2 = create_pdf_with_text(text2)

    resp1 = client.post("/api/v1/documents/upload", files={"file": (f"indira_1_{uid}.pdf", pdf1, "application/pdf")})
    doc1_id = resp1.json()["id"]

    # 1. Duplicate Analysis API for Doc 1 (First document -> NEW_DOCUMENT)
    analysis_resp = client.get(f"/api/v1/documents/{doc1_id}/duplicate-analysis")
    assert analysis_resp.status_code == 200
    assert analysis_resp.json()["document_id"] == doc1_id
    assert analysis_resp.json()["classification"] == "NEW_DOCUMENT"
    assert analysis_resp.json()["processing_status"] == "READY_FOR_PARSING"

    resp2 = client.post("/api/v1/documents/upload", files={"file": (f"indira_2_{uid}.pdf", pdf2, "application/pdf")})
    doc2_id = resp2.json()["id"]

    # 2. Document Compare API
    compare_resp = client.get(f"/api/v1/documents/{doc1_id}/compare/{doc2_id}")
    assert compare_resp.status_code == 200
    cmp_data = compare_resp.json()
    assert cmp_data["exact_hash_match"] is False
    assert cmp_data["text_similarity"] > 0.40

    # 3. Duplicate Resolution API (Admin manual decision: MARK_VERSION)
    res_resp = client.post(
        f"/api/v1/documents/{doc2_id}/duplicate-resolution",
        json={
            "decision": "MARK_VERSION",
            "target_document_id": doc1_id,
            "notes": "Verified by admin as official scheme amendment",
        },
    )
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["duplicate_status"] == "CONFIRMED_VERSION"
    assert res_data["processing_status"] == "READY_FOR_PARSING"
    assert res_data["possible_version_of_document_id"] == doc1_id
