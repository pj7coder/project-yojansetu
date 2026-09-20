import json
import logging
import re
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.department import Department
from app.database.models.document import Document
from app.database.models.normalization_run import NormalizationRun
from app.database.models.scheme_draft import SchemeDraft
from app.normalization.aggregator import DocumentSchemeAggregator
from app.normalization.benefits import normalize_benefit
from app.normalization.conflicts import detect_conflicts
from app.normalization.dates import parse_date_expression
from app.normalization.documents import normalize_document_requirement
from app.normalization.eligibility import build_eligibility_tree, normalize_single_criterion
from app.normalization.schemas import (
    ApplicationChannelEnum,
    CanonicalApplication,
    CanonicalContact,
    CanonicalDefinition,
    CanonicalExclusion,
    CanonicalIdentity,
    CanonicalImportantDate,
    CanonicalSchemeDraft,
    CanonicalScope,
    NormalizationStatus,
    NormalizationSummary,
    SchemeNameDetail,
    SchemeOriginEnum,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_repository import ExtractionRunRepository
from app.repositories.scheme_draft_repository import NormalizationRunRepository, SchemeDraftRepository

logger = logging.getLogger("yojansetu.normalization.service")


class SchemeNormalizationService:
    """
    Core service coordinating Layer 2 (Raw Extractions) to Layer 3 (Canonical Scheme Drafts).
    Validates readiness, manages schema normalization, audits conflicts, and produces
    validated canonical scheme draft artifacts.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.doc_repo = DocumentRepository()
        self.extraction_repo = ExtractionRunRepository()
        self.draft_repo = SchemeDraftRepository()
        self.norm_run_repo = NormalizationRunRepository()
        self.dept_repo = DepartmentRepository()

    def normalize_document(
        self,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end normalization for an ingested document.
        Idempotent: Cleanly updates or replaces existing drafts for this document.
        """
        start_time = time.time()
        self.settings.ensure_storage_dirs()

        doc = self.doc_repo.get_by_id(self.db, document_id)
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found")

        # 1. Validation of Readiness
        valid_statuses = {
            "READY_FOR_NORMALIZATION",
            "EXTRACTION_PARTIAL_FAILURE",  # partial extraction: normalize whatever succeeded
            "NORMALIZED",
            "NORMALIZATION_REVIEW_REQUIRED",
            "NORMALIZATION_FAILED",
        }
        if not force and doc.processing_status not in valid_statuses:
            logger.warning(
                "Document %s in status %s is not ready for normalization",
                document_id,
                doc.processing_status,
            )
            # Check if extraction incomplete
            doc.processing_status = "NORMALIZATION_BLOCKED"
            self.doc_repo.update(self.db, doc)
            raise ValueError(
                f"Document status '{doc.processing_status}' cannot be normalized. Expected 'READY_FOR_NORMALIZATION'."
            )

        # 2. Transition status to NORMALIZING
        doc.processing_status = "NORMALIZING"
        self.doc_repo.update(self.db, doc)

        norm_run = NormalizationRun(
            document_id=doc.id,
            schema_version=self.settings.canonical_schema_version,
            normalizer_version=self.settings.normalizer_version,
            status="NORMALIZING",
            schemes_detected=0,
            fields_normalized=0,
            fields_ambiguous=0,
            conflicts_detected=0,
            started_at=doc.created_at,  # will be updated on complete
        )
        self.norm_run_repo.create(self.db, norm_run)

        try:
            # 3. Load Extractions
            chunk_extractions = self._load_extractions(doc)
            if not chunk_extractions:
                logger.info("No raw extractions found for document %s", doc.id)
                norm_run.status = "NO_SCHEME_FOUND"
                norm_run.schemes_detected = 0
                norm_run.duration_ms = int((time.time() - start_time) * 1000)
                self.norm_run_repo.update(self.db, norm_run)

                doc.processing_status = "NORMALIZED"
                self.doc_repo.update(self.db, doc)
                return {
                    "document_id": str(doc.id),
                    "status": "NO_SCHEME_FOUND",
                    "schemes_detected": 0,
                    "drafts": [],
                }

            # 4. Group by scheme candidate
            depts = self.dept_repo.get_all(self.db)
            aggregator = DocumentSchemeAggregator(departments=depts)
            scheme_bundles = aggregator.group_schemes_from_chunks(
                document_id=str(doc.id),
                doc_code=doc.document_code,
                chunk_extractions=chunk_extractions,
            )

            if not scheme_bundles:
                logger.info("Document %s contained no scheme entities (administrative only)", doc.id)
                norm_run.status = "NO_SCHEME_FOUND"
                norm_run.schemes_detected = 0
                norm_run.duration_ms = int((time.time() - start_time) * 1000)
                self.norm_run_repo.update(self.db, norm_run)

                doc.processing_status = "NORMALIZED"
                self.doc_repo.update(self.db, doc)
                return {
                    "document_id": str(doc.id),
                    "status": "NO_SCHEME_FOUND",
                    "schemes_detected": 0,
                    "drafts": [],
                }

            # Idempotency: Clean up any prior drafts for this document
            self.draft_repo.delete_by_document_id(self.db, doc.id)

            total_normalized = 0
            total_ambiguous = 0
            total_conflicts = 0
            created_drafts: List[SchemeDraft] = []
            has_conflicts = False
            has_association_review = False

            # 5. Process each scheme bundle
            for bundle in scheme_bundles:
                draft_model, canonical_obj = self._process_scheme_bundle(
                    doc=doc,
                    bundle=bundle,
                    norm_run_id=norm_run.id,
                    aggregator=aggregator,
                )
                self.draft_repo.create(self.db, draft_model)
                created_drafts.append(draft_model)

                total_normalized += canonical_obj.normalization_summary.fields_normalized
                total_ambiguous += canonical_obj.normalization_summary.fields_ambiguous
                total_conflicts += canonical_obj.normalization_summary.conflicts

                if canonical_obj.conflicts:
                    has_conflicts = True
                if bundle.get("requires_association_review"):
                    has_association_review = True

            # 6. Finalize Run Status & Metrics
            duration_ms = int((time.time() - start_time) * 1000)
            norm_run.schemes_detected = len(created_drafts)
            norm_run.fields_normalized = total_normalized
            norm_run.fields_ambiguous = total_ambiguous
            norm_run.conflicts_detected = total_conflicts
            norm_run.duration_ms = duration_ms

            if has_conflicts or has_association_review:
                norm_run.status = "NORMALIZATION_REVIEW_REQUIRED"
                doc.processing_status = "NORMALIZATION_REVIEW_REQUIRED"
            else:
                norm_run.status = "NORMALIZED"
                doc.processing_status = "READY_FOR_VALIDATION"

            self.norm_run_repo.update(self.db, norm_run)
            self.doc_repo.update(self.db, doc)

            return {
                "document_id": str(doc.id),
                "status": doc.processing_status,
                "schemes_detected": len(created_drafts),
                "duration_ms": duration_ms,
                "drafts": [
                    {
                        "draft_id": str(d.id),
                        "internal_scheme_code": d.internal_scheme_code,
                        "detected_name": d.detected_name,
                        "status": d.status,
                        "conflict_count": d.conflict_count,
                        "artifact_path": d.artifact_path,
                    }
                    for d in created_drafts
                ],
            }

        except Exception as e:
            logger.exception("Normalization failed for document %s: %s", doc.id, e)
            norm_run.status = "NORMALIZATION_FAILED"
            norm_run.failure_reason = str(e)
            norm_run.duration_ms = int((time.time() - start_time) * 1000)
            self.norm_run_repo.update(self.db, norm_run)

            doc.processing_status = "NORMALIZATION_FAILED"
            self.doc_repo.update(self.db, doc)
            raise

    def _process_scheme_bundle(
        self,
        doc: Document,
        bundle: Dict[str, Any],
        norm_run_id: uuid.UUID,
        aggregator: DocumentSchemeAggregator,
    ) -> Tuple[SchemeDraft, CanonicalSchemeDraft]:
        """Convert a raw scheme bundle into a CanonicalSchemeDraft and SchemeDraft DB model."""
        draft_id = uuid.uuid4()
        draft_code = bundle["internal_scheme_code"]
        doc_id_str = str(doc.id)

        # Build evidence registry
        evidence_registry, snippet_to_id = aggregator.build_evidence_registry_for_bundle(
            document_id=doc_id_str,
            bundle=bundle,
        )

        def get_evidence_refs(raw_item: Any) -> List[str]:
            refs = []
            if isinstance(raw_item, dict):
                ev = raw_item.get("evidence")
                if isinstance(ev, dict):
                    t = ev.get("evidence_text", "").strip()
                    if t in snippet_to_id:
                        refs.append(snippet_to_id[t])
            elif isinstance(raw_item, str) and raw_item.strip() in snippet_to_id:
                refs.append(snippet_to_id[raw_item.strip()])
            return refs

        # 1. Identity
        primary_name = bundle["primary_name"]
        canonical_identity = CanonicalIdentity(
            scheme_id=draft_code,
            name=SchemeNameDetail(raw=primary_name),
            official_name_raw=primary_name,
            normalized_name_for_matching=bundle["normalized_name"],
            department=bundle.get("matched_department_name") or bundle.get("department_raw"),
            department_id=bundle.get("matched_department_id"),
            jurisdiction="RAJASTHAN",
            scheme_origin=SchemeOriginEnum.RAJASTHAN_STATE,
        )

        # 2. Scope
        canonical_scope = CanonicalScope(state="Rajasthan")

        # 3. Eligibility conditions
        raw_conditions: List[str] = []
        cond_evidence_map: Dict[int, List[str]] = {}
        for raw_s in bundle["raw_schemes"]:
            for cond in raw_s.get("eligibility_conditions", []):
                if isinstance(cond, dict):
                    # extraction schema field is "condition", not "clause"
                    clause = cond.get("condition") or cond.get("clause", "")
                    if clause:
                        idx = len(raw_conditions)
                        raw_conditions.append(clause)
                        cond_evidence_map[idx] = get_evidence_refs(cond)

        normalized_conditions = []
        for idx, text in enumerate(raw_conditions):
            refs = cond_evidence_map.get(idx, [])
            c_norm = normalize_single_criterion(text, refs, idx + 1)
            normalized_conditions.append(c_norm)

        # Run conflict detection & duplicate merging
        processed_conditions, conflicts = detect_conflicts(normalized_conditions)
        canonical_eligibility = build_eligibility_tree(processed_conditions)

        # 4. Exclusions
        exclusions: List[CanonicalExclusion] = []
        excl_counter = 1
        for raw_s in bundle["raw_schemes"]:
            for excl in raw_s.get("exclusions", []):
                if isinstance(excl, dict):
                    # extraction schema field is "exclusion", not "condition"
                    t = excl.get("exclusion") or excl.get("condition", "")
                    if t:
                        exclusions.append(
                            CanonicalExclusion(
                                exclusion_id=f"EXCL-{excl_counter:03d}",
                                raw_text=t,
                                evidence_refs=get_evidence_refs(excl),
                            )
                        )
                        excl_counter += 1

        # 5. Benefits
        benefits = []
        ben_counter = 1
        for raw_s in bundle["raw_schemes"]:
            for ben in raw_s.get("benefits", []):
                if isinstance(ben, dict):
                    # extraction schema fields: raw_amount, frequency_text, description
                    b_norm = normalize_benefit(
                        raw_text=ben.get("description") or ben.get("benefit_description", ""),
                        raw_amount=ben.get("raw_amount") or ben.get("amount"),
                        frequency_text=ben.get("frequency_text") or ben.get("frequency"),
                        description=ben.get("description") or ben.get("benefit_description"),
                        benefit_type_hint=ben.get("benefit_type"),
                        evidence_refs=get_evidence_refs(ben),
                        benefit_id=f"BEN-{ben_counter:03d}",
                    )
                    benefits.append(b_norm)
                    ben_counter += 1

        # 6. Required Documents
        required_documents = []
        doc_req_counter = 1
        for raw_s in bundle["raw_schemes"]:
            for d in raw_s.get("required_documents", []):
                if isinstance(d, dict):
                    d_norm = normalize_document_requirement(
                        name_raw=d.get("document_name", ""),
                        mandatory_stated=d.get("mandatory"),
                        notes=d.get("purpose"),
                        evidence_refs=get_evidence_refs(d),
                        doc_id=f"DOC-REQ-{doc_req_counter:03d}",
                    )
                    required_documents.append(d_norm)
                    doc_req_counter += 1

        # 7. Application procedure
        app_steps = []
        app_channels = []
        portal_url = None
        for raw_s in bundle["raw_schemes"]:
            for step in raw_s.get("application_process", []):
                if isinstance(step, dict):
                    # extraction schema field is "description", not "procedure"
                    proc = step.get("description") or step.get("procedure", "")
                    if proc:
                        app_steps.append(proc)
                        p_lower = proc.lower()
                        if "online" in p_lower or "portal" in p_lower:
                            app_channels.append(ApplicationChannelEnum.ONLINE)
                        if "emitra" in p_lower or "e-mitra" in p_lower:
                            app_channels.append(ApplicationChannelEnum.EMITRA)
                        if "sso" in p_lower:
                            app_channels.append(ApplicationChannelEnum.SSO)
                        if "office" in p_lower or "कार्यालय" in p_lower:
                            app_channels.append(ApplicationChannelEnum.OFFLINE)
                        if "http" in p_lower:
                            m_url = re.search(r'(https?://[^\s]+)', proc)
                            if m_url:
                                portal_url = m_url.group(1)

        canonical_app = CanonicalApplication(
            channels=list(set(app_channels)) or [ApplicationChannelEnum.OTHER],
            portal_url=portal_url,
            steps=app_steps,
        )

        # 8. Important Dates
        important_dates = []
        for raw_s in bundle["raw_schemes"]:
            for dt in raw_s.get("important_dates", []):
                if isinstance(dt, dict):
                    # extraction schema fields: raw_date_text, event_name
                    raw_dt_str = dt.get("raw_date_text") or dt.get("date_or_period", "")
                    if raw_dt_str:
                        d_info = parse_date_expression(raw_dt_str)
                        important_dates.append(
                            CanonicalImportantDate(
                                event_name=dt.get("event_name") or dt.get("event", "Milestone Date"),
                                date_type=d_info["date_type"],
                                normalized_date=d_info["normalized_date"],
                                raw_date_text=raw_dt_str,
                                relative_duration=d_info["relative_duration"],
                                evidence_refs=get_evidence_refs(dt),
                            )
                        )

        # 9. Contacts
        contacts = []
        for raw_s in bundle["raw_schemes"]:
            for ct in raw_s.get("contacts", []):
                if isinstance(ct, dict):
                    # extraction schema field is "value", not "details"
                    val = ct.get("value") or ct.get("details", "")
                    if val:
                        contacts.append(
                            CanonicalContact(
                                contact_type=ct.get("contact_type", "contact"),
                                value=val,
                                raw_text=val,
                                evidence_refs=get_evidence_refs(ct),
                            )
                        )

        # Summary Counts
        f_norm = len(processed_conditions) + len(benefits) + len(required_documents) + len(important_dates)
        f_ambig = sum(1 for c in processed_conditions if c.normalization_status == NormalizationStatus.AMBIGUOUS)
        f_conf = len(conflicts)

        summary = NormalizationSummary(
            fields_normalized=f_norm,
            fields_ambiguous=f_ambig,
            conflicts=f_conf,
            unresolved=f_ambig + f_conf,
            evidence_items_registered=len(evidence_registry),
        )

        # Determine draft status
        draft_status = "READY_FOR_VALIDATION"
        if conflicts:
            draft_status = "NORMALIZATION_REVIEW_REQUIRED"
        elif bundle.get("requires_association_review"):
            draft_status = "SCHEME_ASSOCIATION_REVIEW_REQUIRED"

        # Construct Canonical Scheme Draft
        canonical_draft = CanonicalSchemeDraft(
            schema_version=self.settings.canonical_schema_version,
            normalizer_version=self.settings.normalizer_version,
            internal_scheme_code=draft_code,
            document_id=doc_id_str,
            status=draft_status,
            scheme_identity=canonical_identity,
            scope=canonical_scope,
            eligibility=canonical_eligibility,
            exclusions=exclusions,
            benefits=benefits,
            required_documents=required_documents,
            application=canonical_app,
            important_dates=important_dates,
            contacts=contacts,
            definitions=[],
            evidence_registry=evidence_registry,
            conflicts=conflicts,
            normalization_summary=summary,
        )

        # Write artifacts to storage/normalized/<doc_id>/<draft_id>/
        draft_dir = self.settings.normalized_dir / doc_id_str / str(draft_id)
        draft_dir.mkdir(parents=True, exist_ok=True)

        canonical_path = draft_dir / "canonical.json"
        with open(canonical_path, "w", encoding="utf-8") as f:
            f.write(canonical_draft.model_dump_json(indent=2))

        conflicts_path = draft_dir / "conflicts.json"
        with open(conflicts_path, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in conflicts], f, indent=2, ensure_ascii=False)

        report_path = draft_dir / "normalization_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)

        relative_artifact_path = f"storage/normalized/{doc_id_str}/{draft_id}/canonical.json"

        # Create SchemeDraft database model
        draft_db = SchemeDraft(
            id=draft_id,
            document_id=doc.id,
            normalization_run_id=norm_run_id,
            internal_scheme_code=draft_code,
            detected_name=primary_name,
            official_name_raw=primary_name,
            normalized_name_for_matching=bundle["normalized_name"],
            department_id=uuid.UUID(bundle["matched_department_id"]) if bundle.get("matched_department_id") else None,
            department_name_raw=bundle.get("department_raw"),
            schema_version=self.settings.canonical_schema_version,
            normalizer_version=self.settings.normalizer_version,
            status=draft_status,
            artifact_path=relative_artifact_path,
            conflict_count=f_conf,
            unresolved_field_count=summary.unresolved,
            summary_counts=summary.model_dump(),
        )

        return draft_db, canonical_draft

    def _load_extractions(self, doc: Document) -> List[Dict[str, Any]]:
        """Load raw chunk extractions (ChunkExtractionResult dicts) for normalization.

        Tries three strategies in order:
        1. Read chunk_summaries from master document_extractions.json → load each
           chunk's extraction.json artifact from its subdirectory.
        2. Walk storage/extracted/<doc_id>/**/extraction.json directly.
        3. Load from ExtractionRun DB records (artifact_path column).
        """
        base_dir = Path(self.settings.base_dir).resolve()
        doc_id_str = str(doc.id)

        # --- Strategy 1: Via master document_extractions.json chunk_summaries ---
        master_path = self.settings.extracted_dir / doc_id_str / "document_extractions.json"
        if master_path.exists():
            try:
                with open(master_path, "r", encoding="utf-8") as f:
                    master = json.load(f)

                results: List[Dict[str, Any]] = []
                for summary in master.get("chunk_summaries", []):
                    # Only include successfully extracted chunks
                    if summary.get("status") not in ("EXTRACTED", "EXTRACTION_REVIEW_REQUIRED"):
                        continue
                    art_path = summary.get("artifact_path", "")
                    if not art_path:
                        continue
                    ext_file = (base_dir / art_path).resolve()
                    if ext_file.exists():
                        try:
                            with open(ext_file, "r", encoding="utf-8") as ef:
                                payload = json.load(ef)
                                if payload.get("schemes") is not None:
                                    results.append(payload)
                        except Exception as e:
                            logger.warning("Could not read extraction artifact %s: %s", ext_file, e)

                if results:
                    logger.info(
                        "Loaded %d chunk extractions via master document_extractions.json for %s",
                        len(results), doc_id_str,
                    )
                    return results
            except Exception as e:
                logger.warning("Could not parse master extraction artifact for %s: %s", doc_id_str, e)

        # --- Strategy 2: Glob storage/extracted/<doc_id>/**/extraction.json ---
        extracted_doc_dir = self.settings.extracted_dir / doc_id_str
        if extracted_doc_dir.exists():
            # Files are nested: storage/extracted/<doc_id>/<chunk_id_str>/extraction.json
            chunk_files = list(extracted_doc_dir.glob("*/extraction.json"))
            if chunk_files:
                results = []
                for cf in sorted(chunk_files):
                    try:
                        with open(cf, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            if payload.get("schemes") is not None:
                                results.append(payload)
                    except Exception as e:
                        logger.warning("Error reading %s: %s", cf, e)
                if results:
                    logger.info(
                        "Loaded %d chunk extractions via glob for %s",
                        len(results), doc_id_str,
                    )
                    return results

        # --- Strategy 3: ExtractionRun DB records via artifact_path ---
        runs = self.extraction_repo.get_all_by_document_id(self.db, doc.id)
        db_results = []
        for r in runs:
            # Statuses set by extraction service are EXTRACTED / EXTRACTION_REVIEW_REQUIRED
            if r.status not in ("EXTRACTED", "EXTRACTION_REVIEW_REQUIRED"):
                continue
            if not r.artifact_path:
                continue
            art_file = (base_dir / r.artifact_path).resolve()
            if art_file.exists():
                try:
                    with open(art_file, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                        if payload.get("schemes") is not None:
                            db_results.append(payload)
                except Exception as e:
                    logger.warning("Error reading DB artifact %s: %s", art_file, e)

        if db_results:
            logger.info(
                "Loaded %d chunk extractions via DB ExtractionRun records for %s",
                len(db_results), doc_id_str,
            )
        return db_results
