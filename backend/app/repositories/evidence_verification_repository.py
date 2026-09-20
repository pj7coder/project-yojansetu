from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from app.database.models.evidence_verification_run import EvidenceVerificationRun
from app.database.models.fact_verification import FactVerification
from app.verification.schemas import FactVerificationDTO, VerificationRunStatus


class EvidenceVerificationRepository:
    """Repository for evidence_verification_runs and fact_verifications tables."""

    @staticmethod
    def create_run(
        db: Session,
        scheme_draft_id: uuid.UUID,
        canonical_artifact_sha256: str,
        verifier_version: str,
        prompt_version: str,
        schema_version: str,
        status: str = VerificationRunStatus.EVIDENCE_VERIFYING.value,
        started_at: Optional[datetime] = None,
    ) -> EvidenceVerificationRun:
        run = EvidenceVerificationRun(
            scheme_draft_id=scheme_draft_id,
            canonical_artifact_sha256=canonical_artifact_sha256,
            verifier_version=verifier_version,
            prompt_version=prompt_version,
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
        facts_total: int,
        facts_supported: int,
        facts_contradicted: int,
        facts_insufficient: int,
        facts_failed: int,
        critical_issues_count: int,
        deterministic_count: int,
        llm_count: int,
        ocr_risk_count: int,
        artifact_path: Optional[str],
        duration_ms: int,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Optional[EvidenceVerificationRun]:
        run = db.get(EvidenceVerificationRun, run_id)
        if not run:
            return None

        run.status = status
        run.facts_total = facts_total
        run.facts_supported = facts_supported
        run.facts_contradicted = facts_contradicted
        run.facts_insufficient = facts_insufficient
        run.facts_failed = facts_failed
        run.critical_issues_count = critical_issues_count
        run.deterministic_count = deterministic_count
        run.llm_count = llm_count
        run.ocr_risk_count = ocr_risk_count
        run.artifact_path = artifact_path
        run.duration_ms = duration_ms
        run.diagnostics = diagnostics
        run.completed_at = datetime.now(timezone.utc)
        db.flush()
        return run

    @staticmethod
    def add_fact_verifications(
        db: Session,
        run_id: uuid.UUID,
        scheme_draft_id: uuid.UUID,
        fact_dtos: List[FactVerificationDTO],
        prompt_version: Optional[str] = None,
        schema_version: Optional[str] = None,
    ) -> List[FactVerification]:
        records: List[FactVerification] = []
        for dto in fact_dtos:
            record = FactVerification(
                verification_run_id=run_id,
                scheme_draft_id=scheme_draft_id,
                fact_id=dto.fact_id,
                field_path=dto.field_path,
                fact_type=dto.fact_type.value,
                risk_level=dto.risk_level.value,
                statement=dto.statement,
                canonical_value=dto.canonical_value,
                evidence_refs=dto.evidence_refs,
                evidence_text=dto.evidence_text,
                result=dto.result.value,
                reason_code=dto.reason_code.value,
                verification_method=dto.verification_method.value,
                explanation=dto.explanation,
                ocr_risk=dto.ocr_risk,
                model_provider=dto.model_provider,
                model_name=dto.model_name,
                duration_ms=dto.duration_ms,
            )
            db.add(record)
            records.append(record)
        db.flush()
        return records

    @staticmethod
    def get_latest_run_by_draft_id(
        db: Session, draft_id: uuid.UUID
    ) -> Optional[EvidenceVerificationRun]:
        stmt = (
            select(EvidenceVerificationRun)
            .where(EvidenceVerificationRun.scheme_draft_id == draft_id)
            .order_by(desc(EvidenceVerificationRun.created_at))
            .limit(1)
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_run_by_id(
        db: Session, run_id: uuid.UUID
    ) -> Optional[EvidenceVerificationRun]:
        return db.get(EvidenceVerificationRun, run_id)

    @staticmethod
    def get_fact_by_id(
        db: Session, fact_verification_id: uuid.UUID
    ) -> Optional[FactVerification]:
        return db.get(FactVerification, fact_verification_id)

    @staticmethod
    def get_facts_by_draft(
        db: Session,
        draft_id: uuid.UUID,
        run_id: Optional[uuid.UUID] = None,
        result: Optional[str] = None,
        fact_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        verification_method: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FactVerification]:
        stmt = select(FactVerification).where(
            FactVerification.scheme_draft_id == draft_id
        )
        if run_id:
            stmt = stmt.where(FactVerification.verification_run_id == run_id)
        if result:
            stmt = stmt.where(FactVerification.result == result.upper())
        if fact_type:
            stmt = stmt.where(FactVerification.fact_type == fact_type.upper())
        if risk_level:
            stmt = stmt.where(FactVerification.risk_level == risk_level.upper())
        if verification_method:
            stmt = stmt.where(
                FactVerification.verification_method == verification_method.upper()
            )

        stmt = (
            stmt.order_by(desc(FactVerification.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def mark_prior_runs_stale(
        db: Session,
        scheme_draft_id: uuid.UUID,
        exclude_run_id: Optional[uuid.UUID] = None,
    ) -> int:
        stmt = (
            update(EvidenceVerificationRun)
            .where(EvidenceVerificationRun.scheme_draft_id == scheme_draft_id)
            .where(
                EvidenceVerificationRun.status != VerificationRunStatus.STALE.value
            )
        )
        if exclude_run_id:
            stmt = stmt.where(EvidenceVerificationRun.id != exclude_run_id)
        stmt = stmt.values(status=VerificationRunStatus.STALE.value)
        res = db.execute(stmt)
        db.flush()
        return res.rowcount
