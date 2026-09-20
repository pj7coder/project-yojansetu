from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import Session

from app.admin.schemas import AdminConflictItem, AdminConflictListResponse
from app.database.models.fact_verification import FactVerification
from app.database.models.human_review_session import HumanReviewSession
from app.database.models.scheme import Scheme
from app.database.models.scheme_change_set import SchemeChangeSet
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.source_change_event import SourceChangeEvent
from app.database.models.validation_issue import ValidationIssue

logger = logging.getLogger("yojansetu.admin.conflicts")


class AdminConflictService:
    """Operations service aggregating unresolved conflicts across normalization, validation, and versioning."""

    def list_conflicts(
        self,
        db: Session,
        conflict_type: Optional[str] = None,
        severity: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> AdminConflictListResponse:
        now = datetime.now(timezone.utc)
        items: List[AdminConflictItem] = []

        # 1. Evidence Verification Contradictions (FIELD_VALUE_CONFLICT)
        fact_stmt = (
            select(FactVerification, SchemeDraft)
            .join(SchemeDraft, FactVerification.scheme_draft_id == SchemeDraft.id)
            .where(
                and_(
                    FactVerification.result == "CONTRADICTED",
                    SchemeDraft.status.in_(["READY_FOR_HUMAN_REVIEW", "IN_REVIEW"]),
                )
            )
        )
        fact_rows = db.execute(fact_stmt).all()
        for fv, draft in fact_rows:
            scheme_title = draft.detected_name or draft.official_name_raw or "Draft Scheme"
            items.append(
                AdminConflictItem(
                    id=str(fv.id),
                    conflict_type="FIELD_VALUE_CONFLICT",
                    severity="CRITICAL",
                    title=f"Evidence Contradiction: {fv.field_path}",
                    description=fv.explanation or fv.statement or f"Contradicts official text for {fv.field_path}",
                    scheme_id=str(draft.id),
                    scheme_name=scheme_title,
                    document_id=str(draft.document_id),
                    source_count=1,
                    status="UNRESOLVED_CONTRADICTION",
                    link=f"/admin/review/{draft.id}",
                    created_at=(fv.created_at or now).isoformat(),
                )
            )

        # 2. Critical Validation Issues (FIELD_VALUE_CONFLICT / SCHEME_ASSOCIATION_CONFLICT)
        val_stmt = (
            select(ValidationIssue, SchemeDraft)
            .join(SchemeDraft, ValidationIssue.scheme_draft_id == SchemeDraft.id)
            .where(
                and_(
                    ValidationIssue.severity.in_(["CRITICAL", "BLOCKER", "ERROR"]),
                    SchemeDraft.status.in_(["VALIDATING", "READY_FOR_HUMAN_REVIEW", "IN_REVIEW"]),
                )
            )
        )
        val_rows = db.execute(val_stmt).all()
        for vi, draft in val_rows:
            scheme_title = draft.detected_name or draft.official_name_raw or "Draft Scheme"
            items.append(
                AdminConflictItem(
                    id=str(vi.id),
                    conflict_type="FIELD_VALUE_CONFLICT" if "rule" in vi.rule_code.lower() else "SCHEME_ASSOCIATION_CONFLICT",
                    severity="CRITICAL",
                    title=f"Validation Failure: {vi.field_path or vi.rule_code}",
                    description=vi.message,
                    scheme_id=str(draft.id),
                    scheme_name=scheme_title,
                    document_id=str(draft.document_id),
                    source_count=1,
                    status="CRITICAL_VALIDATION_ERROR",
                    link=f"/admin/review/{draft.id}",
                    created_at=(vi.created_at or now).isoformat(),
                )
            )

        # 3. Scheme Change Set Conflicts (VERSION_RELATIONSHIP_CONFLICT / EFFECTIVE_DATE_CONFLICT)
        cs_stmt = (
            select(SchemeChangeSet, Scheme)
            .join(Scheme, SchemeChangeSet.scheme_id == Scheme.id)
            .where(
                or_(
                    SchemeChangeSet.conflict_reason.isnot(None),
                    SchemeChangeSet.critical_changes_count > 0,
                    SchemeChangeSet.status == "REVIEW_REQUIRED",
                )
            )
        )
        cs_rows = db.execute(cs_stmt).all()
        for cs, scheme in cs_rows:
            has_conflict = cs.conflict_reason is not None
            items.append(
                AdminConflictItem(
                    id=str(cs.id),
                    conflict_type="VERSION_RELATIONSHIP_CONFLICT" if has_conflict else "EFFECTIVE_DATE_CONFLICT",
                    severity="CRITICAL" if has_conflict else "WARNING",
                    title=f"Version Conflict: {cs.conflict_reason or 'Review Required'}",
                    description=cs.change_summary or cs.conflict_reason or f"Version change set requiring review against base version {cs.base_version_id}",
                    scheme_id=str(scheme.id),
                    scheme_name=scheme.name_hi or scheme.name_en,
                    document_id=str(cs.source_document_id),
                    source_count=2,
                    status=cs.status,
                    link=f"/admin/versions",
                    created_at=(cs.created_at or now).isoformat(),
                )
            )

        # 4. Source Discrepancies (SOURCE_CONFLICT)
        sc_stmt = (
            select(SourceChangeEvent)
            .where(
                and_(
                    SourceChangeEvent.processing_status == "FAILED",
                )
            )
        )
        sc_rows = db.execute(sc_stmt).scalars().all()
        for sc in sc_rows:
            items.append(
                AdminConflictItem(
                    id=str(sc.id),
                    conflict_type="SOURCE_CONFLICT",
                    severity="WARNING",
                    title=f"Source Discrepancy: {sc.change_type}",
                    description=f"Source change event {sc.change_type} failed processing",
                    scheme_id=None,
                    scheme_name=None,
                    document_id=None,
                    source_count=1,
                    status="FAILED_SOURCE_CHANGE",
                    link="/admin/sources",
                    created_at=(sc.created_at or now).isoformat(),
                )
            )

        # Apply in-memory filters
        if conflict_type:
            items = [it for it in items if it.conflict_type.upper() == conflict_type.upper()]
        if severity:
            items = [it for it in items if it.severity.upper() == severity.upper()]

        # Sort by severity (CRITICAL first) then created_at desc
        items.sort(key=lambda x: (0 if x.severity == "CRITICAL" else 1, x.created_at), reverse=False)

        total = len(items)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_items = items[start_idx:end_idx]

        return AdminConflictListResponse(
            items=paged_items,
            total=total,
            page=page,
            page_size=page_size,
        )
