from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from threading import RLock
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.eligibility.models import CompiledScheme

logger = logging.getLogger("jansetu.cache.rules")


@dataclass(frozen=True)
class CachedRuleEntry:
    """Immutable cached entry wrapping a compiled scheme AST and version metadata."""
    scheme_id: str
    scheme_version: str
    version_hash: str
    compiled_scheme: CompiledScheme
    cached_at: datetime
    updated_at: Optional[datetime] = None


@dataclass
class CacheMetrics:
    """Operational metrics for rule cache performance without storing citizen data."""
    hits: int = 0
    misses: int = 0
    loads: int = 0
    refreshes: int = 0
    compile_failures: int = 0


class VerifiedRuleCache:
    """
    Thread-safe in-memory cache for compiled verified scheme rule trees.
    Eliminates redundant database deserialization and AST compilation on citizen requests.
    Supports fallback to PostgreSQL, stale artifact detection, and atomic refreshes.
    """

    def __init__(self, max_entries: Optional[int] = None):
        settings = get_settings()
        self._max_entries = max_entries or settings.rule_cache_max_entries
        self._cache: Dict[str, CachedRuleEntry] = {}
        self._metrics = CacheMetrics()
        self._lock = RLock()

    @property
    def metrics(self) -> CacheMetrics:
        with self._lock:
            return CacheMetrics(
                hits=self._metrics.hits,
                misses=self._metrics.misses,
                loads=self._metrics.loads,
                refreshes=self._metrics.refreshes,
                compile_failures=self._metrics.compile_failures,
            )

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Returns snapshot of cache performance metrics for admin/monitoring."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "hits": self._metrics.hits,
                "misses": self._metrics.misses,
                "loads": self._metrics.loads,
                "refreshes": self._metrics.refreshes,
                "compile_failures": self._metrics.compile_failures,
            }

    @staticmethod
    def _compute_version_hash(raw_scheme: Dict[str, Any]) -> str:
        """Computes or extracts a deterministic version hash from verified scheme data."""
        review_info = raw_scheme.get("review", {})
        if "artifact_sha256" in review_info:
            return str(review_info["artifact_sha256"])
        if "verified_artifact_sha256" in raw_scheme:
            return str(raw_scheme["verified_artifact_sha256"])
        
        # Fallback to sha256 hash of canonical scheme JSON
        canonical = raw_scheme.get("canonical_scheme") or raw_scheme
        encoded = json.dumps(canonical, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, scheme_id: str, session: Optional[Session] = None) -> Optional[CompiledScheme]:
        """
        Retrieves a compiled scheme by ID from memory.
        If cache miss and DB session is provided, safely falls back to PostgreSQL,
        compiles the rule AST, caches the immutable object, and returns it.
        """
        clean_id = scheme_id.strip()
        with self._lock:
            entry = self._cache.get(clean_id)
            if entry is not None:
                self._metrics.hits += 1
                return entry.compiled_scheme
            self._metrics.misses += 1

        # Cache Miss: fallback to DB if session provided
        if session is None:
            return None

        return self._load_compile_and_cache(clean_id, session)

    def get_many(self, scheme_ids: List[str], session: Optional[Session] = None) -> Dict[str, CompiledScheme]:
        """
        Bulk retrieval of compiled schemes for candidate filtering.
        Avoids redundant lock acquisitions and optimizes candidate evaluation throughput.
        """
        results: Dict[str, CompiledScheme] = {}
        missing_ids: List[str] = []

        with self._lock:
            for sid in scheme_ids:
                clean_id = sid.strip()
                entry = self._cache.get(clean_id)
                if entry is not None:
                    self._metrics.hits += 1
                    results[clean_id] = entry.compiled_scheme
                else:
                    self._metrics.misses += 1
                    missing_ids.append(clean_id)

        if missing_ids and session is not None:
            for mid in missing_ids:
                compiled = self._load_compile_and_cache(mid, session)
                if compiled is not None:
                    results[mid] = compiled

        return results

    def _load_compile_and_cache(self, scheme_id: str, session: Session) -> Optional[CompiledScheme]:
        """Loads verified scheme from DB/disk, compiles AST, and stores in cache safely."""
        from app.eligibility.compiler import EligibilityRuleCompiler
        from app.eligibility.repository import SchemeNotFoundError, UnverifiedSchemeAccessError, VerifiedSchemeRepository

        try:
            raw_verified = VerifiedSchemeRepository.get_verified_scheme(session, scheme_id)
        except (SchemeNotFoundError, UnverifiedSchemeAccessError) as e:
            logger.debug(f"Rule cache could not load scheme '{scheme_id}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected database error loading scheme '{scheme_id}' for cache: {e}")
            return None

        try:
            compiled = EligibilityRuleCompiler.compile_scheme(raw_verified)
            version_hash = self._compute_version_hash(raw_verified)
            canonical = raw_verified.get("canonical_scheme") or raw_verified
            scheme_ver = str(canonical.get("scheme_version", "1.0"))
            
            entry = CachedRuleEntry(
                scheme_id=compiled.scheme_id,
                scheme_version=scheme_ver,
                version_hash=version_hash,
                compiled_scheme=compiled,
                cached_at=datetime.now(timezone.utc),
            )

            with self._lock:
                # Evict oldest if limit reached
                if len(self._cache) >= self._max_entries and compiled.scheme_id not in self._cache:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

                self._cache[compiled.scheme_id] = entry
                self._metrics.loads += 1
                logger.info(f"Rule cache loaded scheme '{compiled.scheme_id}' (version={scheme_ver}, hash={version_hash[:8]})")

            return compiled
        except Exception as e:
            with self._lock:
                self._metrics.compile_failures += 1
            logger.error(f"Rule compilation failure for scheme '{scheme_id}': {e}")
            return None

    def refresh_scheme(self, scheme_id: str, session: Optional[Session] = None) -> Optional[CompiledScheme]:
        """
        Refreshes a specific scheme in cache when new human verification occurs or rules change.
        If session is provided, immediately reloads and recompiles.
        If session is None, invalidates the entry so the next request reloads from DB.
        """
        clean_id = scheme_id.strip()
        if session is not None:
            compiled = self._load_compile_and_cache(clean_id, session)
            with self._lock:
                self._metrics.refreshes += 1
            return compiled
        else:
            with self._lock:
                if clean_id in self._cache:
                    del self._cache[clean_id]
                self._metrics.refreshes += 1
            logger.info(f"Rule cache invalidated scheme '{clean_id}' for lazy refresh")
            return None

    def refresh_all(self, session: Optional[Session] = None) -> int:
        """
        Refreshes all cached schemes or warms cache for all active verified schemes.
        """
        with self._lock:
            self._metrics.refreshes += 1
            if session is None:
                count = len(self._cache)
                self._cache.clear()
                logger.info(f"Rule cache cleared {count} entries for refresh_all")
                return count

        # If session provided, reload all existing cached schemes
        with self._lock:
            existing_ids = list(self._cache.keys())

        refreshed_count = 0
        for sid in existing_ids:
            if self._load_compile_and_cache(sid, session) is not None:
                refreshed_count += 1

        return refreshed_count

    def invalidate(self, scheme_id: str) -> bool:
        """Removes a scheme from cache (e.g. on deactivation)."""
        clean_id = scheme_id.strip()
        with self._lock:
            if clean_id in self._cache:
                del self._cache[clean_id]
                logger.info(f"Rule cache invalidated scheme '{clean_id}'")
                return True
            return False

    def clear(self) -> None:
        """Clears all cached entries and resets entry state."""
        with self._lock:
            self._cache.clear()
            logger.info("Rule cache cleared completely")

    def contains(self, scheme_id: str) -> bool:
        """Checks whether a scheme is currently loaded in memory."""
        with self._lock:
            return scheme_id.strip() in self._cache

    def is_stale(self, scheme_id: str, latest_version_hash: str) -> bool:
        """Determines if the cached compiled AST has become stale compared to latest artifact hash."""
        with self._lock:
            entry = self._cache.get(scheme_id.strip())
            if entry is None:
                return True
            return entry.version_hash != latest_version_hash


# Singleton instance
_RULE_CACHE_INSTANCE: Optional[VerifiedRuleCache] = None
_CACHE_INIT_LOCK = RLock()


def get_rule_cache() -> VerifiedRuleCache:
    """Returns the process-level singleton instance of VerifiedRuleCache."""
    global _RULE_CACHE_INSTANCE
    if _RULE_CACHE_INSTANCE is None:
        with _CACHE_INIT_LOCK:
            if _RULE_CACHE_INSTANCE is None:
                _RULE_CACHE_INSTANCE = VerifiedRuleCache()
    return _RULE_CACHE_INSTANCE
