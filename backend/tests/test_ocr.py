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
from app.ocr.detector import OCRDetectionService, calculate_garbled_ratio
from app.ocr.interface import ExtractionMethod, OCRPageResult, OCRRegion, OCRStatus
from app.ocr.merger import OCRMergeService
from app.ocr.paddle import MockOCRProvider, PaddleOCRAdapter, is_numeric_text
from app.ocr.renderer import PDFPageRenderer
from app.ocr.service import OCRService
from app.ocr.worker import OCRWorker
from app.parser.service import DocumentParserService
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_repository import OCRRunRepository

client = TestClient(app)
settings = get_settings()


def create_sample_pdf(pages_text: list[str], author: str = "YojanSetu Admin") -> bytes:
    """Generate a multi-page PDF with selectable digital text."""
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


def create_dummy_png(seed: str = "") -> bytes:
    """Generate a 120x120 PNG in memory with unique pixel values to prevent hash collisions."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 120), False)
    val = (sum(ord(c) for c in seed) % 200 + 30) if seed else 240
    pix.clear_with(val)
    buf = pix.tobytes("png")
    return buf


def create_scanned_pdf(page_count: int = 1, seed: str = "") -> bytes:
    """Generate a PDF containing only raster images (scanned document) with unique hash."""
    doc = pymupdf.open()
    png_bytes = create_dummy_png(seed=seed or uuid.uuid4().hex)

    for _ in range(page_count):
        page = doc.new_page(width=500, height=600)
        page.insert_image(pymupdf.Rect(20, 20, 480, 580), stream=png_bytes)

    buf = doc.tobytes()
    doc.close()
    return buf


def create_mixed_pdf(seed: str = "") -> bytes:
    """Generate a 3-page PDF: Page 1 Digital, Page 2 Scanned (Image), Page 3 Digital."""
    uid = seed or uuid.uuid4().hex[:8]
    doc = pymupdf.open()
    png_bytes = create_dummy_png(seed=uid)

    # Page 1: Digital text
    p1 = doc.new_page(width=500, height=600)
    p1.insert_text((50, 70), f"राजस्थान सरकार अधिसूचना {uid} - पेज 1 डिजिटल टेक्स्ट। यह पूर्णतः डिजिटल अधिसूचना है।", fontsize=12)

    # Page 2: Scanned image (no text)
    p2 = doc.new_page(width=500, height=600)
    p2.insert_image(pymupdf.Rect(20, 20, 480, 580), stream=png_bytes)

    # Page 3: Digital text
    p3 = doc.new_page(width=500, height=600)
    p3.insert_text((50, 70), f"राजस्थान सरकार अधिसूचना {uid} - पेज 3 डिजिटल टेक्स्ट। यह भी डिजिटल है।", fontsize=12)

    buf = doc.tobytes()
    doc.close()
    return buf


def upload_and_advance_to_ready_for_ocr_check(pdf_bytes: bytes, filename: str, title: str) -> uuid.UUID:
    """Upload PDF, run duplicate detection, parse with MinerU/builtin to reach READY_FOR_OCR_CHECK."""
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data={"title": title},
    )
    assert resp.status_code == 201
    doc_id = uuid.UUID(resp.json()["id"])

    db = SessionLocal()
    # Step 1: Duplicate check -> READY_FOR_PARSING
    dup_service = DuplicateDetectionService()
    dup_res = dup_service.detect_duplicates(db, doc_id)
    assert dup_res.resulting_processing_status == "READY_FOR_PARSING"

    # Step 2: Document parsing -> READY_FOR_OCR_CHECK
    parser_service = DocumentParserService()
    parsed_doc = parser_service.parse_document(db, doc_id)
    assert parsed_doc.parse_status == "PARSED"

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_OCR_CHECK"
    db.close()

    return doc_id


@pytest.fixture(autouse=True)
def ensure_storage():
    """Ensure all storage directories exist."""
    settings.ensure_storage_dirs()
    yield


# --------------------------------------------------------------------------
# Test 1: Digital PDF skips OCR (Section 64)
# --------------------------------------------------------------------------
def test_digital_pdf_skips_ocr():
    """Verify that a clean selectable-text PDF does not trigger unnecessary OCR."""
    uid = uuid.uuid4().hex[:8]
    pdf_bytes = create_sample_pdf([
        f"राजस्थान सरकार अधिसूचना {uid} - सामाजिक न्याय विभाग। यह एक पूरी तरह से डिजिटल अधिसूचना है जिसमें पर्याप्त टेक्स्ट उपलब्ध है।",
        f"पात्रता की शर्तें {uid}: आवेदक राजस्थान का मूल निवासी होना चाहिए। वार्षिक पारिवारिक आय ₹2,50,000 से अधिक न हो।",
    ])
    doc_id = upload_and_advance_to_ready_for_ocr_check(
        pdf_bytes, f"digital_doc_{uid}.pdf", f"Digital Scheme Notification {uid}"
    )

    db = SessionLocal()
    ocr_service = OCRService()
    ocr_run = ocr_service.process_document(db, doc_id)

    assert ocr_run.status == "SKIPPED_NOT_NEEDED"
    assert ocr_run.pages_ocr_required == 0
    assert ocr_run.pages_ocr_success == 0

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_CHUNKING"
    assert "document.json" in ocr_run.chunking_source_path
    db.close()


# --------------------------------------------------------------------------
# Test 2: Fully scanned PDF triggers OCR and merges cleanly (Section 65)
# --------------------------------------------------------------------------
def test_fully_scanned_pdf_ocr():
    """Verify image-only scanned PDF is rendered at 250 DPI, OCR'd, and merged to READY_FOR_CHUNKING."""
    uid = uuid.uuid4().hex[:8]
    scanned_bytes = create_scanned_pdf(page_count=2, seed=uid)
    doc_id = upload_and_advance_to_ready_for_ocr_check(
        scanned_bytes, f"scanned_doc_{uid}.pdf", f"Scanned Scheme Order {uid}"
    )

    db = SessionLocal()
    ocr_service = OCRService()
    ocr_run = ocr_service.process_document(db, doc_id)

    assert ocr_run.status == "COMPLETED"
    assert ocr_run.pages_total == 2
    assert ocr_run.pages_ocr_required == 2
    assert ocr_run.pages_ocr_success == 2
    assert ocr_run.pages_ocr_failed == 0
    assert ocr_run.output_path is not None
    assert "merged_document.json" in ocr_run.chunking_source_path

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_CHUNKING"

    # Verify merged document integrity and block provenance
    merged_path = settings.ocr_dir / str(doc.id) / "merged_document.json"
    assert merged_path.exists()

    with open(merged_path, "r", encoding="utf-8") as f:
        merged_data = json.load(f)

    assert merged_data["page_count"] == 2
    assert len(merged_data["pages"]) == 2
    for page in merged_data["pages"]:
        assert page["extraction_method"] == ExtractionMethod.PADDLEOCR.value
        for blk in page["blocks"]:
            assert blk["extraction_method"] == ExtractionMethod.PADDLEOCR.value

    # Verify rendered page PNG exists at 250 DPI
    p1_img = settings.ocr_dir / str(doc.id) / "pages" / "page_001.png"
    p2_img = settings.ocr_dir / str(doc.id) / "pages" / "page_002.png"
    assert p1_img.exists()
    assert p2_img.exists()
    db.close()


# --------------------------------------------------------------------------
# Test 3: Mixed PDF — selective page OCR (Section 66)
# --------------------------------------------------------------------------
def test_mixed_pdf_selective_ocr():
    """Verify mixed 3-page PDF: only Page 2 is OCR'd; Pages 1 & 3 retain MINERU provenance."""
    uid = uuid.uuid4().hex[:8]
    mixed_bytes = create_mixed_pdf(seed=uid)
    doc_id = upload_and_advance_to_ready_for_ocr_check(
        mixed_bytes, f"mixed_doc_{uid}.pdf", f"Mixed Scheme PDF {uid}"
    )

    db = SessionLocal()
    ocr_service = OCRService()
    ocr_run = ocr_service.process_document(db, doc_id)

    assert ocr_run.status == "COMPLETED"
    assert ocr_run.pages_total == 3
    assert ocr_run.pages_ocr_required == 1
    assert ocr_run.pages_ocr_success == 1

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "READY_FOR_CHUNKING"

    # Verify Page 1 and Page 3 images were NOT rendered
    p1_img = settings.ocr_dir / str(doc.id) / "pages" / "page_001.png"
    p2_img = settings.ocr_dir / str(doc.id) / "pages" / "page_002.png"
    p3_img = settings.ocr_dir / str(doc.id) / "pages" / "page_003.png"
    assert not p1_img.exists()  # Page 1 was digital -> skipped
    assert p2_img.exists()      # Page 2 was scanned -> rendered
    assert not p3_img.exists()  # Page 3 was digital -> skipped

    # Inspect merged_document.json
    merged_path = settings.ocr_dir / str(doc.id) / "merged_document.json"
    with open(merged_path, "r", encoding="utf-8") as f:
        merged = json.load(f)

    # CRITICAL INTEGRITY CHECK: Page count invariance (Section 62)
    assert merged["page_count"] == 3
    assert len(merged["pages"]) == 3

    # Provenance Check (Section 63)
    p1_data = merged["pages"][0]
    p2_data = merged["pages"][1]
    p3_data = merged["pages"][2]

    assert p1_data["page_number"] == 1
    assert p1_data["extraction_method"] == ExtractionMethod.MINERU.value

    assert p2_data["page_number"] == 2
    assert p2_data["extraction_method"] == ExtractionMethod.PADDLEOCR.value

    assert p3_data["page_number"] == 3
    assert p3_data["extraction_method"] == ExtractionMethod.MINERU.value
    db.close()


# --------------------------------------------------------------------------
# Test 4: Hindi text and Devanagari numerals survive OCR (Section 67, 27)
# --------------------------------------------------------------------------
def test_hindi_and_devanagari_digits():
    """Verify Rajasthan keywords and Devanagari numerals (०१२३४५६७८९) survive OCR intact."""
    provider = MockOCRProvider(
        simulated_texts={
            1: (
                "राजस्थान सरकार - सामाजिक न्याय\n"
                "योजना: मुख्यमंत्री कन्यादान योजना २०२६\n"
                "पात्रता: वार्षिक आय ₹२,००,००० से कम हो\n"
                "लाभार्थी: बीपीएल परिवार की कन्याएं\n"
                "आवेदन हेतु आवश्यक दस्तावेज: जन आधार कार्ड\n"
                "क्रमांक: ०१२३४५६७८९"
            )
        }
    )
    result = provider.ocr_page(settings.ocr_dir / "test.png", page_number=1)
    assert result.success is True

    full_text = result.raw_text
    keywords = ["राजस्थान", "योजना", "पात्रता", "आय", "लाभार्थी", "आवेदन", "दस्तावेज", "०१२३४५६७८९"]
    for kw in keywords:
        assert kw in full_text, f"Missing expected Hindi keyword/digit: {kw}"


# --------------------------------------------------------------------------
# Test 5: Numeric risk detection and low confidence flag (Section 68, 26)
# --------------------------------------------------------------------------
def test_numeric_risk_detection():
    """Verify numeric indicators (₹, years, %, dates) are detected and flagged if confidence is low."""
    # Test numeric regex helper
    assert is_numeric_text("वार्षिक आय सीमा ₹2,00,000") is True
    assert is_numeric_text("आयु सीमा 18 वर्ष से 60 वर्ष") is True
    assert is_numeric_text("अंतिम तिथि 31/03/2026") is True
    assert is_numeric_text("छूट 40% देय होगी") is True
    assert is_numeric_text("सामान्य निर्देश एवं नियम") is False

    # Simulate low-confidence numeric OCR
    low_conf_provider = MockOCRProvider(
        simulated_texts={
            1: "वार्षिक आय सीमा ₹2,00,000\nआयु सीमा 60 वर्ष\nअंतिम तिथि 31/03/2026"
        }
    )
    res = low_conf_provider.ocr_page(
        settings.ocr_dir / "test.png",
        page_number=1,
        simulated_confidence=0.65,  # Below 0.80 threshold
    )
    assert res.success is True
    low_conf_regions = [r for r in res.regions if r.low_confidence_numeric]
    assert len(low_conf_regions) >= 2


# --------------------------------------------------------------------------
# Test 6: Scanned table OCR handling (Section 69, 28)
# --------------------------------------------------------------------------
def test_scanned_table_ocr():
    """Verify scanned table page preserves coordinates and flags table_structure_uncertain."""
    table_text = (
        "तालिका विवरण\n"
        "क्र.सं. | योजना का नाम | अनुदान राशि\n"
        "1 | अनुप्रति योजना | ₹1,00,000\n"
        "2 | स्कूटी योजना | 1 स्कूटी"
    )
    provider = MockOCRProvider(simulated_texts={1: table_text})
    res = provider.ocr_page(settings.ocr_dir / "test.png", page_number=1)
    assert res.success is True

    # Test merge with table
    merger = OCRMergeService()
    parsed_doc_data = {
        "schema_version": "1.0",
        "document_id": "DOC-TABLE-01",
        "pages": [{"page_number": 1, "status": "NO_TEXT", "blocks": []}],
    }
    merged = merger.merge("DOC-TABLE-01", parsed_doc_data, {1: res})

    table_blocks = [b for b in merged["pages"][0]["blocks"] if b.get("metadata", {}).get("table_structure_uncertain")]
    assert len(table_blocks) > 0


# --------------------------------------------------------------------------
# Test 7: Blank page divider does not trigger false OCR (Section 70, 9)
# --------------------------------------------------------------------------
def test_blank_page_no_false_ocr():
    """Verify a blank divider page with 0 text and 0 images does not require OCR."""
    detector = OCRDetectionService(min_text_chars=50)
    decision = detector.evaluate_page(
        page_number=2,
        status="TEXT_OK",
        blocks=[],
        image_count=0,
    )
    assert decision.needs_ocr is False
    assert decision.reason == "BLANK_DIVIDER"


# --------------------------------------------------------------------------
# Test 8: Partial failure handling (Section 71, 42)
# --------------------------------------------------------------------------
def test_partial_failure_handling():
    """Verify when an OCR required page fails, document transitions to OCR_FAILED, NOT READY_FOR_CHUNKING."""
    uid = uuid.uuid4().hex[:8]
    scanned_bytes = create_scanned_pdf(page_count=2, seed=uid)
    doc_id = upload_and_advance_to_ready_for_ocr_check(
        scanned_bytes, f"fail_doc_{uid}.pdf", f"Partial Failure Test {uid}"
    )

    # Inject mock provider configured to fail on page 2
    failing_provider = MockOCRProvider(fail_pages=[2])
    db = SessionLocal()
    ocr_service = OCRService(provider=failing_provider)
    ocr_run = ocr_service.process_document(db, doc_id)

    assert ocr_run.status == "PARTIAL_FAILURE"
    assert ocr_run.pages_ocr_failed > 0

    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, doc_id)
    assert doc.processing_status == "OCR_FAILED"
    db.close()


# --------------------------------------------------------------------------
# Test 9: Worker idempotency (Section 72, 40)
# --------------------------------------------------------------------------
def test_ocr_worker_idempotency():
    """Verify OCRWorker processes batches idempotently without duplicate records."""
    worker = OCRWorker()
    # Drain any existing pending documents in database from prior tests
    while worker.process_batch(batch_size=50) > 0:
        pass

    uid = uuid.uuid4().hex[:8]
    pdf_bytes = create_sample_pdf([f"राजस्थान सरकार का आदेश {uid}। पूर्णतः डिजिटल टेक्स्ट।"])
    doc_id = upload_and_advance_to_ready_for_ocr_check(
        pdf_bytes, f"worker_doc_{uid}.pdf", f"Worker Test {uid}"
    )

    count_1 = worker.process_batch(batch_size=10)
    assert count_1 == 1

    # Second pass: already in READY_FOR_CHUNKING -> should process 0
    count_2 = worker.process_batch(batch_size=10)
    assert count_2 == 0

    db = SessionLocal()
    ocr_repo = OCRRunRepository()
    runs = ocr_repo.get_all_by_document_id(db, doc_id)
    assert len(runs) == 1
    db.close()


# --------------------------------------------------------------------------
# Test 10: OCR REST APIs (Section 47, 48)
# --------------------------------------------------------------------------
def test_ocr_rest_apis():
    """Verify POST /ocr-check, GET /ocr, GET /ocr/pages/{num}, and GET /ocr/merged."""
    uid = uuid.uuid4().hex[:8]
    scanned_bytes = create_scanned_pdf(page_count=1, seed=uid)
    doc_id = upload_and_advance_to_ready_for_ocr_check(
        scanned_bytes, f"api_ocr_{uid}.pdf", f"API OCR Test {uid}"
    )

    # POST /ocr-check
    resp_check = client.post(f"/api/v1/documents/{doc_id}/ocr-check")
    assert resp_check.status_code == 200
    data_check = resp_check.json()
    assert data_check["status"] == "READY_FOR_CHUNKING"
    assert data_check["ocr_run"]["status"] == "COMPLETED"

    # GET /ocr
    resp_meta = client.get(f"/api/v1/documents/{doc_id}/ocr")
    assert resp_meta.status_code == 200
    data_meta = resp_meta.json()
    assert data_meta["pages_total"] == 1
    assert data_meta["pages_ocr_success"] == 1

    # GET /ocr/pages/1
    resp_page = client.get(f"/api/v1/documents/{doc_id}/ocr/pages/1")
    assert resp_page.status_code == 200
    data_page = resp_page.json()
    assert data_page["page_number"] == 1
    assert data_page["regions_count"] > 0

    # GET /ocr/merged
    resp_merged = client.get(f"/api/v1/documents/{doc_id}/ocr/merged")
    assert resp_merged.status_code == 200
    assert "schema_version" in resp_merged.json()
