import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Optional, Tuple
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crawler.browser_fallback import BrowserFallbackService, is_http_content_sufficient
from app.crawler.diff_service import WebpageDiffResult, WebpageDiffService
from app.crawler.html_cleaner import CleanedPage, HtmlContentCleaner
from app.crawler.link_discovery import LinkDiscoveryService
from app.crawler.relevance import DeterministicRelevanceClassifier
from app.crawler.resource_fetcher import DiscoveredResourceFetcher
from app.database.models.discovered_resource import DiscoveredResource
from app.database.models.source_change_analysis import SourceChangeAnalysis
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_url import SourceUrl
from app.repositories.change_analysis_repository import ChangeAnalysisRepository

logger = logging.getLogger(__name__)


class SourceChangeAnalysisService:
    """Orchestrator for analyzing source change events, computing diffs, discovering links, and ingesting documents."""

    def __init__(
        self,
        html_cleaner: Optional[HtmlContentCleaner] = None,
        diff_service: Optional[WebpageDiffService] = None,
        link_discovery: Optional[LinkDiscoveryService] = None,
        relevance_classifier: Optional[DeterministicRelevanceClassifier] = None,
        resource_fetcher: Optional[DiscoveredResourceFetcher] = None,
        browser_fallback: Optional[BrowserFallbackService] = None,
        repository: Optional[ChangeAnalysisRepository] = None,
    ):
        self.cleaner = html_cleaner or HtmlContentCleaner()
        self.diff_service = diff_service or WebpageDiffService()
        self.discovery = link_discovery or LinkDiscoveryService(
            max_resources=getattr(settings, "max_discovered_resources_per_event", 50)
        )
        self.relevance = relevance_classifier or DeterministicRelevanceClassifier()
        self.fetcher = resource_fetcher or DiscoveredResourceFetcher()
        self.browser = browser_fallback or BrowserFallbackService()
        self.repo = repository or ChangeAnalysisRepository()
        self.max_fetch = getattr(settings, "max_fetched_resources_per_event", 20)

    def _get_change_dir(self, source_url_id: uuid.UUID, event_id: uuid.UUID) -> Path:
        base_dir = getattr(settings, "monitoring_dir", Path("storage/monitoring"))
        p = base_dir / str(source_url_id) / "changes" / str(event_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _get_baseline_html_path(self, source_url_id: uuid.UUID) -> Optional[Path]:
        base_dir = getattr(settings, "monitoring_dir", Path("storage/monitoring"))
        p = base_dir / str(source_url_id) / "baseline" / "response.html"
        return p if p.exists() else None

    def analyze_event(
        self,
        db: Session,
        event: SourceChangeEvent,
    ) -> SourceChangeAnalysis:
        """Execute full Day 18 analysis pipeline for a confirmed change event."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc)

        # 1. Check idempotency: if already analyzed, return existing record
        existing_analysis = self.repo.get_analysis_by_event_id(db, event.id)
        if existing_analysis and existing_analysis.status == "ANALYZED":
            logger.info(f"Change event {event.id} already analyzed, returning existing record.")
            return existing_analysis

        analysis = existing_analysis or SourceChangeAnalysis(
            change_event_id=event.id,
            status="ANALYSIS_CLAIMED",
            started_at=started_at,
        )
        if not existing_analysis:
            db.add(analysis)
            db.commit()
            db.refresh(analysis)

        # 2. Identify Source URL and base URL
        source_url = event.source_url or db.get(SourceUrl, event.source_url_id)
        base_url = source_url.url if source_url else "https://rajasthan.gov.in"
        source_id = source_url.source_id if source_url else None

        change_dir = self._get_change_dir(event.source_url_id, event.id)
        curr_html_path = change_dir / "response.html"

        # 3. Read current raw HTML or fetch if missing
        raw_html = ""
        render_method = "HTTP"

        if curr_html_path.exists():
            try:
                with open(curr_html_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_html = f.read()
            except Exception as e:
                logger.warning(f"Failed to read current snapshot file: {e}")

        if not raw_html and base_url:
            try:
                with httpx.Client(timeout=15) as client:
                    resp = client.get(base_url)
                    raw_html = resp.text
                    with open(curr_html_path, "w", encoding="utf-8", errors="replace") as f:
                        f.write(raw_html)
            except Exception as e:
                logger.warning(f"Direct fetch of current HTML failed: {e}")

        # 4. Clean current HTML
        curr_cleaned = self.cleaner.clean(raw_html, source_url=base_url)

        # 5. Check if HTTP content is sufficient; if not, invoke Playwright fallback
        if not is_http_content_sufficient(raw_html, curr_cleaned.cleaned_text):
            logger.info(f"HTTP content insufficient for {base_url}; checking Playwright fallback...")
            if self.browser.enabled:
                try:
                    # Run async Playwright renderer
                    success, rendered_html, err_msg = asyncio.run(
                        self.browser.render_page(base_url)
                    )
                    if success and rendered_html:
                        render_method = "PLAYWRIGHT"
                        raw_html = rendered_html
                        rendered_path = change_dir / "rendered.html"
                        with open(rendered_path, "w", encoding="utf-8", errors="replace") as f:
                            f.write(rendered_html)
                        curr_cleaned = self.cleaner.clean(rendered_html, source_url=base_url)
                    else:
                        logger.warning(f"Playwright fallback failed or unavailable: {err_msg}")
                        render_method = "HTTP"
                except Exception as pe:
                    logger.warning(f"Error during Playwright fallback execution: {pe}")
                    render_method = "HTTP"

        analysis.render_method = render_method
        analysis.current_snapshot_path = str(curr_html_path)

        # 6. Save cleaned current snapshot
        cleaned_json_path = change_dir / "cleaned.json"
        cleaned_txt_path = change_dir / "cleaned.txt"
        with open(cleaned_json_path, "w", encoding="utf-8") as f:
            json.dump(curr_cleaned.to_dict(), f, indent=2, ensure_ascii=False)
        with open(cleaned_txt_path, "w", encoding="utf-8") as f:
            f.write(curr_cleaned.cleaned_text)

        analysis.cleaned_snapshot_path = str(cleaned_json_path)

        # 7. Load and clean previous snapshot (baseline or earlier change)
        prev_cleaned: Optional[CleanedPage] = None
        baseline_path = self._get_baseline_html_path(event.source_url_id)
        
        if baseline_path and baseline_path.exists():
            try:
                with open(baseline_path, "r", encoding="utf-8", errors="replace") as f:
                    prev_raw = f.read()
                prev_cleaned = self.cleaner.clean(prev_raw, source_url=base_url)
                analysis.previous_snapshot_path = str(baseline_path)
            except Exception as e:
                logger.warning(f"Failed to load baseline snapshot: {e}")

        # If baseline wasn't found, check prior change event
        if not prev_cleaned:
            prior_stmt = (
                select(SourceChangeEvent)
                .where(
                    SourceChangeEvent.source_url_id == event.source_url_id,
                    SourceChangeEvent.id != event.id,
                    SourceChangeEvent.created_at < event.created_at,
                )
                .order_by(SourceChangeEvent.created_at.desc())
                .limit(1)
            )
            prior_event = db.execute(prior_stmt).scalars().first()
            if prior_event:
                prior_dir = self._get_change_dir(event.source_url_id, prior_event.id)
                prior_html = prior_dir / "response.html"
                if prior_html.exists():
                    try:
                        with open(prior_html, "r", encoding="utf-8", errors="replace") as f:
                            prev_raw = f.read()
                        prev_cleaned = self.cleaner.clean(prev_raw, source_url=base_url)
                        analysis.previous_snapshot_path = str(prior_html)
                    except Exception as e:
                        logger.warning(f"Failed to load prior event snapshot: {e}")

        # 8. Compute Structured Diff
        diff_result = self.diff_service.compute_diff(prev_cleaned, curr_cleaned)
        diff_json_path = change_dir / "diff.json"
        with open(diff_json_path, "w", encoding="utf-8") as f:
            json.dump(diff_result.to_dict(), f, indent=2, ensure_ascii=False)

        analysis.diff_summary_path = str(diff_json_path)
        analysis.diff_summary = diff_result.summary()
        analysis.text_changes_count = diff_result.text_changes_count
        analysis.links_added_count = diff_result.links_added_count
        analysis.links_removed_count = diff_result.links_removed_count
        analysis.links_changed_count = diff_result.links_changed_count
        analysis.numeric_changes_count = diff_result.numeric_changes_count
        analysis.has_high_priority_change = diff_result.has_high_priority_change

        # 9. Discover candidate links
        candidates = self.discovery.discover_candidates(
            diff_result=diff_result,
            current_page=curr_cleaned,
            base_url=base_url,
        )

        relevant_count = 0
        uncertain_count = 0
        irrelevant_count = 0
        persisted_candidates = []

        # 10. Classify relevance and persist candidates
        for cand in candidates:
            classification = self.relevance.classify(cand)

            if classification.status == "RELEVANT":
                relevant_count += 1
            elif classification.status == "UNCERTAIN":
                uncertain_count += 1
            else:
                irrelevant_count += 1

            # Check if DiscoveredResource already exists for this event + normalized_url
            existing_res_stmt = select(DiscoveredResource).where(
                DiscoveredResource.change_event_id == event.id,
                DiscoveredResource.normalized_url == cand.normalized_url,
            )
            res_record = db.execute(existing_res_stmt).scalars().first()

            if not res_record:
                res_record = DiscoveredResource(
                    change_event_id=event.id,
                    source_url_id=event.source_url_id,
                    url=cand.url,
                    normalized_url=cand.normalized_url,
                    anchor_text=cand.anchor_text[:512] if cand.anchor_text else None,
                    context_text=cand.context_text,
                    resource_type=cand.resource_type,
                    discovery_reason=cand.discovery_reason,
                    relevance_status=classification.status,
                    relevance_reason={
                        "signals": classification.signals,
                        "reason": classification.reason,
                    },
                    fetch_status="PENDING" if classification.status == "RELEVANT" else "SKIPPED",
                )
                db.add(res_record)
                db.flush()
            else:
                res_record.relevance_status = classification.status
                res_record.relevance_reason = {
                    "signals": classification.signals,
                    "reason": classification.reason,
                }
                db.flush()

            persisted_candidates.append(res_record)

        analysis.relevant_resources_count = relevant_count
        analysis.uncertain_resources_count = uncertain_count
        analysis.irrelevant_resources_count = irrelevant_count

        # 11. Fetch and Ingest Relevant Candidates
        relevant_candidates = [
            c for c in persisted_candidates if c.relevance_status == "RELEVANT"
        ][: self.max_fetch]

        fetched_count = 0
        ingested_count = 0
        had_fetch_failures = False

        for cand_rec in relevant_candidates:
            success, err_msg = self.fetcher.fetch_and_ingest_candidate(
                db=db,
                candidate_record=cand_rec,
                source_base_url=base_url,
                source_id=source_id,
            )
            if success:
                fetched_count += 1
                if cand_rec.document_id:
                    ingested_count += 1
            else:
                had_fetch_failures = True

        analysis.fetched_resources_count = fetched_count
        analysis.ingested_documents_count = ingested_count

        # 12. Finalize status
        duration = (time.time() - start_time) * 1000.0
        analysis.duration_ms = duration
        analysis.completed_at = datetime.now(timezone.utc)

        if had_fetch_failures:
            analysis.status = "ANALYSIS_REVIEW_REQUIRED"
            event.processing_status = "ANALYSIS_REVIEW_REQUIRED"
        else:
            analysis.status = "ANALYZED"
            event.processing_status = "ANALYZED"

        db.commit()
        db.refresh(analysis)
        logger.info(
            f"Completed analysis for event {event.id}: status={analysis.status} | "
            f"diff={analysis.text_changes_count}T/{analysis.links_added_count}L | "
            f"relevant={relevant_count} | ingested={ingested_count} | duration={duration:.1f}ms"
        )
        return analysis
