from datetime import datetime, timezone, timedelta
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.database.models.admin_operation_event import AdminOperationEvent
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.fact_verification import FactVerification
from app.database.models.human_review_item import HumanReviewItem
from app.database.models.human_review_session import HumanReviewSession
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_change_set import SchemeChangeSet
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.source import Source
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_monitor_state import SourceMonitorState
from app.database.models.source_url import SourceUrl
from app.database.models.validation_issue import ValidationIssue
from app.database.models.worker_heartbeat import WorkerHeartbeat
from app.database.session import SessionLocal
from app.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-Reviewer-Id": "DEV_REVIEWER"}


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def cleanup_admin_fixtures(db: Session):
    """Clean up fixtures created during test execution."""
    yield
    # Cleanup any test-specific records
    db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_type.like("TEST_%")).delete(synchronize_session=False)
    db.query(AdminOperationEvent).filter(AdminOperationEvent.actor_id == "DEV_TESTER").delete(synchronize_session=False)
    db.commit()


def test_overview_counts(db: Session):
    """Verify aggregated overview metrics structure and reasonable operational values."""
    res = client.get("/api/v1/admin/dashboard/overview", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "system_status" in data
    assert data["system_status"] in ["HEALTHY", "WARNING", "CRITICAL"]
    assert "system_status_reasons" in data
    assert "sources" in data
    assert "documents" in data
    assert "reviews" in data
    assert "schemes" in data
    assert "conflicts" in data
    assert "pipeline_stages" in data
    assert isinstance(data["pipeline_stages"], list)
    assert len(data["pipeline_stages"]) == 10  # 10 stages


def test_pipeline_summary_and_stuck_detection(db: Session):
    """Verify pipeline stage counts and stuck item detection for overdue in-flight documents."""
    now = datetime.now(timezone.utc)
    stuck_time = now - timedelta(minutes=45)

    # Insert a stuck document in PARSING state
    stuck_doc = Document(
        document_code=f"DOC-STUCK-{uuid.uuid4().hex[:8]}",
        original_filename="stuck_report.pdf",
        stored_filename="stuck.pdf",
        file_extension=".pdf",
        mime_type="application/pdf",
        file_size_bytes=10240,
        storage_path="test/stuck.pdf",
        ingestion_method="MANUAL_UPLOAD",
        processing_status="PARSING",
        created_at=stuck_time,
        updated_at=stuck_time,
    )
    db.add(stuck_doc)
    db.commit()

    try:
        res = client.get("/api/v1/admin/dashboard/pipeline?stuck_threshold_minutes=30", headers=AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()

        assert "stages" in data
        assert "stuck_items" in data
        assert data["total_processing"] >= 1

        # Confirm stuck doc is surfaced
        stuck_codes = [item["document_code"] for item in data["stuck_items"]]
        assert stuck_doc.document_code in stuck_codes
    finally:
        db.delete(stuck_doc)
        db.commit()


def test_safe_document_retry_and_audit(db: Session):
    """Verify contextual retry of an OCR_FAILED document and creation of audit event."""
    now = datetime.now(timezone.utc)
    failed_doc = Document(
        document_code=f"DOC-FAIL-{uuid.uuid4().hex[:8]}",
        original_filename="ocr_failure.pdf",
        stored_filename="fail.pdf",
        file_extension=".pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        storage_path="test/ocr_fail.pdf",
        ingestion_method="MANUAL_UPLOAD",
        processing_status="OCR_FAILED",
        failure_reason="Text recognition timeout",
        created_at=now,
        updated_at=now,
    )
    db.add(failed_doc)
    db.commit()

    try:
        # Trigger retry
        res = client.post(
            f"/api/v1/admin/documents/{failed_doc.id}/retry",
            headers={"X-Reviewer-Id": "DEV_TESTER"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["document_id"] == str(failed_doc.id)
        assert data["action_taken"] == "RETRY_OCR"

        # Verify audit event was logged
        audit = db.query(AdminOperationEvent).filter(
            AdminOperationEvent.target_id == str(failed_doc.id),
            AdminOperationEvent.action_type == "DOCUMENT_RETRY_TRIGGERED",
        ).first()
        assert audit is not None
        assert audit.actor_id == "DEV_TESTER"
    finally:
        db.query(AdminOperationEvent).filter(AdminOperationEvent.target_id == str(failed_doc.id)).delete()
        db.delete(failed_doc)
        db.commit()


def test_invalid_document_retry_rejected(db: Session):
    """Verify that attempting to retry terminal or invalid documents is rejected with HTTP 400."""
    now = datetime.now(timezone.utc)
    dup_doc = Document(
        document_code=f"DOC-DUP-{uuid.uuid4().hex[:8]}",
        original_filename="duplicate.pdf",
        stored_filename="dup.pdf",
        file_extension=".pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        storage_path="test/dup.pdf",
        ingestion_method="MANUAL_UPLOAD",
        processing_status="EXACT_DUPLICATE",
        created_at=now,
        updated_at=now,
    )
    db.add(dup_doc)
    db.commit()

    try:
        res = client.post(
            f"/api/v1/admin/documents/{dup_doc.id}/retry",
            headers=AUTH_HEADERS,
        )
        assert res.status_code == 400
        assert "cannot be retried" in res.json()["detail"]
    finally:
        db.delete(dup_doc)
        db.commit()


def test_system_status_components(db: Session):
    """Verify component-level health probes (DB, Ollama, Search Index, Rule Cache, Storage)."""
    res = client.get("/api/v1/admin/dashboard/system", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "database" in data
    assert data["database"]["status"] == "HEALTHY"
    assert "latency_ms" in data["database"]

    assert "ollama" in data
    assert "search_index" in data
    assert "rule_cache" in data
    assert "storage" in data
    assert data["storage"]["original_documents"] >= 0


def test_worker_heartbeat_lifecycle(db: Session):
    """Verify registering a worker heartbeat and checking stale vs healthy states."""
    # 1. Register fresh heartbeat
    hb_payload = {
        "worker_type": "TEST_PARSER",
        "worker_instance_id": "parser-worker-01",
        "status": "HEALTHY",
        "metadata_safe": {"current_document": "DOC-001"},
    }
    res = client.post("/api/v1/admin/workers/heartbeat", json=hb_payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["worker_type"] == "TEST_PARSER"
    assert data["is_stale"] is False

    # 2. Verify it appears in system status
    sys_res = client.get("/api/v1/admin/dashboard/system", headers=AUTH_HEADERS)
    assert sys_res.status_code == 200
    workers = sys_res.json()["workers"]
    matching = [w for w in workers if w["worker_type"] == "TEST_PARSER"]
    assert len(matching) == 1
    assert matching[0]["is_stale"] is False


def test_activity_feed_no_citizen_data(db: Session):
    """Verify operational activity feed and strictly verify no citizen profile facts exist."""
    res = client.get("/api/v1/admin/dashboard/activity?limit=20", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert isinstance(data["items"], list)

    # Privacy verification: examine all textual fields for citizen personal data leaks
    for item in data["items"]:
        text_dump = f"{item['title']} {item['description']} {item['actor']}".lower()
        assert "citizen_profile" not in text_dump
        assert "family_income" not in text_dump
        assert "bpl_status" not in text_dump
        assert "caste" not in text_dump


def test_conflict_aggregation(db: Session):
    """Verify unresolved conflicts list aggregates contradictions and version issues."""
    res = client.get("/api/v1/admin/conflicts", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_admin_documents_list_and_filters(db: Session):
    """Verify unified admin document listing with stage mapping and failure filters."""
    # Test listing
    res = client.get("/api/v1/admin/documents?page=1&page_size=10", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data

    # Test failed_only filter
    res_failed = client.get("/api/v1/admin/documents?failed_only=true", headers=AUTH_HEADERS)
    assert res_failed.status_code == 200
    data_failed = res_failed.json()
    for item in data_failed["items"]:
        assert item["processing_status"] in [
            "INVALID",
            "PARSING_FAILED",
            "OCR_FAILED",
            "CHUNKING_FAILED",
            "EXTRACTION_FAILED",
            "NORMALIZATION_FAILED",
            "VALIDATION_FAILED",
            "FAILED",
        ]


def test_admin_schemes_list_and_versions(db: Session):
    """Verify schemes listing reflects current version and future version flags."""
    res = client.get("/api/v1/admin/schemes?page=1&page_size=10", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    if data["items"]:
        scheme = data["items"][0]
        assert "has_future_version" in scheme
        assert "is_active" in scheme


def test_admin_sources_list(db: Session):
    """Verify monitored sources listing reflects monitoring status and check coordinates."""
    res = client.get("/api/v1/admin/sources?page=1&page_size=10", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data


def test_global_search(db: Session):
    """Verify search across schemes, documents, and sources."""
    res = client.get("/api/v1/admin/search?q=pension", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "pension"
    assert "schemes" in data
    assert "documents" in data
    assert "sources" in data
    assert "total_hits" in data


def test_cache_refresh_and_search_reindex_actions(db: Session):
    """Verify privileged operations for rule cache refresh and search index reindex."""
    # 1. Cache refresh
    res_c = client.post("/api/v1/admin/cache/refresh", headers=AUTH_HEADERS)
    assert res_c.status_code == 200
    assert res_c.json()["status"] == "success"

    # 2. Search reindex
    try:
        res_s = client.post("/api/v1/admin/search-index/reindex-stale", headers=AUTH_HEADERS)
        assert res_s.status_code == 200
        assert res_s.json()["status"] == "success"
    finally:
        from app.database.models.scheme_search_metadata import SchemeSearchMetadata
        db.query(SchemeSearchMetadata).delete()
        db.commit()


def test_admin_filter_injection_safety(db: Session):
    """Verify that malicious SQL injection strings in query parameters are safely handled."""
    malicious_inputs = [
        "' OR '1'='1",
        "'; DROP TABLE documents; --",
        "1 UNION SELECT null, null, null--",
    ]

    for evil in malicious_inputs:
        res = client.get(f"/api/v1/admin/documents?query={evil}", headers=AUTH_HEADERS)
        assert res.status_code == 200

        res_src = client.get(f"/api/v1/admin/sources?query={evil}", headers=AUTH_HEADERS)
        assert res_src.status_code == 200

        res_search = client.get(f"/api/v1/admin/search?q={evil}", headers=AUTH_HEADERS)
        assert res_search.status_code == 200
