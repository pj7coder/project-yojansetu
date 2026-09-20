import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional, Set, Tuple
from urllib.parse import urlparse
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crawler.html_cleaner import HtmlContentCleaner
from app.crawler.link_discovery import LinkCandidate
from app.database.models.discovered_resource import DiscoveredResource
from app.database.models.web_content_artifact import WebContentArtifact
from app.ingestion.service import DocumentIngestionError, DocumentIngestionService
from app.monitoring.safety import validate_url_safety

logger = logging.getLogger(__name__)

# Trusted government second-level domains and CDNs
ALLOWED_GOV_DOMAINS = {
    "rajasthan.gov.in",
    "gov.in",
    "nic.in",
    "digitalindia.gov.in",
    "india.gov.in",
}


def is_domain_allowed(target_url: str, source_base_url: str) -> Tuple[bool, str]:
    """Check if target URL domain is permitted (same domain, approved government domain, or allowlist).
    
    Returns:
        (is_allowed: bool, reason: str)
    """
    try:
        t_parsed = urlparse(target_url)
        s_parsed = urlparse(source_base_url)
        t_host = (t_parsed.hostname or "").lower()
        s_host = (s_parsed.hostname or "").lower()

        if not t_host:
            return False, "Target URL missing hostname"

        # 1. Exact or sub-domain of source URL
        if t_host == s_host or t_host.endswith(f".{s_host}"):
            return True, "Same domain or subdomain as source URL"

        # 2. Approved government domain
        for gov_domain in ALLOWED_GOV_DOMAINS:
            if t_host == gov_domain or t_host.endswith(f".{gov_domain}"):
                return True, f"Approved official government domain ({gov_domain})"

        return False, f"Untrusted external domain '{t_host}' blocked by policy"
    except Exception as e:
        return False, f"Domain check error: {e}"


class DiscoveredResourceFetcher:
    """Safely fetches and ingests discovered candidate resources (PDF documents and scheme HTML pages)."""

    def __init__(
        self,
        ingestion_service: Optional[DocumentIngestionService] = None,
        html_cleaner: Optional[HtmlContentCleaner] = None,
        max_bytes: Optional[int] = None,
        timeout_seconds: int = 30,
    ):
        self.ingestion_service = ingestion_service or DocumentIngestionService()
        self.html_cleaner = html_cleaner or HtmlContentCleaner()
        self.max_bytes = max_bytes or getattr(settings, "resource_max_bytes", 50 * 1024 * 1024)
        self.timeout_seconds = timeout_seconds
        self.temp_dir = getattr(settings, "incoming_dir", Path("storage/incoming"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def fetch_and_ingest_candidate(
        self,
        db: Session,
        candidate_record: DiscoveredResource,
        source_base_url: str,
        source_id: Optional[uuid.UUID] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Download and ingest candidate resource.
        
        PDFs are handed off to Day 4 DocumentIngestionService.
        HTML pages are preserved as WebContentArtifacts.
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        url = candidate_record.normalized_url

        # 1. SSRF check
        is_safe, ssrf_err = validate_url_safety(url, allow_localhost=False)
        if not is_safe:
            candidate_record.fetch_status = "FAILED"
            candidate_record.fetch_error = f"SSRF violation: {ssrf_err}"
            db.commit()
            return False, candidate_record.fetch_error

        # 2. Domain policy check
        is_allowed, domain_msg = is_domain_allowed(url, source_base_url)
        if not is_allowed:
            candidate_record.fetch_status = "BLOCKED_BY_POLICY"
            candidate_record.fetch_error = domain_msg
            db.commit()
            return False, domain_msg

        candidate_record.fetch_status = "FETCHING"
        db.commit()

        # 3. Streamed HTTP download with safe redirect inspection
        try:
            current_url = url
            headers = {
                "User-Agent": getattr(
                    settings,
                    "monitoring_user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) YojanSetuBot/1.0",
                ),
                "Accept": "*/*",
            }

            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                resp = None
                for redirect_hop in range(5):
                    # Check safety on every redirect target
                    safe_hop, hop_err = validate_url_safety(current_url, allow_localhost=False)
                    if not safe_hop:
                        raise ValueError(f"Redirect SSRF safety violation to {current_url}: {hop_err}")

                    resp = client.get(current_url, headers=headers)
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise ValueError("Redirect response missing Location header")
                        from urllib.parse import urljoin
                        current_url = urljoin(current_url, location)
                        continue
                    break

                if resp is None or resp.status_code >= 400:
                    status = resp.status_code if resp else "NO_RESPONSE"
                    raise ValueError(f"HTTP request failed with status {status}")

                content_type = resp.headers.get("content-type", "").lower()
                
                # Check resource handling
                if candidate_record.resource_type == "PDF" or "application/pdf" in content_type:
                    return self._handle_pdf_download(
                        db=db,
                        candidate_record=candidate_record,
                        response=resp,
                        source_id=source_id,
                    )
                elif candidate_record.resource_type == "HTML_PAGE" or "text/html" in content_type:
                    return self._handle_html_content(
                        db=db,
                        candidate_record=candidate_record,
                        raw_html=resp.text,
                    )
                else:
                    # Non-PDF, non-HTML (e.g. DOC, XLS, etc.) - keep candidate record as SKIPPED for Day 18
                    candidate_record.fetch_status = "SKIPPED"
                    candidate_record.fetch_error = f"Resource type '{candidate_record.resource_type}' not ingested in Day 18 pipeline"
                    db.commit()
                    return True, None

        except Exception as e:
            error_msg = f"Resource fetch failed: {str(e)}"
            logger.warning(f"Error fetching candidate {url}: {error_msg}")
            candidate_record.fetch_status = "FAILED"
            candidate_record.fetch_error = error_msg
            db.commit()
            return False, error_msg

    def _handle_pdf_download(
        self,
        db: Session,
        candidate_record: DiscoveredResource,
        response: httpx.Response,
        source_id: Optional[uuid.UUID],
    ) -> Tuple[bool, Optional[str]]:
        """Stream PDF to temporary file, enforce max size, and hand off to DocumentIngestionService."""
        temp_file = self.temp_dir / f"crawler_{uuid.uuid4().hex}.pdf"
        bytes_written = 0

        try:
            with open(temp_file, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=65536):
                    bytes_written += len(chunk)
                    if bytes_written > self.max_bytes:
                        raise ValueError(
                            f"Downloaded file size ({bytes_written} bytes) exceeds maximum allowed limit ({self.max_bytes} bytes)"
                        )
                    f.write(chunk)

            # Derive filename from URL or anchor
            parsed = urlparse(candidate_record.normalized_url)
            filename = Path(parsed.path).name or "document.pdf"
            if not filename.lower().endswith(".pdf"):
                filename = f"{filename}.pdf"

            title = candidate_record.anchor_text or filename

            # Hand off directly to Day 4 DocumentIngestionService
            logger.info(
                f"Handing off downloaded PDF ({bytes_written} bytes) to DocumentIngestionService: {filename}"
            )
            doc = self.ingestion_service.ingest_document(
                db=db,
                file_path=temp_file,
                original_filename=filename,
                ingestion_method="WEB_MONITOR",
                source_id=source_id,
                source_url_id=candidate_record.source_url_id,
                title=title,
                move_file=True,
            )

            candidate_record.fetch_status = "FETCHED"
            candidate_record.document_id = doc.id
            candidate_record.fetch_error = None
            db.commit()
            return True, None

        except DocumentIngestionError as die:
            error_msg = f"Document ingestion validation rejected file: {die.message}"
            candidate_record.fetch_status = "FAILED"
            candidate_record.fetch_error = error_msg
            if die.document:
                candidate_record.document_id = die.document.id
            db.commit()
            return False, error_msg
        except Exception as e:
            error_msg = f"PDF processing error: {str(e)}"
            candidate_record.fetch_status = "FAILED"
            candidate_record.fetch_error = error_msg
            db.commit()
            return False, error_msg
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def _handle_html_content(
        self,
        db: Session,
        candidate_record: DiscoveredResource,
        raw_html: str,
    ) -> Tuple[bool, Optional[str]]:
        """Clean and preserve relevant HTML scheme webpage as a WebContentArtifact."""
        try:
            cleaned = self.html_cleaner.clean(
                raw_html=raw_html,
                source_url=candidate_record.normalized_url,
            )
            title = cleaned.title or candidate_record.anchor_text or "Government Scheme Webpage"

            artifact = WebContentArtifact(
                source_url_id=candidate_record.source_url_id,
                change_event_id=candidate_record.change_event_id,
                title=title,
                source_url=candidate_record.normalized_url,
                cleaned_content=cleaned.to_dict(),
                cleaned_text=cleaned.cleaned_text,
                status="READY_FOR_WEB_CONTENT_PROCESSING",
                captured_at=datetime.now(timezone.utc),
            )
            db.add(artifact)
            candidate_record.fetch_status = "FETCHED"
            candidate_record.fetch_error = None
            db.commit()
            logger.info(f"Preserved HTML scheme content artifact for {candidate_record.normalized_url}")
            return True, None
        except Exception as e:
            error_msg = f"Failed to preserve HTML artifact: {str(e)}"
            candidate_record.fetch_status = "FAILED"
            candidate_record.fetch_error = error_msg
            db.commit()
            return False, error_msg
