from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.evidence_verification_run import EvidenceVerificationRun
from app.database.models.fact_verification import FactVerification
from app.database.models.human_review_item import HumanReviewItem
from app.database.models.human_review_session import HumanReviewSession
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.validation_issue import ValidationIssue
from app.database.models.validation_run import ValidationRun
from app.repositories.evidence_verification_repository import (
    EvidenceVerificationRepository,
)
from app.repositories.review_repository import ReviewRepository
from app.repositories.validation_repository import ValidationRepository
from app.review.artifact_builder import VerifiedArtifactBuilder
from app.review.completion import ReviewCompletionGuard
from app.review.conflict_service import ConflictResolutionService
from app.review.item_builder import ReviewItemBuilder
from app.review.schemas import (
    CompleteReviewRequest,
    ConflictItemDTO,
    ConflictResolutionChoice,
    ConflictResolutionRequest,
    HumanReviewItemResponse,
    ItemDecisionRequest,
    ReviewActionType,
    ReviewDecision,
    ReviewQueueItemDTO,
    ReviewQueueResponse,
    ReviewSessionDetailResponse,
    ReviewSessionStatus,
)
from app.validation.service import SchemeValidationService
from app.verification.service import EvidenceVerificationService

logger = logging.getLogger("jansetu.review.service")


class HumanReviewService:
    """
    Day 13 Human Verification Workflow Service.
    Orchestrates reviewer sessions, field-level decisions, conflict resolutions,
    re-validation triggers, optimistic concurrency, and verified artifact sealing.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repo = ReviewRepository()
        self.val_repo = ValidationRepository()
        self.verif_repo = EvidenceVerificationRepository()

    def get_review_queue(
        self,
        page: int = 1,
        page_size: int = 25,
        status_filter: Optional[str] = None,
        department_id: Optional[uuid.UUID] = None,
    ) -> ReviewQueueResponse:
        """Fetch prioritized list of scheme drafts awaiting review."""
        drafts, total = self.repo.query_queue_drafts(
            db=self.db,
            status_filter=status_filter,
            department_id=department_id,
            page=page,
            page_size=page_size,
        )

        queue_items: List[ReviewQueueItemDTO] = []
        for draft in drafts:
            doc = draft.document
            latest_session = self.repo.get_latest_session_by_draft_id(self.db, draft.id)
            review_status = latest_session.status if latest_session else "NOT_STARTED"

            # Count issues and contradictions
            latest_val = self.val_repo.get_latest_run_by_draft_id(self.db, draft.id)
            crit_issues = (
                (latest_val.blocker_count + latest_val.error_count)
                if latest_val
                else 0
            )

            latest_verif = self.verif_repo.get_latest_run_by_draft_id(self.db, draft.id)
            contradictions = latest_verif.facts_contradicted if latest_verif else 0
            insufficient = latest_verif.facts_insufficient if latest_verif else 0
            ocr_risks = (
                latest_verif.diagnostics.get("ocr_risk_count", 0)
                if latest_verif and latest_verif.diagnostics
                else 0
            )
            total_facts = latest_verif.facts_total if latest_verif else 0

            resolved_facts = 0
            if latest_session and latest_session.items:
                resolved_facts = sum(
                    1 for i in latest_session.items if i.decision != "PENDING"
                )

            item_dto = ReviewQueueItemDTO(
                draft_id=draft.id,
                internal_scheme_code=draft.internal_scheme_code,
                scheme_name=draft.detected_name,
                department_name=draft.department_name_raw,
                source_filename=doc.original_filename if doc else "document.pdf",
                document_id=draft.document_id,
                draft_status=draft.status,
                review_status=review_status,
                critical_issues=crit_issues,
                contradicted_facts=contradictions,
                insufficient_facts=insufficient,
                ocr_risks=ocr_risks,
                conflicts=draft.conflict_count,
                total_facts=total_facts,
                resolved_facts=resolved_facts,
                last_updated=draft.updated_at,
            )
            queue_items.append(item_dto)

        return ReviewQueueResponse(
            items=queue_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def start_or_get_review_session(
        self,
        draft_id: uuid.UUID,
        reviewer_id: str = "DEV_REVIEWER",
    ) -> HumanReviewSession:
        """Start a new review session or return existing active session."""
        draft = self.db.get(SchemeDraft, draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID '{draft_id}' not found.")

        # Read canonical JSON and compute current SHA-256
        canonical_path = self._resolve_artifact_path(draft.artifact_path)
        if not canonical_path.exists():
            raise FileNotFoundError(f"Canonical draft file not found at {canonical_path}")

        raw_bytes = canonical_path.read_bytes()
        canonical_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        raw_canonical = json.loads(raw_bytes.decode("utf-8"))

        existing_session = self.repo.get_latest_session_by_draft_id(self.db, draft_id)
        if existing_session and existing_session.status not in ["STALE", "REJECTED"]:
            # Check if canonical draft changed while session was open
            if existing_session.canonical_artifact_sha256 != canonical_sha256:
                logger.warning(
                    f"Canonical draft changed for {draft_id}. Marking previous session STALE."
                )
                existing_session.status = "STALE"
                self.db.flush()
            else:
                return existing_session

        # Create new review session
        latest_val = self.val_repo.get_latest_run_by_draft_id(self.db, draft_id)
        latest_verif = self.verif_repo.get_latest_run_by_draft_id(self.db, draft_id)

        next_ver = (existing_session.review_version + 1) if existing_session else 1
        session = self.repo.create_session(
            db=self.db,
            scheme_draft_id=draft_id,
            reviewer_id=reviewer_id,
            canonical_artifact_sha256=canonical_sha256,
            validation_run_id=latest_val.id if latest_val else None,
            evidence_verification_run_id=latest_verif.id if latest_verif else None,
            status=ReviewSessionStatus.IN_PROGRESS.value,
            review_version=next_ver,
        )
        self.db.flush()

        # Update draft status
        draft.status = "IN_HUMAN_REVIEW"
        self.db.flush()

        # Gather validation issues and fact verifications for item correlation
        val_issues = (
            self.val_repo.get_issues_by_draft(self.db, draft_id, limit=500)
            if latest_val
            else []
        )
        fact_verifs = (
            self.verif_repo.get_facts_by_draft(self.db, draft_id, limit=500)
            if latest_verif
            else []
        )

        # Build and persist atomic review items
        items = ReviewItemBuilder.build_review_items(
            review_session_id=session.id,
            scheme_draft_id=draft_id,
            raw_canonical_data=raw_canonical,
            fact_verifications=fact_verifs,
            validation_issues=val_issues,
        )
        self.repo.add_review_items(self.db, items)

        # Append audit event
        self.repo.add_audit_event(
            db=self.db,
            session_id=session.id,
            scheme_draft_id=draft_id,
            reviewer_id=reviewer_id,
            action_type=ReviewActionType.REVIEW_STARTED,
            reason="Review session initiated by reviewer.",
        )

        self.db.commit()
        return session

    def get_review_detail(self, draft_id: uuid.UUID) -> ReviewSessionDetailResponse:
        """Fetch consolidated review workspace data including items, validation, and verification."""
        draft = self.db.get(SchemeDraft, draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID '{draft_id}' not found.")

        session = self.repo.get_latest_session_by_draft_id(self.db, draft_id)
        if not session:
            # Auto-start review session if not yet started
            session = self.start_or_get_review_session(draft_id)

        canonical_path = self._resolve_artifact_path(draft.artifact_path)
        raw_canonical: Dict[str, Any] = {}
        canonical_sha256 = session.canonical_artifact_sha256
        if canonical_path.exists():
            raw_bytes = canonical_path.read_bytes()
            canonical_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            raw_canonical = json.loads(raw_bytes.decode("utf-8"))

        is_stale = session.canonical_artifact_sha256 != canonical_sha256

        # Parse conflicts list
        conflicts_raw = raw_canonical.get("conflicts", [])
        conflicts_dto: List[ConflictItemDTO] = []
        for c in conflicts_raw:
            conflicts_dto.append(
                ConflictItemDTO(
                    conflict_id=c.get("conflict_id", "CONF-000"),
                    field=c.get("field", "unknown"),
                    status=c.get("status", "REVIEW_REQUIRED"),
                    explanation=c.get("explanation"),
                    values=c.get("values", []),
                )
            )

        # Summaries
        latest_val = self.val_repo.get_latest_run_by_draft_id(self.db, draft_id)
        latest_verif = self.verif_repo.get_latest_run_by_draft_id(self.db, draft_id)

        audit_events = self.repo.get_audit_events_by_draft(self.db, draft_id)
        items = session.items or []

        return ReviewSessionDetailResponse(
            session_id=session.id,
            scheme_draft_id=draft_id,
            document_id=draft.document_id,
            internal_scheme_code=draft.internal_scheme_code,
            scheme_name=draft.detected_name,
            department_name=draft.department_name_raw,
            reviewer_id=session.reviewer_id,
            session_status=session.status,
            draft_status=draft.status,
            review_version=session.review_version,
            canonical_artifact_sha256=canonical_sha256,
            is_stale=is_stale,
            notes=session.notes,
            summary={
                "total_items": len(items),
                "approved": sum(1 for i in items if i.decision == "APPROVED"),
                "edited": sum(1 for i in items if i.decision == "EDITED"),
                "rejected": sum(1 for i in items if i.decision == "REJECTED"),
                "not_applicable": sum(1 for i in items if i.decision == "NOT_APPLICABLE"),
                "pending": sum(1 for i in items if i.decision == "PENDING"),
            },
            items=[HumanReviewItemResponse.model_validate(i) for i in items],
            conflicts=conflicts_dto,
            validation_summary=latest_val.diagnostics if latest_val else None,
            verification_summary=latest_verif.diagnostics if latest_verif else None,
            audit_events=audit_events,
            started_at=session.started_at,
            completed_at=session.completed_at,
        )

    def submit_item_decision(
        self,
        item_id: uuid.UUID,
        reviewer_id: str,
        request: ItemDecisionRequest,
        review_version: Optional[int] = None,
    ) -> HumanReviewItem:
        """
        Record reviewer decision on an atomic fact.
        When EDITED: modifies canonical draft on disk, triggers automatic revalidation & reverification.
        """
        item = self.repo.get_item_by_id(self.db, item_id)
        if not item:
            raise ValueError(f"Review item with ID '{item_id}' not found.")

        session = item.review_session
        if review_version is not None and session.review_version != review_version:
            raise ValueError(
                f"Optimistic lock conflict: submitted version {review_version} does not match current {session.review_version}."
            )

        draft = session.scheme_draft
        before_snapshot = item.current_value_json

        # 1. Handle APPROVE
        if request.decision == ReviewDecision.APPROVED:
            # Overriding CONTRADICTED or NOT_ENOUGH_EVIDENCE requires an explicit reason
            if item.verification_result in ["CONTRADICTED", "NOT_ENOUGH_EVIDENCE"]:
                if not request.override_reason and not request.reviewer_comment:
                    raise ValueError(
                        f"Field '{item.field_path}' is {item.verification_result}. "
                        "An explicit override reason is mandatory to approve this field."
                    )

            item.decision = "APPROVED"
            item.reviewer_comment = request.reviewer_comment
            item.override_reason = request.override_reason
            item.reviewed_at = datetime.now(timezone.utc)
            item.reviewed_by = reviewer_id

            action_type = (
                ReviewActionType.VERIFICATION_OVERRIDE
                if request.override_reason
                else ReviewActionType.FIELD_APPROVED
            )
            self.repo.add_audit_event(
                db=self.db,
                session_id=session.id,
                scheme_draft_id=draft.id,
                reviewer_id=reviewer_id,
                action_type=action_type,
                field_path=item.field_path,
                item_id=item.id,
                before_value=before_snapshot,
                after_value=item.current_value_json,
                reason=request.override_reason or request.reviewer_comment or "Field approved by reviewer.",
            )

        # 2. Handle REJECT
        elif request.decision == ReviewDecision.REJECTED:
            item.decision = "REJECTED"
            item.reviewer_comment = request.reviewer_comment
            item.reviewed_at = datetime.now(timezone.utc)
            item.reviewed_by = reviewer_id

            self.repo.add_audit_event(
                db=self.db,
                session_id=session.id,
                scheme_draft_id=draft.id,
                reviewer_id=reviewer_id,
                action_type=ReviewActionType.FIELD_REJECTED,
                field_path=item.field_path,
                item_id=item.id,
                before_value=before_snapshot,
                after_value=None,
                reason=request.reviewer_comment or "Field rejected by reviewer.",
            )

        # 3. Handle NOT_APPLICABLE
        elif request.decision == ReviewDecision.NOT_APPLICABLE:
            item.decision = "NOT_APPLICABLE"
            item.reviewer_comment = request.reviewer_comment
            item.reviewed_at = datetime.now(timezone.utc)
            item.reviewed_by = reviewer_id

            self.repo.add_audit_event(
                db=self.db,
                session_id=session.id,
                scheme_draft_id=draft.id,
                reviewer_id=reviewer_id,
                action_type=ReviewActionType.FIELD_REJECTED,
                field_path=item.field_path,
                item_id=item.id,
                before_value=before_snapshot,
                after_value=None,
                reason=request.reviewer_comment or "Marked NOT_APPLICABLE.",
            )

        # 4. Handle EDIT
        elif request.decision == ReviewDecision.EDITED:
            if not request.edit_value:
                raise ValueError("edit_value dictionary is required when editing a field.")
            if not request.edit_reason:
                raise ValueError("edit_reason is mandatory when modifying canonical facts.")

            after_snapshot = request.edit_value
            item.current_value_json = after_snapshot
            item.decision = "EDITED"
            item.edit_reason = request.edit_reason
            item.reviewer_comment = request.reviewer_comment
            item.reviewed_at = datetime.now(timezone.utc)
            item.reviewed_by = reviewer_id

            # Apply edit to canonical JSON file on disk
            self._apply_field_edit_to_disk(
                draft=draft,
                field_path=item.field_path,
                new_value=after_snapshot,
            )

            # Recompute canonical artifact hash
            canonical_path = self._resolve_artifact_path(draft.artifact_path)
            new_bytes = canonical_path.read_bytes()
            new_sha256 = hashlib.sha256(new_bytes).hexdigest()
            session.canonical_artifact_sha256 = new_sha256
            session.review_version += 1

            self.repo.add_audit_event(
                db=self.db,
                session_id=session.id,
                scheme_draft_id=draft.id,
                reviewer_id=reviewer_id,
                action_type=ReviewActionType.FIELD_EDITED,
                field_path=item.field_path,
                item_id=item.id,
                before_value=before_snapshot,
                after_value=after_snapshot,
                reason=request.edit_reason,
            )

            # Trigger Automatic Revalidation and Re-verification!
            self._revalidate_and_reverify_after_edit(draft, session, item)

        self.db.commit()
        return item

    def resolve_conflict(
        self,
        draft_id: uuid.UUID,
        conflict_id: str,
        reviewer_id: str,
        request: ConflictResolutionRequest,
    ) -> Dict[str, Any]:
        """Resolve an extraction contradiction or version conflict."""
        draft = self.db.get(SchemeDraft, draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID '{draft_id}' not found.")

        session = self.repo.get_latest_session_by_draft_id(self.db, draft_id)
        if not session:
            session = self.start_or_get_review_session(draft_id, reviewer_id)

        canonical_path = self._resolve_artifact_path(draft.artifact_path)
        raw_canonical = json.loads(canonical_path.read_text(encoding="utf-8"))

        updated_canonical, target_conflict = ConflictResolutionService.resolve_conflict_in_canonical_data(
            raw_canonical_data=raw_canonical,
            conflict_id=conflict_id,
            choice=request.choice,
            selected_value=request.selected_value,
        )

        # Write updated canonical JSON back to disk
        canonical_path.write_text(json.dumps(updated_canonical, indent=2, ensure_ascii=False), encoding="utf-8")
        new_sha256 = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
        session.canonical_artifact_sha256 = new_sha256
        session.review_version += 1

        # Decrement unresolved conflict count if resolved
        if request.choice in [ConflictResolutionChoice.SELECT_VALUE, ConflictResolutionChoice.KEEP_CONDITIONAL, ConflictResolutionChoice.REJECT_FIELD]:
            if draft.conflict_count > 0:
                draft.conflict_count -= 1

        self.repo.add_audit_event(
            db=self.db,
            session_id=session.id,
            scheme_draft_id=draft.id,
            reviewer_id=reviewer_id,
            action_type=ReviewActionType.CONFLICT_RESOLVED,
            field_path=target_conflict.get("field") if target_conflict else conflict_id,
            reason=f"Choice: {request.choice.value}. {request.reason}",
        )

        self.db.commit()
        return target_conflict or {}

    def complete_review(
        self,
        draft_id: uuid.UUID,
        reviewer_id: str,
        request: CompleteReviewRequest,
    ) -> Dict[str, Any]:
        """
        Finalize human verification of a canonical scheme draft.
        Enforces strict completion guards, seals verified artifacts, and sets status to HUMAN_VERIFIED.
        """
        draft = self.db.get(SchemeDraft, draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID '{draft_id}' not found.")

        session = self.repo.get_latest_session_by_draft_id(self.db, draft_id)
        if not session:
            raise ValueError("No active review session found for draft.")

        # Optimistic concurrency check
        if request.review_version != session.review_version:
            raise ValueError(
                f"Review version mismatch ({request.review_version} vs {session.review_version}). Reload latest data."
            )

        # Check current canonical SHA-256
        canonical_path = self._resolve_artifact_path(draft.artifact_path)
        canonical_sha256 = hashlib.sha256(canonical_path.read_bytes()).hexdigest()

        # Check for unresolved blockers from latest validation run
        latest_val = self.val_repo.get_latest_run_by_draft_id(self.db, draft_id)
        has_blockers = (latest_val.blocker_count > 0) if latest_val else False

        # Run Completion Guards
        can_complete, blocking_reasons = ReviewCompletionGuard.check_completion_eligibility(
            session=session,
            current_canonical_sha256=canonical_sha256,
            has_unresolved_blockers=has_blockers,
        )

        if not can_complete:
            raise ValueError(
                f"Cannot complete human verification. Blocked by: {'; '.join(blocking_reasons)}"
            )

        # All completion guards passed! Seal verified artifacts
        raw_canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        session.notes = request.notes
        session.completed_at = datetime.now(timezone.utc)
        session.status = ReviewSessionStatus.COMPLETED.value

        artifact_file, summary_payload = VerifiedArtifactBuilder.seal_verified_artifacts(
            session=session,
            raw_canonical_data=raw_canonical,
            validation_report_data=latest_val.diagnostics if latest_val else None,
        )

        session.verified_artifact_path = str(artifact_file.relative_to(self.settings.storage_path))
        session.summary_counts = summary_payload

        # Update draft status
        draft.status = "HUMAN_VERIFIED"

        self.repo.add_audit_event(
            db=self.db,
            session_id=session.id,
            scheme_draft_id=draft.id,
            reviewer_id=reviewer_id,
            action_type=ReviewActionType.SCHEME_APPROVED,
            reason=request.notes or "All review items approved; scheme verified.",
        )
        self.db.commit()

        # Convert and promote draft to primary Scheme, SchemeVersion, and SchemeSearchMetadata
        try:
            from app.services.scheme_conversion_service import SchemeConversionService
            scheme, version = SchemeConversionService.convert_draft_to_scheme(
                session=self.db,
                draft_id_or_model=draft,
                reviewer_id=reviewer_id,
                auto_activate=True,
            )
            logger.info("Successfully converted draft %s to primary Scheme %s (v%d)", draft.id, scheme.scheme_code, version.version_number)
        except Exception as conv_err:
            logger.error("Failed converting draft %s to primary scheme: %s", draft.id, conv_err, exc_info=True)

        # Invalidate/refresh rule cache for this verified scheme
        try:
            from app.cache.verified_rule_cache import get_rule_cache
            cache = get_rule_cache()
            scheme_ident = draft.internal_scheme_code or str(draft.id)
            cache.refresh_scheme(scheme_ident, session=self.db)
            if draft.internal_scheme_code:
                cache.refresh_scheme(str(draft.id), session=self.db)
        except Exception as e:
            logger.warning(f"Could not refresh rule cache for verified scheme {draft.id}: {e}")

        return summary_payload

    def reject_scheme(
        self,
        draft_id: uuid.UUID,
        reviewer_id: str,
        reason: str,
    ) -> HumanReviewSession:
        """Mark entire scheme draft as HUMAN_REJECTED."""
        draft = self.db.get(SchemeDraft, draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID '{draft_id}' not found.")

        session = self.repo.get_latest_session_by_draft_id(self.db, draft_id)
        if not session:
            session = self.start_or_get_review_session(draft_id, reviewer_id)

        session.status = ReviewSessionStatus.REJECTED.value
        session.completed_at = datetime.now(timezone.utc)
        session.notes = f"Rejected: {reason}"

        draft.status = "HUMAN_REJECTED"

        self.repo.add_audit_event(
            db=self.db,
            session_id=session.id,
            scheme_draft_id=draft.id,
            reviewer_id=reviewer_id,
            action_type=ReviewActionType.SCHEME_REJECTED,
            reason=reason,
        )

        self.db.commit()

        try:
            from app.cache.verified_rule_cache import get_rule_cache
            cache = get_rule_cache()
            cache.invalidate(draft.internal_scheme_code or str(draft.id))
            cache.invalidate(str(draft.id))
        except Exception:
            pass

        return session

    def reopen_review(
        self,
        draft_id: uuid.UUID,
        reviewer_id: str,
        reason: str,
    ) -> HumanReviewSession:
        """Reopen a previously completed review session by creating a new versioned session."""
        draft = self.db.get(SchemeDraft, draft_id)
        if not draft:
            raise ValueError(f"SchemeDraft with ID '{draft_id}' not found.")

        prev_session = self.repo.get_latest_session_by_draft_id(self.db, draft_id)
        next_version = (prev_session.review_version + 1) if prev_session else 1

        canonical_path = self._resolve_artifact_path(draft.artifact_path)
        canonical_sha256 = hashlib.sha256(canonical_path.read_bytes()).hexdigest()

        new_session = self.repo.create_session(
            db=self.db,
            scheme_draft_id=draft_id,
            reviewer_id=reviewer_id,
            canonical_artifact_sha256=canonical_sha256,
            status=ReviewSessionStatus.IN_PROGRESS.value,
            review_version=next_version,
        )
        self.db.flush()

        draft.status = "IN_HUMAN_REVIEW"

        # Duplicate prior items into new session as starting point
        if prev_session:
            new_items = []
            for item in prev_session.items:
                new_item = HumanReviewItem(
                    review_session_id=new_session.id,
                    scheme_draft_id=draft_id,
                    fact_id=item.fact_id,
                    field_path=item.field_path,
                    item_type=item.item_type,
                    risk_level=item.risk_level,
                    statement=item.statement,
                    original_value_json=item.original_value_json,
                    current_value_json=item.current_value_json,
                    raw_text=item.raw_text,
                    evidence_refs=item.evidence_refs,
                    evidence_text=item.evidence_text,
                    page_number=item.page_number,
                    block_id=item.block_id,
                    decision=item.decision,
                    reviewer_comment=item.reviewer_comment,
                    edit_reason=item.edit_reason,
                    override_reason=item.override_reason,
                    validation_issues_summary=item.validation_issues_summary,
                    verification_result=item.verification_result,
                    verification_reason_code=item.verification_reason_code,
                    ocr_risk=item.ocr_risk,
                )
                new_items.append(new_item)
            self.repo.add_review_items(self.db, new_items)

        self.repo.add_audit_event(
            db=self.db,
            session_id=new_session.id,
            scheme_draft_id=draft.id,
            reviewer_id=reviewer_id,
            action_type=ReviewActionType.REVIEW_REOPENED,
            reason=reason,
        )

        self.db.commit()
        return new_session

    def _apply_field_edit_to_disk(
        self,
        draft: SchemeDraft,
        field_path: str,
        new_value: Dict[str, Any],
    ) -> None:
        """Updates canonical JSON file on disk at the specified dot/bracket notation path."""
        canonical_path = self._resolve_artifact_path(draft.artifact_path)
        data = json.loads(canonical_path.read_text(encoding="utf-8"))

        # Simple navigation: e.g. eligibility.root_rule.children[0]
        parts = field_path.replace("]", "").split(".")
        curr = data
        for i, part in enumerate(parts[:-1]):
            if "[" in part:
                name, idx_str = part.split("[")
                curr = curr[name][int(idx_str)]
            else:
                curr = curr[part]

        last_part = parts[-1]
        if "[" in last_part:
            name, idx_str = last_part.split("[")
            target_list = curr[name]
            idx = int(idx_str)
            if isinstance(target_list[idx], dict):
                target_list[idx].update(new_value)
            else:
                target_list[idx] = new_value
        else:
            if isinstance(curr.get(last_part), dict):
                curr[last_part].update(new_value)
            else:
                curr[last_part] = new_value

        canonical_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _revalidate_and_reverify_after_edit(
        self,
        draft: SchemeDraft,
        session: HumanReviewSession,
        edited_item: HumanReviewItem,
    ) -> None:
        """Rerun Day 11 deterministic validation and Day 12 evidence verification after field edit."""
        try:
            val_service = SchemeValidationService(self.db)
            val_report = val_service.validate_draft(draft.id, force=True)
            session.validation_run_id = uuid.UUID(val_report.scheme_draft_id) if hasattr(val_report, "run_id") else session.validation_run_id
        except Exception as ex:
            logger.warning(f"Revalidation after edit had notice: {ex}")

        try:
            verif_service = EvidenceVerificationService(self.db)
            verif_report = verif_service.verify_scheme_draft(draft.id, force=True)
            # Find updated fact evaluation for this edited item
            for f in verif_report.facts:
                if f.field_path == edited_item.field_path or f.fact_id == edited_item.fact_id:
                    edited_item.verification_result = f.result.value
                    edited_item.verification_reason_code = f.reason_code.value
                    break
        except Exception as ex:
            logger.warning(f"Re-verification after edit had notice: {ex}")

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
