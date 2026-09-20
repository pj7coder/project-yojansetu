from datetime import datetime, timezone
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import urllib.robotparser

logger = logging.getLogger(__name__)


class RobotsPolicyService:
    """Service to fetch, parse, cache and evaluate robots.txt policies for approved domains."""

    def __init__(self, cache_ttl_seconds: int = 86400):
        self.cache_ttl_seconds = cache_ttl_seconds
        # Host -> (RobotFileParser, cached_at_timestamp)
        self._cache: Dict[str, Tuple[urllib.robotparser.RobotFileParser, float]] = {}

    def _get_robots_url(self, target_url: str) -> Tuple[str, str]:
        """Derive scheme://host and robots.txt URL from target URL."""
        parsed = urlparse(target_url)
        host_key = f"{parsed.scheme}://{parsed.netloc}".lower()
        robots_url = f"{host_key}/robots.txt"
        return host_key, robots_url

    def is_allowed(
        self,
        url: str,
        user_agent: str = "YojanSetu-Monitor/1.0",
        robots_content: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Check if target URL is allowed by robots.txt for the given user-agent.
        
        Returns:
            (is_allowed, reason_if_blocked)
        """
        try:
            host_key, robots_url = self._get_robots_url(url)
            now = datetime.now(timezone.utc).timestamp()

            # Check cache
            cached_entry = self._cache.get(host_key)
            if cached_entry and (now - cached_entry[1]) < self.cache_ttl_seconds:
                rp = cached_entry[0]
                allowed = rp.can_fetch(user_agent, url)
                if not allowed:
                    return False, f"Disallowed by robots.txt for user-agent '{user_agent}'"
                return True, None

            # Build parser
            rp = urllib.robotparser.RobotFileParser()
            if robots_content is not None:
                rp.parse(robots_content.splitlines())
                self._cache[host_key] = (rp, now)
            else:
                # If robots_content not directly supplied, set url
                rp.set_url(robots_url)
                try:
                    rp.read()
                except Exception as e:
                    logger.warning(f"Could not read robots.txt from {robots_url}: {e}. Defaulting to allowed.")
                    # Per RFC 9309 / standard, missing or unreachable robots.txt means all access is allowed
                    rp.parse(["User-agent: *", "Allow: /"])
                self._cache[host_key] = (rp, now)

            allowed = rp.can_fetch(user_agent, url)
            if not allowed:
                return False, f"Disallowed by robots.txt for user-agent '{user_agent}'"
            return True, None
        except Exception as e:
            logger.warning(f"Robots policy evaluation encountered error: {e}. Defaulting to allowed.")
            return True, None

    def set_cached_robots(self, host_url: str, content: str) -> None:
        """Manually inject cached robots content (useful for mocking and tests)."""
        parsed = urlparse(host_url)
        host_key = f"{parsed.scheme}://{parsed.netloc}".lower()
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(content.splitlines())
        self._cache[host_key] = (rp, datetime.now(timezone.utc).timestamp())

    def clear_cache(self) -> None:
        """Clear cached robots files."""
        self._cache.clear()
