from datetime import datetime, timedelta, timezone
import logging
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import get_settings
from app.eligibility.profile import CitizenProfile
from app.sessions.models import CitizenSession, FieldRecord, FieldValueState

logger = logging.getLogger("jansetu.sessions.manager")


class SessionNotFoundError(Exception):
    """Raised when the requested session ID is not found or has expired."""
    pass


class SessionLimitExceededError(Exception):
    """Raised when maximum concurrent in-memory active sessions threshold is breached."""
    pass


class CitizenSessionManager:
    """
    In-memory citizen session manager.
    Maintains structured citizen facts across conversational turns.
    Strict privacy guarantees:
    - Process RAM only; zero database persistence.
    - Automatic TTL expiration.
    - Explicit delete/reset support.
    - Safe logging with zero personal demographic attributes.
    """

    def __init__(self, ttl_minutes: Optional[int] = None, max_sessions: Optional[int] = None):
        settings = get_settings()
        self._ttl_minutes = ttl_minutes or settings.citizen_session_ttl_minutes
        self._max_sessions = max_sessions or settings.max_active_sessions
        self._sessions: Dict[str, CitizenSession] = {}
        self._lock = RLock()

    def _cleanup_expired_locked(self, now: datetime) -> int:
        """Internal helper to sweep expired sessions while holding the lock."""
        expired_keys = [
            sid for sid, s in self._sessions.items()
            if s.is_expired(now)
        ]
        for sid in expired_keys:
            del self._sessions[sid]
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired citizen session(s)")
        return len(expired_keys)

    def cleanup_expired_sessions(self) -> int:
        """Public method to sweep expired sessions."""
        now = datetime.now(timezone.utc)
        with self._lock:
            return self._cleanup_expired_locked(now)

    def create_session(self) -> CitizenSession:
        """
        Generates a new ephemeral session with a cryptographically secure random identifier.
        """
        now = datetime.now(timezone.utc)
        session_id = uuid.uuid4().hex

        with self._lock:
            # Opportunistic cleanup if near capacity
            if len(self._sessions) >= self._max_sessions:
                self._cleanup_expired_locked(now)
                if len(self._sessions) >= self._max_sessions:
                    # Evict oldest session
                    oldest_id = next(iter(self._sessions))
                    del self._sessions[oldest_id]
                    logger.warning("Max sessions limit reached; evicted oldest session")

            expires_at = now + timedelta(minutes=self._ttl_minutes)
            session = CitizenSession(
                session_id=session_id,
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
            )
            self._sessions[session_id] = session
            logger.info(f"Created citizen session '{session_id[:8]}...' (TTL: {self._ttl_minutes}m)")
            return session

    def get_session(self, session_id: str) -> Optional[CitizenSession]:
        """
        Retrieves an active session. Returns None if unknown or expired.
        Validates identifier format to prevent traversal attacks.
        """
        clean_id = session_id.strip()
        if not clean_id or "/" in clean_id or "\\" in clean_id or ".." in clean_id:
            return None

        now = datetime.now(timezone.utc)
        with self._lock:
            session = self._sessions.get(clean_id)
            if session is None:
                return None

            if session.is_expired(now):
                del self._sessions[clean_id]
                logger.info(f"Citizen session '{clean_id[:8]}...' expired and removed on access")
                return None

            return session

    def require_session(self, session_id: str) -> CitizenSession:
        """Retrieves session or raises SessionNotFoundError."""
        session = self.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(f"Citizen session '{session_id}' not found or has expired.")
        return session

    def update_profile(
        self,
        session_id: str,
        patch: Dict[str, Any],
        clear_fields: Optional[List[str]] = None,
        source: str = "USER_INPUT",
    ) -> CitizenSession:
        """
        Applies partial profile updates with patch semantics.
        Reuses Day 14 CitizenProfile validation rules.
        Preserves boolean False (False != UNKNOWN).
        Supports corrections and explicit clearing.
        Invalidates cached candidate discovery.
        """
        session = self.require_session(session_id)
        now = datetime.now(timezone.utc)

        with self._lock:
            # 1. Build tentative profile merging existing facts with incoming patch
            merged_profile = dict(session.profile)

            # Process explicit clearing
            if clear_fields:
                for field_name in clear_fields:
                    clean_f = field_name.strip()
                    merged_profile.pop(clean_f, None)
                    session.field_states[clean_f] = FieldValueState.UNKNOWN
                    session.field_records[clean_f] = FieldRecord(
                        field_name=clean_f,
                        value=None,
                        state=FieldValueState.UNKNOWN,
                        source=source,
                        updated_at=now,
                    )

            # Merge patch values
            for k, v in patch.items():
                clean_k = k.strip()
                if v is None:
                    # None in patch means clear unless it's a known non-null
                    merged_profile.pop(clean_k, None)
                    session.field_states[clean_k] = FieldValueState.UNKNOWN
                else:
                    merged_profile[clean_k] = v

            # 2. Validate entire merged profile through Day 14 domain validator
            # Rejects impossible inputs (e.g. age < 0 or negative income)
            validated_obj = CitizenProfile(**merged_profile)
            validated_dict = validated_obj.model_dump(exclude_unset=False)

            # 3. Commit valid updates to session state
            for k, v in patch.items():
                clean_k = k.strip()
                if v is not None:
                    canonical_val = validated_dict.get(clean_k)
                    # If model_dump set None but original was provided (or vice versa), store canonical_val
                    stored_val = canonical_val if canonical_val is not None else v
                    session.profile[clean_k] = stored_val
                    session.field_states[clean_k] = FieldValueState.KNOWN
                    session.field_records[clean_k] = FieldRecord(
                        field_name=clean_k,
                        value=stored_val,
                        state=FieldValueState.KNOWN,
                        source=source,
                        updated_at=now,
                    )

            session.updated_at = now
            session.profile_version += 1
            session.invalidate_results()
            # Refresh TTL on activity
            session.expires_at = now + timedelta(minutes=self._ttl_minutes)

            logger.info(
                f"Updated profile for session '{session.session_id[:8]}...': "
                f"updated_fields={len(patch)}, "
                f"known_fields={len(session.get_known_field_names())}, "
                f"version={session.profile_version}"
            )
            return session

    def decline_field(
        self,
        session_id: str,
        field_name: str,
        reason: Optional[str] = None,
    ) -> CitizenSession:
        """
        Marks a field as explicitly DECLINED by citizen.
        Prevents the question selector from repeatedly asking for this attribute.
        """
        session = self.require_session(session_id)
        clean_f = field_name.strip()
        now = datetime.now(timezone.utc)

        with self._lock:
            session.profile.pop(clean_f, None)
            session.field_states[clean_f] = FieldValueState.DECLINED
            session.field_records[clean_f] = FieldRecord(
                field_name=clean_f,
                value=None,
                state=FieldValueState.DECLINED,
                source="USER_REFUSAL",
                updated_at=now,
            )
            session.updated_at = now
            session.profile_version += 1
            session.expires_at = now + timedelta(minutes=self._ttl_minutes)

            logger.info(f"Citizen declined field '{clean_f}' in session '{session.session_id[:8]}...'")
            return session

    def record_asked_field(self, session_id: str, field_name: str) -> CitizenSession:
        """Tracks that a field question was presented to citizen to penalize repetition."""
        session = self.require_session(session_id)
        clean_f = field_name.strip()
        with self._lock:
            if clean_f not in session.asked_fields:
                session.asked_fields.append(clean_f)
            session.field_ask_counts[clean_f] = session.field_ask_counts.get(clean_f, 0) + 1
            return session

    def set_need_text(self, session_id: str, need_text: Optional[str]) -> CitizenSession:
        """Updates expressed citizen need / intent for semantic candidate ranking."""
        session = self.require_session(session_id)
        now = datetime.now(timezone.utc)
        with self._lock:
            session.need_text = need_text.strip() if need_text else None
            session.updated_at = now
            session.expires_at = now + timedelta(minutes=self._ttl_minutes)
            return session

    def delete_session(self, session_id: str) -> bool:
        """Explicitly deletes/resets citizen session state."""
        clean_id = session_id.strip()
        with self._lock:
            if clean_id in self._sessions:
                del self._sessions[clean_id]
                logger.info(f"Citizen session '{clean_id[:8]}...' explicitly deleted")
                return True
            return False

    def count_active_sessions(self) -> int:
        """Returns count of non-expired sessions currently in RAM."""
        now = datetime.now(timezone.utc)
        with self._lock:
            return sum(1 for s in self._sessions.values() if not s.is_expired(now))

    def set_pending_confirmation(
        self,
        session_id: str,
        confirmation: Dict[str, Any],
        pending_updates: Optional[List[Dict[str, Any]]] = None,
    ) -> CitizenSession:
        """Sets an active confirmation request and optional queued candidate facts in ephemeral RAM."""
        session = self.require_session(session_id)
        now = datetime.now(timezone.utc)
        with self._lock:
            session.pending_confirmation = confirmation
            if pending_updates is not None:
                session.pending_profile_updates = pending_updates
            session.updated_at = now
            session.expires_at = now + timedelta(minutes=self._ttl_minutes)
            return session

    def confirm_pending(
        self,
        session_id: str,
        decision: str,
    ) -> Tuple[CitizenSession, bool, Optional[str]]:
        """
        Applies or rejects active pending confirmation.
        If YES: patches session.profile with the confirmed field value, logs to history, clears pending.
        If NO: discards active pending confirmation.
        Returns: (session, was_accepted, confirmed_field)
        """
        session = self.require_session(session_id)
        now = datetime.now(timezone.utc)

        with self._lock:
            pending = session.pending_confirmation
            if not pending:
                return (session, False, None)

            confirmed_field = pending.get("field")
            proposed_val = pending.get("proposed_value")

            if decision.upper() == "YES" and confirmed_field:
                patch = {confirmed_field: proposed_val}
                for cand in session.pending_profile_updates:
                    if cand.get("field") == confirmed_field:
                        if cand.get("frequency") and confirmed_field in ("annual_income", "family_income"):
                            patch[f"{confirmed_field}_frequency"] = cand.get("frequency")
                        if cand.get("unit") and confirmed_field == "land_holding":
                            patch["land_holding_unit"] = cand.get("unit")
                        break

                self.update_profile(session_id, patch=patch, source="CONFIRMED_USER_INPUT")
                session.update_history.append({
                    "field": confirmed_field,
                    "value": proposed_val,
                    "timestamp": now.isoformat(),
                    "status": "CONFIRMED",
                    "reason": pending.get("reason_code"),
                })
                session.pending_confirmation = None
                session.pending_profile_updates = [
                    c for c in session.pending_profile_updates if c.get("field") != confirmed_field
                ]
                return (session, True, confirmed_field)

            elif decision.upper() == "NO":
                session.update_history.append({
                    "field": confirmed_field,
                    "proposed_value": proposed_val,
                    "timestamp": now.isoformat(),
                    "status": "REJECTED_BY_CITIZEN",
                    "reason": pending.get("reason_code"),
                })
                session.pending_confirmation = None
                session.pending_profile_updates = [
                    c for c in session.pending_profile_updates if c.get("field") != confirmed_field
                ]
                session.updated_at = now
                return (session, False, confirmed_field)

            return (session, False, None)

    def clear_pending_confirmation(self, session_id: str) -> CitizenSession:
        """Clears any pending confirmation for session."""
        session = self.require_session(session_id)
        now = datetime.now(timezone.utc)
        with self._lock:
            session.pending_confirmation = None
            session.updated_at = now
            return session

    def reset_session_conversation(self, session_id: str) -> CitizenSession:
        """Resets conversational state and profile facts for a fresh start-over turn."""
        session = self.require_session(session_id)
        now = datetime.now(timezone.utc)
        with self._lock:
            session.reset_conversation()
            session.updated_at = now
            session.expires_at = now + timedelta(minutes=self._ttl_minutes)
            return session

    def record_turn_processed(self, session_id: str, turn_id: str) -> bool:
        """
        Records a client_turn_id to prevent double-processing on network retries.
        Returns True if turn is new and recorded, False if already processed (duplicate).
        """
        session = self.require_session(session_id)
        with self._lock:
            if turn_id in session.processed_turn_ids:
                return False
            session.processed_turn_ids.append(turn_id)
            if len(session.processed_turn_ids) > 50:
                session.processed_turn_ids = session.processed_turn_ids[-50:]
            return True


# Singleton instance
_SESSION_MANAGER_INSTANCE: Optional[CitizenSessionManager] = None
_SESSION_MANAGER_LOCK = RLock()


def get_session_manager() -> CitizenSessionManager:
    """Returns the process-level singleton instance of CitizenSessionManager."""
    global _SESSION_MANAGER_INSTANCE
    if _SESSION_MANAGER_INSTANCE is None:
        with _SESSION_MANAGER_LOCK:
            if _SESSION_MANAGER_INSTANCE is None:
                _SESSION_MANAGER_INSTANCE = CitizenSessionManager()
    return _SESSION_MANAGER_INSTANCE
