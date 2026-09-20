import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.scheme_draft import SchemeDraft
from app.repositories.evidence_verification_repository import (
    EvidenceVerificationRepository,
)
from app.verification.deterministic import DeterministicVerifier
from app.verification.evidence_resolver import EvidenceResolver
from app.verification.fact_builder import CanonicalFactBuilder
from app.verification.llm_verifier import LLMEvidenceVerifier
from app.verification.schemas import (
    EvidenceVerificationReportDTO,
    EvidenceVerificationSummaryDTO,
    FactRiskLevel,
    FactVerificationDTO,
    VerifiableFact,
    VerificationMethod,
    VerificationReasonCode,
    VerificationResult,
    VerificationRunStatus,
)

logger = logging.getLogger("yojansetu.verification.service")


class EvidenceVerificationService:
    """
    Day 12 Second-Pass Evidence Verification Service.
    Challenges individual canonical facts against exact government source evidence
    using deterministic checks and local Llama 3.2 3B.
    """

    def __init__(
        self,
        db: Session,
        llm_verifier: Optional[LLMEvidenceVerifier] = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.repo = EvidenceVerificationRepository()
        self.fact_builder = CanonicalFactBuilder()
        self.evidence_resolver = EvidenceResolver(db)
        self.deterministic_verifier = DeterministicVerifier()
        self.llm_verifier = llm_verifier or LLMEvidenceVerifier()

    def verify_scheme_draft(
        self,
        scheme_draft_id: uuid.UUID,
        force: bool = False,
    ) -> EvidenceVerificationReportDTO:
        """
        Verify all atomic facts of a canonical scheme draft against official evidence.
        Idempotent: Identical draft content and verifier version reuses cached run.
        """
        start_time = time.time()
        self.settings.ensure_storage_dirs()

        draft = self.db.get(SchemeDraft, scheme_draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID {scheme_draft_id} not found")

        # 1. Input status validation
        blocked_statuses = ["NORMALIZATION_FAILED", "VALIDATION_FAILED"]
        if draft.status in blocked_statuses and not force:
            raise ValueError(
                f"Cannot verify draft {scheme_draft_id} with status '{draft.status}'. "
                f"Fix validation blockers before evidence verification."
            )

        # 2. Load canonical JSON artifact
        canonical_file_path = self._resolve_artifact_path(draft.artifact_path)
        if not canonical_file_path.exists():
            raise FileNotFoundError(
                f"Canonical artifact not found at {canonical_file_path}"
            )

        raw_bytes = canonical_file_path.read_bytes()
        canonical_artifact_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        try:
            raw_canonical_data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as ex:
            raise ValueError(f"Failed to parse canonical artifact JSON: {ex}")

        # 3. Idempotency and Stale Check
        latest_run = self.repo.get_latest_run_by_draft_id(self.db, scheme_draft_id)
        if (
            not force
            and latest_run
            and latest_run.canonical_artifact_sha256 == canonical_artifact_sha256
            and latest_run.verifier_version == self.settings.evidence_verifier_version
            and latest_run.status != VerificationRunStatus.STALE.value
            and latest_run.status != VerificationRunStatus.EVIDENCE_VERIFYING.value
            and latest_run.artifact_path
        ):
            cached_path = self._resolve_artifact_path(latest_run.artifact_path)
            if cached_path.exists():
                logger.info(
                    f"Reusing cached verification run {latest_run.id} for draft {scheme_draft_id}"
                )
                try:
                    with open(cached_path, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    return EvidenceVerificationReportDTO.model_validate(cached_data)
                except Exception:
                    pass  # Fall through to re-run if cache corrupted

        # Mark prior verification runs STALE if hash or version changed
        if latest_run and (
            latest_run.canonical_artifact_sha256 != canonical_artifact_sha256
            or latest_run.verifier_version != self.settings.evidence_verifier_version
        ):
            logger.info(
                f"Canonical draft changed for {scheme_draft_id}. Marking previous runs STALE."
            )
            self.repo.mark_prior_runs_stale(self.db, scheme_draft_id)

        # 4. Initialize Run Record
        draft.status = VerificationRunStatus.EVIDENCE_VERIFYING.value
        self.db.flush()

        v_run = self.repo.create_run(
            db=self.db,
            scheme_draft_id=scheme_draft_id,
            canonical_artifact_sha256=canonical_artifact_sha256,
            verifier_version=self.settings.evidence_verifier_version,
            prompt_version=self.settings.evidence_verification_prompt_version,
            schema_version=self.settings.evidence_verification_schema_version,
            status=VerificationRunStatus.EVIDENCE_VERIFYING.value,
        )
        self.db.flush()

        logger.info(
            f"Evidence verification started for draft {scheme_draft_id} (run_id: {v_run.id})"
        )

        # 5. Atomic Fact Construction
        facts: List[VerifiableFact] = self.fact_builder.build_facts(raw_canonical_data)
        evidence_registry = (
            raw_canonical_data.get("evidence_registry")
            or raw_canonical_data.get("evidence")
            or {}
        )

        # Setup artifact directory
        out_dir = self.settings.verification_dir / str(scheme_draft_id)
        runs_dir = out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        facts_file_path = out_dir / "facts.json"
        with open(facts_file_path, "w", encoding="utf-8") as f:
            json.dump([fact.model_dump() for fact in facts], f, indent=2, ensure_ascii=False)

        # 6. Evaluate Each Fact
        fact_evaluations: List[FactVerificationDTO] = []

        for fact in facts:
            dto = self._evaluate_single_fact(
                fact=fact,
                raw_canonical_data=raw_canonical_data,
                evidence_registry=evidence_registry,
                document_id=draft.document_id,
            )
            fact_evaluations.append(dto)

        # 7. Metrics Aggregation
        facts_total = len(fact_evaluations)
        facts_supported = sum(
            1 for f in fact_evaluations if f.result == VerificationResult.SUPPORTED
        )
        facts_contradicted = sum(
            1 for f in fact_evaluations if f.result == VerificationResult.CONTRADICTED
        )
        facts_insufficient = sum(
            1 for f in fact_evaluations if f.result == VerificationResult.NOT_ENOUGH_EVIDENCE
        )
        facts_failed = sum(
            1 for f in fact_evaluations if f.explanation and "failed" in f.explanation.lower()
        )
        critical_issues_count = sum(
            1
            for f in fact_evaluations
            if f.risk_level in [FactRiskLevel.CRITICAL, FactRiskLevel.HIGH]
            and f.result in [VerificationResult.CONTRADICTED, VerificationResult.NOT_ENOUGH_EVIDENCE]
        )
        deterministic_count = sum(
            1 for f in fact_evaluations if f.verification_method == VerificationMethod.DETERMINISTIC
        )
        llm_count = sum(
            1 for f in fact_evaluations if f.verification_method == VerificationMethod.LLM
        )
        ocr_risk_count = sum(1 for f in fact_evaluations if f.ocr_risk)

        # 8. Lifecycle Status
        if facts_failed > 0:
            final_run_status = VerificationRunStatus.EVIDENCE_VERIFICATION_FAILED
            final_draft_status = "EVIDENCE_REVIEW_REQUIRED"
        elif facts_contradicted > 0 or facts_insufficient > 0 or critical_issues_count > 0:
            final_run_status = VerificationRunStatus.EVIDENCE_REVIEW_REQUIRED
            final_draft_status = "READY_FOR_HUMAN_REVIEW"
        else:
            final_run_status = VerificationRunStatus.EVIDENCE_VERIFIED
            final_draft_status = "READY_FOR_HUMAN_REVIEW"

        duration_ms = int((time.time() - start_time) * 1000)

        # 9. Write Verification Artifacts
        summary_dto = EvidenceVerificationSummaryDTO(
            facts_total=facts_total,
            facts_supported=facts_supported,
            facts_contradicted=facts_contradicted,
            facts_insufficient=facts_insufficient,
            facts_failed=facts_failed,
            critical_issues_count=critical_issues_count,
            deterministic_count=deterministic_count,
            llm_count=llm_count,
            ocr_risk_count=ocr_risk_count,
        )

        run_artifact_file = runs_dir / f"{v_run.id}.json"
        summary_file_path = out_dir / "verification_summary.json"

        report_dto = EvidenceVerificationReportDTO(
            schema_version=self.settings.evidence_verification_schema_version,
            verifier_version=self.settings.evidence_verifier_version,
            prompt_version=self.settings.evidence_verification_prompt_version,
            scheme_draft_id=str(scheme_draft_id),
            canonical_artifact_sha256=canonical_artifact_sha256,
            status=final_run_status,
            summary=summary_dto,
            facts=fact_evaluations,
            duration_ms=duration_ms,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        with open(run_artifact_file, "w", encoding="utf-8") as f:
            json.dump(report_dto.model_dump(), f, indent=2, ensure_ascii=False)

        with open(summary_file_path, "w", encoding="utf-8") as f:
            json.dump(summary_dto.model_dump(), f, indent=2, ensure_ascii=False)

        rel_run_artifact = str(run_artifact_file.relative_to(self.settings.storage_path))

        # 10. Persist DB Records
        self.repo.complete_run(
            db=self.db,
            run_id=v_run.id,
            status=final_run_status.value,
            facts_total=facts_total,
            facts_supported=facts_supported,
            facts_contradicted=facts_contradicted,
            facts_insufficient=facts_insufficient,
            facts_failed=facts_failed,
            critical_issues_count=critical_issues_count,
            deterministic_count=deterministic_count,
            llm_count=llm_count,
            ocr_risk_count=ocr_risk_count,
            artifact_path=rel_run_artifact,
            duration_ms=duration_ms,
            diagnostics={"summary": summary_dto.model_dump()},
        )

        self.repo.add_fact_verifications(
            db=self.db,
            run_id=v_run.id,
            scheme_draft_id=scheme_draft_id,
            fact_dtos=fact_evaluations,
            prompt_version=self.settings.evidence_verification_prompt_version,
            schema_version=self.settings.evidence_verification_schema_version,
        )

        # Update SchemeDraft status
        draft.status = final_draft_status
        self.db.commit()

        logger.info(
            f"Evidence verification completed for draft {scheme_draft_id}: "
            f"run_status={final_run_status.value}, draft_status={final_draft_status}, "
            f"facts={facts_total}, supported={facts_supported}, contradicted={facts_contradicted}, "
            f"insufficient={facts_insufficient}, duration={duration_ms}ms"
        )

        return report_dto

    def _evaluate_single_fact(
        self,
        fact: VerifiableFact,
        raw_canonical_data: Dict[str, Any],
        evidence_registry: Dict[str, Any],
        document_id: Optional[uuid.UUID],
    ) -> FactVerificationDTO:
        """Evaluates one atomic claim against its evidence."""
        fact_start = time.time()

        # Check for missing evidence references
        if not fact.evidence_refs:
            return FactVerificationDTO(
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                fact_type=fact.fact_type,
                risk_level=fact.risk_level,
                statement=fact.statement,
                canonical_value=fact.canonical_value,
                evidence_text=None,
                result=VerificationResult.NOT_ENOUGH_EVIDENCE,
                reason_code=VerificationReasonCode.EVIDENCE_MISSING,
                explanation="No evidence references provided for this canonical fact.",
                verification_method=VerificationMethod.DETERMINISTIC,
                evidence_refs=[],
                ocr_risk=False,
                duration_ms=int((time.time() - fact_start) * 1000),
            )

        # Resolve evidence references
        res_items, broken_refs = self.evidence_resolver.resolve_evidence_refs(
            evidence_refs=fact.evidence_refs,
            evidence_registry=evidence_registry,
            document_id=document_id,
        )

        # If any reference is broken
        if broken_refs:
            return FactVerificationDTO(
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                fact_type=fact.fact_type,
                risk_level=fact.risk_level,
                statement=fact.statement,
                canonical_value=fact.canonical_value,
                evidence_text=None,
                result=VerificationResult.NOT_ENOUGH_EVIDENCE,
                reason_code=VerificationReasonCode.FACT_NOT_PRESENT,
                explanation=f"Evidence reference cannot be resolved: {broken_refs}",
                verification_method=VerificationMethod.DETERMINISTIC,
                evidence_refs=fact.evidence_refs,
                ocr_risk=False,
                duration_ms=int((time.time() - fact_start) * 1000),
            )

        ocr_risk = any(item.ocr_risk for item in res_items)

        # Check for conflicting evidence items
        has_conflict, conflict_desc = self.evidence_resolver.detect_source_evidence_conflict(
            res_items, fact
        )
        if has_conflict:
            return FactVerificationDTO(
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                fact_type=fact.fact_type,
                risk_level=fact.risk_level,
                statement=fact.statement,
                canonical_value=fact.canonical_value,
                evidence_text="\n".join([i.text for i in res_items]),
                result=VerificationResult.NOT_ENOUGH_EVIDENCE,
                reason_code=VerificationReasonCode.AMBIGUOUS_SOURCE,
                explanation=f"Conflicting source evidence detected: {conflict_desc}",
                verification_method=VerificationMethod.DETERMINISTIC,
                evidence_refs=fact.evidence_refs,
                ocr_risk=ocr_risk,
                duration_ms=int((time.time() - fact_start) * 1000),
            )

        # 1. Deterministic Pre-Verification
        det_result = self.deterministic_verifier.verify_deterministic(fact, res_items)
        if det_result is not None:
            res, reason, expl = det_result
            return FactVerificationDTO(
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                fact_type=fact.fact_type,
                risk_level=fact.risk_level,
                statement=fact.statement,
                canonical_value=fact.canonical_value,
                evidence_text="\n".join([i.text for i in res_items]),
                result=res,
                reason_code=reason,
                explanation=expl,
                verification_method=VerificationMethod.DETERMINISTIC,
                evidence_refs=fact.evidence_refs,
                ocr_risk=ocr_risk,
                duration_ms=int((time.time() - fact_start) * 1000),
            )

        # 2. Local Llama Verification Fallback
        sandboxed_evidence = self.evidence_resolver.format_sandboxed_evidence(
            res_items, fact
        )
        llm_resp, metadata, err = self.llm_verifier.verify_fact(fact, sandboxed_evidence)

        duration_ms = int((time.time() - fact_start) * 1000)

        if llm_resp is not None:
            return FactVerificationDTO(
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                fact_type=fact.fact_type,
                risk_level=fact.risk_level,
                statement=fact.statement,
                canonical_value=fact.canonical_value,
                evidence_text="\n".join([i.text for i in res_items]),
                result=llm_resp.result,
                reason_code=llm_resp.reason_code,
                explanation=llm_resp.explanation,
                verification_method=VerificationMethod.LLM,
                evidence_refs=fact.evidence_refs,
                ocr_risk=ocr_risk,
                model_provider=metadata.provider if metadata else "ollama",
                model_name=metadata.model_name if metadata else "llama3.2:3b",
                duration_ms=duration_ms,
            )
        else:
            return FactVerificationDTO(
                fact_id=fact.fact_id,
                field_path=fact.field_path,
                fact_type=fact.fact_type,
                risk_level=fact.risk_level,
                statement=fact.statement,
                canonical_value=fact.canonical_value,
                evidence_text="\n".join([i.text for i in res_items]),
                result=VerificationResult.NOT_ENOUGH_EVIDENCE,
                reason_code=VerificationReasonCode.INSUFFICIENT_CONTEXT,
                explanation=f"LLM verification failed: {err}",
                verification_method=VerificationMethod.LLM,
                evidence_refs=fact.evidence_refs,
                ocr_risk=ocr_risk,
                duration_ms=duration_ms,
            )

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
