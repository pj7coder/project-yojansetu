from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from app.database.models.validation_issue import ValidationIssue
from app.database.models.validation_run import ValidationRun
from app.validation.schemas import ValidationIssueDTO, ValidationRunStatus


class ValidationRepository:
    """Repository for managing validation_runs and validation_issues tables."""

    @staticmethod
    def create_run(
        db: Session,
        scheme_draft_id: uuid.UUID,
        canonical_artifact_hash: str,
        validator_version: str,
        schema_version: str,
        status: str = "VALIDATING",
        started_at: Optional[datetime] = None,
    ) -> ValidationRun:
        run = ValidationRun(
            scheme_draft_id=scheme_draft_id,
            canonical_artifact_hash=canonical_artifact_hash,
            validator_version=validator_version,
            schema_version=schema_version,
            status=status,
            started_at=started_at or datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()
        return run

    @staticmethod
    def complete_run(
        db: Session,
        run_id: uuid.UUID,
        status: str,
        blocker_count: int,
        error_count: int,
        warning_count: int,
        info_count: int,
        rules_checked_count: int,
        artifact_path: Optional[str],
        duration_ms: int,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Optional[ValidationRun]:
        run = db.get(ValidationRun, run_id)
        if not run:
            return None

        run.status = status
        run.blocker_count = blocker_count
        run.error_count = error_count
        run.warning_count = warning_count
        run.info_count = info_count
        run.rules_checked_count = rules_checked_count
        run.artifact_path = artifact_path
        run.duration_ms = duration_ms
        run.diagnostics = diagnostics
        run.completed_at = datetime.now(timezone.utc)
        db.flush()
        return run

    @staticmethod
    def add_issues(
        db: Session,
        run_id: uuid.UUID,
        scheme_draft_id: uuid.UUID,
        issues: List[ValidationIssueDTO],
    ) -> List[ValidationIssue]:
        db_issues: List[ValidationIssue] = []
        for dto in issues:
            issue = ValidationIssue(
                validation_run_id=run_id,
                scheme_draft_id=scheme_draft_id,
                rule_code=dto.rule_code,
                severity=dto.severity.value,
                field_path=dto.field_path,
                message=dto.message,
                actual_value=dto.actual_value,
                evidence_refs=dto.evidence_refs,
                status=dto.status.value,
                resolution_notes=dto.resolution_notes,
            )
            db.add(issue)
            db_issues.append(issue)
        db.flush()
        return db_issues

    @staticmethod
    def get_latest_run_by_draft_id(db: Session, draft_id: uuid.UUID) -> Optional[ValidationRun]:
        stmt = (
            select(ValidationRun)
            .where(ValidationRun.scheme_draft_id == draft_id)
            .order_by(desc(ValidationRun.created_at))
            .limit(1)
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_run_by_id(db: Session, run_id: uuid.UUID) -> Optional[ValidationRun]:
        return db.get(ValidationRun, run_id)

    @staticmethod
    def get_issues_by_draft(
        db: Session,
        draft_id: uuid.UUID,
        severity: Optional[str] = None,
        rule_code: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ValidationIssue]:
        stmt = select(ValidationIssue).where(ValidationIssue.scheme_draft_id == draft_id)
        if severity:
            stmt = stmt.where(ValidationIssue.severity == severity.upper())
        if rule_code:
            stmt = stmt.where(ValidationIssue.rule_code == rule_code)
        if status:
            stmt = stmt.where(ValidationIssue.status == status.upper())
        stmt = stmt.order_by(desc(ValidationIssue.created_at)).limit(limit).offset(offset)
        return list(db.scalars(stmt).all())

    @staticmethod
    def mark_prior_runs_stale(
        db: Session,
        scheme_draft_id: uuid.UUID,
        exclude_run_id: Optional[uuid.UUID] = None,
    ) -> int:
        stmt = (
            update(ValidationRun)
            .where(ValidationRun.scheme_draft_id == scheme_draft_id)
            .where(ValidationRun.status != ValidationRunStatus.STALE.value)
        )
        if exclude_run_id:
            stmt = stmt.where(ValidationRun.id != exclude_run_id)
        stmt = stmt.values(status=ValidationRunStatus.STALE.value)
        result = db.execute(stmt)
        db.flush()
        return result.rowcount
