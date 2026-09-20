import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from app.crawler.diff_service import WebpageDiffResult
from app.crawler.html_cleaner import CleanedLink, CleanedPage
from app.crawler.relevance_terms import (
    APPLICATION_TERMS,
    NEGATIVE_TERMS,
    NOTIFICATION_TERMS,
    SCHEME_TERMS,
)

logger = logging.getLogger(__name__)

DOC_EXTENSIONS = {
    ".pdf": "PDF",
    ".doc": "DOC",
    ".docx": "DOCX",
    ".xls": "XLS",
    ".xlsx": "XLSX",
    ".csv": "CSV",
    ".zip": "ARCHIVE",
    ".rar": "ARCHIVE",
    ".jpg": "IMAGE",
    ".jpeg": "IMAGE",
    ".png": "IMAGE",
    ".gif": "IMAGE",
    ".webp": "IMAGE",
    ".svg": "IMAGE",
}

HTML_EXTENSIONS = {
    ".html",
    ".htm",
    ".php",
    ".asp",
    ".aspx",
    ".jsp",
    ".action",
    ".do",
}


@dataclass
class LinkCandidate:
    """Discovered resource candidate for relevance classification."""
    url: str
    normalized_url: str
    anchor_text: str
    resource_type: str  # PDF, HTML_PAGE, DOC, DOCX, XLS, XLSX, IMAGE, UNKNOWN
    discovery_reason: str  # NEW_LINK, CHANGED_LINK, NEW_NOTIFICATION, NEW_PDF, CHANGED_SCHEME_TEXT
    context_text: Optional[str] = None
    all_anchors: List[str] = field(default_factory=list)


def normalize_candidate_url(raw_url: str, base_url: str) -> Optional[str]:
    """Resolve relative URL, trim fragments, and normalize casing for comparison."""
    if not raw_url or not raw_url.strip():
        return None

    raw_clean = raw_url.strip()
    # Ignore javascript: and mailto: and tel: links
    lower = raw_clean.lower()
    if lower.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None

    try:
        resolved = urljoin(base_url, raw_clean)
        parsed = urlparse(resolved)
        if parsed.scheme.lower() not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None

        # Reconstruct without fragment
        clean_netloc = parsed.netloc.lower()
        clean_path = parsed.path or "/"
        # Normalize redundant slashes in path
        while "//" in clean_path:
            clean_path = clean_path.replace("//", "/")

        normalized = urlunparse((
            parsed.scheme.lower(),
            clean_netloc,
            clean_path,
            parsed.params,
            parsed.query,
            "",  # Strip fragment
        ))
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL '{raw_url}' against base '{base_url}': {e}")
        return None


def detect_resource_type(normalized_url: str) -> str:
    """Classify resource type from URL path extension."""
    try:
        parsed = urlparse(normalized_url)
        url_lower = normalized_url.lower()
        path = parsed.path.lower()
        
        # Check explicit file extensions in path or query
        for ext, res_type in DOC_EXTENSIONS.items():
            if (
                path.endswith(ext)
                or f"{ext}?" in url_lower
                or f"{ext}&" in url_lower
                or url_lower.endswith(ext)
                or f"{ext}#" in url_lower
            ):
                return res_type

        # Check HTML extensions
        for ext in HTML_EXTENSIONS:
            if (
                path.endswith(ext)
                or f"{ext}?" in url_lower
                or f"{ext}&" in url_lower
                or url_lower.endswith(ext)
            ):
                return "HTML_PAGE"

        # If path ends with slash or has no dot in the last segment, it's typically an HTML page
        last_seg = path.rstrip("/").split("/")[-1] if path else ""
        if "." not in last_seg:
            return "HTML_PAGE"

        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"


class LinkDiscoveryService:
    """Discovers candidate links from diff changes and cleaned webpage representation."""

    def __init__(self, max_resources: int = 50):
        self.max_resources = max_resources

    def discover_candidates(
        self,
        diff_result: WebpageDiffResult,
        current_page: CleanedPage,
        base_url: str,
    ) -> List[LinkCandidate]:
        """Extract and prioritize candidate resources from diff and current page.
        
        Crawl depth is strictly 1: only direct links on the changed page are considered.
        """
        candidates_by_url: Dict[str, LinkCandidate] = {}

        # 1. First pass: extract from diff changes (highest priority)
        for change in diff_result.changes:
            if change.change_type in ("LINK_ADDED", "LINK_CHANGED"):
                new_val = change.new_value or {}
                raw_url = new_val.get("url") or ""
                anchor = (new_val.get("text") or "").strip()
                norm_url = normalize_candidate_url(raw_url, base_url)
                if not norm_url:
                    continue

                res_type = detect_resource_type(norm_url)
                
                # Determine discovery reason
                lower_text = f"{anchor} {norm_url}".lower()
                is_notification = any(kw.lower() in lower_text for kw in NOTIFICATION_TERMS)
                is_scheme = any(kw.lower() in lower_text for kw in SCHEME_TERMS)
                
                if res_type == "PDF":
                    if is_notification or is_scheme:
                        reason = "NEW_NOTIFICATION"
                    else:
                        reason = "NEW_PDF"
                elif change.change_type == "LINK_CHANGED":
                    reason = "CHANGED_LINK"
                else:
                    reason = "NEW_LINK"

                if norm_url not in candidates_by_url:
                    candidates_by_url[norm_url] = LinkCandidate(
                        url=raw_url,
                        normalized_url=norm_url,
                        anchor_text=anchor,
                        resource_type=res_type,
                        discovery_reason=reason,
                        all_anchors=[anchor] if anchor else [],
                    )
                else:
                    if anchor and anchor not in candidates_by_url[norm_url].all_anchors:
                        candidates_by_url[norm_url].all_anchors.append(anchor)

            elif change.change_type in ("TEXT_ADDED", "TEXT_CHANGED"):
                # If text changed, see if any links in the current page are close or if links were added
                pass

        # 2. Second pass: If baseline was missing or very few diff links were discovered,
        # inspect links on current page directly (bounded by max_resources)
        if len(candidates_by_url) < self.max_resources and (
            diff_result.is_baseline_missing or not diff_result.has_changes
        ):
            for link in current_page.links:
                if len(candidates_by_url) >= self.max_resources:
                    break
                norm_url = normalize_candidate_url(link.url, base_url)
                if not norm_url or norm_url in candidates_by_url:
                    continue
                res_type = detect_resource_type(norm_url)
                anchor = (link.text or "").strip()

                candidates_by_url[norm_url] = LinkCandidate(
                    url=link.url,
                    normalized_url=norm_url,
                    anchor_text=anchor,
                    resource_type=res_type,
                    discovery_reason="CHANGED_SCHEME_TEXT" if diff_result.has_changes else "NEW_LINK",
                    all_anchors=[anchor] if anchor else [],
                )

        # Truncate to max resources
        candidate_list = list(candidates_by_url.values())[: self.max_resources]
        logger.info(
            f"Discovered {len(candidate_list)} candidate resources from diff (max={self.max_resources})"
        )
        return candidate_list
