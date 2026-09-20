from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.source import Source
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_monitor_run import SourceMonitorRun
from app.database.models.source_monitor_state import SourceMonitorState
from app.database.models.source_url import SourceUrl


class SourceMonitorRepository:
    """Repository for managing source monitoring operational state, runs, and change events."""

    def get_or_create_state(self, db: Session, source_url_id: uuid.UUID) -> SourceMonitorState:
        """Fetch existing monitoring state or initialize a fresh NEVER_CHECKED state."""
        state = db.execute(
            select(SourceMonitorState).where(SourceMonitorState.source_url_id == source_url_id)
        ).scalar_one_or_none()

        if state is None:
            state = SourceMonitorState(
                source_url_id=source_url_id,
                monitor_status="NEVER_CHECKED",
                consecutive_failures=0,
                next_check_at=datetime.now(timezone.utc),
            )
            db.add(state)
            db.commit()
            db.refresh(state)

        return state

    def ensure_states_for_all_urls(self, db: Session) -> int:
        """Initialize missing SourceMonitorState rows for all active SourceUrls."""
        stmt = (
            select(SourceUrl.id)
            .outerjoin(SourceMonitorState, SourceUrl.id == SourceMonitorState.source_url_id)
            .where(SourceMonitorState.id.is_(None))
        )
        missing_ids = list(db.execute(stmt).scalars().all())
        count = 0
        for sid in missing_ids:
            state = SourceMonitorState(
                source_url_id=sid,
                monitor_status="NEVER_CHECKED",
                consecutive_failures=0,
                next_check_at=datetime.now(timezone.utc),
            )
            db.add(state)
            count += 1
        if count > 0:
            db.commit()
        return count

    def get_due_monitoring_sources(
        self,
        db: Session,
        now: Optional[datetime] = None,
        limit: int = 10,
        lock: bool = True,
    ) -> List[Tuple[SourceUrl, SourceMonitorState]]:
        """Query active approved SourceUrls due for check using row-level locking (SKIP LOCKED).
        
        Guarantees:
        - Source is active
        - SourceUrl is active and crawl_allowed is True
        - State monitor_status != 'DISABLED'
        - State next_check_at <= now OR next_check_at IS NULL OR monitor_status == 'NEVER_CHECKED'
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # First ensure all active URLs have state rows
        self.ensure_states_for_all_urls(db)

        query = (
            select(SourceUrl, SourceMonitorState)
            .join(Source, SourceUrl.source_id == Source.id)
            .join(SourceMonitorState, SourceUrl.id == SourceMonitorState.source_url_id)
            .where(
                Source.enabled.is_(True),
                SourceUrl.enabled.is_(True),
                SourceUrl.crawl_allowed.is_(True),
                SourceMonitorState.monitor_status != "DISABLED",
                (
                    (SourceMonitorState.next_check_at.is_(None))
                    | (SourceMonitorState.next_check_at <= now)
                    | (SourceMonitorState.monitor_status == "NEVER_CHECKED")
                ),
            )
            .order_by(
                # Prioritize never checked or lowest next_check_at
                SourceMonitorState.next_check_at.asc().nullsfirst(),
                SourceUrl.priority.asc(),
            )
            .limit(limit)
        )

        if lock:
            # Row lock on the state row to prevent concurrent workers picking same target
            query = query.with_for_update(of=SourceMonitorState, skip_locked=True)

        results = list(db.execute(query).all())
        return [(r[0], r[1]) for r in results]

    def record_run(self, db: Session, run: SourceMonitorRun) -> SourceMonitorRun:
        """Insert historical audit run record."""
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def update_state(self, db: Session, state: SourceMonitorState) -> SourceMonitorState:
        """Update operational state."""
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def create_change_event(
        self,
        db: Session,
        event: SourceChangeEvent,
        idempotency_key: Optional[str] = None,
    ) -> SourceChangeEvent:
        """Create a SourceChangeEvent if no pending duplicate exists for this URL and fingerprint."""
        if idempotency_key:
            existing_by_key = db.execute(
                select(SourceChangeEvent).where(SourceChangeEvent.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing_by_key:
                return existing_by_key

        body_fp = ""
        if event.new_state_reference and isinstance(event.new_state_reference, dict):
            body_fp = event.new_state_reference.get("body_fingerprint", "")

        # Check existing PENDING_ANALYSIS change events for the same source_url_id
        pending_stmt = (
            select(SourceChangeEvent)
            .where(
                SourceChangeEvent.source_url_id == event.source_url_id,
                SourceChangeEvent.processing_status == "PENDING_ANALYSIS",
            )
        )
        existing_events = list(db.execute(pending_stmt).scalars().all())

        for ex in existing_events:
            if idempotency_key and ex.idempotency_key == idempotency_key:
                return ex
            if body_fp and ex.new_state_reference and isinstance(ex.new_state_reference, dict):
                if ex.new_state_reference.get("body_fingerprint") == body_fp:
                    return ex

        # If not duplicate, persist
        if not event.idempotency_key and idempotency_key:
            event.idempotency_key = idempotency_key

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_state_by_source_url_id(
        self, db: Session, source_url_id: uuid.UUID
    ) -> Optional[SourceMonitorState]:
        """Fetch state by source_url_id."""
        stmt = (
            select(SourceMonitorState)
            .where(SourceMonitorState.source_url_id == source_url_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_recent_runs_by_source_url_id(
        self, db: Session, source_url_id: uuid.UUID, limit: int = 10
    ) -> List[SourceMonitorRun]:
        """Fetch latest N monitoring runs for a source URL."""
        stmt = (
            select(SourceMonitorRun)
            .where(SourceMonitorRun.source_url_id == source_url_id)
            .order_by(desc(SourceMonitorRun.started_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def list_states(
        self,
        db: Session,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        due_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[SourceMonitorState], int]:
        """List states with optional filters and pagination."""
        stmt = select(SourceMonitorState).join(
            SourceUrl, SourceMonitorState.source_url_id == SourceUrl.id
        )

        if status:
            stmt = stmt.where(SourceMonitorState.monitor_status == status)
        if priority:
            stmt = stmt.where(SourceUrl.priority == priority)
        if due_only:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(
                (SourceMonitorState.next_check_at.is_(None))
                | (SourceMonitorState.next_check_at <= now)
            )

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(total_stmt).scalar_one()

        paged_stmt = (
            stmt.order_by(SourceMonitorState.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(db.execute(paged_stmt).scalars().all())
        return items, total

    def list_change_events(
        self,
        db: Session,
        processing_status: Optional[str] = None,
        change_type: Optional[str] = None,
        source_url_id: Optional[uuid.UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[SourceChangeEvent], int]:
        """List change events with filtering and pagination."""
        stmt = select(SourceChangeEvent)

        if processing_status:
            stmt = stmt.where(SourceChangeEvent.processing_status == processing_status)
        if change_type:
            stmt = stmt.where(SourceChangeEvent.change_type == change_type)
        if source_url_id:
            stmt = stmt.where(SourceChangeEvent.source_url_id == source_url_id)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.execute(total_stmt).scalar_one()

        paged_stmt = (
            stmt.order_by(desc(SourceChangeEvent.detected_at))
            .offset(offset)
            .limit(limit)
        )
        items = list(db.execute(paged_stmt).scalars().all())
        return items, total

    def get_source_health_summary(self, db: Session) -> Dict[str, Any]:
        """Aggregate health metrics across all monitored sources."""
        total_sources = db.execute(
            select(func.count()).select_from(SourceUrl).where(SourceUrl.enabled.is_(True))
        ).scalar_one()

        never_checked = db.execute(
            select(func.count())
            .select_from(SourceMonitorState)
            .where(SourceMonitorState.monitor_status == "NEVER_CHECKED")
        ).scalar_one()

        healthy = db.execute(
            select(func.count())
            .select_from(SourceMonitorState)
            .where(
                SourceMonitorState.monitor_status.in_(["UNCHANGED", "CHANGED"]),
                SourceMonitorState.consecutive_failures == 0,
            )
        ).scalar_one()

        temporarily_failing = db.execute(
            select(func.count())
            .select_from(SourceMonitorState)
            .where(
                SourceMonitorState.consecutive_failures > 0,
                SourceMonitorState.consecutive_failures < 5,
            )
        ).scalar_one()

        long_term_failing = db.execute(
            select(func.count())
            .select_from(SourceMonitorState)
            .where(SourceMonitorState.consecutive_failures >= 5)
        ).scalar_one()

        blocked = db.execute(
            select(func.count())
            .select_from(SourceMonitorState)
            .where(
                SourceMonitorState.monitor_status.in_(
                    ["BLOCKED_BY_POLICY", "ACCESS_FORBIDDEN", "AUTH_REQUIRED"]
                )
            )
        ).scalar_one()

        disabled = db.execute(
            select(func.count())
            .select_from(SourceMonitorState)
            .where(SourceMonitorState.monitor_status == "DISABLED")
        ).scalar_one()

        pending_change_events = db.execute(
            select(func.count())
            .select_from(SourceChangeEvent)
            .where(SourceChangeEvent.processing_status == "PENDING_ANALYSIS")
        ).scalar_one()

        return {
            "total_monitored_sources": total_sources,
            "healthy": healthy,
            "temporarily_failing": temporarily_failing,
            "long_term_failing": long_term_failing,
            "blocked": blocked,
            "never_checked": never_checked,
            "disabled": disabled,
            "pending_change_events": pending_change_events,
        }
