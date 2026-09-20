import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch
import uuid
from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.database.models.department import Department
from app.database.models.source import Source
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_monitor_run import SourceMonitorRun
from app.database.models.source_monitor_state import SourceMonitorState
from app.database.models.source_url import SourceUrl
from app.database.session import SessionLocal
from app.main import app
from app.monitoring.fingerprint import (
    compute_body_fingerprint,
    compute_feed_fingerprint,
    compute_link_fingerprint,
    compute_sitemap_fingerprint,
    extract_and_normalize_links,
    normalize_html_body,
    normalize_link_url,
)
from app.monitoring.http_client import HttpResponseResult, MonitoringHttpClient
from app.monitoring.robots import RobotsPolicyService
from app.monitoring.safety import is_ip_blocked, validate_url_safety
from app.monitoring.scheduler import MonitoringScheduler
from app.monitoring.service import SourceMonitoringService
from app.monitoring.snapshots import SnapshotManager
from app.repositories.source_monitor_repository import SourceMonitorRepository

client = TestClient(app)


# ==========================================
# 1. URL Safety & SSRF Tests
# ==========================================

def test_url_safety_valid():
    safe, err = validate_url_safety("https://sjd.rajasthan.gov.in/schemes", allow_localhost=False, resolve_dns=False)
    assert safe is True
    assert err is None


def test_url_safety_private_ips():
    # Loopback
    safe, err = validate_url_safety("http://127.0.0.1/admin", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "SSRF protection" in err

    # Private RFC 1918
    safe, err = validate_url_safety("http://192.168.1.1/secret", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "SSRF protection" in err

    # AWS/GCP Metadata link-local
    safe, err = validate_url_safety("http://169.254.169.254/latest/meta-data", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "SSRF protection" in err

    # Hostname localhost
    safe, err = validate_url_safety("http://localhost:8000/api", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "reserved" in err


def test_url_safety_unsupported_schemes():
    safe, err = validate_url_safety("file:///etc/passwd", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "Unsupported URL scheme" in err

    safe, err = validate_url_safety("ftp://ftp.rajasthan.gov.in/pub", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "Unsupported URL scheme" in err


def test_url_safety_excessive_length():
    long_url = "https://rajasthan.gov.in/" + ("a" * 2100)
    safe, err = validate_url_safety(long_url, allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "exceeds maximum allowed length" in err


# ==========================================
# 2. Fingerprinting & Link Extraction Tests
# ==========================================

def test_html_normalization_removes_comments_and_whitespace():
    raw_html = """
    <html>
        <!-- Unstable server timestamp: 2026-09-06 12:00:00 -->
        <body>
            <h1>  Jan Soochna   Portal  </h1>
            <p>
                Active Schemes
            </p>
        </body>
    </html>
    """
    normalized = normalize_html_body(raw_html)
    assert "Unstable server timestamp" not in normalized
    assert "<h1> Jan Soochna Portal </h1>" in normalized
    assert "<p>" in normalized


def test_link_normalization_relative_urls():
    base = "https://sjd.rajasthan.gov.in/schemes/index.html"
    rel_href = "../downloads/pension_circular_2026.pdf"
    normalized = normalize_link_url(rel_href, base)
    assert normalized == "https://sjd.rajasthan.gov.in/downloads/pension_circular_2026.pdf"


def test_link_normalization_query_parameters_preserved():
    base = "https://dipr.rajasthan.gov.in"
    url1 = normalize_link_url("/press-releases?id=101&category=welfare", base)
    url2 = normalize_link_url("/press-releases?id=102&category=welfare", base)
    assert url1 != url2
    assert url1 == "https://dipr.rajasthan.gov.in/press-releases?id=101&category=welfare"
    assert url2 == "https://dipr.rajasthan.gov.in/press-releases?id=102&category=welfare"


def test_link_normalization_fragment_stripped():
    base = "https://sjd.rajasthan.gov.in"
    url1 = normalize_link_url("/rules/pension.html#section2", base)
    url2 = normalize_link_url("/rules/pension.html#section5", base)
    assert url1 == url2
    assert url1 == "https://sjd.rajasthan.gov.in/rules/pension.html"


def test_same_length_content_change_detected():
    # Two HTML snippets with exact identical byte length but different text
    html_a = "<div>Application deadline: 31 March 2026. Verified.</div>"
    html_b = "<div>Application deadline: 30 April 2026. Verified.</div>"
    assert len(html_a.encode("utf-8")) == len(html_b.encode("utf-8"))

    fp_a = compute_body_fingerprint(html_a)
    fp_b = compute_body_fingerprint(html_b)
    assert fp_a != fp_b, "Different content must produce distinct body fingerprints despite same byte length"


def test_link_set_fingerprint():
    html_v1 = """
    <html>
        <body>
            <a href="/doc1.pdf">Doc 1</a>
            <a href="/doc2.pdf">Doc 2</a>
        </body>
    </html>
    """
    html_v2 = """
    <html>
        <body>
            <a href="/doc1.pdf">Doc 1</a>
            <a href="/doc2.pdf">Doc 2</a>
            <a href="/doc3.pdf">Doc 3</a>
        </body>
    </html>
    """
    links_v1 = extract_and_normalize_links(html_v1, "https://welfare.rajasthan.gov.in")
    links_v2 = extract_and_normalize_links(html_v2, "https://welfare.rajasthan.gov.in")

    assert len(links_v1) == 2
    assert len(links_v2) == 3

    fp_v1 = compute_link_fingerprint(links_v1)
    fp_v2 = compute_link_fingerprint(links_v2)
    assert fp_v1 != fp_v2


def test_sitemap_fingerprint():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
       <url>
          <loc>https://jansoochna.rajasthan.gov.in/scheme/pension</loc>
          <lastmod>2026-01-01</lastmod>
       </url>
       <url>
          <loc>https://jansoochna.rajasthan.gov.in/scheme/palhar</loc>
          <lastmod>2026-02-01</lastmod>
       </url>
    </urlset>
    """
    fp1, count1 = compute_sitemap_fingerprint(sitemap_xml)
    assert count1 == 2
    assert len(fp1) == 64


def test_feed_fingerprint():
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
       <channel>
          <title>Rajasthan DIPR Notifications</title>
          <item>
             <title>New Pension Guidelines 2026</title>
             <link>https://dipr.rajasthan.gov.in/circular/101</link>
             <pubDate>Mon, 01 Mar 2026 10:00:00 GMT</pubDate>
          </item>
       </channel>
    </rss>
    """
    fp, count = compute_feed_fingerprint(rss_xml)
    assert count == 1
    assert len(fp) == 64


# ==========================================
# 3. Scheduler & Adaptive Interval Tests
# ==========================================

def test_scheduler_priority_intervals():
    scheduler = MonitoringScheduler(jitter_seconds=0)
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    # TIER_1 = 60m
    next_t1 = scheduler.calculate_next_check(priority="TIER_1", result_status="BASELINE_CREATED", from_time=now)
    assert (next_t1 - now).total_seconds() == 60 * 60

    # TIER_2 = 360m (6h)
    next_t2 = scheduler.calculate_next_check(priority="TIER_2", result_status="BASELINE_CREATED", from_time=now)
    assert (next_t2 - now).total_seconds() == 360 * 60

    # TIER_3 = 1440m (24h)
    next_t3 = scheduler.calculate_next_check(priority="TIER_3", result_status="BASELINE_CREATED", from_time=now)
    assert (next_t3 - now).total_seconds() == 1440 * 60


def test_scheduler_adaptive_unchanged_scaling():
    scheduler = MonitoringScheduler(jitter_seconds=0, unchanged_backoff_factor=1.5)
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    # Normal (< 5 unchanged)
    next_normal = scheduler.calculate_next_check(priority="TIER_1", result_status="UNCHANGED", consecutive_unchanged=2, from_time=now)
    assert (next_normal - now).total_seconds() == 60 * 60

    # 5+ unchanged checks -> scales up by 1.5x
    next_scaled_5 = scheduler.calculate_next_check(priority="TIER_1", result_status="UNCHANGED", consecutive_unchanged=5, from_time=now)
    assert (next_scaled_5 - now).total_seconds() == 90 * 60

    # 10+ unchanged checks -> scales up by 1.5^2 = 2.25x
    next_scaled_10 = scheduler.calculate_next_check(priority="TIER_1", result_status="UNCHANGED", consecutive_unchanged=10, from_time=now)
    assert (next_scaled_10 - now).total_seconds() == 135 * 60

    # Detected change resets to base interval (60m)
    next_changed = scheduler.calculate_next_check(priority="TIER_1", result_status="CHANGED", consecutive_unchanged=15, from_time=now)
    assert (next_changed - now).total_seconds() == 60 * 60


def test_scheduler_failure_backoff():
    scheduler = MonitoringScheduler(jitter_seconds=0, failure_backoff_factor=2.0)
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    # 1st failure -> 15m
    next_f1 = scheduler.calculate_next_check(priority="TIER_1", result_status="CHECK_FAILED", consecutive_failures=1, from_time=now)
    assert (next_f1 - now).total_seconds() == 15 * 60

    # 2nd failure -> 30m
    next_f2 = scheduler.calculate_next_check(priority="TIER_1", result_status="CHECK_FAILED", consecutive_failures=2, from_time=now)
    assert (next_f2 - now).total_seconds() == 30 * 60

    # 3rd failure -> 60m
    next_f3 = scheduler.calculate_next_check(priority="TIER_1", result_status="CHECK_FAILED", consecutive_failures=3, from_time=now)
    assert (next_f3 - now).total_seconds() == 60 * 60


def test_scheduler_rate_limit_retry_after():
    scheduler = MonitoringScheduler(jitter_seconds=0)
    now = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

    next_retry = scheduler.calculate_next_check(
        priority="TIER_1",
        result_status="RATE_LIMITED",
        retry_after_seconds=3600,
        from_time=now,
    )
    assert (next_retry - now).total_seconds() == 3600


# ==========================================
# 4. Robots Policy Service Tests
# ==========================================

def test_robots_policy_evaluation():
    robots = RobotsPolicyService(cache_ttl_seconds=3600)
    robots_txt = """
    User-agent: *
    Disallow: /private/
    Disallow: /admin/
    Allow: /schemes/
    """
    robots.set_cached_robots("https://sjd.rajasthan.gov.in", robots_txt)

    allowed, _ = robots.is_allowed("https://sjd.rajasthan.gov.in/schemes/pension.html")
    assert allowed is True

    disallowed, reason = robots.is_allowed("https://sjd.rajasthan.gov.in/private/secret.html")
    assert disallowed is False
    assert "Disallowed by robots.txt" in reason


# ==========================================
# 5. Full End-to-End Monitoring Integration Tests
# ==========================================

@pytest.fixture
def setup_monitoring_target():
    """Ensure an active department, source, and approved source URL exist in DB."""
    db = SessionLocal()
    try:
        dept = db.execute(
            Department.__table__.select().where(Department.code == "SJD-TEST-D17")
        ).first()

        if not dept:
            dept_id = uuid.uuid4()
            db.execute(
                Department.__table__.insert().values(
                    id=dept_id,
                    code="SJD-TEST-D17",
                    name_en="Social Justice Dept (Day 17)",
                    name_hi="सामाजिक न्याय विभाग",
                    description="Social Justice Department for Day 17 monitoring tests",
                    active=True,
                )
            )
            db.commit()
        else:
            dept_id = dept.id

        source = db.execute(
            Source.__table__.select().where(Source.name == "SJD Official Portal Day 17")
        ).first()

        if not source:
            source_id = uuid.uuid4()
            db.execute(
                Source.__table__.insert().values(
                    id=source_id,
                    name="SJD Official Portal Day 17",
                    base_url="https://sjd.rajasthan.gov.in",
                    department_id=dept_id,
                    source_type="DEPARTMENT_WEBSITE",
                    priority="TIER_1",
                    enabled=True,
                )
            )
            db.commit()
        else:
            source_id = source.id

        # Insert approved SourceUrl
        source_url = db.execute(
            SourceUrl.__table__.select().where(
                SourceUrl.url == "https://sjd.rajasthan.gov.in/schemes/announcements.html"
            )
        ).first()

        if not source_url:
            source_url_id = uuid.uuid4()
            db.execute(
                SourceUrl.__table__.insert().values(
                    id=source_url_id,
                    source_id=source_id,
                    url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
                    url_type="SCHEME_PAGE",
                    priority="TIER_1",
                    enabled=True,
                    crawl_allowed=True,
                    strategy="AUTO",
                )
            )
            db.commit()
        else:
            source_url_id = source_url.id

        return {"db": db, "source_id": source_id, "source_url_id": source_url_id}
    finally:
        db.close()


def test_first_check_creates_baseline(setup_monitoring_target):
    """Rule 29/30: First check must classify BASELINE_CREATED, not CHANGED."""
    from sqlalchemy import delete
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    # Ensure completely fresh state for baseline test
    db.execute(delete(SourceChangeEvent).where(SourceChangeEvent.source_url_id == source_url_id))
    db.execute(delete(SourceMonitorRun).where(SourceMonitorRun.source_url_id == source_url_id))
    db.execute(delete(SourceMonitorState).where(SourceMonitorState.source_url_id == source_url_id))
    db.commit()

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=200,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={"etag": '"v1.0"', "content-type": "text/html"},
        content=b"<html><body><h1>Rajasthan Welfare</h1><a href='/pension.pdf'>Pension</a></body></html>",
        text="<html><body><h1>Rajasthan Welfare</h1><a href='/pension.pdf'>Pension</a></body></html>",
        etag='"v1.0"',
        duration_ms=45.0,
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id, force_check=True))

    assert result["status"] == "UNCHANGED"
    assert result["result"] == "BASELINE_CREATED"
    assert result.get("change_event_id") is None

    # Verify state in DB
    state = service.repo.get_state_by_source_url_id(db, source_url_id)
    assert state is not None
    assert state.monitor_status == "UNCHANGED"
    assert state.body_fingerprint is not None
    assert state.link_fingerprint is not None
    assert state.etag == '"v1.0"'
    assert state.consecutive_failures == 0

    db.close()


def test_second_check_unchanged_304(setup_monitoring_target):
    """Rule 15/81: HTTP 304 Not Modified immediately classifies UNCHANGED."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=304,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={},
        content=b"",
        text="",
        etag='"v1.0"',
        duration_ms=15.0,
        is_304=True,
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    assert result["status"] == "UNCHANGED"
    assert result["result"] == "304_NOT_MODIFIED"
    assert result["change_signals"]["is_304"] is True
    assert result.get("change_event_id") is None

    db.close()


def test_third_check_detects_link_set_change(setup_monitoring_target):
    """Rule 24/83: Adding a new link changes link_fingerprint -> emits PENDING_ANALYSIS event."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    new_html = (
        "<html><body><h1>Rajasthan Welfare</h1>"
        "<a href='/pension.pdf'>Pension</a>"
        "<a href='/scholarship_2026.pdf'>New Scholarship 2026</a>"
        "</body></html>"
    )
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=200,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={"etag": '"v2.0"'},
        content=new_html.encode("utf-8"),
        text=new_html,
        etag='"v2.0"',
        duration_ms=50.0,
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    assert result["status"] == "CHANGED"
    assert result["result"] == "CHANGE_DETECTED"
    assert result["change_event_id"] is not None

    # Verify change event in DB
    event = db.get(SourceChangeEvent, result["change_event_id"])
    assert event is not None
    assert event.processing_status == "PENDING_ANALYSIS"
    assert event.source_url_id == source_url_id

    db.close()


def test_repeated_changed_check_idempotency(setup_monitoring_target):
    """Rule 28/94: Repeating check with identical changed content does NOT emit duplicate event."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    same_changed_html = (
        "<html><body><h1>Rajasthan Welfare</h1>"
        "<a href='/pension.pdf'>Pension</a>"
        "<a href='/scholarship_2026.pdf'>New Scholarship 2026</a>"
        "</body></html>"
    )
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=200,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={"etag": '"v2.0"'},
        content=same_changed_html.encode("utf-8"),
        text=same_changed_html,
        etag='"v2.0"',
        duration_ms=30.0,
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    # Identical fingerprints to current state -> UNCHANGED
    assert result["status"] == "UNCHANGED"
    assert result["result"] == "CONTENT_UNCHANGED"
    assert result.get("change_event_id") is None

    db.close()


def test_source_monitoring_disabled_guard(setup_monitoring_target):
    """Rule 113/114: Disabled or crawl_disallowed sources are rejected."""
    db = SessionLocal()
    source_id = setup_monitoring_target["source_id"]

    # Create crawl_allowed=False URL
    url_id = uuid.uuid4()
    db.execute(
        SourceUrl.__table__.insert().values(
            id=url_id,
            source_id=source_id,
            url="https://sjd.rajasthan.gov.in/private/internal_listing",
            url_type="SCHEME_PAGE",
            priority="TIER_1",
            enabled=True,
            crawl_allowed=False,  # Disallowed
            strategy="AUTO",
        )
    )
    db.commit()

    service = SourceMonitoringService()
    result = asyncio.run(service.check_source_url(db, url_id))
    assert result["status"] == "DISABLED"
    assert result["result"] == "CRAWL_DISALLOWED"

    db.close()


def test_source_monitoring_timeout_failure_backoff(setup_monitoring_target):
    """Rule 98/99: Network timeout increments consecutive failures and applies backoff."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=0,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={},
        content=b"",
        text="",
        duration_ms=15000.0,
        error_code="TIMEOUT",
        error_message="HTTP request timed out after 15s",
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    assert result["status"] == "CHECK_FAILED"
    assert result["result"] == "CHECK_FAILED"

    state = service.repo.get_state_by_source_url_id(db, source_url_id)
    assert state.consecutive_failures > 0
    assert state.next_check_at is not None

    db.close()


def test_source_monitoring_429_rate_limit(setup_monitoring_target):
    """Rule 40/100: HTTP 429 respects Retry-After header."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=429,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={"retry-after": "300"},
        content=b"Too Many Requests",
        text="Too Many Requests",
        duration_ms=20.0,
        retry_after=300,
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    assert result["status"] == "TEMPORARILY_UNAVAILABLE"
    assert result["result"] == "RATE_LIMITED"

    db.close()


def test_source_monitoring_403_no_bypass(setup_monitoring_target):
    """Rule 41/101: HTTP 403 recorded as ACCESS_FORBIDDEN without stealth bypass."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=403,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={},
        content=b"Forbidden",
        text="Forbidden",
        duration_ms=25.0,
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    assert result["status"] == "ACCESS_FORBIDDEN"
    assert result["result"] == "ACCESS_FORBIDDEN"

    db.close()



# ==========================================
# 6. API Endpoint Integration Tests
# ==========================================

def test_api_health_summary():
    response = client.get("/api/v1/admin/source-monitoring/health-summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_monitored_sources" in data
    assert "healthy" in data
    assert "never_checked" in data
    assert "pending_change_events" in data


def test_api_list_monitoring():
    response = client.get("/api/v1/admin/source-monitoring?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_api_get_monitoring_detail(setup_monitoring_target):
    source_url_id = str(setup_monitoring_target["source_url_id"])
    response = client.get(f"/api/v1/admin/source-monitoring/{source_url_id}")
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert "recent_runs" in data
    assert data["state"]["source_url_id"] == source_url_id


def test_api_list_change_events():
    response = client.get("/api/v1/admin/source-change-events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_api_manual_check_endpoint(setup_monitoring_target):
    source_url_id = str(setup_monitoring_target["source_url_id"])
    with patch.object(
        SourceMonitoringService, "check_source_url", new_callable=AsyncMock
    ) as mock_check:
        mock_check.return_value = {
            "source_url_id": uuid.UUID(source_url_id),
            "status": "UNCHANGED",
            "result": "304_NOT_MODIFIED",
            "change_signals": {"is_304": True},
            "http_status": 304,
            "duration_ms": 12.0,
            "next_check_at": datetime.now(timezone.utc),
            "message": "Resource unchanged",
        }

        response = client.post(f"/api/v1/admin/sources/{source_url_id}/check")
        assert response.status_code == 200
        data = response.json()
        assert data["source_url_id"] == source_url_id
        assert data["status"] == "UNCHANGED"
        assert data["result"] == "304_NOT_MODIFIED"


# ==========================================
# 7. Additional Resilience & Concurrency Tests
# ==========================================

def test_direct_pdf_hash_monitoring(setup_monitoring_target):
    """Rule 50/51/106: Direct PDF URLs monitor SHA-256 without PDF parsing."""
    from app.monitoring.fingerprint import compute_stream_sha256
    pdf_bytes_v1 = b"%PDF-1.4\n1 0 obj\n<< /Title (Pension Scheme) >>\nendobj\n"
    pdf_bytes_v2 = b"%PDF-1.4\n1 0 obj\n<< /Title (Pension Scheme 2026 Amended) >>\nendobj\n"

    hash_v1, size_v1 = compute_stream_sha256([pdf_bytes_v1])
    hash_v2, size_v2 = compute_stream_sha256([pdf_bytes_v2])

    assert hash_v1 != hash_v2
    assert size_v1 == len(pdf_bytes_v1)
    assert size_v2 == len(pdf_bytes_v2)


def test_oversized_response_abort(setup_monitoring_target):
    """Rule 48/105: Response exceeding byte cap aborts safely without memory exhaustion."""
    db = SessionLocal()
    source_url_id = setup_monitoring_target["source_url_id"]

    mock_http = AsyncMock(spec=MonitoringHttpClient)
    mock_http.execute_staged_check.return_value = HttpResponseResult(
        status_code=200,
        http_method="GET",
        final_url="https://sjd.rajasthan.gov.in/schemes/announcements.html",
        headers={"content-length": "10485760"},
        content=b"",
        text="",
        duration_ms=120.0,
        error_code="RESPONSE_TOO_LARGE",
        error_message="Response exceeded size limit of 5242880 bytes",
    )

    service = SourceMonitoringService(http_client=mock_http)
    result = asyncio.run(service.check_source_url(db, source_url_id))

    assert result["status"] == "CHECK_FAILED"
    assert result["result"] == "RESPONSE_TOO_LARGE"
    db.close()


def test_snapshot_persistence_layout(tmp_path):
    """Rule 72-76: Snapshot storage preserves baseline and change snapshots immutably."""
    mgr = SnapshotManager(base_dir=tmp_path)
    source_url_id = uuid.uuid4()
    event_id = uuid.uuid4()

    # Save baseline
    baseline_saved = mgr.save_baseline_snapshot(
        source_url_id=source_url_id,
        raw_content=b"<html>Baseline Content</html>",
        metadata={"url": "https://gov.in", "status_code": 200},
    )
    assert Path(baseline_saved["content_path"]).exists()
    assert Path(baseline_saved["metadata_path"]).exists()

    # Read back baseline
    loaded_baseline = mgr.get_baseline_snapshot(source_url_id)
    assert loaded_baseline is not None
    assert loaded_baseline["content"] == b"<html>Baseline Content</html>"

    # Save change
    change_saved = mgr.save_change_snapshot(
        source_url_id=source_url_id,
        event_id=event_id,
        raw_content=b"<html>Changed Content</html>",
        metadata={"url": "https://gov.in", "status_code": 200},
    )
    assert Path(change_saved["content_path"]).exists()
    assert str(event_id) in change_saved["content_path"]

    # Verify baseline is unchanged (immutable)
    loaded_baseline_again = mgr.get_baseline_snapshot(source_url_id)
    assert loaded_baseline_again["content"] == b"<html>Baseline Content</html>"


def test_worker_claiming_and_run_once(setup_monitoring_target):
    """Rule 33/115/116: Worker claims due sources via SKIP LOCKED and runs one pass."""
    from app.monitoring.worker import SourceMonitorWorker

    db = SessionLocal()
    repo = SourceMonitorRepository()
    due = repo.get_due_monitoring_sources(db, limit=5, lock=True)
    assert isinstance(due, list)
    db.close()

    # Test worker run_once with mock service
    mock_service = SourceMonitoringService()
    worker = SourceMonitorWorker(service=mock_service, batch_size=2)
    checked = asyncio.run(worker.run_once())
    assert isinstance(checked, int)

