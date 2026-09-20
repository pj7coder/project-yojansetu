import io
import os
import shutil
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.ingestion.service import DocumentIngestionService
from app.ingestion.storage import StorageManager
from app.ingestion.validator import DocumentValidationService
from app.ingestion.watcher import FolderWatcher, IncomingFolderHandler
from app.main import app
from app.repositories.document_repository import DocumentRepository

client = TestClient(app)
settings = get_settings()


def create_minimal_pdf_bytes() -> bytes:
    """Generate a syntactically valid minimal PDF in memory."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def ensure_storage():
    """Ensure storage directories are clean and initialized for tests."""
    settings.ensure_storage_dirs()
    yield


def test_upload_valid_pdf():
    """Verify uploading a valid PDF succeeds and sets READY_FOR_DUPLICATE_CHECK."""
    pdf_bytes = create_minimal_pdf_bytes()
    filename = "मुख्यमंत्री_अनुप्रति_कोचिंग_2026.pdf"

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
        data={"title": "Mukhyamantri Anuprati Coaching Scheme 2026"},
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert "id" in data
    assert data["document_code"].startswith("DOC-")
    assert data["original_filename"] == filename
    assert data["stored_filename"] == "original.pdf"
    assert data["file_extension"] == ".pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["file_size_bytes"] == len(pdf_bytes)
    assert data["ingestion_method"] == "MANUAL_UPLOAD"
    assert data["processing_status"] == "READY_FOR_DUPLICATE_CHECK"
    assert data["sha256"] is not None
    assert len(data["sha256"]) == 64
    assert data["title"] == "Mukhyamantri Anuprati Coaching Scheme 2026"

    # Verify physical file existence in originals storage
    doc_id = data["id"]
    storage_mgr = StorageManager()
    expected_path = storage_mgr.originals_dir / doc_id / "original.pdf"
    assert expected_path.exists()
    assert expected_path.stat().st_size == len(pdf_bytes)


def test_upload_invalid_extension():
    """Verify uploading a file with non-pdf extension is rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("malicious.exe", b"MZ executable code here", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_upload_fake_pdf():
    """Verify uploading a fake file with .pdf extension is rejected with 400 Bad Request."""
    fake_content = b"This is plain text and not a real PDF structure"
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("fake.pdf", fake_content, "application/pdf")},
    )
    assert response.status_code == 400
    assert "Missing '%PDF' signature" in response.json()["detail"]


def test_upload_empty_pdf():
    """Verify uploading a 0-byte PDF is rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "Empty file: document size is 0 bytes" in response.json()["detail"]


def test_upload_oversized_validation():
    """Verify validation service rejects files exceeding the configured limit."""
    validator = DocumentValidationService(max_size_mb=1)  # 1 MB limit
    # Create temp file larger than 1 MB
    temp_path = settings.incoming_dir / "large_test.pdf"
    try:
        with open(temp_path, "wb") as f:
            f.write(b"%PDF-1.4" + b"0" * (1024 * 1024 + 500))
        result = validator.validate(temp_path)
        assert result.valid is False
        assert any("exceeds maximum allowed limit" in err for err in result.errors)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_list_documents_pagination_and_filter():
    """Verify GET /api/v1/documents returns paginated results and supports status filtering."""
    response = client.get("/api/v1/documents?page=1&page_size=10&processing_status=READY_FOR_DUPLICATE_CHECK")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert isinstance(data["items"], list)
    if data["items"]:
        assert data["items"][0]["processing_status"] == "READY_FOR_DUPLICATE_CHECK"


def test_get_document_detail_and_file_download():
    """Verify retrieving document metadata and streaming the actual PDF file."""
    pdf_bytes = create_minimal_pdf_bytes()
    upload_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("download_test.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # 1. Detail endpoint
    detail_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == doc_id
    assert detail_resp.json()["original_filename"] == "download_test.pdf"

    # 2. File download endpoint
    file_resp = client.get(f"/api/v1/documents/{doc_id}/file")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "application/pdf"
    assert file_resp.content == pdf_bytes


def test_path_traversal_sanitization():
    """Verify filenames with path traversal characters are sanitized."""
    storage_mgr = StorageManager()
    sanitized = storage_mgr.sanitize_filename("../../etc/passwd.pdf")
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert sanitized == "passwd.pdf"

    sanitized_win = storage_mgr.sanitize_filename("..\\..\\Windows\\System32\\calc.pdf")
    assert ".." not in sanitized_win
    assert "\\" not in sanitized_win
    assert sanitized_win == "calc.pdf"


def test_folder_watcher_startup_scan():
    """Verify FolderWatcher processes pre-existing incoming files on startup."""
    pdf_bytes = create_minimal_pdf_bytes()
    incoming_file = settings.incoming_dir / "backlog_scheme.pdf"
    with open(incoming_file, "wb") as f:
        f.write(pdf_bytes)

    assert incoming_file.exists()

    watcher = FolderWatcher()
    # Execute startup scan
    processed = watcher.scan_existing_files()
    assert processed >= 1

    # Verify file is no longer in incoming/
    assert not incoming_file.exists()

    # Verify document in DB
    db = SessionLocal()
    repo = DocumentRepository()
    items, total = repo.list(db, ingestion_method="FOLDER_WATCHER")
    assert total >= 1
    found = any(doc.original_filename == "backlog_scheme.pdf" for doc in items)
    assert found
    db.close()


def test_folder_watcher_invalid_file_handling():
    """Verify invalid file in incoming/ is moved to failed/ and recorded as INVALID in DB."""
    incoming_bad = settings.incoming_dir / "corrupted_document.pdf"
    with open(incoming_bad, "wb") as f:
        f.write(b"Not a valid PDF at all")

    handler = IncomingFolderHandler(
        ingestion_service=DocumentIngestionService(),
        stability_interval_sec=0.1,
        max_stability_checks=3,
    )
    handler._handle_candidate_file(incoming_bad)

    # Verify file is removed from incoming
    assert not incoming_bad.exists()

    # Verify moved to failed/
    storage_mgr = StorageManager()
    failed_files = list(storage_mgr.failed_dir.glob("*_corrupted_document.pdf"))
    assert len(failed_files) >= 1

    # Verify database status is INVALID
    db = SessionLocal()
    repo = DocumentRepository()
    items, total = repo.list(db, processing_status="INVALID")
    assert total >= 1
    found = any("corrupted_document.pdf" in (doc.original_filename or "") for doc in items)
    assert found
    db.close()


def test_multiple_files_batch_processing():
    """Verify multiple files dropped in incoming are all processed independently without loss."""
    pdf_bytes = create_minimal_pdf_bytes()
    filenames = ["multi_1.pdf", "multi_2.pdf", "multi_3.pdf"]

    for name in filenames:
        with open(settings.incoming_dir / name, "wb") as f:
            f.write(pdf_bytes)

    watcher = FolderWatcher()
    count = watcher.scan_existing_files()
    assert count >= 3

    # Ensure none remain in incoming
    for name in filenames:
        assert not (settings.incoming_dir / name).exists()

    # Check DB
    db = SessionLocal()
    repo = DocumentRepository()
    items, total = repo.list(db, ingestion_method="FOLDER_WATCHER")
    db_names = {doc.original_filename for doc in items}
    for name in filenames:
        assert name in db_names
    db.close()


def test_watcher_restart_recovery():
    """Verify watcher cleanly discovers and processes files added while watcher was stopped."""
    pdf_bytes = create_minimal_pdf_bytes()
    test_file = settings.incoming_dir / "restart_test_scheme.pdf"

    # Watcher is NOT running; file appears in incoming
    with open(test_file, "wb") as f:
        f.write(pdf_bytes)
    assert test_file.exists()

    # Watcher starts
    watcher = FolderWatcher()
    processed = watcher.scan_existing_files()
    assert processed >= 1
    assert not test_file.exists()

    db = SessionLocal()
    repo = DocumentRepository()
    items, _ = repo.list(db, ingestion_method="FOLDER_WATCHER")
    assert any(doc.original_filename == "restart_test_scheme.pdf" for doc in items)
    db.close()


def test_watcher_live_filesystem_detection():
    """Verify live watchdog filesystem event detection and ingestion."""
    pdf_bytes = create_minimal_pdf_bytes()
    live_file = settings.incoming_dir / "live_watchdog_test.pdf"

    # Use a faster stability check for the test
    fast_handler = IncomingFolderHandler(
        ingestion_service=DocumentIngestionService(),
        stability_interval_sec=0.2,
        max_stability_checks=5,
    )
    watcher = FolderWatcher()
    watcher.event_handler = fast_handler

    watcher.start()
    try:
        # Write file while watcher is running
        with open(live_file, "wb") as f:
            f.write(pdf_bytes)

        # Poll briefly until watcher has processed it
        start_time = time.time()
        ingested = False
        while time.time() - start_time < 5.0:
            if not live_file.exists():
                ingested = True
                break
            time.sleep(0.2)

        assert ingested, "Live watcher did not process the incoming file within timeout"

        # Check DB
        db = SessionLocal()
        repo = DocumentRepository()
        items, _ = repo.list(db, ingestion_method="FOLDER_WATCHER")
        assert any(doc.original_filename == "live_watchdog_test.pdf" for doc in items)
        db.close()
    finally:
        watcher.stop()
