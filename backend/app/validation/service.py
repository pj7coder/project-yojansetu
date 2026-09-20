import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.ocr_run import OCRRun
from app.database.models.parsed_document import ParsedDocument
from app.database.models.scheme_draft import SchemeDraft
from app.repositories.validation_repository import ValidationRepository
from app.validation.registry import VALIDATION_RULES
from app.validation.schemas import (
    ValidationIssueDTO,
    ValidationReportDTO,
    ValidationRunStatus,
    ValidationSeverity,
    ValidationSummaryDTO,
)
from app.validation.validators.application import ApplicationValidator
from app.validation.validators.base import ValidationContext
from app.validation.validators.benefits import BenefitsValidator
from app.validation.validators.conflicts import ConflictsValidator
from app.validation.validators.dates import DatesValidator
from app.validation.validators.documents import DocumentsValidator
from app.validation.validators.eligibility import EligibilityValidator
from app.validation.validators.evidence import EvidenceValidator
from app.validation.validators.geography import GeographyValidator
from app.validation.validators.numbers import NumbersValidator
from app.validation.validators.provenance import ProvenanceValidator
from app.validation.validators.schema import SchemaValidator

logger = logging.getLogger("yojansetu.validation.service")


class SchemeValidationService:
    """
    Day 11 Deterministic Validation Engine Service.
    Coordinates deterministic schema, evidence, provenance, numbers, geography,
    dates, rules, benefits, and conflicts validation over Canonical Scheme Drafts.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repo = ValidationRepository()

    def validate_draft(
        self,
        scheme_draft_id: uuid.UUID,
        force: bool = False,
    ) -> ValidationReportDTO:
        """
        Execute deterministic validation for a canonical SchemeDraft.
        Idempotent: Identical canonical draft and validator version will reuse cached report.
        """
        start_time = time.time()
        self.settings.ensure_storage_dirs()

        draft = self.db.get(SchemeDraft, scheme_draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID {scheme_draft_id} not found")

        # Load canonical JSON artifact
        canonical_file_path = self._resolve_artifact_path(draft.artifact_path)
        if not canonical_file_path.exists():
            raise FileNotFoundError(f"Canonical artifact not found at {canonical_file_path}")

        raw_bytes = canonical_file_path.read_bytes()
        canonical_artifact_hash = hashlib.sha256(raw_bytes).hexdigest()

        try:
            raw_canonical_data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as ex:
            raw_canonical_data = {"error": str(ex)}

        # Check idempotency
        latest_run = self.repo.get_latest_run_by_draft_id(self.db, scheme_draft_id)
        if (
            not force
            and latest_run
            and latest_run.canonical_artifact_hash == canonical_artifact_hash
            and latest_run.validator_version == self.settings.validator_version
            and latest_run.status != ValidationRunStatus.STALE.value
            and latest_run.status != ValidationRunStatus.VALIDATING.value
            and latest_run.artifact_path
        ):
            cached_report_path = self._resolve_artifact_path(latest_run.artifact_path)
            if cached_report_path.exists():
                logger.info(f"Reusing cached validation run {latest_run.id} for draft {scheme_draft_id}")
                try:
                    with open(cached_report_path, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    return ValidationReportDTO.model_validate(cached_data)
                except Exception:
                    pass  # Fall through to re-validate if cache corrupted

        # Mark prior validation runs as STALE
        if latest_run and latest_run.canonical_artifact_hash != canonical_artifact_hash:
            logger.info(f"Canonical draft changed for {scheme_draft_id}. Marking previous runs STALE.")
            self.repo.mark_prior_runs_stale(self.db, scheme_draft_id)

        # Update draft state to VALIDATING
        draft.status = ValidationRunStatus.VALIDATING.value
        self.db.flush()

        # Create ValidationRun record
        v_run = self.repo.create_run(
            db=self.db,
            scheme_draft_id=scheme_draft_id,
            canonical_artifact_hash=canonical_artifact_hash,
            validator_version=self.settings.validator_version,
            schema_version=self.settings.validation_schema_version,
            status=ValidationRunStatus.VALIDATING.value,
        )
        self.db.flush()

        logger.info(f"Validation started for draft {scheme_draft_id} (run_id: {v_run.id})")

        # Gather provenance context
        doc_page_count, chunk_ids, block_ids, chunk_page_ranges, ocr_low_conf_blocks = (
            self._gather_document_metadata(draft.document_id)
        )
        registered_dept_ids = self._gather_registered_departments()

        context = ValidationContext(
            scheme_draft_id=str(scheme_draft_id),
            document_id=str(draft.document_id),
            raw_canonical_data=raw_canonical_data,
            doc_page_count=doc_page_count,
            chunk_ids=chunk_ids,
            block_ids=block_ids,
            chunk_page_ranges=chunk_page_ranges,
            ocr_low_confidence_blocks=ocr_low_conf_blocks,
            registered_department_ids=registered_dept_ids,
        )

        # 1. Run Schema Validator
        schema_validator = SchemaValidator()
        schema_validator.validate(context)

        # 2. Run domain validators only if schema is valid
        if context.draft:
            validators = [
                EvidenceValidator(),
                ProvenanceValidator(),
                NumbersValidator(),
                GeographyValidator(),
                DatesValidator(),
                EligibilityValidator(),
                BenefitsValidator(),
                DocumentsValidator(),
                ApplicationValidator(),
                ConflictsValidator(),
            ]
            for v in validators:
                v.validate(context)

        # Compute issue counts
        blocker_count = sum(1 for i in context.issues if i.severity == ValidationSeverity.BLOCKER)
        error_count = sum(1 for i in context.issues if i.severity == ValidationSeverity.ERROR)
        warning_count = sum(1 for i in context.issues if i.severity == ValidationSeverity.WARNING)
        info_count = sum(1 for i in context.issues if i.severity == ValidationSeverity.INFO)

        # Determine final status
        if blocker_count > 0:
            final_status = ValidationRunStatus.VALIDATION_FAILED
        elif error_count > 0:
            final_status = ValidationRunStatus.VALIDATION_REVIEW_REQUIRED
        else:
            final_status = ValidationRunStatus.VALIDATION_PASSED

        duration_ms = int((time.time() - start_time) * 1000)

        # Save validation artifacts
        out_dir = self.settings.validation_dir / str(scheme_draft_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / "validation_report.json"
        summary_path = out_dir / "validation_summary.json"

        summary_dto = ValidationSummaryDTO(
            blockers=blocker_count,
            errors=error_count,
            warnings=warning_count,
            info=info_count,
            total_issues=len(context.issues),
            rules_checked=context.rules_checked,
        )

        report_dto = ValidationReportDTO(
            schema_version=self.settings.validation_schema_version,
            validator_version=self.settings.validator_version,
            scheme_draft_id=str(scheme_draft_id),
            canonical_artifact_hash=canonical_artifact_hash,
            status=final_status,
            summary=summary_dto,
            issues=context.issues,
            duration_ms=duration_ms,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_dto.model_dump(), f, indent=2, ensure_ascii=False)

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_dto.model_dump(), f, indent=2, ensure_ascii=False)

        # Update DB records
        rel_report_path = str(report_path.relative_to(self.settings.storage_path))
        self.repo.complete_run(
            db=self.db,
            run_id=v_run.id,
            status=final_status.value,
            blocker_count=blocker_count,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            rules_checked_count=context.rules_checked,
            artifact_path=rel_report_path,
            duration_ms=duration_ms,
            diagnostics={"summary": summary_dto.model_dump()},
        )

        self.repo.add_issues(
            db=self.db,
            run_id=v_run.id,
            scheme_draft_id=scheme_draft_id,
            issues=context.issues,
        )

        # Update SchemeDraft status
        draft.status = final_status.value
        self.db.commit()

        logger.info(
            f"Validation completed for draft {scheme_draft_id}: "
            f"status={final_status.value}, blockers={blocker_count}, errors={error_count}, "
            f"warnings={warning_count}, info={info_count}, duration={duration_ms}ms"
        )

        return report_dto

    def _resolve_artifact_path(self, path_str: str) -> Path:
        p = Path(path_str)
        if p.is_absolute():
            return p
        base_cand = (self.settings.base_dir / p).resolve()
        if base_cand.exists():
            return base_cand
        clean_str = str(p).replace("storage/", "", 1).replace("storage\\", "", 1)
        storage_cand = (self.settings.storage_path / clean_str).resolve()
        if storage_cand.exists():
            return storage_cand
        return (self.settings.storage_path / p).resolve()

    def _gather_document_metadata(
        self, document_id: uuid.UUID
    ) -> Tuple[Optional[int], Set[str], Set[str], Dict[str, Tuple[int, int]], Set[str]]:
        doc = self.db.get(Document, document_id)
        doc_page_count = doc.page_count if doc else None

        # Chunks
        chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        chunks = self.db.scalars(chunk_stmt).all()
        chunk_ids = {c.chunk_id_str for c in chunks}
        chunk_page_ranges: Dict[str, Tuple[int, int]] = {}
        for c in chunks:
            chunk_page_ranges[c.chunk_id_str] = (c.page_start, c.page_end)

        # Parsed document source blocks
        parsed_stmt = select(ParsedDocument).where(ParsedDocument.document_id == document_id)
        parsed_doc = self.db.scalars(parsed_stmt).first()
        block_ids: Set[str] = set()
        if parsed_doc and parsed_doc.output_path:
            b_path = self._resolve_artifact_path(parsed_doc.output_path)
            if b_path.is_dir():
                doc_json = b_path / "document.json"
                if doc_json.exists():
                    b_path = doc_json
            if b_path.exists() and b_path.is_file():
                try:
                    with open(b_path, "r", encoding="utf-8") as f:
                        doc_data = json.load(f)
                    blocks_data = doc_data.get("blocks", []) if isinstance(doc_data, dict) else (doc_data if isinstance(doc_data, list) else [])
                    for b in blocks_data:
                        if isinstance(b, dict) and "id" in b:
                            block_ids.add(str(b["id"]))
                except Exception:
                    pass

        # OCR low confidence blocks
        ocr_low_conf_blocks: Set[str] = set()
        ocr_stmt = select(OCRRun).where(OCRRun.document_id == document_id)
        ocr_runs = self.db.scalars(ocr_stmt).all()
        for r in ocr_runs:
            if r.diagnostics and isinstance(r.diagnostics, dict):
                low_blocks = r.diagnostics.get("low_confidence_blocks", [])
                ocr_low_conf_blocks.update(str(b) for b in low_blocks)

        return doc_page_count, chunk_ids, block_ids, chunk_page_ranges, ocr_low_conf_blocks

    def _gather_registered_departments(self) -> Set[str]:
        dept_stmt = select(Department.id)
        return {str(d_id) for d_id in self.db.scalars(dept_stmt).all()}


# Alias for backward compatibility with auto_runner
ValidationService = SchemeValidationService
