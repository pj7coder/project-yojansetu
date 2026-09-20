import asyncio
import logging
from typing import Optional, Tuple

from app.core.config import settings
from app.monitoring.safety import validate_url_safety

logger = logging.getLogger(__name__)

# Shell indicators suggesting client-side rendering
JS_SHELL_PATTERNS = [
    '<div id="app"></div>',
    '<div id="root"></div>',
    '<div id="__next"></div>',
    "please enable javascript",
    "javascript is required",
    "you need to enable javascript to run this app",
    "noscript",
]

# Resource types to abort to save memory and bandwidth
BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "websocket"}


def is_http_content_sufficient(
    raw_html: str,
    cleaned_text: str,
    min_chars: Optional[int] = None,
) -> bool:
    """Check if normal HTTP fetch yielded meaningful content.
    
    Returns True if content is sufficient (no browser fallback needed).
    Returns False if browser fallback should be attempted.
    """
    threshold = min_chars or getattr(settings, "html_min_meaningful_text_chars", 300)
    
    if not raw_html or not raw_html.strip():
        return False

    clean_len = len(cleaned_text.strip()) if cleaned_text else 0
    if clean_len >= threshold:
        return True

    # If below threshold, check if it's a known JS shell
    lower_raw = raw_html.lower()
    for pattern in JS_SHELL_PATTERNS:
        if pattern in lower_raw:
            return False

    # Short content without JS shell could still be a tiny page, but if text is less than 50 chars, mark insufficient
    if clean_len < 50:
        return False

    return True


class BrowserFallbackService:
    """Playwright-based passive headless browser renderer for JavaScript-rendered government portals."""

    def __init__(
        self,
        enabled: Optional[bool] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.enabled = (
            enabled if enabled is not None else getattr(settings, "playwright_enabled", True)
        )
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "playwright_page_timeout_seconds", 20)
        )

    async def render_page(
        self,
        url: str,
        expected_host: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Passively render a page using headless Chromium.
        
        Returns:
            (success: bool, rendered_html: Optional[str], error_message: Optional[str])
        """
        if not self.enabled:
            return False, None, "Playwright browser fallback is disabled by configuration"

        # Pre-flight SSRF safety check
        is_safe, error_msg = validate_url_safety(url, allow_localhost=False)
        if not is_safe:
            return False, None, f"URL rejected by SSRF safety validation: {error_msg}"

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return (
                False,
                None,
                "Playwright package is not installed or available in this environment",
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                context = await browser.new_context(
                    user_agent=getattr(
                        settings,
                        "monitoring_user_agent",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) YojanSetuBot/1.0",
                    ),
                    viewport={"width": 1280, "height": 800},
                    java_script_enabled=True,
                )

                page = await context.new_page()

                # Passive resource blocking (images, videos, fonts, tracking)
                async def route_interceptor(route):
                    req = route.request
                    if req.resource_type in BLOCKED_RESOURCE_TYPES:
                        await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", route_interceptor)

                timeout_ms = self.timeout_seconds * 1000
                logger.info(f"Rendering {url} via Playwright (timeout={self.timeout_seconds}s)")

                # Navigate passively - do NOT click or submit anything
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )

                if response is None:
                    await browser.close()
                    return False, None, "Playwright navigation returned no response"

                # Brief wait for client-side JS DOM hydration (capped at 3s)
                try:
                    await page.wait_for_load_state("load", timeout=min(5000, timeout_ms))
                except Exception:
                    pass  # Non-fatal if page load takes longer but DOM is ready

                rendered_html = await page.content()
                await browser.close()

                if not rendered_html or len(rendered_html.strip()) < 50:
                    return False, None, "Playwright rendered content was empty or trivial"

                return True, rendered_html, None

        except Exception as e:
            error_text = f"Playwright rendering failed for {url}: {e}"
            logger.warning(error_text)
            return False, None, error_text
