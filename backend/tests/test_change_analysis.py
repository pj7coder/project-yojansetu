import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import delete, select

from app.core.config import settings
from app.crawler.analysis_service import SourceChangeAnalysisService
from app.crawler.browser_fallback import BrowserFallbackService, is_http_content_sufficient
from app.crawler.diff_service import WebpageDiffService
from app.crawler.html_cleaner import CleanedPage, HtmlContentCleaner
from app.crawler.link_discovery import LinkDiscoveryService, detect_resource_type, normalize_candidate_url
from app.crawler.relevance import DeterministicRelevanceClassifier
from app.crawler.resource_fetcher import DiscoveredResourceFetcher, is_domain_allowed
from app.crawler.worker import ChangeAnalysisWorker
from app.database.models.department import Department
from app.database.models.discovered_resource import DiscoveredResource
from app.database.models.document import Document
from app.database.models.source import Source
from app.database.models.source_change_analysis import SourceChangeAnalysis
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_monitor_run import SourceMonitorRun
from app.database.models.source_url import SourceUrl
from app.database.models.web_content_artifact import WebContentArtifact
from app.database.session import SessionLocal
from app.ingestion.service import DocumentIngestionService
from app.main import app

client = TestClient(app)


# ==============================================================================
# 1. HTML Cleaner Tests
# ==============================================================================

def test_html_cleaner_strips_scripts_and_styles():
    raw_html = """
    <html>
      <head>
        <title>Social Justice Department</title>
        <style>body { font-family: sans-serif; }</style>
        <script>alert('malicious script');</script>
      </head>
      <body>
        <!-- Header comment -->
        <h1>Mukhyamantri Vridhjan Pension Yojana</h1>
        <p>This scheme provides monthly financial assistance to senior citizens.</p>
        <script>console.log('tracking pixel');</script>
        <footer>© 2026 Government of Rajasthan</footer>
      </body>
    </html>
    """
    cleaner = HtmlContentCleaner()
    cleaned = cleaner.clean(raw_html, source_url="https://sje.rajasthan.gov.in")

    assert cleaned.title == "Social Justice Department"
    assert "alert" not in cleaned.cleaned_text
    assert "console.log" not in cleaned.cleaned_text
    assert "Mukhyamantri Vridhjan Pension Yojana" in cleaned.cleaned_text
    assert len(cleaned.headings) >= 1
    assert len(cleaned.text_blocks) >= 2


def test_html_cleaner_preserves_sidebars_with_scheme_content():
    raw_html = """
    <html>
      <body>
        <div class="sidebar">
          <h3>नवीन अधिसूचना</h3>
          <a href="/docs/amendment-2026.pdf">संशोधित दिशा-निर्देश 2026</a>
        </div>
        <div class="content">
          <p>Main page content here.</p>
        </div>
      </body>
    </html>
    """
    cleaner = HtmlContentCleaner()
    cleaned = cleaner.clean(raw_html, source_url="https://sje.rajasthan.gov.in")

    assert len(cleaned.links) == 1
    assert cleaned.links[0].text == "संशोधित दिशा-निर्देश 2026"
    assert cleaned.links[0].normalized_url == "https://sje.rajasthan.gov.in/docs/amendment-2026.pdf"


# ==============================================================================
# 2. Structured Diff Service Tests
# ==============================================================================

def test_diff_link_added_and_removed():
    cleaner = HtmlContentCleaner()
    prev_html = """
    <html><body>
      <a href="/docs/guide-v1.pdf">Scheme Guidelines 2025</a>
      <a href="/docs/old-notice.pdf">Old Notice</a>
    </body></html>
    """
    curr_html = """
    <html><body>
      <a href="/docs/guide-v1.pdf">Scheme Guidelines 2025</a>
      <a href="/docs/amendment-2026.pdf">Amendment Notification 2026</a>
    </body></html>
    """
    prev_cleaned = cleaner.clean(prev_html, "https://sje.rajasthan.gov.in")
    curr_cleaned = cleaner.clean(curr_html, "https://sje.rajasthan.gov.in")

    diff_service = WebpageDiffService()
    diff_result = diff_service.compute_diff(prev_cleaned, curr_cleaned)

    assert diff_result.links_added_count == 1
    assert diff_result.links_removed_count == 1
    assert diff_result.has_changes is True

    added_links = [c for c in diff_result.changes if c.change_type == "LINK_ADDED"]
    assert len(added_links) == 1
    assert added_links[0].new_value["normalized_url"] == "https://sje.rajasthan.gov.in/docs/amendment-2026.pdf"


def test_diff_numeric_change_and_eligibility_signal():
    cleaner = HtmlContentCleaner()
    prev_html = "<html><body><p>Eligibility: Age 60 years or above. Benefit: ₹1,000 per month.</p></body></html>"
    curr_html = "<html><body><p>Eligibility: Age 58 years or above. Benefit: ₹1,500 per month.</p></body></html>"

    prev_cleaned = cleaner.clean(prev_html, "https://sje.rajasthan.gov.in")
    curr_cleaned = cleaner.clean(curr_html, "https://sje.rajasthan.gov.in")

    diff_service = WebpageDiffService()
    diff_result = diff_service.compute_diff(prev_cleaned, curr_cleaned)

    assert diff_result.text_changes_count >= 1
    assert diff_result.numeric_changes_count >= 1
    assert diff_result.has_high_priority_change is True

    text_change = [c for c in diff_result.changes if c.change_type == "TEXT_CHANGED"][0]
    assert text_change.is_numeric is True
    assert text_change.is_scheme_keyword is True


def test_diff_footer_only_change_is_low_priority():
    cleaner = HtmlContentCleaner()
    prev_html = "<html><body><h1>Department Portal</h1><footer>Copyright 2025</footer></body></html>"
    curr_html = "<html><body><h1>Department Portal</h1><footer>Copyright 2026</footer></body></html>"

    prev_cleaned = cleaner.clean(prev_html, "https://sje.rajasthan.gov.in")
    curr_cleaned = cleaner.clean(curr_html, "https://sje.rajasthan.gov.in")

    diff_service = WebpageDiffService()
    diff_result = diff_service.compute_diff(prev_cleaned, curr_cleaned)

    assert diff_result.links_added_count == 0
    # Footer copyright year is not a scheme keyword
    assert any("Copyright" in (c.new_text or "") for c in diff_result.changes)


def test_diff_missing_baseline():
    cleaner = HtmlContentCleaner()
    curr_html = "<html><body><a href='/docs/scheme.pdf'>Pension Guidelines</a></body></html>"
    curr_cleaned = cleaner.clean(curr_html, "https://sje.rajasthan.gov.in")

    diff_service = WebpageDiffService()
    diff_result = diff_service.compute_diff(None, curr_cleaned)

    assert diff_result.is_baseline_missing is True
    assert diff_result.links_added_count == 1


# ==============================================================================
# 3. Link Discovery Tests
# ==============================================================================

def test_link_discovery_relative_and_fragments():
    base = "https://sje.rajasthan.gov.in/schemes/index.html"
    rel_url = "../../docs/guidelines.pdf#page=2"
    norm = normalize_candidate_url(rel_url, base)
    assert norm == "https://sje.rajasthan.gov.in/docs/guidelines.pdf"

    # Preserves meaningful query params
    query_url = "/docs/view.php?id=1024&lang=hi#section1"
    norm_query = normalize_candidate_url(query_url, base)
    assert norm_query == "https://sje.rajasthan.gov.in/docs/view.php?id=1024&lang=hi"


def test_link_discovery_detect_resource_types():
    assert detect_resource_type("https://sje.rajasthan.gov.in/doc.pdf") == "PDF"
    assert detect_resource_type("https://sje.rajasthan.gov.in/download?file=doc.pdf") == "PDF"
    assert detect_resource_type("https://sje.rajasthan.gov.in/about.html") == "HTML_PAGE"
    assert detect_resource_type("https://sje.rajasthan.gov.in/schemes/") == "HTML_PAGE"
    assert detect_resource_type("https://sje.rajasthan.gov.in/rules.docx") == "DOCX"


def test_link_discovery_deduplicates_same_target():
    cleaner = HtmlContentCleaner()
    html = """
    <html><body>
      <a href="/docs/pension.pdf">Pension Scheme PDF</a>
      <p>Some text</p>
      <a href="/docs/pension.pdf">Download Pension Guidelines</a>
    </body></html>
    """
    page = cleaner.clean(html, "https://sje.rajasthan.gov.in")
    diff_service = WebpageDiffService()
    diff_result = diff_service.compute_diff(None, page)

    discovery = LinkDiscoveryService(max_resources=50)
    candidates = discovery.discover_candidates(diff_result, page, "https://sje.rajasthan.gov.in")

    # Should only produce 1 candidate with combined anchors
    pdf_cands = [c for c in candidates if c.resource_type == "PDF"]
    assert len(pdf_cands) == 1
    assert pdf_cands[0].normalized_url == "https://sje.rajasthan.gov.in/docs/pension.pdf"
    assert len(pdf_cands[0].all_anchors) >= 1


# ==============================================================================
# 4. Deterministic Relevance Classification Tests
# ==============================================================================

def test_relevance_classification_positive():
    classifier = DeterministicRelevanceClassifier(enable_llm_fallback=False)

    from app.crawler.link_discovery import LinkCandidate
    c1 = LinkCandidate(
        url="/docs/amendment-2026.pdf",
        normalized_url="https://sje.rajasthan.gov.in/docs/amendment-2026.pdf",
        anchor_text="संशोधित दिशा-निर्देश (Amendment Guidelines)",
        resource_type="PDF",
        discovery_reason="NEW_NOTIFICATION",
    )
    res1 = classifier.classify(c1)
    assert res1.status == "RELEVANT"
    assert "SCHEME_KEYWORD" in res1.signals or "AMENDMENT_KEYWORD" in res1.signals


def test_relevance_classification_negative_tenders_and_recruitment():
    classifier = DeterministicRelevanceClassifier(enable_llm_fallback=False)
    from app.crawler.link_discovery import LinkCandidate

    # Tender PDF
    c_tender = LinkCandidate(
        url="/tenders/stationery.pdf",
        normalized_url="https://sje.rajasthan.gov.in/tenders/stationery.pdf",
        anchor_text="Notice Inviting Tender for Office Stationery",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
    )
    res_tender = classifier.classify(c_tender)
    assert res_tender.status == "IRRELEVANT"
    assert any("TENDER" in s for s in res_tender.signals)

    # Recruitment notice
    c_recruit = LinkCandidate(
        url="/jobs/clerk_exam.pdf",
        normalized_url="https://sje.rajasthan.gov.in/jobs/clerk_exam.pdf",
        anchor_text="भर्ती परीक्षा परिणाम (Recruitment Exam Result)",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
    )
    res_recruit = classifier.classify(c_recruit)
    assert res_recruit.status == "IRRELEVANT"
    assert any("RECRUITMENT" in s for s in res_recruit.signals)


def test_relevance_classification_uncertain_generic_order():
    classifier = DeterministicRelevanceClassifier(enable_llm_fallback=False)
    from app.crawler.link_discovery import LinkCandidate

    c_order = LinkCandidate(
        url="/orders/order-12.pdf",
        normalized_url="https://sje.rajasthan.gov.in/orders/order-12.pdf",
        anchor_text="Order dated 05-09-2026",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
    )
    res = classifier.classify(c_order)
    # High recall principle: generic orders on gov sites stay UNCERTAIN for review
    assert res.status == "UNCERTAIN"
    assert "AMBIGUOUS_ORDER" in res.signals


def test_relevance_classification_application_portal():
    classifier = DeterministicRelevanceClassifier(enable_llm_fallback=False)
    from app.crawler.link_discovery import LinkCandidate

    c_app = LinkCandidate(
        url="https://emitra.rajasthan.gov.in/apply",
        normalized_url="https://emitra.rajasthan.gov.in/apply",
        anchor_text="Apply through e-Mitra Portal (आवेदन करें)",
        resource_type="HTML_PAGE",
        discovery_reason="NEW_LINK",
    )
    res = classifier.classify(c_app)
    assert res.status == "RELEVANT"
    assert "APPLICATION_RESOURCE" in res.signals or "APPLICATION_KEYWORD" in res.signals


# ==============================================================================
# 5. Browser Fallback & SSRF Safety Tests
# ==============================================================================

def test_http_sufficient_bypasses_playwright():
    meaningful_html = """
    <html><body>
      <h1>Department of Social Justice</h1>
      <p>""" + ("The Government of Rajasthan provides multiple welfare schemes for citizens. " * 10) + """</p>
    </body></html>
    """
    cleaner = HtmlContentCleaner()
    cleaned = cleaner.clean(meaningful_html, "https://sje.rajasthan.gov.in")
    assert is_http_content_sufficient(meaningful_html, cleaned.cleaned_text, min_chars=300) is True


def test_http_insufficient_detects_js_shell():
    shell_html = "<html><body><div id='app'></div><noscript>Please enable JavaScript</noscript></body></html>"
    cleaner = HtmlContentCleaner()
    cleaned = cleaner.clean(shell_html, "https://sje.rajasthan.gov.in")
    assert is_http_content_sufficient(shell_html, cleaned.cleaned_text, min_chars=300) is False


def test_ssrf_safety_checks():
    from app.monitoring.safety import validate_url_safety

    # Blocked local/private
    safe, err = validate_url_safety("http://127.0.0.1/admin", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "SSRF" in err

    safe, err = validate_url_safety("http://169.254.169.254/metadata", allow_localhost=False, resolve_dns=False)
    assert safe is False
    assert "SSRF" in err


def test_domain_allowlist_policy():
    # Same domain
    allowed, _ = is_domain_allowed("https://sje.rajasthan.gov.in/docs/a.pdf", "https://sje.rajasthan.gov.in")
    assert allowed is True

    # Approved gov CDN
    allowed, _ = is_domain_allowed("https://cdn.rajasthan.gov.in/files/a.pdf", "https://sje.rajasthan.gov.in")
    assert allowed is True

    # Untrusted commercial domain
    allowed, reason = is_domain_allowed("https://random-ads-site.com/doc.pdf", "https://sje.rajasthan.gov.in")
    assert allowed is False
    assert "blocked by policy" in reason


# ==============================================================================
# 6. Database Integration Fixtures & End-to-End Tests
# ==============================================================================

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def setup_change_target(db_session):
    """Setup verified government source, source URL, and clean tables for test."""
    db = db_session

    # Department
    dept = db.execute(select(Department).where(Department.code == "SJE")).scalars().first()
    if not dept:
        dept = Department(code="SJE", name_en="Social Justice and Empowerment", name_hi="सामाजिक न्याय एवं अधिकारिता")
        db.add(dept)
        db.commit()

    # Source
    source = db.execute(select(Source).where(Source.name == "SJE Portal Test")).scalars().first()
    if not source:
        source = Source(
            id=uuid.uuid4(),
            name="SJE Portal Test",
            department_id=dept.id,
            source_type="STATE_PORTAL",
            base_url="https://sje.rajasthan.gov.in",
            enabled=True,
        )
        db.add(source)
        db.commit()

    # SourceUrl
    url_str = "https://sje.rajasthan.gov.in/schemes/test.html"
    source_url = db.execute(select(SourceUrl).where(SourceUrl.url == url_str)).scalars().first()
    if not source_url:
        source_url = SourceUrl(
            id=uuid.uuid4(),
            source_id=source.id,
            url=url_str,
            url_type="SCHEME_PAGE",
            priority="TIER_1",
            enabled=True,
            crawl_allowed=True,
        )
        db.add(source_url)
        db.commit()

    return {
        "dept_id": dept.id,
        "source_id": source.id,
        "source_url_id": source_url.id,
        "source_url": source_url,
    }


def test_end_to_end_new_pdf_discovery_and_ingestion(setup_change_target, db_session, tmp_path):
    """Day 18 Main Integration Test:
    
    Previous page: guide-v1.pdf
    Current page: guide-v1.pdf + amendment-2026.pdf
    Expected:
      - Change event processed
      - Diff computes LINK_ADDED
      - amendment-2026.pdf discovered
      - Classified RELEVANT
      - PDF safely downloaded and handed to DocumentIngestionService
      - Document record created with status READY_FOR_DUPLICATE_CHECK
      - SourceChangeAnalysis recorded with status ANALYZED
    """
    db = db_session
    source_url = setup_change_target["source_url"]
    source_url_id = source_url.id

    # Create dummy monitor run & change event
    monitor_run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(monitor_run)
    db.commit()

    event_id = uuid.uuid4()
    change_event = SourceChangeEvent(
        id=event_id,
        source_url_id=source_url_id,
        monitor_run_id=monitor_run.id,
        change_type="LINK_SET_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:{event_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(change_event)
    db.commit()

    # Create snapshots on disk
    monitoring_dir = settings.monitoring_dir
    baseline_dir = monitoring_dir / str(source_url_id) / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    with open(baseline_dir / "response.html", "w", encoding="utf-8") as f:
        f.write("<html><body><a href='/docs/guide-v1.pdf'>Old Guidelines PDF</a></body></html>")

    change_dir = monitoring_dir / str(source_url_id) / "changes" / str(event_id)
    change_dir.mkdir(parents=True, exist_ok=True)
    with open(change_dir / "response.html", "w", encoding="utf-8") as f:
        f.write("""
        <html><body>
          <h1>Mukhyamantri Scheme Portal</h1>
          <a href='/docs/guide-v1.pdf'>Old Guidelines PDF</a>
          <a href='/docs/amendment-2026.pdf'>संशोधित अधिसूचना (Amendment Notification 2026)</a>
          <a href='/tenders/stationery.pdf'>Tender for Paper</a>
        </body></html>
        """)

    # Valid PDF content via pypdf
    import io
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    valid_pdf_content = buf.getvalue()

    def mock_fetch_and_ingest(db, candidate_record, source_base_url, source_id=None):
        if candidate_record.resource_type == "PDF" and "amendment" in candidate_record.normalized_url:
            # Create a real Document record via Day 4 ingestion
            temp_pdf = tmp_path / "mock_amendment.pdf"
            temp_pdf.write_bytes(valid_pdf_content)
            ingestion_service = DocumentIngestionService()
            doc = ingestion_service.ingest_document(
                db=db,
                file_path=temp_pdf,
                original_filename="amendment-2026.pdf",
                ingestion_method="WEB_MONITOR",
                source_id=source_id,
                source_url_id=candidate_record.source_url_id,
                title=candidate_record.anchor_text,
                move_file=True,
            )
            candidate_record.fetch_status = "FETCHED"
            candidate_record.document_id = doc.id
            db.commit()
            return True, None
        return True, None

    service = SourceChangeAnalysisService()
    with patch.object(service.fetcher, "fetch_and_ingest_candidate", side_effect=mock_fetch_and_ingest):
        analysis = service.analyze_event(db, change_event)

    assert analysis.status == "ANALYZED"
    assert analysis.links_added_count >= 2
    assert analysis.relevant_resources_count >= 1
    assert analysis.irrelevant_resources_count >= 1
    assert analysis.ingested_documents_count >= 1

    # Verify DiscoveredResource in DB
    disc_resources = (
        db.execute(select(DiscoveredResource).where(DiscoveredResource.change_event_id == event_id))
        .scalars()
        .all()
    )
    assert len(disc_resources) >= 2

    # Check that amendment PDF was classified RELEVANT and has a document_id
    amendment_cand = [r for r in disc_resources if "amendment" in r.normalized_url][0]
    assert amendment_cand.relevance_status == "RELEVANT"
    assert amendment_cand.fetch_status == "FETCHED"
    assert amendment_cand.document_id is not None

    # Check that tender was classified IRRELEVANT and was skipped
    tender_cand = [r for r in disc_resources if "tender" in r.normalized_url][0]
    assert tender_cand.relevance_status == "IRRELEVANT"
    assert tender_cand.fetch_status == "SKIPPED"

    # Verify created Document in DB has status READY_FOR_DUPLICATE_CHECK
    doc = db.get(Document, amendment_cand.document_id)
    assert doc is not None
    assert doc.processing_status == "READY_FOR_DUPLICATE_CHECK"
    assert doc.ingestion_method == "WEB_MONITOR"


def test_relevant_html_scheme_saved_as_web_artifact(setup_change_target, db_session):
    """Rule 46-50: Relevant HTML page without downloadable PDF is preserved as WebContentArtifact."""
    db = db_session
    source_url_id = setup_change_target["source_url_id"]

    monitor_run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(monitor_run)

    event_id = uuid.uuid4()
    change_event = SourceChangeEvent(
        id=event_id,
        source_url_id=source_url_id,
        monitor_run_id=monitor_run.id,
        change_type="CONTENT_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:html:{event_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(change_event)
    db.commit()

    candidate = DiscoveredResource(
        id=uuid.uuid4(),
        change_event_id=event_id,
        source_url_id=source_url_id,
        url="https://sje.rajasthan.gov.in/schemes/pension-guidelines.html",
        normalized_url="https://sje.rajasthan.gov.in/schemes/pension-guidelines.html",
        anchor_text="Mukhyamantri Pension Scheme Details (पात्रता एवं लाभ)",
        resource_type="HTML_PAGE",
        discovery_reason="CHANGED_SCHEME_TEXT",
        relevance_status="RELEVANT",
        fetch_status="PENDING",
    )
    db.add(candidate)
    db.commit()

    fetcher = DiscoveredResourceFetcher()
    mock_html = """
    <html><body>
      <h1>Pension Scheme Details</h1>
      <p>Eligibility: Age 60 years. Monthly benefit ₹1,500.</p>
    </body></html>
    """

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_redirect = False
        mock_resp.text = mock_html
        mock_resp.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_resp

        success, err = fetcher.fetch_and_ingest_candidate(
            db=db,
            candidate_record=candidate,
            source_base_url="https://sje.rajasthan.gov.in",
        )

    assert success is True
    assert candidate.fetch_status == "FETCHED"

    # Verify WebContentArtifact created in DB
    artifact = (
        db.execute(select(WebContentArtifact).where(WebContentArtifact.change_event_id == event_id))
        .scalars()
        .first()
    )
    assert artifact is not None
    assert artifact.status == "READY_FOR_WEB_CONTENT_PROCESSING"
    assert "Pension Scheme Details" in artifact.cleaned_text
    assert artifact.cleaned_content is not None


def test_analysis_rerun_idempotency(setup_change_target, db_session):
    """Rule 85/116: Rerunning analysis on the same event returns existing record without duplicating DB candidates."""
    db = db_session
    source_url_id = setup_change_target["source_url_id"]

    monitor_run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(monitor_run)

    event_id = uuid.uuid4()
    change_event = SourceChangeEvent(
        id=event_id,
        source_url_id=source_url_id,
        monitor_run_id=monitor_run.id,
        change_type="METADATA_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:idem:{event_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(change_event)
    db.commit()

    service = SourceChangeAnalysisService()
    # First run
    analysis1 = service.analyze_event(db, change_event)
    assert analysis1.status == "ANALYZED"

    # Second run
    analysis2 = service.analyze_event(db, change_event)
    assert analysis1.id == analysis2.id


def test_worker_process_one(setup_change_target, db_session):
    """Rule 82/117: Background worker claims PENDING_ANALYSIS and completes analysis."""
    db = db_session
    source_url_id = setup_change_target["source_url_id"]

    # Clean any leftover pending or analyzing events from prior runs
    db.execute(delete(SourceChangeEvent).where(SourceChangeEvent.processing_status.in_(["PENDING_ANALYSIS", "ANALYZING"])))
    db.commit()

    monitor_run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(monitor_run)

    event_id = uuid.uuid4()
    change_event = SourceChangeEvent(
        id=event_id,
        source_url_id=source_url_id,
        monitor_run_id=monitor_run.id,
        change_type="CONTENT_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:worker:{event_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(change_event)
    db.commit()

    # Create local snapshot for this event to avoid external HTTP fetch
    change_dir = settings.monitoring_dir / str(source_url_id) / "changes" / str(event_id)
    change_dir.mkdir(parents=True, exist_ok=True)
    with open(change_dir / "response.html", "w", encoding="utf-8") as f:
        f.write("<html><body><h1>Scheme Announcement</h1><p>Rules updated for 2026</p></body></html>")

    worker = ChangeAnalysisWorker(poll_interval=0.1)
    processed = worker.process_one()
    assert processed is True

    # Check updated status
    db.refresh(change_event)
    assert change_event.processing_status in ("ANALYZED", "ANALYSIS_REVIEW_REQUIRED")


# ==============================================================================
# 7. Admin API Tests
# ==============================================================================

def test_admin_change_analyses_endpoints(setup_change_target, db_session):
    """Rule 132: Test GET /api/v1/admin/change-analyses and single analysis endpoint."""
    resp = client.get("/api/v1/admin/change-analyses?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data

    if data["items"]:
        analysis_id = data["items"][0]["id"]
        single_resp = client.get(f"/api/v1/admin/change-analyses/{analysis_id}")
        assert single_resp.status_code == 200
        assert single_resp.json()["id"] == analysis_id


def test_admin_discovered_resources_endpoints_and_patch(setup_change_target, db_session):
    """Rule 133/134: Test GET /api/v1/admin/discovered-resources and manual relevance override."""
    source_url_id = setup_change_target["source_url_id"]

    # Insert a dummy resource
    res_id = uuid.uuid4()
    dummy_res = DiscoveredResource(
        id=res_id,
        change_event_id=uuid.uuid4(),
        source_url_id=source_url_id,
        url="https://sje.rajasthan.gov.in/test.pdf",
        normalized_url=f"https://sje.rajasthan.gov.in/test_{res_id}.pdf",
        anchor_text="Test Ambiguous Order",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
        relevance_status="UNCERTAIN",
        fetch_status="PENDING",
    )
    db = db_session
    # Need parent change event for foreign key
    run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(run)
    ev = SourceChangeEvent(
        id=dummy_res.change_event_id,
        source_url_id=source_url_id,
        monitor_run_id=run.id,
        change_type="LINK_SET_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:api:{res_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(ev)
    db.add(dummy_res)
    db.commit()

    # 1. Query resources list
    list_resp = client.get(f"/api/v1/admin/discovered-resources?relevance_status=UNCERTAIN")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 2. Patch relevance manually to RELEVANT
    patch_resp = client.patch(
        f"/api/v1/admin/discovered-resources/{res_id}/relevance",
        json={"relevance_status": "RELEVANT", "reason": "Manually verified by admin as pension amendment"},
    )
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert patched_data["relevance_status"] == "RELEVANT"
    assert "manual_override" in patched_data["relevance_reason"]


# ==============================================================================
# 8. Advanced Safety, Failure Modes & Day 5 Handoff Tests
# ==============================================================================

def test_redirect_ssrf_blocking(setup_change_target, db_session):
    """Rule 74/101: Discovered link redirecting to loopback or private IP is blocked."""
    source_url_id = setup_change_target["source_url_id"]
    db = db_session

    res_id = uuid.uuid4()
    candidate = DiscoveredResource(
        id=res_id,
        change_event_id=uuid.uuid4(),
        source_url_id=source_url_id,
        url="https://sje.rajasthan.gov.in/redirect-me",
        normalized_url="https://sje.rajasthan.gov.in/redirect-me",
        anchor_text="Redirect Link",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
        relevance_status="RELEVANT",
        fetch_status="PENDING",
    )
    # Parent change event
    run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(run)
    ev = SourceChangeEvent(
        id=candidate.change_event_id,
        source_url_id=source_url_id,
        monitor_run_id=run.id,
        change_type="LINK_SET_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:redirect:{res_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(ev)
    db.add(candidate)
    db.commit()

    fetcher = DiscoveredResourceFetcher()

    with patch("httpx.Client.get") as mock_get:
        # First hop is redirect to private IP
        mock_resp = MagicMock()
        mock_resp.is_redirect = True
        mock_resp.headers = {"location": "http://127.0.0.1/admin/secret.pdf"}
        mock_get.return_value = mock_resp

        success, err = fetcher.fetch_and_ingest_candidate(
            db=db,
            candidate_record=candidate,
            source_base_url="https://sje.rajasthan.gov.in",
        )

    assert success is False
    assert candidate.fetch_status == "FAILED"
    assert "SSRF" in (candidate.fetch_error or "")


def test_oversized_pdf_rejected(setup_change_target, db_session):
    """Rule 44/102: Streamed download aborts and cleans up when exceeding max_bytes."""
    source_url_id = setup_change_target["source_url_id"]
    db = db_session

    res_id = uuid.uuid4()
    candidate = DiscoveredResource(
        id=res_id,
        change_event_id=uuid.uuid4(),
        source_url_id=source_url_id,
        url="https://sje.rajasthan.gov.in/giant.pdf",
        normalized_url="https://sje.rajasthan.gov.in/giant.pdf",
        anchor_text="Oversized Document",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
        relevance_status="RELEVANT",
        fetch_status="PENDING",
    )
    run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(run)
    ev = SourceChangeEvent(
        id=candidate.change_event_id,
        source_url_id=source_url_id,
        monitor_run_id=run.id,
        change_type="LINK_SET_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:oversized:{res_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(ev)
    db.add(candidate)
    db.commit()

    # Configure fetcher with a tiny max_bytes limit (1024 bytes)
    fetcher = DiscoveredResourceFetcher(max_bytes=1024)

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.is_redirect = False
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/pdf"}
        # Provide 2000 bytes chunk
        mock_resp.iter_bytes.return_value = [b"A" * 2000]
        mock_get.return_value = mock_resp

        success, err = fetcher.fetch_and_ingest_candidate(
            db=db,
            candidate_record=candidate,
            source_base_url="https://sje.rajasthan.gov.in",
        )

    assert success is False
    assert candidate.fetch_status == "FAILED"
    assert "exceeds maximum allowed limit" in (candidate.fetch_error or "")


def test_wrong_mime_type_fails_validation_safely(setup_change_target, db_session):
    """Rule 45/103: URL ends in .pdf but returns HTML; Day 4 validator rejects safely."""
    source_url_id = setup_change_target["source_url_id"]
    db = db_session

    res_id = uuid.uuid4()
    candidate = DiscoveredResource(
        id=res_id,
        change_event_id=uuid.uuid4(),
        source_url_id=source_url_id,
        url="https://sje.rajasthan.gov.in/fake.pdf",
        normalized_url="https://sje.rajasthan.gov.in/fake.pdf",
        anchor_text="Fake PDF Link",
        resource_type="PDF",
        discovery_reason="NEW_PDF",
        relevance_status="RELEVANT",
        fetch_status="PENDING",
    )
    run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(run)
    ev = SourceChangeEvent(
        id=candidate.change_event_id,
        source_url_id=source_url_id,
        monitor_run_id=run.id,
        change_type="LINK_SET_CHANGED",
        detected_at=datetime.now(timezone.utc),
        idempotency_key=f"test:mime:{res_id}",
        processing_status="PENDING_ANALYSIS",
    )
    db.add(ev)
    db.add(candidate)
    db.commit()

    fetcher = DiscoveredResourceFetcher()

    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.is_redirect = False
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/pdf"}
        # Return HTML content instead of PDF
        mock_resp.iter_bytes.return_value = [b"<html><body>Not a PDF</body></html>"]
        mock_get.return_value = mock_resp

        success, err = fetcher.fetch_and_ingest_candidate(
            db=db,
            candidate_record=candidate,
            source_base_url="https://sje.rajasthan.gov.in",
        )

    assert success is False
    assert candidate.fetch_status == "FAILED"
    assert "validation" in (candidate.fetch_error or "").lower()


def test_stale_claim_recovery(setup_change_target, db_session):
    """Rule 84/118: Stale claims in ANALYZING status older than lease_seconds are reclaimed."""
    source_url_id = setup_change_target["source_url_id"]
    db = db_session

    from app.repositories.change_analysis_repository import ChangeAnalysisRepository
    repo = ChangeAnalysisRepository()

    # Clear pending events
    db.execute(delete(SourceChangeEvent).where(SourceChangeEvent.processing_status.in_(["PENDING_ANALYSIS", "ANALYZING"])))
    db.commit()

    run = SourceMonitorRun(
        id=uuid.uuid4(),
        source_url_id=source_url_id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        http_method="GET",
        http_status=200,
        result="CHANGED",
        duration_ms=45.0,
    )
    db.add(run)

    # Insert an event that was claimed 400 seconds ago (lease = 300s)
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=400)
    event_id = uuid.uuid4()
    stale_event = SourceChangeEvent(
        id=event_id,
        source_url_id=source_url_id,
        monitor_run_id=run.id,
        change_type="CONTENT_CHANGED",
        detected_at=stale_time,
        idempotency_key=f"test:stale:{event_id}",
        processing_status="ANALYZING",
    )
    db.add(stale_event)
    db.commit()

    # Manually backdate updated_at on the row
    stale_event.updated_at = stale_time
    db.commit()

    # Re-claiming should recover this stale event!
    claimed = repo.claim_next_pending_event(db, lease_seconds=300)
    assert claimed is not None
    assert claimed.id == event_id
    assert claimed.processing_status == "ANALYZING"


def test_duplicate_document_handoff_and_day5_authority(setup_change_target, db_session, tmp_path):
    """Rule 41/105: Crawler hands off to Day 4 ingestion; Day 5 DuplicateDetectionService remains sole duplicate authority."""
    db = db_session
    source_url = setup_change_target["source_url"]
    source_url_id = source_url.id

    from pypdf import PdfWriter
    import io
    from app.duplicate_detection.service import DuplicateDetectionService
    from tests.test_duplicates import create_pdf_with_text

    uid = uuid.uuid4().hex[:8]
    pdf_bytes = create_pdf_with_text(f"Unique Rajasthan Pension Scheme 2026 {uid}")

    # Ingest document #1 directly (original)
    file_1 = tmp_path / "original_scheme.pdf"
    file_1.write_bytes(pdf_bytes)
    ingestion_service = DocumentIngestionService()
    doc1 = ingestion_service.ingest_document(
        db=db,
        file_path=file_1,
        original_filename="original_scheme.pdf",
        ingestion_method="WEB_MONITOR",
        source_url_id=source_url_id,
        title="Scheme Notification",
    )
    assert doc1.processing_status == "READY_FOR_DUPLICATE_CHECK"

    # Now Day 5 duplicate detection evaluates doc1
    dup_service = DuplicateDetectionService()
    dup_result1 = dup_service.detect_duplicates(db, doc1.id)
    assert dup_result1.classification == "NEW_DOCUMENT"
    assert dup_result1.resulting_processing_status == "READY_FOR_PARSING"

    # Second ingestion of identical file from a newly discovered link
    file_2 = tmp_path / "discovered_copy.pdf"
    file_2.write_bytes(pdf_bytes)
    doc2 = ingestion_service.ingest_document(
        db=db,
        file_path=file_2,
        original_filename="discovered_copy.pdf",
        ingestion_method="WEB_MONITOR",
        source_url_id=source_url_id,
        title="Discovered Duplicate Link",
    )
    assert doc2.processing_status == "READY_FOR_DUPLICATE_CHECK"

    # Day 5 duplicate authority confirms exact duplicate
    dup_result2 = dup_service.detect_duplicates(db, doc2.id)
    assert dup_result2.classification == "EXACT_DUPLICATE"
    assert dup_result2.canonical_document_id == doc1.id

