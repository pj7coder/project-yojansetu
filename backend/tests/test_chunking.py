import json
from pathlib import Path
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient

from app.chunking.formatter import ChunkFormatter
from app.chunking.section_detector import SectionDetector
from app.chunking.section_patterns import PROVISO_EXCEPTION_REGEX, SectionType
from app.chunking.service import DocumentChunkingService
from app.chunking.splitter import CandidateChunk, SemanticSplitter
from app.chunking.tokenizer import estimate_tokens
from app.chunking.validator import ChunkValidationError, ChunkValidator
from app.chunking.worker import ChunkingWorker
from app.core.config import settings
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.session import SessionLocal
from app.main import app
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit Tests: Token Estimation & Calibrated Counting
# ---------------------------------------------------------------------------

def test_token_estimation_english_and_hindi():
    """Verify calibrated token estimation handles English and Devanagari subwords."""
    eng_text = "This is a government circular specifying income eligibility criteria."
    hi_text = "यह एक सरकारी अधिसूचना है जिसमें आय सीमा और पात्रता की शर्तें दी गई हैं।"

    eng_tokens = estimate_tokens(eng_text)
    hi_tokens = estimate_tokens(hi_text)

    assert eng_tokens > 0
    assert hi_tokens > 0
    # Devanagari UTF-8 bytes require more subword tokens per word than English
    assert hi_tokens > len(hi_text.split())


# ---------------------------------------------------------------------------
# Unit Tests: Section Detection & Hindi Support
# ---------------------------------------------------------------------------

def test_section_detector_english_headings():
    """Test English heading recognition across key scheme sections."""
    detector = SectionDetector()

    test_cases = [
        ({"block_type": "HEADING", "text": "1. Scheme Overview and Objectives"}, SectionType.OVERVIEW),
        ({"block_type": "HEADING", "text": "2. Eligibility Criteria for Beneficiaries"}, SectionType.ELIGIBILITY),
        ({"block_type": "HEADING", "text": "3. Exclusions from Scheme Benefits"}, SectionType.EXCLUSIONS),
        ({"block_type": "HEADING", "text": "4. Financial Benefits and Allowances"}, SectionType.BENEFITS),
        ({"block_type": "HEADING", "text": "5. List of Required Documents"}, SectionType.DOCUMENTS_REQUIRED),
        ({"block_type": "HEADING", "text": "6. Application Procedure and Online Portal"}, SectionType.APPLICATION_PROCESS),
        ({"block_type": "HEADING", "text": "7. Corrigendum and Amendment to Circular"}, SectionType.AMENDMENT),
    ]

    for block, expected_type in test_cases:
        result = detector.detect_section(block)
        assert result is not None, f"Failed to detect: {block['text']}"
        sec_type, title = result
        assert sec_type == expected_type


def test_section_detector_hindi_headings():
    """Test Hindi heading recognition with vernacular terminology."""
    detector = SectionDetector()

    test_cases = [
        ({"block_type": "HEADING", "text": "पात्रता एवं शर्तें"}, SectionType.ELIGIBILITY),
        ({"block_type": "HEADING", "text": "लाभ एवं सहायता राशि"}, SectionType.BENEFITS),
        ({"block_type": "HEADING", "text": "आवश्यक दस्तावेज की सूची"}, SectionType.DOCUMENTS_REQUIRED),
        ({"block_type": "HEADING", "text": "आवेदन प्रक्रिया एवं दिशा निर्देश"}, SectionType.APPLICATION_PROCESS),
        ({"block_type": "HEADING", "text": "योजना का संक्षिप्त विवरण"}, SectionType.OVERVIEW),
        ({"block_type": "HEADING", "text": "संशोधन अधिसूचना 2026"}, SectionType.AMENDMENT),
        ({"block_type": "HEADING", "text": "परिशिष्ट - अ"}, SectionType.ANNEXURE),
    ]

    for block, expected_type in test_cases:
        result = detector.detect_section(block)
        assert result is not None, f"Failed to detect Hindi section: {block['text']}"
        sec_type, title = result
        assert sec_type == expected_type


def test_section_detector_unknown_heading():
    """Verify that unrecognized headings map gracefully to SectionType.UNKNOWN."""
    detector = SectionDetector()
    block = {"block_type": "HEADING", "text": "Miscellaneous Department Routine Meeting Minutes"}
    result = detector.detect_section(block)
    assert result is not None
    sec_type, title = result
    assert sec_type == SectionType.UNKNOWN


def test_section_detector_hierarchy():
    """Test hierarchical section path tracking."""
    detector = SectionDetector()
    p1 = detector.update_hierarchy(SectionType.ELIGIBILITY, "Eligibility Criteria")
    assert p1 == ["Eligibility Criteria"]

    p2 = detector.update_hierarchy(SectionType.ELIGIBILITY, "Income Limits")
    assert p2 == ["Eligibility Criteria", "Income Limits"]

    # Shifting to a different section type resets top-level hierarchy
    p3 = detector.update_hierarchy(SectionType.BENEFITS, "Financial Assistance")
    assert p3 == ["Financial Assistance"]


# ---------------------------------------------------------------------------
# Unit Tests: Formatter & Table Rendering
# ---------------------------------------------------------------------------

def test_chunk_formatter_markdown_table_rendering():
    """Test markdown rendering of structured table blocks."""
    table_block = {
        "block_type": "TABLE",
        "headers": ["Category", "Income Limit", "Assistance Amount"],
        "rows": [
            ["General", "₹2,50,000", "₹1,000/month"],
            ["BPL / Antyodaya", "₹5,00,000", "₹2,500/month"],
        ],
    }
    rendered = ChunkFormatter.render_table_markdown(table_block)
    assert "| Category | Income Limit | Assistance Amount |" in rendered
    assert "| General | ₹2,50,000 | ₹1,000/month |" in rendered
    assert "| BPL / Antyodaya | ₹5,00,000 | ₹2,500/month |" in rendered


def test_chunk_formatter_boilerplate_filtering():
    """Verify administrative boilerplate and footers are identified and excluded."""
    header_block = {"block_type": "HEADER", "text": "Government of Rajasthan"}
    footer_block = {"block_type": "FOOTER", "text": "Page 3 of 12"}
    url_block = {"block_type": "PARAGRAPH", "text": "https://rajasthan.gov.in"}
    meaningful_block = {"block_type": "PARAGRAPH", "text": "Applicants must be permanent residents of Rajasthan."}

    assert ChunkFormatter.is_boilerplate(header_block) is True
    assert ChunkFormatter.is_boilerplate(footer_block) is True
    assert ChunkFormatter.is_boilerplate(url_block) is True
    assert ChunkFormatter.is_boilerplate(meaningful_block) is False


# ---------------------------------------------------------------------------
# Unit Tests: Legal Proviso & Exception Bonding
# ---------------------------------------------------------------------------

def test_exception_proviso_regex_signals():
    """Test regex recognition of English and Hindi legal exception / proviso clauses."""
    en_proviso = "Provided that applicants owning more than 2 hectares shall not be eligible."
    hi_proviso = "परंतु ऐसे आवेदक जो पूर्व से किसी अन्य पेंशन का लाभ ले रहे हैं, वे पात्र नहीं होंगे।"
    normal_rule = "All resident senior citizens are eligible."

    assert bool(PROVISO_EXCEPTION_REGEX.search(en_proviso)) is True
    assert bool(PROVISO_EXCEPTION_REGEX.search(hi_proviso)) is True
    assert bool(PROVISO_EXCEPTION_REGEX.search(normal_rule)) is False


def test_proviso_context_bonding_in_splitter():
    """
    CRITICAL TEST: Verify that a legal proviso / exception clause cannot split away
    from its parent rule block, even if a boundary would otherwise occur.
    """
    splitter = SemanticSplitter(target_tokens=100, max_tokens=200, min_tokens=20)

    pages = [{
        "page_number": 1,
        "blocks": [
            {
                "block_id": "b-1",
                "order_index": 0,
                "block_type": "HEADING",
                "text": "Eligibility Criteria",
                "page_number": 1,
            },
            {
                "block_id": "b-2",
                "order_index": 1,
                "block_type": "PARAGRAPH",
                "text": "Applicants above 60 years of age are eligible for the pension.",
                "page_number": 1,
            },
            {
                "block_id": "b-3",
                "order_index": 2,
                "block_type": "PARAGRAPH",
                # This proviso starts with 'Provided that' and must stay bonded
                "text": "Provided that applicants already receiving XYZ central pension shall not be eligible.",
                "page_number": 1,
            },
        ],
    }]

    chunks = splitter.build_chunks("test-doc-proviso", pages)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.section_type == SectionType.ELIGIBILITY.value
    chunk_bids = [b["block_id"] for b in chunk.blocks]
    # Both the base rule (b-2) and the proviso (b-3) must be in the same chunk
    assert "b-2" in chunk_bids
    assert "b-3" in chunk_bids


# ---------------------------------------------------------------------------
# Unit Tests: Oversized Section Splitting with Overlap
# ---------------------------------------------------------------------------

def test_oversized_section_splitting_with_overlap():
    """Verify that sections exceeding max tokens are split with controlled overlap."""
    # Set small target tokens to force splitting
    splitter = SemanticSplitter(target_tokens=60, max_tokens=100, min_tokens=10, overlap_tokens=25)

    blocks = [
        {
            "block_id": "head-1",
            "order_index": 0,
            "block_type": "HEADING",
            "text": "Eligibility Conditions",
            "page_number": 1,
        }
    ]
    # Add 10 paragraphs each ~20 tokens
    for i in range(1, 11):
        blocks.append({
            "block_id": f"p-{i}",
            "order_index": i,
            "block_type": "PARAGRAPH",
            "text": f"Condition {i}: Beneficiary must satisfy municipal dwelling criteria and documentation clause number {i}.",
            "page_number": 1 + (i // 5),
        })

    pages = [{"page_number": 1, "blocks": blocks}]
    chunks = splitter.build_chunks("test-doc-split", pages)

    assert len(chunks) > 1
    # Check that subsequent sub-chunks have overlap_from_previous marked
    assert chunks[0].overlap_from_previous is False
    assert chunks[1].overlap_from_previous is True


# ---------------------------------------------------------------------------
# Unit Tests: ChunkValidator (Coverage, Continuity, Zero Unassigned Blocks)
# ---------------------------------------------------------------------------

def test_chunk_validator_coverage_and_quality():
    """Test ChunkValidator reports zero unassigned blocks and valid diagnostics."""
    all_blocks = [
        {"block_id": "b-hdr", "block_type": "HEADER", "text": "Page Header", "page_number": 1},
        {"block_id": "b-1", "block_type": "HEADING", "text": "Overview", "page_number": 1},
        {"block_id": "b-2", "block_type": "PARAGRAPH", "text": "Content overview paragraph.", "page_number": 1},
        {"block_id": "b-ftr", "block_type": "FOOTER", "text": "Page 1 of 1", "page_number": 1},
    ]

    candidate = CandidateChunk(
        section_type="OVERVIEW",
        section_path=["Overview"],
        chunk_title="Overview",
        blocks=[all_blocks[1], all_blocks[2]],
        page_start=1,
        page_end=1,
        token_count=150,
        contains_table=False,
        contains_ocr=False,
    )

    report = ChunkValidator.validate(all_blocks, [candidate], hard_max_tokens=8000)

    assert report.is_valid is True
    assert report.total_blocks == 4
    assert report.included_blocks == 2
    assert report.excluded_boilerplate_blocks == 2
    assert report.unassigned_blocks == 0
    assert report.errors == []


def test_chunk_validator_flags_unassigned_blocks():
    """Verify validator fails if a non-boilerplate block is accidentally dropped."""
    all_blocks = [
        {"block_id": "b-1", "block_type": "HEADING", "text": "Overview", "page_number": 1},
        {"block_id": "b-2", "block_type": "PARAGRAPH", "text": "Included paragraph.", "page_number": 1},
        {"block_id": "b-3", "block_type": "PARAGRAPH", "text": "Forgotten critical rule.", "page_number": 1},
    ]

    candidate = CandidateChunk(
        section_type="OVERVIEW",
        section_path=["Overview"],
        chunk_title="Overview",
        blocks=[all_blocks[0], all_blocks[1]],  # b-3 is omitted!
        page_start=1,
        page_end=1,
        token_count=100,
    )

    report = ChunkValidator.validate(all_blocks, [candidate], hard_max_tokens=8000)
    assert report.is_valid is False
    assert report.unassigned_blocks == 1
    assert "b-3" in report.unassigned_block_ids


# ---------------------------------------------------------------------------
# Integration Tests: End-to-End DocumentChunkingService & Worker
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_mock_structured_doc(doc_id: uuid.UUID, include_ocr: bool = False, include_table: bool = True) -> dict:
    """Helper to generate a realistic structured document payload."""
    blocks_p1 = [
        {
            "block_id": f"{doc_id}-p1-b0",
            "order_index": 0,
            "block_type": "HEADER",
            "text": "Government of Rajasthan - Circular",
            "page_number": 1,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p1-b1",
            "order_index": 1,
            "block_type": "HEADING",
            "text": "1. Overview of the Scheme",
            "page_number": 1,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p1-b2",
            "order_index": 2,
            "block_type": "PARAGRAPH",
            "text": "The Rajasthan Social Security Assistance scheme aims to support elderly residents.",
            "page_number": 1,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p1-b3",
            "order_index": 3,
            "block_type": "HEADING",
            "text": "2. Eligibility Criteria",
            "page_number": 1,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p1-b4",
            "order_index": 4,
            "block_type": "PARAGRAPH",
            "text": "All applicants must be above 58 years of age and permanent residents of Rajasthan.",
            "page_number": 1,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p1-b5",
            "order_index": 5,
            "block_type": "PARAGRAPH",
            "text": "Provided that individuals in government service shall not be eligible.",
            "page_number": 1,
            "extraction_method": "MINERU",
        },
    ]

    blocks_p2 = [
        {
            "block_id": f"{doc_id}-p2-b0",
            "order_index": 0,
            "block_type": "HEADING",
            "text": "3. Benefits and Allowances",
            "page_number": 2,
            "extraction_method": "PADDLEOCR" if include_ocr else "MINERU",
        },
    ]

    if include_table:
        blocks_p2.append({
            "block_id": f"{doc_id}-p2-b1",
            "order_index": 1,
            "block_type": "TABLE",
            "page_number": 2,
            "extraction_method": "PADDLEOCR" if include_ocr else "MINERU",
            "headers": ["Age Bracket", "Monthly Pension"],
            "rows": [["58 - 75 years", "₹1,150"], ["Above 75 years", "₹1,500"]],
        })

    blocks_p2.extend([
        {
            "block_id": f"{doc_id}-p2-b2",
            "order_index": 2,
            "block_type": "HEADING",
            "text": "4. Required Documents",
            "page_number": 2,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p2-b3",
            "order_index": 3,
            "block_type": "LIST_ITEM",
            "text": "1. Jan Aadhaar Card\n2. Bank Passbook\n3. Age Proof",
            "page_number": 2,
            "extraction_method": "MINERU",
        },
        {
            "block_id": f"{doc_id}-p2-b4",
            "order_index": 4,
            "block_type": "FOOTER",
            "text": "Page 2 of 2",
            "page_number": 2,
            "extraction_method": "MINERU",
        },
    ])

    return {
        "document_id": str(doc_id),
        "total_pages": 2,
        "pages": [
            {"page_number": 1, "blocks": blocks_p1},
            {"page_number": 2, "blocks": blocks_p2},
        ],
    }


def test_chunking_service_end_to_end(test_db):
    """
    End-to-end test of DocumentChunkingService:
    1. Seed a document in READY_FOR_CHUNKING.
    2. Write structured document JSON to storage.
    3. Execute service.chunk_document().
    4. Verify transitions to READY_FOR_EXTRACTION, chunk persistence in DB & filesystem.
    """
    doc_repo = DocumentRepository()
    chunk_repo = DocumentChunkRepository()

    doc = Document(
        document_code=f"DOC-CHUNK-{uuid.uuid4().hex[:6].upper()}",
        original_filename="rajasthan_pension_rules.pdf",
        storage_path="storage/raw/test.pdf",
        file_size_bytes=12345,
        page_count=2,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_CHUNKING",
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    # Save mock structured document JSON
    parsed_dir = Path(settings.parsed_storage_dir) / str(doc.id)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    doc_data = create_mock_structured_doc(doc.id, include_ocr=True, include_table=True)
    json_path = parsed_dir / "document.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(doc_data, f)

    service = DocumentChunkingService()
    result = service.chunk_document(test_db, doc.id)

    assert result["success"] is True
    assert result["status"] == "READY_FOR_EXTRACTION"
    assert result["chunk_count"] > 0

    # Verify DB records
    db_chunks = chunk_repo.get_by_document_id(test_db, doc.id)
    assert len(db_chunks) == result["chunk_count"]

    # Verify section types preserved
    sec_types = [c.section_type for c in db_chunks]
    assert "ELIGIBILITY" in sec_types
    assert "BENEFITS" in sec_types
    assert "DOCUMENTS_REQUIRED" in sec_types

    # Verify OCR and table flags
    assert any(c.contains_ocr for c in db_chunks) is True
    assert any(c.contains_table for c in db_chunks) is True

    # Verify master chunks.json and txt files exist on disk
    chunk_dir = Path(settings.chunks_dir) / str(doc.id)
    assert (chunk_dir / "chunks.json").exists()
    assert len(list((chunk_dir / "chunks").glob("*.txt"))) == len(db_chunks)


def test_chunking_service_idempotent_rerun(test_db):
    """Verify running chunking twice replaces chunks safely without duplicates."""
    doc_repo = DocumentRepository()
    chunk_repo = DocumentChunkRepository()

    doc = Document(
        document_code=f"DOC-IDEMP-{uuid.uuid4().hex[:6].upper()}",
        original_filename="rajasthan_idempotent_test.pdf",
        storage_path="storage/raw/test2.pdf",
        file_size_bytes=8900,
        page_count=2,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_CHUNKING",
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    parsed_dir = Path(settings.parsed_storage_dir) / str(doc.id)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    doc_data = create_mock_structured_doc(doc.id, include_ocr=False, include_table=False)
    with open(parsed_dir / "document.json", "w", encoding="utf-8") as f:
        json.dump(doc_data, f)

    service = DocumentChunkingService()

    # First run
    res1 = service.chunk_document(test_db, doc.id)
    initial_chunks = chunk_repo.get_by_document_id(test_db, doc.id)
    assert len(initial_chunks) == res1["chunk_count"]

    # Second run with force=True
    res2 = service.chunk_document(test_db, doc.id, force=True)
    rerun_chunks = chunk_repo.get_by_document_id(test_db, doc.id)

    # Must have the exact same number of chunks, no duplicates
    assert len(rerun_chunks) == len(initial_chunks)


def test_chunking_worker_batch_processing(test_db):
    """Test ChunkingWorker batch processing of documents."""
    doc = Document(
        document_code=f"DOC-WRK-{uuid.uuid4().hex[:6].upper()}",
        original_filename="worker_test.pdf",
        storage_path="storage/raw/test3.pdf",
        file_size_bytes=7000,
        page_count=2,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_CHUNKING",
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    parsed_dir = Path(settings.parsed_storage_dir) / str(doc.id)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    doc_data = create_mock_structured_doc(doc.id, include_ocr=False, include_table=True)
    with open(parsed_dir / "document.json", "w", encoding="utf-8") as f:
        json.dump(doc_data, f)

    worker = ChunkingWorker()
    success = worker.process_single(str(doc.id))
    assert success is True

    test_db.refresh(doc)
    assert doc.processing_status == "READY_FOR_EXTRACTION"

    # Also verify process_batch runs without exception
    batch_count = worker.process_batch(batch_size=5)
    assert isinstance(batch_count, int)


# ---------------------------------------------------------------------------
# API Tests: REST Endpoints
# ---------------------------------------------------------------------------

def test_api_chunk_document_and_fetch_chunks(test_db):
    """Test POST /documents/{id}/chunk, GET /documents/{id}/chunks, and GET /chunks/{chunk_id}."""
    doc = Document(
        document_code=f"DOC-API-{uuid.uuid4().hex[:6].upper()}",
        original_filename="api_test.pdf",
        storage_path="storage/raw/test4.pdf",
        file_size_bytes=6500,
        page_count=2,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        ingestion_method="MANUAL_UPLOAD",
        processing_status="READY_FOR_CHUNKING",
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)

    parsed_dir = Path(settings.parsed_storage_dir) / str(doc.id)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    doc_data = create_mock_structured_doc(doc.id, include_ocr=False, include_table=True)
    with open(parsed_dir / "document.json", "w", encoding="utf-8") as f:
        json.dump(doc_data, f)

    # 1. Trigger chunking via POST
    resp_post = client.post(f"/api/v1/documents/{doc.id}/chunk")
    assert resp_post.status_code == 200
    post_json = resp_post.json()
    assert post_json["status"] == "READY_FOR_EXTRACTION"
    assert post_json["chunk_count"] > 0

    # 2. Fetch chunk list via GET
    resp_list = client.get(f"/api/v1/documents/{doc.id}/chunks")
    assert resp_list.status_code == 200
    list_json = resp_list.json()
    assert list_json["total_chunks"] == post_json["chunk_count"]
    assert len(list_json["chunks"]) == post_json["chunk_count"]

    first_chunk = list_json["chunks"][0]
    chunk_id_str = first_chunk["chunk_id_str"]
    chunk_uuid = first_chunk["id"]

    # 3. Fetch single chunk detail via UUID
    resp_detail_uuid = client.get(f"/api/v1/chunks/{chunk_uuid}")
    assert resp_detail_uuid.status_code == 200
    detail_json_uuid = resp_detail_uuid.json()
    assert detail_json_uuid["chunk_id_str"] == chunk_id_str
    assert detail_json_uuid["text"] is not None

    # 4. Fetch single chunk detail via string identifier
    resp_detail_str = client.get(f"/api/v1/chunks/{chunk_id_str}")
    assert resp_detail_str.status_code == 200
    detail_json_str = resp_detail_str.json()
    assert detail_json_str["id"] == chunk_uuid
    assert detail_json_str["text"] is not None


def test_api_chunk_document_not_found():
    """Test 404 response on non-existent document or chunk."""
    random_doc_id = uuid.uuid4()
    resp = client.post(f"/api/v1/documents/{random_doc_id}/chunk")
    assert resp.status_code == 404

    resp2 = client.get(f"/api/v1/documents/{random_doc_id}/chunks")
    assert resp2.status_code == 404

    resp3 = client.get(f"/api/v1/chunks/NON_EXISTENT_CHUNK_ID")
    assert resp3.status_code == 404
