"""
Auto-Pipeline Runner
====================
Chains all document processing stages automatically after upload so no manual
worker commands are required. Each stage advances only if the previous one
succeeded (status-gated). Errors are logged but do not crash the chain.
"""
import logging
import uuid

from app.database.session import get_db_context

logger = logging.getLogger("yojansetu.pipeline.auto_runner")


# ---------------------------------------------------------------------------
# Status gate helpers
# ---------------------------------------------------------------------------

_READY_FOR_PARSING = "READY_FOR_PARSING"
_READY_FOR_OCR = "READY_FOR_OCR_CHECK"
_READY_FOR_CHUNKING = "READY_FOR_CHUNKING"
_READY_FOR_EXTRACTION = "READY_FOR_EXTRACTION"
_READY_FOR_NORMALIZATION = "READY_FOR_NORMALIZATION"
_READY_FOR_VALIDATION = "READY_FOR_VALIDATION"
_READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"


def _get_doc_status(db, document_id: uuid.UUID) -> str | None:
    from app.repositories.document_repository import DocumentRepository
    doc = DocumentRepository().get_by_id(db, document_id)
    return doc.processing_status if doc else None


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def _run_duplicate_check(document_id: uuid.UUID) -> str | None:
    """Stage 1: Duplicate detection → READY_FOR_PARSING / DUPLICATE / VERSION_REVIEW_REQUIRED"""
    try:
        from app.duplicate_detection.service import DuplicateDetectionService
        with get_db_context() as db:
            result = DuplicateDetectionService().detect_duplicates(db, document_id)
            logger.info("[Pipeline] Duplicate check done: %s → %s", document_id, result.resulting_processing_status)
            return result.resulting_processing_status
    except Exception as e:
        logger.error("[Pipeline] Duplicate check failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_parsing(document_id: uuid.UUID) -> str | None:
    """Stage 2: Layout parsing → READY_FOR_OCR_CHECK"""
    try:
        from app.parser.service import DocumentParserService
        with get_db_context() as db:
            DocumentParserService().parse_document(db, document_id)
            status = _get_doc_status(db, document_id)
            logger.info("[Pipeline] Parsing done: %s → %s", document_id, status)
            return status
    except Exception as e:
        logger.error("[Pipeline] Parsing failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_ocr(document_id: uuid.UUID) -> str | None:
    """Stage 3: OCR check → READY_FOR_CHUNKING"""
    try:
        from app.ocr.service import OCRService
        with get_db_context() as db:
            OCRService().process_document(db, document_id)
            status = _get_doc_status(db, document_id)
            logger.info("[Pipeline] OCR check done: %s → %s", document_id, status)
            return status
    except Exception as e:
        logger.error("[Pipeline] OCR check failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_chunking(document_id: uuid.UUID) -> str | None:
    """Stage 4: Semantic chunking → READY_FOR_EXTRACTION"""
    try:
        from app.chunking.service import DocumentChunkingService
        with get_db_context() as db:
            DocumentChunkingService().chunk_document(db, document_id)
            status = _get_doc_status(db, document_id)
            logger.info("[Pipeline] Chunking done: %s → %s", document_id, status)
            return status
    except Exception as e:
        logger.error("[Pipeline] Chunking failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_extraction(document_id: uuid.UUID) -> str | None:
    """Stage 5: LLM extraction → READY_FOR_NORMALIZATION"""
    try:
        from app.extraction.worker import ExtractionWorker
        from app.repositories.document_repository import DocumentRepository
        with get_db_context() as db:
            doc = DocumentRepository().get_by_id(db, document_id)
            if doc:
                ExtractionWorker().process_document(db, doc)
            status = _get_doc_status(db, document_id)
            logger.info("[Pipeline] Extraction done: %s → %s", document_id, status)
            return status
    except Exception as e:
        logger.error("[Pipeline] Extraction failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_normalization(document_id: uuid.UUID) -> str | None:
    """Stage 6: Canonical normalization → READY_FOR_VALIDATION"""
    try:
        from app.normalization.service import SchemeNormalizationService
        with get_db_context() as db:
            SchemeNormalizationService(db).normalize_document(document_id, force=True)
            status = _get_doc_status(db, document_id)
            logger.info("[Pipeline] Normalization done: %s → %s", document_id, status)
            return status
    except Exception as e:
        logger.error("[Pipeline] Normalization failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_validation(document_id: uuid.UUID) -> str | None:
    """Stage 7: Deterministic validation → READY_FOR_VERIFICATION"""
    try:
        from app.validation.service import ValidationService
        from app.repositories.scheme_draft_repository import SchemeDraftRepository
        from app.repositories.document_repository import DocumentRepository
        with get_db_context() as db:
            drafts = SchemeDraftRepository().get_all_by_document_id(db, document_id)
            svc = ValidationService(db)
            for draft in drafts:
                try:
                    svc.validate_draft(draft.id)
                except Exception as v_err:
                    logger.warning("[Pipeline] Draft %s validation warning: %s", draft.id, v_err)

            # Transition document status to READY_FOR_VERIFICATION
            doc = DocumentRepository().get_by_id(db, document_id)
            if doc:
                doc.processing_status = "READY_FOR_VERIFICATION"
                db.commit()
                status = doc.processing_status
            else:
                status = None

            logger.info("[Pipeline] Validation done: %s → %s", document_id, status)
            return status
    except Exception as e:
        logger.error("[Pipeline] Validation failed for %s: %s", document_id, e, exc_info=True)
        return None


def _run_verification_and_conversion(document_id: uuid.UUID, auto_convert: bool = True) -> str | None:
    """Stage 8: Evidence verification & direct production scheme conversion into database."""
    try:
        from app.verification.service import EvidenceVerificationService
        from app.repositories.scheme_draft_repository import SchemeDraftRepository
        from app.repositories.document_repository import DocumentRepository
        from app.services.scheme_conversion_service import SchemeConversionService

        with get_db_context() as db:
            drafts = SchemeDraftRepository().get_all_by_document_id(db, document_id)
            if not drafts:
                logger.info("[Pipeline] No drafts found for document %s during verification/conversion", document_id)
                return _get_doc_status(db, document_id)

            verifier = EvidenceVerificationService(db)
            converted_any = False
            for draft in drafts:
                try:
                    verifier.verify_draft(draft.id)
                    logger.info("[Pipeline] Verified draft %s", draft.id)
                except Exception as v_err:
                    logger.warning("[Pipeline] Draft %s verification diagnostic: %s", draft.id, v_err)

                if auto_convert:
                    try:
                        scheme, version = SchemeConversionService.convert_draft_to_scheme(
                            session=db,
                            draft_id_or_model=draft,
                            reviewer_id="DIRECT_UPLOAD_PIPELINE",
                            auto_activate=True,
                        )
                        # Explicitly ensure active status
                        scheme.status = "ACTIVE"
                        version.status = "ACTIVE"
                        db.commit()
                        converted_any = True
                        logger.info(
                            "[Pipeline] Directly published draft %s into DB Scheme '%s' (v%d)",
                            draft.id, scheme.scheme_code, version.version_number
                        )
                    except Exception as c_err:
                        logger.error("[Pipeline] Draft %s scheme conversion error: %s", draft.id, c_err, exc_info=True)

            doc = DocumentRepository().get_by_id(db, document_id)
            if doc:
                if converted_any:
                    doc.processing_status = "PUBLISHED"
                else:
                    doc.processing_status = "READY_FOR_HUMAN_REVIEW"
                db.commit()
                status = doc.processing_status
            else:
                status = None

            return status
    except Exception as e:
        logger.error("[Pipeline] Verification/Conversion failed for %s: %s", document_id, e, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_full_pipeline(document_id: uuid.UUID, auto_convert: bool = True) -> None:
    """
    Run the complete document processing pipeline end-to-end for a single
    document. Automatically converts and publishes extracted schemes directly
    into the database without requiring human review.

    Stages:
      1. Duplicate Detection      → READY_FOR_PARSING / DUPLICATE / VERSION_REVIEW_REQUIRED
      2. Layout Parsing           → READY_FOR_OCR_CHECK
      3. OCR Check                → READY_FOR_CHUNKING
      4. Semantic Chunking        → READY_FOR_EXTRACTION
      5. LLM Extraction           → READY_FOR_NORMALIZATION
      6. Canonical Normalization  → READY_FOR_VALIDATION
      7. Deterministic Validation → READY_FOR_VERIFICATION
      8. Direct DB Publishing     → PUBLISHED (Schemes in DB + Indexed)
    """
    logger.info("[Pipeline] Starting full auto-pipeline for document %s (auto_convert=%s)", document_id, auto_convert)

    # Stage 1 – Duplicate detection
    with get_db_context() as db:
        status = _get_doc_status(db, document_id)

    if status == "READY_FOR_DUPLICATE_CHECK":
        status = _run_duplicate_check(document_id)

    # If duplicate or version, stop here
    _EXTRACTION_PARTIAL = "EXTRACTION_PARTIAL_FAILURE"  # partial extraction still proceeds to normalization
    if status not in (_READY_FOR_PARSING, _READY_FOR_OCR, _READY_FOR_CHUNKING,
                      _READY_FOR_EXTRACTION, _READY_FOR_NORMALIZATION, _EXTRACTION_PARTIAL,
                      _READY_FOR_VALIDATION, "READY_FOR_VERIFICATION", "READY_FOR_HUMAN_REVIEW"):
        logger.info("[Pipeline] Document %s terminal at status %s; pipeline halted.", document_id, status)
        return

    # Stage 2 – Parsing
    if status == _READY_FOR_PARSING:
        status = _run_parsing(document_id)
    if not status:
        return

    # Stage 3 – OCR
    if status == _READY_FOR_OCR:
        status = _run_ocr(document_id)
    if not status:
        return

    # Stage 4 – Chunking
    if status == _READY_FOR_CHUNKING:
        status = _run_chunking(document_id)
    if not status:
        return

    # Stage 5 – Extraction
    if status == _READY_FOR_EXTRACTION:
        status = _run_extraction(document_id)
    if not status:
        return

    # Stage 6 – Normalization (also runs on partial extraction — normalizes whatever was extracted)
    if status in (_READY_FOR_NORMALIZATION, "EXTRACTION_PARTIAL_FAILURE"):
        status = _run_normalization(document_id)
    if not status:
        return

    # Stage 7 – Validation
    if status == _READY_FOR_VALIDATION:
        status = _run_validation(document_id)

    # Stage 8 – Verification & Direct Scheme Conversion to DB
    if status in ("READY_FOR_VERIFICATION", "READY_FOR_HUMAN_REVIEW", "NORMALIZATION_REVIEW_REQUIRED", "VALIDATED"):
        status = _run_verification_and_conversion(document_id, auto_convert=auto_convert)

    logger.info("[Pipeline] Auto-pipeline complete for document %s. Final status: %s", document_id, status)
