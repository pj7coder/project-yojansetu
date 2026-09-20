import asyncio
from contextlib import asynccontextmanager
import logging
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainRateLimiter:
    """Manages concurrency limits globally and per-domain to prevent overloading government portals."""

    def __init__(
        self,
        max_global_concurrency: int = 5,
        max_per_host_concurrency: int = 1,
    ):
        self.max_global_concurrency = max_global_concurrency
        self.max_per_host_concurrency = max_per_host_concurrency
        self._global_semaphore: Optional[asyncio.Semaphore] = None
        self._host_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    def _get_global_semaphore(self) -> asyncio.Semaphore:
        if self._global_semaphore is None:
            self._global_semaphore = asyncio.Semaphore(self.max_global_concurrency)
        return self._global_semaphore

    async def _get_host_semaphore(self, host: str) -> asyncio.Semaphore:
        async with self._lock:
            if host not in self._host_semaphores:
                self._host_semaphores[host] = asyncio.Semaphore(self.max_per_host_concurrency)
            return self._host_semaphores[host]

    def extract_host(self, url: str) -> str:
        """Extract canonical netloc host from URL."""
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return "unknown-host"

    @asynccontextmanager
    async def acquire(self, url: str):
        """Asynchronously acquire both a global concurrency slot and a per-host permit."""
        host = self.extract_host(url)
        global_sem = self._get_global_semaphore()
        host_sem = await self._get_host_semaphore(host)

        await global_sem.acquire()
        try:
            await host_sem.acquire()
            try:
                yield
            finally:
                host_sem.release()
        finally:
            global_sem.release()
