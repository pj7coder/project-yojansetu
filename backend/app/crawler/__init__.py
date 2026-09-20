"""Day 18 Change Analysis, Structured HTML Diffing, Document Discovery, and Playwright Fallback subsystem."""

from app.crawler.analysis_service import SourceChangeAnalysisService
from app.crawler.browser_fallback import BrowserFallbackService, is_http_content_sufficient
from app.crawler.diff_service import WebpageDiffResult, WebpageDiffService
from app.crawler.html_cleaner import CleanedPage, HtmlContentCleaner
from app.crawler.link_discovery import LinkCandidate, LinkDiscoveryService
from app.crawler.relevance import DeterministicRelevanceClassifier, RelevanceClassification
from app.crawler.resource_fetcher import DiscoveredResourceFetcher

__all__ = [
    "SourceChangeAnalysisService",
    "BrowserFallbackService",
    "is_http_content_sufficient",
    "WebpageDiffResult",
    "WebpageDiffService",
    "CleanedPage",
    "HtmlContentCleaner",
    "LinkCandidate",
    "LinkDiscoveryService",
    "DeterministicRelevanceClassifier",
    "RelevanceClassification",
    "DiscoveredResourceFetcher",
]
