from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminOverviewResponse,
    ConflictOverview,
    CriticalIssue,
    DocumentOverview,
    PipelineStageCount,
    ReviewOverview,
    SchemeOverview,
    SourceOverview,
)
from app.database.models.document import Document
from app.database.models.human_review_item import HumanReviewItem
from app.database.models.human_review_session import HumanReviewSession
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_change_set import SchemeChangeSet
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.source import Source
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.source_monitor_state import SourceMonitorState
from app.database.models.validation_issue import ValidationIssue

logger = logging.getLogger("yojansetu.admin.dashboard")


class AdminDashboardService:
    """Consolidated operational overview aggregator for YojanSetu administrative control center."""

    STAGE_STATUS_MAP = {
        "INGESTION": ["RECEIVED", "VALIDATING"],
        "DUPLICATE_CHECK": ["READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING"],
        "PARSER": ["READY_FOR_PARSING", "PARSING"],
        "OCR": ["READY_FOR_OCR_CHECK", "OCR_CHECKING", "OCR_RUNNING"],
        "CHUNKING": ["READY_FOR_CHUNKING", "CHUNKING"],
        "EXTRACTION": ["READY_FOR_EXTRACTION", "EXTRACTING"],
        "NORMALIZATION": ["READY_FOR_NORMALIZATION", "NORMALIZING"],
        "VALIDATION": ["READY_FOR_VALIDATION"],
        "VERIFICATION": ["READY_FOR_VERIFICATION", "VERIFYING"],
        "HUMAN_REVIEW": ["READY_FOR_HUMAN_REVIEW", "IN_REVIEW"],
    }

    FAILED_STATUS_MAP = {
        "INGESTION": ["INVALID"],
        "DUPLICATE_CHECK": [],
        "PARSER": ["PARSING_FAILED"],
        "OCR": ["OCR_FAILED"],
        "CHUNKING": ["CHUNKING_FAILED"],
        "EXTRACTION": ["EXTRACTION_FAILED"],
        "NORMALIZATION": ["NORMALIZATION_FAILED"],
        "VALIDATION": ["VALIDATION_FAILED"],
        "VERIFICATION": ["FAILED"],
        "HUMAN_REVIEW": ["HUMAN_REJECTED"],
    }

    PROCESSING_STATUSES = {
        "VALIDATING",
        "DUPLICATE_CHECKING",
        "PARSING",
        "OCR_CHECKING",
        "OCR_RUNNING",
        "CHUNKING",
        "EXTRACTING",
        "NORMALIZING",
        "VERIFYING",
        "IN_REVIEW",
    }

    FAILED_STATUSES = {
        "INVALID",
        "PARSING_FAILED",
        "OCR_FAILED",
        "CHUNKING_FAILED",
        "EXTRACTION_FAILED",
        "NORMALIZATION_FAILED",
        "VALIDATION_FAILED",
        "FAILED",
    }

    _cached_overview: Optional[AdminOverviewResponse] = None
    _cached_overview_ts: float = 0.0
    CACHE_TTL_SECONDS: float = 5.0

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cached_overview = None
        cls._cached_overview_ts = 0.0

    def get_overview(self, db: Session, force_refresh: bool = False) -> AdminOverviewResponse:
        import time as _t
        cur_t = _t.time()
        if not force_refresh and AdminDashboardService._cached_overview and (cur_t - AdminDashboardService._cached_overview_ts) < self.CACHE_TTL_SECONDS:
            return AdminDashboardService._cached_overview

        now = datetime.now(timezone.utc)
        reasons: List[str] = []
        critical_issues: List[CriticalIssue] = []

        # 1. Sources Overview
        source_total = db.scalar(select(func.count()).select_from(Source)) or 0
        source_active = db.scalar(select(func.count()).select_from(Source).where(Source.enabled.is_(True))) or 0
        
        failing_sources_stmt = select(func.count()).select_from(SourceMonitorState).where(
            or_(
                SourceMonitorState.monitor_status == "CHECK_FAILED",
                SourceMonitorState.consecutive_failures > 0,
            )
        )
        source_failing = db.scalar(failing_sources_stmt) or 0

        yesterday = now - timedelta(hours=24)
        recent_changes_stmt = select(func.count()).select_from(SourceChangeEvent).where(
            SourceChangeEvent.created_at >= yesterday
        )
        source_recently_changed = db.scalar(recent_changes_stmt) or 0

        sources_overview = SourceOverview(
            total=source_total,
            active=source_active,
            failing=source_failing,
            recently_changed=source_recently_changed,
        )

        if source_failing > 0:
            reasons.append(f"{source_failing} official source(s) report check failures")
            # Surface failing source issue
            failing_states = db.execute(
                select(SourceMonitorState)
                .where(SourceMonitorState.consecutive_failures > 0)
                .order_by(SourceMonitorState.consecutive_failures.desc())
                .limit(3)
            ).scalars().all()
            for fs in failing_states:
                critical_issues.append(
                    CriticalIssue(
                        id=str(fs.id),
                        category="SOURCE",
                        severity="WARNING" if fs.consecutive_failures < 3 else "CRITICAL",
                        title=f"Source check failing ({fs.consecutive_failures} errors)",
                        description=f"Source URL {fs.source_url_id} last failed at {fs.last_attempt_at or 'recently'}",
                        link=f"/admin/sources",
                        created_at=(fs.last_attempt_at or now).isoformat(),
                    )
                )

        # 2. Documents Overview (Single optimized GROUP BY query replaces 40+ separate queries)
        status_rows = db.execute(
            select(
                Document.processing_status,
                func.count(),
                func.min(Document.updated_at),
            ).group_by(Document.processing_status)
        ).all()
        status_map: Dict[str, int] = {}
        oldest_map: Dict[str, datetime] = {}
        for status_val, cnt, min_dt in status_rows:
            if status_val:
                status_map[status_val] = cnt
                if min_dt:
                    oldest_map[status_val] = min_dt

        doc_total = sum(status_map.values())
        doc_processing = sum(status_map.get(s, 0) for s in self.PROCESSING_STATUSES)
        doc_failed = sum(status_map.get(s, 0) for s in self.FAILED_STATUSES)
        doc_waiting_review = status_map.get("READY_FOR_HUMAN_REVIEW", 0)

        docs_overview = DocumentOverview(
            total=doc_total,
            processing=doc_processing,
            failed=doc_failed,
            waiting_review=doc_waiting_review,
        )

        if doc_failed > 0:
            reasons.append(f"{doc_failed} document(s) in failed processing states")
            failed_docs = db.execute(
                select(Document)
                .where(Document.processing_status.in_(self.FAILED_STATUSES))
                .order_by(Document.updated_at.desc())
                .limit(3)
            ).scalars().all()
            for fd in failed_docs:
                critical_issues.append(
                    CriticalIssue(
                        id=str(fd.id),
                        category="DOCUMENT",
                        severity="CRITICAL" if fd.processing_status in ["PARSING_FAILED", "OCR_FAILED"] else "WARNING",
                        title=f"{fd.processing_status}: {fd.document_code}",
                        description=fd.failure_reason or f"Document processing halted at {fd.processing_status}",
                        link=f"/admin/documents?status={fd.processing_status}",
                        created_at=(fd.updated_at or now).isoformat(),
                    )
                )

        # 3. Pipeline Stages Breakdown (Computed in-memory in microseconds)
        pipeline_stages: List[PipelineStageCount] = []
        for stage_name, active_statuses in self.STAGE_STATUS_MAP.items():
            failed_statuses = self.FAILED_STATUS_MAP.get(stage_name, [])
            
            waiting_status = active_statuses[0] if active_statuses else None
            processing_statuses = active_statuses[1:] if len(active_statuses) > 1 else []

            w_count = status_map.get(waiting_status, 0) if waiting_status else 0
            p_count = sum(status_map.get(s, 0) for s in processing_statuses)
            f_count = sum(status_map.get(s, 0) for s in failed_statuses)

            oldest_sec: Optional[int] = None
            if waiting_status and w_count > 0 and waiting_status in oldest_map:
                oldest_dt = oldest_map[waiting_status]
                diff = (now - oldest_dt).total_seconds()
                oldest_sec = max(0, int(diff))

            pipeline_stages.append(
                PipelineStageCount(
                    stage=stage_name,
                    waiting=w_count,
                    processing=p_count,
                    failed=f_count,
                    oldest_waiting_seconds=oldest_sec,
                )
            )

        # 4. Human Review Overview
        rev_pending = db.scalar(
            select(func.count()).select_from(HumanReviewSession).where(
                HumanReviewSession.status.in_(["OPEN", "IN_PROGRESS"])
            )
        ) or 0
        rev_in_review = db.scalar(
            select(func.count()).select_from(HumanReviewSession).where(
                HumanReviewSession.status == "IN_PROGRESS"
            )
        ) or 0

        # Critical review issues: pending review items that are contradictions or OCR risks
        rev_critical = db.scalar(
            select(func.count())
            .select_from(HumanReviewItem)
            .join(HumanReviewSession, HumanReviewItem.review_session_id == HumanReviewSession.id)
            .where(
                and_(
                    HumanReviewSession.status.in_(["OPEN", "IN_PROGRESS"]),
                    HumanReviewItem.decision == "PENDING",
                    or_(
                        HumanReviewItem.verification_result == "CONTRADICTED",
                        HumanReviewItem.risk_level.in_(["CRITICAL", "HIGH"]),
                        HumanReviewItem.ocr_risk.is_(True),
                    ),
                )
            )
        ) or 0

        reviews_overview = ReviewOverview(
            pending=rev_pending,
            critical=rev_critical,
            in_review=rev_in_review,
        )

        if rev_critical > 0:
            reasons.append(f"{rev_critical} critical evidence contradiction(s) awaiting reviewer resolution")

        # 5. Schemes & Versions Overview
        scheme_total = db.scalar(select(func.count()).select_from(Scheme)) or 0
        scheme_verified = db.scalar(
            select(func.count()).select_from(SchemeDraft).where(SchemeDraft.status == "HUMAN_VERIFIED")
        ) or 0
        
        today = now.date()
        active_versions = db.scalar(
            select(func.count()).select_from(SchemeVersion).where(
                and_(
                    SchemeVersion.status == "ACTIVE",
                    SchemeVersion.is_current.is_(True),
                )
            )
        ) or 0

        future_versions = db.scalar(
            select(func.count()).select_from(SchemeVersion).where(
                or_(
                    SchemeVersion.valid_from > today,
                    and_(
                        SchemeVersion.status == "HUMAN_VERIFIED",
                        SchemeVersion.effective_date > today,
                    ),
                )
            )
        ) or 0

        superseded_versions = db.scalar(
            select(func.count()).select_from(SchemeVersion).where(
                SchemeVersion.status == "SUPERSEDED"
            )
        ) or 0

        schemes_overview = SchemeOverview(
            total=scheme_total,
            human_verified=scheme_verified,
            active_versions=active_versions,
            future_versions=future_versions,
            superseded_versions=superseded_versions,
        )

        # 6. Conflicts Overview
        # Unresolved change sets with conflicts
        cs_conflicts = db.scalar(
            select(func.count()).select_from(SchemeChangeSet).where(
                SchemeChangeSet.status.in_(["CONFLICT_DETECTED", "PENDING_REVIEW"])
            )
        ) or 0

        # Unresolved critical validation issues
        val_conflicts = db.scalar(
            select(func.count())
            .select_from(ValidationIssue)
            .join(SchemeDraft, ValidationIssue.scheme_draft_id == SchemeDraft.id)
            .where(
                and_(
                    ValidationIssue.severity.in_(["CRITICAL", "BLOCKER", "ERROR"]),
                    SchemeDraft.status.in_(["VALIDATING", "READY_FOR_HUMAN_REVIEW", "IN_REVIEW"]),
                )
            )
        ) or 0

        total_conflicts = cs_conflicts + val_conflicts + rev_critical
        conflicts_overview = ConflictOverview(
            total_unresolved=total_conflicts,
            critical_count=cs_conflicts + rev_critical,
        )

        if cs_conflicts > 0:
            reasons.append(f"{cs_conflicts} pending version change set(s) require conflict resolution")
            critical_issues.append(
                CriticalIssue(
                    id="conflict-change-sets",
                    category="CONFLICT",
                    severity="CRITICAL",
                    title="Version Change Set Conflict Detected",
                    description=f"{cs_conflicts} version amendment(s) exhibit contradictory or overlapping conditions",
                    link="/admin/versions",
                    created_at=now.isoformat(),
                )
            )

        # 7. Evaluate System State
        system_status = "HEALTHY"
        if doc_failed > 5 or source_failing > 2 or (cs_conflicts + rev_critical) > 5:
            system_status = "CRITICAL"
        elif doc_failed > 0 or source_failing > 0 or total_conflicts > 0 or rev_pending > 5:
            system_status = "WARNING"

        response = AdminOverviewResponse(
            system_status=system_status,
            system_status_reasons=reasons,
            sources=sources_overview,
            documents=docs_overview,
            reviews=reviews_overview,
            schemes=schemes_overview,
            conflicts=conflicts_overview,
            pipeline_stages=pipeline_stages,
            critical_issues=critical_issues,
            generated_at=now.isoformat(),
        )
        AdminDashboardService._cached_overview = response
        AdminDashboardService._cached_overview_ts = cur_t
        return response

