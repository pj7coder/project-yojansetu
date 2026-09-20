from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.ocr_run import OCRRun
from app.ocr.detector import OCRDetectionService
from app.ocr.interface import (
    ExtractionMethod,
    OCREngineUnavailableException,
    OCRError,
    OCRPageResult,
    OCRProvider,
    OCRStatus,
)
from app.ocr.merger import OCRMergeService
from app.ocr.paddle import MockOCRProvider, PaddleOCRAdapter
from app.ocr.renderer import PDFPageRenderer
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_repository import OCRRunRepository
from app.ingestion.storage import StorageManager

logger = logging.getLogger("jansetu.ocr.service")


class OCRService:
    """
    Central orchestration service managing OCR detection, targeted page OCR,
    output merging, and transition from READY_FOR_OCR_CHECK to READY_FOR_CHUNKING.
    """

    def __init__(
        self,
        provider: Optional[OCRProvider] = None,
        detector: Optional[OCRDetectionService] = None,
        renderer: Optional[PDFPageRenderer] = None,
        merger: Optional[OCRMergeService] = None,
        doc_repo: Optional[DocumentRepository] = None,
        ocr_repo: Optional[OCRRunRepository] = None,
        storage: Optional[StorageManager] = None,
    ):
        self.settings = get_settings()
        self.detector = detector or OCRDetectionService()
        self.renderer = renderer or PDFPageRenderer()
        self.merger = merger or OCRMergeService()
        self.doc_repo = doc_repo or DocumentRepository()
        self.ocr_repo = ocr_repo or OCRRunRepository()
        self.storage = storage or StorageManager()

        # Resolve OCR provider
        if provider:
            self.provider = provider
        elif self.settings.ocr_provider == "mock":
            self.provider = MockOCRProvider()
        else:
            paddle_adapter = PaddleOCRAdapter(device=self.settings.ocr_device)
            if paddle_adapter.is_available():
                self.provider = paddle_adapter
            elif self.settings.ocr_fallback_enabled:
                logger.warning(
                    "PaddleOCR unavailable in this environment; falling back to MockOCRProvider."
                )
                self.provider = MockOCRProvider()
            else:
                self.provider = paddle_adapter

    def process_document(
        self,
        db: Session,
        document_id: uuid.UUID,
        force: bool = False,
        **kwargs: Any,
    ) -> OCRRun:
        """
        Execute OCR detection and page-level fallback for a document.

        Args:
            db: SQLAlchemy database session
            document_id: Unique UUID of document entity
            force: Re-process even if already completed
        """
        doc = self.doc_repo.get_by_id(db, document_id)
        if not doc:
            raise ValueError(f"Document with ID {document_id} does not exist.")

        # Idempotency check: If already ready for chunking and not forced, return existing record
        if doc.processing_status == "READY_FOR_CHUNKING" and not force:
            existing = self.ocr_repo.get_latest_by_document_id(db, document_id)
            if existing:
                logger.info(
                    "Document %s already processed for OCR -> READY_FOR_CHUNKING; returning existing record",
                    doc.document_code,
                )
                return existing

        # Validate input lifecycle status
        valid_states = ["READY_FOR_OCR_CHECK", "OCR_FAILED"]
        if force:
            valid_states.extend(["READY_FOR_CHUNKING", "OCR_PROCESSING", "OCR_CHECKING"])

        if doc.processing_status not in valid_states:
            raise ValueError(
                f"Document {doc.document_code} is in status '{doc.processing_status}'. "
                f"Only documents in {valid_states} can undergo OCR check."
            )

        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc)

        # Update status to OCR_CHECKING
        doc.processing_status = "OCR_CHECKING"
        self.doc_repo.update(db, doc)

        # Locate parsed document JSON artifact from Day 6 (checked by UUID, then document_code)
        parsed_doc_path = self.settings.parsed_dir / str(doc.id) / "document.json"
        if not parsed_doc_path.exists():
            parsed_doc_path = self.settings.parsed_dir / doc.document_code / "document.json"
        if not parsed_doc_path.exists():
            error_reason = f"Parsed document artifact missing at {parsed_doc_path}"
            logger.error(error_reason)
            doc.processing_status = "OCR_FAILED"
            self.doc_repo.update(db, doc)
            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.FAILED.value,
                chunking_source_path="",
                failure_reason=error_reason,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )
            return self.ocr_repo.create(db, ocr_run)

        with open(parsed_doc_path, "r", encoding="utf-8") as f:
            parsed_doc_data = json.load(f)

        # 1. Evaluate OCR requirement page by page
        decision = self.detector.evaluate_document(doc.document_code, parsed_doc_data)

        # Case A: Pure digital document with no OCR required on any page
        if not decision.ocr_required:
            logger.info(
                "Document %s does not require OCR (0/%d pages flagged). Advancing directly to READY_FOR_CHUNKING.",
                doc.document_code,
                decision.pages_total,
            )
            doc.processing_status = "READY_FOR_CHUNKING"
            self.doc_repo.update(db, doc)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.SKIPPED_NOT_NEEDED.value,
                pages_total=decision.pages_total,
                pages_checked=decision.pages_total,
                pages_ocr_required=0,
                pages_ocr_success=0,
                pages_ocr_failed=0,
                low_confidence_numeric_regions=0,
                output_path=None,
                chunking_source_path=str(parsed_doc_path),
                diagnostics={
                    "ocr_required": False,
                    "pages_needing_ocr": [],
                    "page_decisions": [
                        {
                            "page_number": pd.page_number,
                            "needs_ocr": pd.needs_ocr,
                            "reason": pd.reason,
                        }
                        for pd in decision.page_decisions
                    ],
                },
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
            )
            return self.ocr_repo.create(db, ocr_run)

        # Case B: Scanned or mixed document requiring OCR fallback on specific pages
        logger.info(
            "Document %s requires OCR on pages: %s. Initiating page rendering and recognition.",
            doc.document_code,
            decision.pages_needing_ocr,
        )

        # Verify OCR engine availability
        if not self.provider.is_available():
            error_reason = "OCR engine unavailable in current environment."
            logger.error("OCR check failed for %s: %s", doc.document_code, error_reason)
            doc.processing_status = "OCR_FAILED"
            self.doc_repo.update(db, doc)
            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.FAILED.value,
                pages_total=decision.pages_total,
                pages_checked=decision.pages_total,
                pages_ocr_required=len(decision.pages_needing_ocr),
                chunking_source_path=str(parsed_doc_path),
                failure_reason=error_reason,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )
            return self.ocr_repo.create(db, ocr_run)

        doc.processing_status = "OCR_PROCESSING"
        self.doc_repo.update(db, doc)

        # Resolve original PDF file path
        original_pdf_path = self.storage.resolve_storage_path(doc.storage_path)
        if not original_pdf_path or not original_pdf_path.exists():
            error_reason = f"Original PDF missing at {doc.storage_path}"
            logger.error(error_reason)
            doc.processing_status = "OCR_FAILED"
            self.doc_repo.update(db, doc)
            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.FAILED.value,
                pages_total=decision.pages_total,
                pages_checked=decision.pages_total,
                pages_ocr_required=len(decision.pages_needing_ocr),
                chunking_source_path="",
                failure_reason=error_reason,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )
            return self.ocr_repo.create(db, ocr_run)

        # Set up document OCR storage directory: storage/ocr/<document_id>/
        doc_ocr_dir = self.settings.ocr_dir / str(doc.id)
        doc_ocr_pages_dir = doc_ocr_dir / "pages"
        doc_ocr_pages_dir.mkdir(parents=True, exist_ok=True)

        ocr_results: Dict[int, OCRPageResult] = {}
        failed_pages: List[int] = []

        # Render and OCR only the flagged pages
        for page_num in decision.pages_needing_ocr:
            page_img_path = doc_ocr_pages_dir / f"page_{page_num:03d}.png"
            page_success = False
            page_result: Optional[OCRPageResult] = None

            # Retry loop for rendering & recognition
            for attempt in range(1, self.settings.ocr_page_max_retries + 1):
                try:
                    # Render only if not already rendered
                    if not page_img_path.exists():
                        self.renderer.render_page_to_image(
                            pdf_path=original_pdf_path,
                            page_number=page_num,
                            output_image_path=page_img_path,
                        )

                    # Execute OCR on rendered page image
                    page_result = self.provider.ocr_page(
                        image_path=page_img_path,
                        page_number=page_num,
                        **kwargs,
                    )

                    if page_result.success:
                        page_success = True
                        break
                    else:
                        logger.warning(
                            "OCR failed on page %d (attempt %d/%d): %s",
                            page_num,
                            attempt,
                            self.settings.ocr_page_max_retries,
                            page_result.error_message,
                        )
                except Exception as exc:
                    logger.warning(
                        "OCR exception on page %d (attempt %d/%d): %s",
                        page_num,
                        attempt,
                        self.settings.ocr_page_max_retries,
                        exc,
                    )

            if page_success and page_result:
                ocr_results[page_num] = page_result
            else:
                failed_pages.append(page_num)

        # Handle partial or total OCR failure
        if failed_pages:
            error_reason = f"OCR failed for pages {failed_pages} after {self.settings.ocr_page_max_retries} retries."
            logger.error(error_reason)
            doc.processing_status = "OCR_FAILED"
            self.doc_repo.update(db, doc)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.PARTIAL_FAILURE.value,
                pages_total=decision.pages_total,
                pages_checked=decision.pages_total,
                pages_ocr_required=len(decision.pages_needing_ocr),
                pages_ocr_success=len(ocr_results),
                pages_ocr_failed=len(failed_pages),
                chunking_source_path=str(parsed_doc_path),
                failure_reason=error_reason,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
            )
            return self.ocr_repo.create(db, ocr_run)

        # 3. Merge successful OCR page results with good MinerU pages
        try:
            merged_doc = self.merger.merge(
                document_id=doc.document_code,
                parsed_doc_data=parsed_doc_data,
                ocr_results=ocr_results,
                ocr_engine_name=self.provider.engine_name,
                ocr_engine_version=self.provider.version,
            )

            # Persist raw page JSONs and canonical merged document
            self.merger.save_raw_ocr_pages(doc_ocr_dir, ocr_results)
            merged_path, merged_sha = self.merger.save_merged_document(doc_ocr_dir, merged_doc)

            # 4. Advance document to READY_FOR_CHUNKING
            doc.processing_status = "READY_FOR_CHUNKING"
            self.doc_repo.update(db, doc)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            ocr_diag = merged_doc.get("diagnostics", {})
            low_conf_num = ocr_diag.get("low_confidence_numeric_regions", 0)

            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.COMPLETED.value,
                pages_total=decision.pages_total,
                pages_checked=decision.pages_total,
                pages_ocr_required=len(decision.pages_needing_ocr),
                pages_ocr_success=len(ocr_results),
                pages_ocr_failed=0,
                low_confidence_numeric_regions=low_conf_num,
                output_path=str(merged_path),
                chunking_source_path=str(merged_path),
                diagnostics={
                    "ocr_required": True,
                    "pages_needing_ocr": decision.pages_needing_ocr,
                    "low_confidence_numeric_regions": low_conf_num,
                    "merged_sha256": merged_sha,
                },
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
            )
            created_run = self.ocr_repo.create(db, ocr_run)
            logger.info(
                "Successfully processed OCR for %s | %d/%d pages OCR'd -> READY_FOR_CHUNKING",
                doc.document_code,
                len(ocr_results),
                decision.pages_total,
            )
            return created_run

        except Exception as exc:
            error_reason = f"OCR merge failed: {exc}"
            logger.error(error_reason)
            doc.processing_status = "OCR_FAILED"
            self.doc_repo.update(db, doc)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            ocr_run = OCRRun(
                document_id=document_id,
                ocr_engine=self.provider.engine_name,
                ocr_version=self.provider.version,
                status=OCRStatus.FAILED.value,
                pages_total=decision.pages_total,
                pages_checked=decision.pages_total,
                pages_ocr_required=len(decision.pages_needing_ocr),
                pages_ocr_success=len(ocr_results),
                pages_ocr_failed=len(decision.pages_needing_ocr) - len(ocr_results),
                chunking_source_path=str(parsed_doc_path),
                failure_reason=error_reason,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
            )
            return self.ocr_repo.create(db, ocr_run)
