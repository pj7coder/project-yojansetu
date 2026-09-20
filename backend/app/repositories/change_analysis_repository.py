from datetime import datetime, timezone, timedelta
import logging
from typing import List, Optional, Tuple
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.database.models.discovered_resource import DiscoveredResource
from app.database.models.source_change_analysis import SourceChangeAnalysis
from app.database.models.source_change_event import SourceChangeEvent

logger = logging.getLogger(__name__)


class ChangeAnalysisRepository:
    """Repository handling persistence, event claiming, and querying for Day 18 analysis."""

    def claim_next_pending_event(
        self,
        db: Session,
        lease_seconds: int = 300,
    ) -> Optional[SourceChangeEvent]:
        """Claim the next PENDING_ANALYSIS event using SELECT FOR UPDATE SKIP LOCKED.
        
        Also recovers stale ANALYZING claims older than lease_seconds.
        """
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(seconds=lease_seconds)

        # 1. Look for pending events
        stmt = (
            select(SourceChangeEvent)
            .where(
                (SourceChangeEvent.processing_status == "PENDING_ANALYSIS")
                | (
                    (SourceChangeEvent.processing_status == "ANALYZING")
                    & (SourceChangeEvent.updated_at < stale_threshold)
                )
            )
            .order_by(SourceChangeEvent.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        event = db.execute(stmt).scalars().first()
        if event:
            event.processing_status = "ANALYZING"
            event.updated_at = now
            db.commit()
            db.refresh(event)
        return event

    def get_analysis_by_id(
        self,
        db: Session,
        analysis_id: uuid.UUID,
    ) -> Optional[SourceChangeAnalysis]:
        return db.get(SourceChangeAnalysis, analysis_id)

    def get_analysis_by_event_id(
        self,
        db: Session,
        event_id: uuid.UUID,
    ) -> Optional[SourceChangeAnalysis]:
        stmt = select(SourceChangeAnalysis).where(SourceChangeAnalysis.change_event_id == event_id)
        return db.execute(stmt).scalars().first()

    def list_analyses(
        self,
        db: Session,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Tuple[List[SourceChangeAnalysis], int]:
        query = select(SourceChangeAnalysis)
        count_query = select(func.count()).select_from(SourceChangeAnalysis)

        if status:
            query = query.where(SourceChangeAnalysis.status == status)
            count_query = count_query.where(SourceChangeAnalysis.status == status)

        total = db.execute(count_query).scalar_one()
        analyses = (
            db.execute(
                query.order_by(desc(SourceChangeAnalysis.created_at))
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return list(analyses), total

    def list_discovered_resources(
        self,
        db: Session,
        limit: int = 50,
        offset: int = 0,
        relevance_status: Optional[str] = None,
        resource_type: Optional[str] = None,
        fetch_status: Optional[str] = None,
        change_event_id: Optional[uuid.UUID] = None,
        source_url_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[DiscoveredResource], int]:
        query = select(DiscoveredResource)
        count_query = select(func.count()).select_from(DiscoveredResource)

        if relevance_status:
            query = query.where(DiscoveredResource.relevance_status == relevance_status)
            count_query = count_query.where(DiscoveredResource.relevance_status == relevance_status)
        if resource_type:
            query = query.where(DiscoveredResource.resource_type == resource_type)
            count_query = count_query.where(DiscoveredResource.resource_type == resource_type)
        if fetch_status:
            query = query.where(DiscoveredResource.fetch_status == fetch_status)
            count_query = count_query.where(DiscoveredResource.fetch_status == fetch_status)
        if change_event_id:
            query = query.where(DiscoveredResource.change_event_id == change_event_id)
            count_query = count_query.where(DiscoveredResource.change_event_id == change_event_id)
        if source_url_id:
            query = query.where(DiscoveredResource.source_url_id == source_url_id)
            count_query = count_query.where(DiscoveredResource.source_url_id == source_url_id)

        total = db.execute(count_query).scalar_one()
        resources = (
            db.execute(
                query.order_by(desc(DiscoveredResource.created_at))
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return list(resources), total

    def get_resource_by_id(
        self,
        db: Session,
        resource_id: uuid.UUID,
    ) -> Optional[DiscoveredResource]:
        return db.get(DiscoveredResource, resource_id)

    def update_resource_relevance(
        self,
        db: Session,
        resource_id: uuid.UUID,
        new_status: str,
        reason_text: str,
    ) -> Optional[DiscoveredResource]:
        res = db.get(DiscoveredResource, resource_id)
        if not res:
            return None
        res.relevance_status = new_status
        current_reason = res.relevance_reason or {}
        current_reason["manual_override"] = {
            "status": new_status,
            "reason": reason_text,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        res.relevance_reason = current_reason
        db.commit()
        db.refresh(res)
        return res
