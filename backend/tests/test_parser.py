import hashlib
import io
import json
import os
import uuid
import pytest
from fastapi.testclient import TestClient
import pymupdf

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.duplicate_detection.service import DuplicateDetectionService
from app.main import app
from app.parser.interface import BlockType, MinerUUnavailableException, PageTextStatus
from app.parser.mineru import MinerUAdapter
from app.parser.service import DocumentParserService
from app.parser.worker import DocumentParserWorker
from app.repositories.document_repository import DocumentRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository

client = TestClient(app)
settings = get_settings()


def create_sample_pdf(pages_text: list[str], author: str = "YojanSetu Admin") -> bytes:
    """Generate a multi-page PDF with text and unicode font support."""
    doc = pymupdf.open()

    font_paths = [
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/mangal.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    for text in pages_text:
        page = doc.new_page(width=500, height=600)
        font_loaded = False
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    page.insert_font(fontname="CustomFont", fontfile=fp)
                    page.insert_text((50, 70), text, fontname="CustomFont", fontsize=12)
                    font_loaded = True
                    break
                except Exception:
                    pass
        if not font_loaded:
            page.insert_text((50, 70), text, fontsize=12)

    doc.set_metadata({"author": author, "title": "Government Scheme Circular"})
    buf = doc.tobytes()
    doc.close()
    return buf


def create_pdf_with_table(title: str, headers: list[str], rows: list[list[str]]) -> bytes:
    """Generate a PDF containing drawn grid and text representing a table."""
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=600)

    # Insert title heading
    page.insert_text((50, 50), title, fontsize=16)

    # Draw table borders and text cells
    col_width = 180
    row_height = 30
    x_start = 50
    y_start = 100

    # Draw headers
    for col_idx, h in enumerate(headers):
        x = x_start + col_idx * col_width
        rect = pymupdf.Rect(x, y_start, x + col_width, y_start + row_height)
        page.draw_rect(rect, color=(0, 0, 0), width=1)
        page.insert_text((x + 10, y_start + 20), h, fontsize=12)

    # Draw rows
    for row_idx, r in enumerate(rows):
        y = y_start + (row_idx + 1) * row_height
        for col_idx, val in enumerate(r):
            x = x_start + col_idx * col_width
            rect = pymupdf.Rect(x, y, x + col_width, y + row_height)
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((x + 10, y + 20), str(val), fontsize=11)

    buf = doc.tobytes()
    doc.close()
    return buf


def upload_and_advance_to_ready_for_parsing(pdf_bytes: bytes, filename: str, title: str) -> uuid.UUID:
    """Helper to upload a document and advance it through Day 5 duplicate check to READY_FOR_PARSING."""
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data={"title": title},
    )
    assert resp.status_code == 201
    doc_id = uuid.UUID(resp.json()["id"])

    # Run Day 5 duplicate detection
    db = SessionLocal()
    dup_service = DuplicateDetectionService()
    res = dup_service.detect_duplicates(db, doc_id)
    assert res.resulting_processing_status == "READY_FOR_PARSING"
    db.close()

    return doc_id


@pytest.fixture(autouse=True)
def ensure_storage():
    """Ensure storage directories are initialized."""
    settings.ensure_storage_dirs()
    yield


def test_valid_digital_pdf_parsing():
    """Verify standard digital PDF parses to READY_FOR_OCR_CHECK with intact originals and normalized outputs."""
    uid = uuid.uuid4().hex[:6]
    text_p1 = (
        f"Government of Rajasthan Higher Education Department Circular {uid}.\n\n"
        "1. Overview and Guidelines:\n"
        "This scheme provides post-matric financial assistance to meritorious students.\n"
        "Applicants must submit family income certificates through e-Mitra.\n"
        "- Requirement 1: Valid Jan Aadhaar card.\n"
        "- Requirement 2: Minimum 60% in secondary examinations."
    )
    pdf_bytes = create_sample_pdf([text_p1])
    original_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"higher_education_{uid}.pdf", f"Higher Education Circular {uid}"
    )

    db = SessionLocal()
    parser_service = DocumentParserService()
    parsed_record = parser_service.parse_document(db, doc_id)

    # Status checks
    assert parsed_record.parse_status == "PARSED"
    assert parsed_record.page_count == 1
    assert parsed_record.pages_with_text == 1
    assert parsed_record.pages_without_text == 0
    assert parsed_record.total_blocks >= 1

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_OCR_CHECK"

    # Verify original file in storage is 100% untouched and unchanged
    original_file = settings.originals_dir / str(doc_id) / "original.pdf"
    assert original_file.exists()
    with open(original_file, "rb") as f:
        current_sha256 = hashlib.sha256(f.read()).hexdigest()
    assert current_sha256 == original_sha256

    # Verify parsed artifacts exist
    parsed_dir = settings.parsed_dir / str(doc_id)
    json_path = parsed_dir / "document.json"
    md_path = parsed_dir / "document.md"
    raw_dir = parsed_dir / "mineru_raw"

    assert json_path.exists()
    assert md_path.exists()
    assert raw_dir.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema_version"] == "1.0"
    assert data["document_id"] == str(doc_id)
    assert len(data["pages"]) == 1
    assert data["pages"][0]["page_number"] == 1
    assert len(data["pages"][0]["blocks"]) >= 1
    db.close()


def test_hindi_unicode_preservation():
    """Verify Devanagari Hindi characters are preserved intact without mojibake or loss."""
    uid = uuid.uuid4().hex[:6]
    hindi_text = (
        f"राजस्थान सरकार सामाजिक न्याय एवं अधिकारिता विभाग {uid}।\n"
        "योजना का नाम: मुख्यमंत्री कन्यादान योजना 2026।\n"
        "पात्रता की शर्तें:\n"
        "1. आवेदक परिवार की वार्षिक आय ₹2,50,000 से अधिक नहीं होनी चाहिए।\n"
        "2. बालिका की आयु 18 वर्ष पूर्ण होनी आवश्यक है।\n"
        "आवेदन प्रक्रिया: समस्त आवेदन ई-मित्र अथवा शाला दर्पण पोर्टल द्वारा स्वीकार किए जाएंगे।"
    )
    pdf_bytes = create_sample_pdf([hindi_text])
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"kanyadan_hindi_{uid}.pdf", f"Kanyadan Scheme {uid}"
    )

    db = SessionLocal()
    parser_service = DocumentParserService()
    parsed_record = parser_service.parse_document(db, doc_id)
    assert parsed_record.parse_status == "PARSED"

    # Inspect normalized JSON blocks
    artifact = parser_service.get_parsed_artifact(doc_id)
    assert artifact is not None

    full_extracted_text = " ".join(
        blk["text"] for p in artifact["pages"] for blk in p["blocks"]
    )

    # Assert critical Hindi terms are preserved
    for required_word in ["राजस्थान", "योजना", "पात्रता", "आय"]:
        assert required_word in full_extracted_text, f"Missing required Hindi word: {required_word}"

    db.close()


def test_table_structure_preservation():
    """Verify table borders and cells are detected and preserved with headers and rows."""
    uid = uuid.uuid4().hex[:6]
    headers = ["Category / श्रेणी", "Income Limit / आय सीमा"]
    rows = [
        ["General / सामान्य", "INR 2,00,000"],
        ["OBC / अन्य पिछड़ा वर्ग", "INR 2,50,000"],
        ["SC/ST / अनुसूचित जाति", "INR 3,00,000"],
    ]
    pdf_bytes = create_pdf_with_table(f"Eligibility Criteria Table {uid}", headers, rows)
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"table_doc_{uid}.pdf", f"Eligibility Table {uid}"
    )

    db = SessionLocal()
    parser_service = DocumentParserService()
    parsed_record = parser_service.parse_document(db, doc_id)
    assert parsed_record.parse_status == "PARSED"

    artifact = parser_service.get_parsed_artifact(doc_id)
    assert artifact is not None

    # Check that table blocks are present
    table_blocks = [
        blk for p in artifact["pages"] for blk in p["blocks"] if blk["block_type"] == BlockType.TABLE
    ]
    assert len(table_blocks) >= 1
    table_blk = table_blocks[0]
    assert len(table_blk["headers"]) == 2
    assert len(table_blk["rows"]) >= 3
    db.close()


def test_multipage_pdf_parsing():
    """Verify 10+ page document preserves sequential 1-based page numbers and block reading order."""
    uid = uuid.uuid4().hex[:6]
    page_count = 11
    pages_text = [
        f"Government of Rajasthan Gazette {uid} - Chapter {i+1}.\n"
        f"Official notification section rules and guidelines for page {i+1}."
        for i in range(page_count)
    ]
    pdf_bytes = create_sample_pdf(pages_text)
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"gazette_{uid}.pdf", f"Rajasthan Gazette {uid}"
    )

    db = SessionLocal()
    parser_service = DocumentParserService()
    parsed_record = parser_service.parse_document(db, doc_id)

    assert parsed_record.page_count == page_count
    assert parsed_record.pages_with_text == page_count
    assert parsed_record.pages_without_text == 0

    artifact = parser_service.get_parsed_artifact(doc_id)
    assert len(artifact["pages"]) == page_count

    # Check 1-based sequential page indexing
    for idx, page in enumerate(artifact["pages"]):
        expected_page_num = idx + 1
        assert page["page_number"] == expected_page_num
        assert page["status"] == PageTextStatus.TEXT_OK
        # Check block reading order
        for b_idx, blk in enumerate(page["blocks"]):
            assert blk["order_index"] == b_idx
            assert blk["page_number"] == expected_page_num

    db.close()


def test_scanned_pdf_diagnostics():
    """Verify image-only / scanned PDF proceeds safely without crash and flags NO_TEXT for Day 7 OCR."""
    uid = uuid.uuid4().hex[:6]
    doc = pymupdf.open()
    doc.new_page(width=300, height=300)  # blank page without text
    pdf_bytes = doc.tobytes()
    doc.close()

    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"scanned_{uid}.pdf", f"Scanned Order {uid}"
    )

    db = SessionLocal()
    parser_service = DocumentParserService()
    parsed_record = parser_service.parse_document(db, doc_id)

    assert parsed_record.parse_status == "PARSED"
    assert parsed_record.page_count == 1
    assert parsed_record.pages_with_text == 0
    assert parsed_record.pages_without_text == 1

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_OCR_CHECK"

    artifact = parser_service.get_parsed_artifact(doc_id)
    assert artifact["diagnostics"]["needs_ocr"] is True
    assert artifact["diagnostics"]["pages_without_text"] == 1
    assert artifact["pages"][0]["status"] == PageTextStatus.NO_TEXT
    db.close()


def test_mixed_digital_and_scanned_pdf():
    """Verify mixed PDF (digital pages + scanned blank pages) flags only the scanned pages."""
    uid = uuid.uuid4().hex[:6]
    doc = pymupdf.open()
    # Page 1: Digital text (>= 100 characters to qualify as TEXT_OK)
    p1 = doc.new_page(width=400, height=400)
    p1_text = (
        f"Government of Rajasthan Circular {uid} on page 1.\n"
        "All departmental officers must verify scheme eligibility rules and documentation standards.\n"
        "Applications must be registered at local municipal offices."
    )
    p1.insert_text((50, 50), p1_text, fontsize=12)
    # Page 2: Blank / scanned page (0 characters -> NO_TEXT)
    doc.new_page(width=400, height=400)
    # Page 3: Digital text (>= 100 characters)
    p3 = doc.new_page(width=400, height=400)
    p3_text = (
        f"Government of Rajasthan Circular {uid} on page 3.\n"
        "Concluding directions and notification guidelines for financial assistance to beneficiaries.\n"
        "Official circular published for public knowledge."
    )
    p3.insert_text((50, 50), p3_text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()

    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"mixed_{uid}.pdf", f"Mixed Circular {uid}"
    )

    db = SessionLocal()
    parser_service = DocumentParserService()
    parsed_record = parser_service.parse_document(db, doc_id)

    assert parsed_record.page_count == 3
    assert parsed_record.pages_with_text == 2
    assert parsed_record.pages_without_text == 1

    artifact = parser_service.get_parsed_artifact(doc_id)
    assert artifact["pages"][0]["status"] == PageTextStatus.TEXT_OK
    assert artifact["pages"][1]["status"] == PageTextStatus.NO_TEXT  # Page 2 flagged for Day 7 OCR
    assert artifact["pages"][2]["status"] == PageTextStatus.TEXT_OK
    db.close()


def test_parser_worker_and_idempotency():
    """Verify background worker processes batch idempotently and skips already parsed documents."""
    uid = uuid.uuid4().hex[:6]
    pdf_bytes = create_sample_pdf([f"Swasthya Bima Circular {uid}.\nMedical assistance guidelines for citizens."])
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"swasthya_{uid}.pdf", f"Swasthya Bima {uid}"
    )

    worker = DocumentParserWorker()

    # Drain backlog until doc_id is processed
    loop_count = 0
    while worker.process_batch(batch_size=20) > 0:
        loop_count += 1
        if loop_count > 10:
            break

    db = SessionLocal()
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_OCR_CHECK"
    db.close()

    # Subsequent run finds no documents in READY_FOR_PARSING (idempotent)
    count2 = worker.process_batch(batch_size=20)
    assert count2 == 0


def test_mineru_unavailable_graceful_failure():
    """Verify when MinerU executable is missing and fallback is disabled, system fails gracefully without crash."""
    uid = uuid.uuid4().hex[:6]
    pdf_bytes = create_sample_pdf([f"Sample test circular {uid}."])
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"mineru_fail_{uid}.pdf", f"MinerU Fail {uid}"
    )

    # Initialize adapter with fallback disabled to simulate environment without MinerU
    adapter_no_fallback = MinerUAdapter(fallback_enabled=False)
    adapter_no_fallback._resolve_mineru_command = lambda: None

    service = DocumentParserService(parser=adapter_no_fallback)

    db = SessionLocal()
    with pytest.raises(MinerUUnavailableException):
        service.parse_document(db, doc_id)

    # Confirm document and database are in PARSING_FAILED state safely
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "PARSING_FAILED"
    assert "MINERU_UNAVAILABLE" in doc.failure_reason

    parsed_repo = ParsedDocumentRepository()
    parsed_record = parsed_repo.get_latest_by_document_id(db, doc_id)
    assert parsed_record.parse_status == "PARSING_FAILED"
    db.close()


def test_corrupt_pdf_failure():
    """Verify corrupted PDF fails safely with PARSING_FAILED without crashing application."""
    uid = uuid.uuid4().hex[:6]
    pdf_bytes = create_sample_pdf([f"Sample valid circular {uid}."])
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"corrupt_{uid}.pdf", f"Corrupt {uid}"
    )

    # Overwrite the stored file with corrupted content to test parser corruption handling
    corrupt_bytes = b"%PDF-1.4\nCorrupted content without xref table\n%%EOF"
    storage_path = settings.originals_dir / str(doc_id) / "original.pdf"
    with open(storage_path, "wb") as f:
        f.write(corrupt_bytes)

    db = SessionLocal()
    parser_service = DocumentParserService()
    with pytest.raises(Exception):
        parser_service.parse_document(db, doc_id)

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "PARSING_FAILED"
    assert doc.failure_reason is not None
    db.close()


def test_parser_rest_apis():
    """Verify POST /parse, GET /parsed, GET /pages/{page_number}, and GET /parsed-artifact."""
    uid = uuid.uuid4().hex[:6]
    text = (
        f"Rajasthan Urban Sanitation Circular {uid}.\n"
        "Section 1: Guidelines for urban bodies.\n"
        "Section 2: Worker safety protocols and equipment."
    )
    pdf_bytes = create_sample_pdf([text])
    doc_id = upload_and_advance_to_ready_for_parsing(
        pdf_bytes, f"urban_sanitation_{uid}.pdf", f"Urban Sanitation {uid}"
    )

    # 1. POST /api/v1/documents/{id}/parse
    parse_resp = client.post(f"/api/v1/documents/{doc_id}/parse")
    assert parse_resp.status_code == 200
    p_data = parse_resp.json()
    assert p_data["document_id"] == str(doc_id)
    assert p_data["status"] == "READY_FOR_OCR_CHECK"
    assert p_data["parsed_record"]["page_count"] == 1

    # 2. GET /api/v1/documents/{id}/parsed
    metadata_resp = client.get(f"/api/v1/documents/{doc_id}/parsed")
    assert metadata_resp.status_code == 200
    meta = metadata_resp.json()
    assert meta["document_id"] == str(doc_id)
    assert meta["parse_status"] == "PARSED"
    assert meta["pages_with_text"] == 1

    # 3. GET /api/v1/documents/{id}/pages/1
    page_resp = client.get(f"/api/v1/documents/{doc_id}/pages/1")
    assert page_resp.status_code == 200
    page_json = page_resp.json()
    assert page_json["page_number"] == 1
    assert page_json["status"] == "TEXT_OK"
    assert len(page_json["blocks"]) >= 1

    # 4. GET /api/v1/documents/{id}/parsed-artifact (JSON)
    art_json_resp = client.get(f"/api/v1/documents/{doc_id}/parsed-artifact?format=json")
    assert art_json_resp.status_code == 200
    assert art_json_resp.headers["content-type"] == "application/json"
    doc_json = art_json_resp.json()
    assert doc_json["schema_version"] == "1.0"
    assert doc_json["document_id"] == str(doc_id)

    # 5. GET /api/v1/documents/{id}/parsed-artifact (Markdown)
    art_md_resp = client.get(f"/api/v1/documents/{doc_id}/parsed-artifact?format=md")
    assert art_md_resp.status_code == 200
    assert "text/markdown" in art_md_resp.headers["content-type"]
    assert f"# Document: {doc_id}" in art_md_resp.text
