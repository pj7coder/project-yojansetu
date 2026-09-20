from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models.source import Source
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_monitor_run import SourceMonitorRun
from app.database.models.source_monitor_state import SourceMonitorState
from app.database.models.source_url import SourceUrl
from app.monitoring.fingerprint import (
    compute_body_fingerprint,
    compute_feed_fingerprint,
    compute_link_fingerprint,
    compute_sitemap_fingerprint,
    extract_and_normalize_links,
)
from app.monitoring.http_client import HttpResponseResult, MonitoringHttpClient
from app.monitoring.rate_limit import DomainRateLimiter
from app.monitoring.robots import RobotsPolicyService
from app.monitoring.scheduler import MonitoringScheduler
from app.monitoring.snapshots import SnapshotManager
from app.repositories.source_monitor_repository import SourceMonitorRepository

logger = logging.getLogger(__name__)


class SourceMonitoringService:
    """Core service for intelligent source monitoring and deterministic change detection."""

    def __init__(
        self,
        repository: Optional[SourceMonitorRepository] = None,
        http_client: Optional[MonitoringHttpClient] = None,
        scheduler: Optional[MonitoringScheduler] = None,
        robots_service: Optional[RobotsPolicyService] = None,
        rate_limiter: Optional[DomainRateLimiter] = None,
        snapshot_manager: Optional[SnapshotManager] = None,
    ):
        self.repo = repository or SourceMonitorRepository()
        self.http_client = http_client or MonitoringHttpClient()
        self.scheduler = scheduler or MonitoringScheduler()
        self.robots = robots_service or RobotsPolicyService()
        self.rate_limiter = rate_limiter or DomainRateLimiter(
            max_global_concurrency=settings.MONITOR_MAX_CONCURRENT_REQUESTS,
            max_per_host_concurrency=settings.MONITOR_MAX_CONCURRENT_PER_HOST,
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    async def check_source_url(
        self,
        db: Session,
        source_url_id: uuid.UUID,
        force_check: bool = False,
    ) -> Dict[str, Any]:
        """Perform a single monitoring check against an approved SourceUrl."""
        started_at = datetime.now(timezone.utc)

        # 1. Fetch SourceUrl and parent Source
        source_url = db.get(SourceUrl, source_url_id)
        if not source_url:
            return {
                "source_url_id": source_url_id,
                "status": "ERROR",
                "result": "SOURCE_NOT_FOUND",
                "message": f"SourceUrl with id {source_url_id} does not exist",
                "duration_ms": 0.0,
            }

        source = db.get(Source, source_url.source_id)
        if not source or not source.is_active:
            return {
                "source_url_id": source_url_id,
                "status": "DISABLED",
                "result": "PARENT_SOURCE_INACTIVE",
                "message": f"Parent Source '{source.name if source else 'Unknown'}' is inactive",
                "duration_ms": 0.0,
            }

        if not source_url.is_active or not source_url.crawl_allowed:
            return {
                "source_url_id": source_url_id,
                "status": "DISABLED",
                "result": "CRAWL_DISALLOWED",
                "message": f"SourceUrl is not enabled or crawl_allowed is False",
                "duration_ms": 0.0,
            }

        # 2. Fetch or create monitoring state
        state = self.repo.get_or_create_state(db, source_url_id)
        state.last_attempt_at = started_at

        # 3. Check Robots Policy
        is_allowed, robot_reason = self.robots.is_allowed(
            source_url.url, user_agent=settings.MONITOR_USER_AGENT
        )
        if not is_allowed:
            completed_at = datetime.now(timezone.utc)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            run = SourceMonitorRun(
                source_url_id=source_url_id,
                started_at=started_at,
                completed_at=completed_at,
                http_method="NONE",
                http_status=None,
                result="BLOCKED_BY_POLICY",
                change_signals={"robot_reason": robot_reason},
                duration_ms=duration_ms,
                error_code="ROBOTS_TXT_DISALLOWED",
                error_message_safe=robot_reason,
            )
            self.repo.record_run(db, run)

            state.monitor_status = "BLOCKED_BY_POLICY"
            state.next_check_at = self.scheduler.calculate_next_check(
                priority=source_url.check_priority,
                result_status="BLOCKED_BY_POLICY",
                custom_interval=source_url.check_interval_minutes,
                from_time=completed_at,
            )
            self.repo.update_state(db, state)

            return {
                "source_url_id": source_url_id,
                "status": "BLOCKED_BY_POLICY",
                "result": "ROBOTS_TXT_DISALLOWED",
                "message": robot_reason,
                "duration_ms": duration_ms,
                "next_check_at": state.next_check_at,
            }

        # 4. Acquire rate limiting permit & execute HTTP request
        async with self.rate_limiter.acquire(source_url.url):
            http_resp: HttpResponseResult = await self.http_client.execute_staged_check(
                url=source_url.url,
                previous_etag=state.etag,
                previous_last_modified=state.last_modified,
                strategy=source_url.monitor_strategy or "AUTO",
            )

        completed_at = datetime.now(timezone.utc)
        duration_ms = http_resp.duration_ms
        signals: Dict[str, Any] = {}
        change_event_id: Optional[uuid.UUID] = None

        # 5. Evaluate HTTP Response
        # Failure / Error cases
        if http_resp.error_code is not None or http_resp.status_code >= 400:
            status_code = http_resp.status_code
            error_code = http_resp.error_code or f"HTTP_{status_code}"
            error_msg = http_resp.error_message or f"HTTP status {status_code}"

            if status_code == 429:
                result = "RATE_LIMITED"
                monitor_status = "TEMPORARILY_UNAVAILABLE"
            elif status_code == 403:
                result = "ACCESS_FORBIDDEN"
                monitor_status = "ACCESS_FORBIDDEN"
            elif status_code in (401, 407):
                result = "AUTH_REQUIRED"
                monitor_status = "AUTH_REQUIRED"
            elif error_code == "SSRF_BLOCKED" or error_code == "REDIRECT_SSRF_BLOCKED":
                result = "BLOCKED_BY_POLICY"
                monitor_status = "BLOCKED_BY_POLICY"
            elif error_code == "RESPONSE_TOO_LARGE":
                result = "RESPONSE_TOO_LARGE"
                monitor_status = "CHECK_FAILED"
            else:
                result = "CHECK_FAILED"
                monitor_status = "CHECK_FAILED"

            state.consecutive_failures += 1
            state.last_http_status = status_code if status_code > 0 else None
            state.monitor_status = monitor_status

            next_check = self.scheduler.calculate_next_check(
                priority=source_url.check_priority,
                result_status=result,
                consecutive_failures=state.consecutive_failures,
                custom_interval=source_url.check_interval_minutes,
                retry_after_seconds=http_resp.retry_after,
                from_time=completed_at,
            )
            state.next_check_at = next_check
            self.repo.update_state(db, state)

            run = SourceMonitorRun(
                source_url_id=source_url_id,
                started_at=started_at,
                completed_at=completed_at,
                http_method=http_resp.http_method,
                http_status=status_code if status_code > 0 else None,
                result=result,
                change_signals={"error_code": error_code},
                duration_ms=duration_ms,
                error_code=error_code,
                error_message_safe=error_msg[:500] if error_msg else None,
            )
            self.repo.record_run(db, run)

            return {
                "source_url_id": source_url_id,
                "status": monitor_status,
                "result": result,
                "http_status": status_code,
                "duration_ms": duration_ms,
                "next_check_at": next_check,
                "message": error_msg,
            }

        # 6. HTTP 304 Not Modified
        if http_resp.is_304 or http_resp.status_code == 304:
            result = "UNCHANGED"
            state.consecutive_failures = 0
            state.last_success_at = completed_at
            state.last_http_status = 304
            state.monitor_status = "UNCHANGED"

            signals["is_304"] = True
            signals["etag_changed"] = False
            signals["last_modified_changed"] = False

            next_check = self.scheduler.calculate_next_check(
                priority=source_url.check_priority,
                result_status="UNCHANGED",
                consecutive_failures=0,
                custom_interval=source_url.check_interval_minutes,
                from_time=completed_at,
            )
            state.next_check_at = next_check
            self.repo.update_state(db, state)

            run = SourceMonitorRun(
                source_url_id=source_url_id,
                started_at=started_at,
                completed_at=completed_at,
                http_method=http_resp.http_method,
                http_status=304,
                result=result,
                change_signals=signals,
                duration_ms=duration_ms,
            )
            self.repo.record_run(db, run)

            return {
                "source_url_id": source_url_id,
                "status": "UNCHANGED",
                "result": "304_NOT_MODIFIED",
                "change_signals": signals,
                "http_status": 304,
                "duration_ms": duration_ms,
                "next_check_at": next_check,
                "message": "Resource unchanged per HTTP 304 cache validation",
            }

        # 7. HTTP 200 OK — Compute Deterministic Fingerprints
        body_fp = ""
        link_fp = ""
        url_type = (source_url.url_type or "SCHEME_PAGE").upper()
        strategy = (source_url.monitor_strategy or "AUTO").upper()

        if url_type == "SITEMAP" or strategy == "SITEMAP":
            body_fp, _ = compute_sitemap_fingerprint(http_resp.text)
            link_fp = body_fp
        elif url_type == "RSS_FEED" or strategy == "FEED":
            body_fp, _ = compute_feed_fingerprint(http_resp.text)
            link_fp = body_fp
        elif url_type == "DIRECT_PDF" or strategy == "DIRECT_FILE":
            import hashlib
            body_fp = hashlib.sha256(http_resp.content).hexdigest()
            link_fp = body_fp
        else:
            # HTML Page
            body_fp = compute_body_fingerprint(http_resp.text)
            links = extract_and_normalize_links(http_resp.text, http_resp.final_url)
            link_fp = compute_link_fingerprint(links)

        # First Check Baseline
        is_first_check = (
            state.monitor_status == "NEVER_CHECKED"
            or state.body_fingerprint is None
            or force_check and state.body_fingerprint is None
        )

        metadata_dict = {
            "source_url_id": str(source_url_id),
            "url": source_url.url,
            "final_url": http_resp.final_url,
            "status_code": http_resp.status_code,
            "etag": http_resp.etag,
            "last_modified": http_resp.last_modified,
            "content_type": http_resp.content_type,
            "content_length": http_resp.content_length,
            "body_fingerprint": body_fp,
            "link_fingerprint": link_fp,
            "requires_browser_fallback": http_resp.requires_browser_fallback,
        }

        if is_first_check:
            result = "BASELINE_CREATED"
            monitor_status = "UNCHANGED"
            state.consecutive_failures = 0
            state.last_success_at = completed_at
            state.last_http_status = 200
            state.monitor_status = monitor_status
            state.etag = http_resp.etag
            state.last_modified = http_resp.last_modified
            state.content_length = http_resp.content_length
            state.content_type = http_resp.content_type
            state.body_fingerprint = body_fp
            state.link_fingerprint = link_fp

            # Save baseline snapshot
            self.snapshots.save_baseline_snapshot(
                source_url_id=source_url_id,
                raw_content=http_resp.content,
                metadata=metadata_dict,
            )

            next_check = self.scheduler.calculate_next_check(
                priority=source_url.check_priority,
                result_status="BASELINE_CREATED",
                consecutive_failures=0,
                custom_interval=source_url.check_interval_minutes,
                from_time=completed_at,
            )
            state.next_check_at = next_check
            self.repo.update_state(db, state)

            run = SourceMonitorRun(
                source_url_id=source_url_id,
                started_at=started_at,
                completed_at=completed_at,
                http_method="GET",
                http_status=200,
                result=result,
                change_signals={"baseline_created": True},
                duration_ms=duration_ms,
            )
            self.repo.record_run(db, run)

            return {
                "source_url_id": source_url_id,
                "status": monitor_status,
                "result": result,
                "change_signals": {"baseline_created": True},
                "http_status": 200,
                "duration_ms": duration_ms,
                "next_check_at": next_check,
                "message": "Initial monitoring baseline created successfully",
            }

        # Subsequent Check: Compare signals
        etag_changed = (
            bool(http_resp.etag and state.etag and http_resp.etag != state.etag)
        )
        last_modified_changed = (
            bool(http_resp.last_modified and state.last_modified and http_resp.last_modified != state.last_modified)
        )
        content_length_changed = (
            bool(http_resp.content_length is not None and state.content_length is not None and http_resp.content_length != state.content_length)
        )
        body_fp_changed = (body_fp != state.body_fingerprint)
        link_fp_changed = (link_fp != state.link_fingerprint)

        signals = {
            "etag_changed": etag_changed,
            "last_modified_changed": last_modified_changed,
            "content_length_changed": content_length_changed,
            "body_fingerprint_changed": body_fp_changed,
            "link_fingerprint_changed": link_fp_changed,
            "is_304": False,
        }

        # Change Detection Decision
        has_changed = body_fp_changed or link_fp_changed

        if has_changed:
            result = "CHANGED"
            monitor_status = "CHANGED"
            state.last_change_at = completed_at

            # Classify change type
            if body_fp_changed and link_fp_changed:
                change_type = "MULTIPLE_SIGNALS"
            elif body_fp_changed:
                change_type = "CONTENT_CHANGED"
            elif link_fp_changed:
                change_type = "LINK_SET_CHANGED"
            else:
                change_type = "METADATA_CHANGED"

            prev_ref = {
                "etag": state.etag,
                "last_modified": state.last_modified,
                "content_length": state.content_length,
                "body_fingerprint": state.body_fingerprint,
                "link_fingerprint": state.link_fingerprint,
            }
            import hashlib
            idem_key = hashlib.sha256(f"{source_url_id}:{body_fp}:{link_fp}".encode("utf-8")).hexdigest()
            new_ref = {
                "etag": http_resp.etag,
                "last_modified": http_resp.last_modified,
                "content_length": http_resp.content_length,
                "body_fingerprint": body_fp,
                "link_fingerprint": link_fp,
                "idempotency_key": idem_key,
            }

            # Create run first so we have run_id
            run = SourceMonitorRun(
                source_url_id=source_url_id,
                started_at=started_at,
                completed_at=completed_at,
                http_method="GET",
                http_status=200,
                result=result,
                change_signals=signals,
                duration_ms=duration_ms,
            )
            self.repo.record_run(db, run)

            # Create change event (with idempotency guard)
            change_event = SourceChangeEvent(
                source_url_id=source_url_id,
                monitor_run_id=run.id,
                change_type=change_type,
                detected_at=completed_at,
                previous_state_reference=prev_ref,
                new_state_reference=new_ref,
                idempotency_key=idem_key,
                processing_status="PENDING_ANALYSIS",
            )
            persisted_event = self.repo.create_change_event(
                db, change_event, idempotency_key=idem_key
            )
            change_event_id = persisted_event.id

            # Save change snapshot
            self.snapshots.save_change_snapshot(
                source_url_id=source_url_id,
                event_id=persisted_event.id,
                raw_content=http_resp.content,
                metadata=metadata_dict,
            )

            # Update state with latest attributes
            state.consecutive_failures = 0
            state.last_success_at = completed_at
            state.last_http_status = 200
            state.monitor_status = monitor_status
            state.etag = http_resp.etag
            state.last_modified = http_resp.last_modified
            state.content_length = http_resp.content_length
            state.content_type = http_resp.content_type
            state.body_fingerprint = body_fp
            state.link_fingerprint = link_fp

            next_check = self.scheduler.calculate_next_check(
                priority=source_url.check_priority,
                result_status="CHANGED",
                consecutive_failures=0,
                custom_interval=source_url.check_interval_minutes,
                from_time=completed_at,
            )
            state.next_check_at = next_check
            self.repo.update_state(db, state)

            return {
                "source_url_id": source_url_id,
                "status": "CHANGED",
                "result": "CHANGE_DETECTED",
                "change_type": change_type,
                "change_signals": signals,
                "change_event_id": change_event_id,
                "http_status": 200,
                "duration_ms": duration_ms,
                "next_check_at": next_check,
                "message": f"Change detected: {change_type}. Queued PENDING_ANALYSIS for Day 18.",
            }

        else:
            # Unchanged (even if HTTP status was 200)
            result = "UNCHANGED"
            monitor_status = "UNCHANGED"
            state.consecutive_failures = 0
            state.last_success_at = completed_at
            state.last_http_status = 200
            state.monitor_status = monitor_status
            state.etag = http_resp.etag or state.etag
            state.last_modified = http_resp.last_modified or state.last_modified

            next_check = self.scheduler.calculate_next_check(
                priority=source_url.check_priority,
                result_status="UNCHANGED",
                consecutive_failures=0,
                custom_interval=source_url.check_interval_minutes,
                from_time=completed_at,
            )
            state.next_check_at = next_check
            self.repo.update_state(db, state)

            run = SourceMonitorRun(
                source_url_id=source_url_id,
                started_at=started_at,
                completed_at=completed_at,
                http_method="GET",
                http_status=200,
                result=result,
                change_signals=signals,
                duration_ms=duration_ms,
            )
            self.repo.record_run(db, run)

            return {
                "source_url_id": source_url_id,
                "status": "UNCHANGED",
                "result": "CONTENT_UNCHANGED",
                "change_signals": signals,
                "http_status": 200,
                "duration_ms": duration_ms,
                "next_check_at": next_check,
                "message": "Resource content and link fingerprints identical to previous state",
            }
