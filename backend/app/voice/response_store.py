"""
YojanSetu - Day 27: Ephemeral Voice Response Store.

Manages temporary synthesized audio responses for citizen playback with strict privacy:
1. Opaque, unguessable response tokens (zero path traversal risk).
2. Bound to specific citizen session_id and conversation_version.
3. Strict TTL expiration (default 300s).
4. Physical cleanup upon expiration or consumption.
5. Never exposes local server filesystem paths to clients.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import threading
from typing import Dict, Optional
import uuid

from app.config.voice import get_voice_settings

logger = logging.getLogger(__name__)


@dataclass
class StoredVoiceResponse:
    response_id: str
    session_id: str
    conversation_version: int
    audio_path: Path
    duration_ms: float
    sample_rate: int
    created_at: datetime
    expires_at: datetime
    is_cached_generic: bool = False

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current >= self.expires_at


class VoiceResponseStore:
    """Thread-safe registry for short-lived synthesized citizen audio responses."""

    def __init__(self, ttl_seconds: Optional[int] = None):
        self.settings = get_voice_settings()
        self.ttl_seconds = ttl_seconds or self.settings.voice_audio_response_ttl_seconds
        self._responses: Dict[str, StoredVoiceResponse] = {}
        self._lock = threading.Lock()

    def store_response(
        self,
        session_id: str,
        conversation_version: int,
        audio_path: Path,
        duration_ms: float,
        sample_rate: int = 16000,
        is_cached_generic: bool = False,
    ) -> str:
        """
        Stores an ephemeral synthesized audio reference and returns an opaque response_id.
        """
        response_id = f"resp_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.ttl_seconds)

        stored = StoredVoiceResponse(
            response_id=response_id,
            session_id=session_id,
            conversation_version=conversation_version,
            audio_path=audio_path.resolve(),
            duration_ms=duration_ms,
            sample_rate=sample_rate,
            created_at=now,
            expires_at=expires_at,
            is_cached_generic=is_cached_generic,
        )

        with self._lock:
            self._cleanup_expired_locked(now)
            self._responses[response_id] = stored

        logger.debug(f"Stored ephemeral voice response '{response_id}' for session '{session_id}' (TTL: {self.ttl_seconds}s)")
        return response_id

    def get_response_path(self, session_id: str, response_id: str) -> Optional[Path]:
        """
        Validates token ownership and returns audio Path if active and not expired.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._responses.get(response_id)
            if not entry:
                return None

            if entry.session_id != session_id:
                logger.warning(f"Unauthorized voice response access attempt: response={response_id}, caller_session={session_id}")
                return None

            if entry.is_expired(now):
                logger.info(f"Voice response '{response_id}' has expired (TTL {self.ttl_seconds}s)")
                self._delete_entry_locked(response_id)
                return None

            if not entry.audio_path.exists():
                logger.warning(f"Voice response audio file disappeared: {entry.audio_path}")
                self._delete_entry_locked(response_id)
                return None

            return entry.audio_path

    def delete_response(self, response_id: str) -> None:
        """Deletes response entry and cleans up temporary audio file if non-generic."""
        with self._lock:
            self._delete_entry_locked(response_id)

    def _delete_entry_locked(self, response_id: str) -> None:
        entry = self._responses.pop(response_id, None)
        if entry and not entry.is_cached_generic and entry.audio_path.exists():
            try:
                entry.audio_path.unlink(missing_ok=True)
                logger.debug(f"Cleaned up ephemeral voice audio: {entry.audio_path}")
            except Exception as exc:
                logger.warning(f"Failed to delete ephemeral voice audio {entry.audio_path}: {exc}")

    def _cleanup_expired_locked(self, now: datetime) -> int:
        expired_ids = [
            rid for rid, r in self._responses.items()
            if r.is_expired(now)
        ]
        for rid in expired_ids:
            self._delete_entry_locked(rid)
        return len(expired_ids)

    def cleanup_all_session_responses(self, session_id: str) -> int:
        """Cleans up all responses belonging to a session upon reset or completion."""
        with self._lock:
            sids = [
                rid for rid, r in self._responses.items()
                if r.session_id == session_id
            ]
            for rid in sids:
                self._delete_entry_locked(rid)
            return len(sids)


_response_store_instance: Optional[VoiceResponseStore] = None


def get_voice_response_store() -> VoiceResponseStore:
    """Returns singleton VoiceResponseStore instance."""
    global _response_store_instance
    if _response_store_instance is None:
        _response_store_instance = VoiceResponseStore()
    return _response_store_instance
