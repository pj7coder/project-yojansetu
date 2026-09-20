from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin
import httpx

from app.core.config import settings
from app.monitoring.safety import SSRFValidationError, validate_url_safety

logger = logging.getLogger(__name__)


@dataclass
class HttpResponseResult:
    """Result container for staged HTTP check."""
    status_code: int
    http_method: str
    final_url: str
    headers: Dict[str, str]
    content: bytes
    text: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_length: Optional[int] = None
    content_type: Optional[str] = None
    duration_ms: float = 0.0
    retry_after: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_304: bool = False
    requires_browser_fallback: bool = False


class MonitoringHttpClient:
    """Staged HTTP client with SSRF verification, conditional requests, size capping, and rate safety."""

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        max_bytes: Optional[int] = None,
        user_agent: Optional[str] = None,
        allow_localhost: bool = False,
    ):
        self.timeout_seconds = timeout_seconds or float(settings.MONITOR_HTTP_TIMEOUT_SECONDS)
        self.max_bytes = max_bytes or settings.MONITOR_MAX_HTML_BYTES
        self.user_agent = user_agent or settings.MONITOR_USER_AGENT
        self.allow_localhost = allow_localhost

    def _prepare_headers(
        self,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
            "Accept-Encoding": "gzip, deflate",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def _parse_retry_after(self, response: httpx.Response) -> Optional[int]:
        val = response.headers.get("Retry-After")
        if not val:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _check_dynamic_rendering_markers(self, text: str) -> bool:
        """Inspect if HTML is a bare JS shell requiring browser fallback."""
        if not text:
            return False
        # If HTML body is tiny and mentions javascript required
        text_lower = text.lower()
        if len(text) < 1500 and (
            "you need to enable javascript" in text_lower
            or "javascript is disabled" in text_lower
            or '<div id="root"></div>' in text_lower
            or '<div id="app"></div>' in text_lower
        ):
            return True
        return False

    async def execute_staged_check(
        self,
        url: str,
        previous_etag: Optional[str] = None,
        previous_last_modified: Optional[str] = None,
        strategy: str = "AUTO",
    ) -> HttpResponseResult:
        """Perform staged HTTP check:
        1. SSRF URL validation.
        2. Build conditional headers (If-None-Match, If-Modified-Since).
        3. Attempt conditional GET (or HEAD if preferred and no body needed).
           Note: Conditional GET returns 304 without transferring body if server supports it,
           avoiding double round-trips while remaining robust against servers that reject HEAD.
        4. Stream body up to max_bytes.
        """
        start_time = time.perf_counter()

        # Step 1: SSRF Validation
        is_safe, error_msg = validate_url_safety(url, allow_localhost=self.allow_localhost)
        if not is_safe:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return HttpResponseResult(
                status_code=0,
                http_method="GET",
                final_url=url,
                headers={},
                content=b"",
                text="",
                duration_ms=duration_ms,
                error_code="SSRF_BLOCKED",
                error_message=error_msg,
            )

        headers = self._prepare_headers(previous_etag, previous_last_modified)

        # Step 2: HTTP Request execution with redirect inspection
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)
        current_url = url

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                redirect_count = 0
                max_redirects = 3
                resp = None

                while redirect_count <= max_redirects:
                    # Validate intermediate redirect URLs
                    if redirect_count > 0:
                        safe_redir, redir_err = validate_url_safety(
                            current_url, allow_localhost=self.allow_localhost
                        )
                        if not safe_redir:
                            duration_ms = (time.perf_counter() - start_time) * 1000
                            return HttpResponseResult(
                                status_code=0,
                                http_method="GET",
                                final_url=current_url,
                                headers={},
                                content=b"",
                                text="",
                                duration_ms=duration_ms,
                                error_code="REDIRECT_SSRF_BLOCKED",
                                error_message=f"Redirect blocked: {redir_err}",
                            )

                    # Use stream to enforce response byte cap
                    async with client.stream("GET", current_url, headers=headers) as stream_resp:
                        if stream_resp.is_redirect:
                            redirect_count += 1
                            loc = stream_resp.headers.get("Location")
                            if not loc:
                                break
                            current_url = urljoin(current_url, loc)
                            continue

                        # Terminal response reached
                        status_code = stream_resp.status_code
                        resp_headers = dict(stream_resp.headers)
                        etag = resp_headers.get("etag") or resp_headers.get("ETag")
                        last_modified = resp_headers.get("last-modified") or resp_headers.get("Last-Modified")
                        content_type = resp_headers.get("content-type")
                        content_length_hdr = resp_headers.get("content-length")
                        content_length = int(content_length_hdr) if content_length_hdr and content_length_hdr.isdigit() else None
                        retry_after = self._parse_retry_after(stream_resp)

                        # Check 304 Not Modified
                        if status_code == 304:
                            duration_ms = (time.perf_counter() - start_time) * 1000
                            return HttpResponseResult(
                                status_code=304,
                                http_method="GET",
                                final_url=current_url,
                                headers=resp_headers,
                                content=b"",
                                text="",
                                etag=etag or previous_etag,
                                last_modified=last_modified or previous_last_modified,
                                content_length=content_length,
                                content_type=content_type,
                                duration_ms=duration_ms,
                                is_304=True,
                            )

                        # Read body up to max_bytes
                        body_chunks = []
                        total_bytes = 0
                        is_truncated = False

                        async for chunk in stream_resp.aiter_bytes():
                            total_bytes += len(chunk)
                            if total_bytes > self.max_bytes:
                                is_truncated = True
                                break
                            body_chunks.append(chunk)

                        duration_ms = (time.perf_counter() - start_time) * 1000
                        full_content = b"".join(body_chunks)

                        if is_truncated:
                            return HttpResponseResult(
                                status_code=status_code,
                                http_method="GET",
                                final_url=current_url,
                                headers=resp_headers,
                                content=full_content,
                                text="",
                                duration_ms=duration_ms,
                                error_code="RESPONSE_TOO_LARGE",
                                error_message=f"Response exceeded size limit of {self.max_bytes} bytes",
                            )

                        # Decode text safely
                        encoding = stream_resp.encoding or "utf-8"
                        try:
                            text_content = full_content.decode(encoding, errors="replace")
                        except Exception:
                            text_content = full_content.decode("utf-8", errors="replace")

                        req_browser = self._check_dynamic_rendering_markers(text_content)

                        return HttpResponseResult(
                            status_code=status_code,
                            http_method="GET",
                            final_url=current_url,
                            headers=resp_headers,
                            content=full_content,
                            text=text_content,
                            etag=etag,
                            last_modified=last_modified,
                            content_length=len(full_content) if content_length is None else content_length,
                            content_type=content_type,
                            duration_ms=duration_ms,
                            retry_after=retry_after,
                            requires_browser_fallback=req_browser,
                        )

                # Redirect loop / exceeded
                duration_ms = (time.perf_counter() - start_time) * 1000
                return HttpResponseResult(
                    status_code=0,
                    http_method="GET",
                    final_url=current_url,
                    headers={},
                    content=b"",
                    text="",
                    duration_ms=duration_ms,
                    error_code="TOO_MANY_REDIRECTS",
                    error_message=f"Exceeded maximum redirect limit of {max_redirects}",
                )

        except httpx.TimeoutException as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return HttpResponseResult(
                status_code=0,
                http_method="GET",
                final_url=url,
                headers={},
                content=b"",
                text="",
                duration_ms=duration_ms,
                error_code="TIMEOUT",
                error_message=f"HTTP request timed out after {self.timeout_seconds}s: {e}",
            )
        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return HttpResponseResult(
                status_code=0,
                http_method="GET",
                final_url=url,
                headers={},
                content=b"",
                text="",
                duration_ms=duration_ms,
                error_code="CONNECT_ERROR",
                error_message=f"Connection failure to host: {e}",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return HttpResponseResult(
                status_code=0,
                http_method="GET",
                final_url=url,
                headers={},
                content=b"",
                text="",
                duration_ms=duration_ms,
                error_code="REQUEST_FAILED",
                error_message=f"HTTP check encountered unexpected exception: {e}",
            )
