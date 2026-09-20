from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminPipelineResponse,
    DocumentRetryResponse,
    PipelineStageCount,
    StuckItem,
)
from app.database.models.admin_operation_event import AdminOperationEvent
from app.database.models.document import Document
from app.ocr.service import OCRService
from app.parser.service import DocumentParserService

logger = logging.getLogger("yojansetu.admin.pipeline")


class AdminPipelineService:
    """Operations service for pipeline workload monitoring, stuck-item detection, and safe stage retries."""

    STUCK_THRESHOLD_MINUTES = 30

    TRANSIENT_STATUSES = {
        "VALIDATING": ("INGESTION", "RETRY_INGESTION"),
        "DUPLICATE_CHECKING": ("DUPLICATE_CHECK", "RETRY_DUPLICATE_CHECK"),
        "PARSING": ("PARSER", "RETRY_PARSING"),
        "OCR_CHECKING": ("OCR", "RETRY_OCR"),
        "OCR_RUNNING": ("OCR", "RETRY_OCR"),
        "CHUNKING": ("CHUNKING", "RETRY_CHUNKING"),
        "EXTRACTING": ("EXTRACTION", "RETRY_EXTRACTION"),
        "NORMALIZING": ("NORMALIZATION", "RETRY_NORMALIZATION"),
        "VERIFYING": ("VERIFICATION", "RETRY_VERIFICATION"),
    }

    FAILED_STATUS_ACTION_MAP = {
        "PARSING_FAILED": "RETRY_PARSING",
        "OCR_FAILED": "RETRY_OCR",
        "CHUNKING_FAILED": "RETRY_CHUNKING",
        "EXTRACTION_FAILED": "RETRY_EXTRACTION",
        "NORMALIZATION_FAILED": "RETRY_NORMALIZATION",
        "VALIDATION_FAILED": "RETRY_VALIDATION",
        "FAILED": "RETRY_PIPELINE",
    }

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

    FAILED_STAGE_STATUS_MAP = {
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

    def get_pipeline_summary(
        self, db: Session, stuck_threshold_minutes: Optional[int] = None
    ) -> AdminPipelineResponse:
        now = datetime.now(timezone.utc)
        threshold_mins = stuck_threshold_minutes or self.STUCK_THRESHOLD_MINUTES
        cutoff_dt = now - timedelta(minutes=threshold_mins)

        # 1. Pipeline Stages Breakdown
        pipeline_stages: List[PipelineStageCount] = []
        # Single query to group document processing statuses and minimum updated_at
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

        total_waiting = 0
        total_processing = 0
        total_failed = 0

        for stage_name, active_statuses in self.STAGE_STATUS_MAP.items():
            failed_statuses = self.FAILED_STAGE_STATUS_MAP.get(stage_name, [])

            waiting_status = active_statuses[0] if active_statuses else None
            processing_statuses = active_statuses[1:] if len(active_statuses) > 1 else []

            w_count = status_map.get(waiting_status, 0) if waiting_status else 0
            p_count = sum(status_map.get(s, 0) for s in processing_statuses)
            f_count = sum(status_map.get(s, 0) for s in failed_statuses)

            total_waiting += w_count
            total_processing += p_count
            total_failed += f_count

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

        # 2. Detect Stuck Items
        stuck_items: List[StuckItem] = []
        transient_keys = list(self.TRANSIENT_STATUSES.keys())
        
        stuck_docs = db.execute(
            select(Document)
            .where(
                and_(
                    Document.processing_status.in_(transient_keys),
                    Document.updated_at <= cutoff_dt,
                )
            )
            .order_by(Document.updated_at.asc())
            .limit(20)
        ).scalars().all()

        for doc in stuck_docs:
            elapsed_m = int((now - (doc.updated_at or now)).total_seconds() // 60)
            stage, retry_action = self.TRANSIENT_STATUSES.get(doc.processing_status, ("UNKNOWN", None))
            stuck_items.append(
                StuckItem(
                    document_id=str(doc.id),
                    document_code=doc.document_code,
                    stage=stage,
                    status=doc.processing_status,
                    elapsed_minutes=elapsed_m,
                    title=doc.title or doc.original_filename,
                    retry_valid=True,
                    valid_retry_action=retry_action,
                )
            )

        return AdminPipelineResponse(
            stages=pipeline_stages,
            stuck_items=stuck_items,
            total_waiting=total_waiting,
            total_processing=total_processing,
            total_failed=total_failed,
            generated_at=now.isoformat(),
        )

    def retry_document(
        self,
        db: Session,
        document_id: uuid.UUID,
        actor_id: str = "DEV_REVIEWER",
    ) -> DocumentRetryResponse:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found",
            )

        curr_status = doc.processing_status

        # Validate retry eligibility
        if curr_status in ["EXACT_DUPLICATE", "HUMAN_VERIFIED", "HUMAN_REJECTED", "INVALID"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document in terminal status '{curr_status}' cannot be retried.",
            )

        action_taken = self.FAILED_STATUS_ACTION_MAP.get(curr_status)
        if not action_taken and curr_status in self.TRANSIENT_STATUSES:
            _, action_taken = self.TRANSIENT_STATUSES[curr_status]

        if not action_taken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No safe retry procedure configured for status '{curr_status}'.",
            )

        # Execute safe retry
        new_status = curr_status
        message = ""

        try:
            if action_taken == "RETRY_PARSING":
                doc.processing_status = "READY_FOR_PARSING"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                try:
                    parser_service = DocumentParserService()
                    parser_service.parse_document(db, doc.id, force=True)
                    db.refresh(doc)
                    new_status = doc.processing_status
                    message = "Parsing re-executed successfully."
                except Exception as parse_err:
                    logger.warning(f"Retry parsing failed for {doc.id}: {parse_err}")
                    new_status = doc.processing_status
                    message = f"Retry parsing triggered; current status: {new_status}"

            elif action_taken == "RETRY_OCR":
                doc.processing_status = "READY_FOR_OCR_CHECK"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                try:
                    ocr_service = OCRService()
                    ocr_service.process_document(db, doc.id, force=True)
                    db.refresh(doc)
                    new_status = doc.processing_status
                    message = "OCR re-executed successfully."
                except Exception as ocr_err:
                    logger.warning(f"Retry OCR failed for {doc.id}: {ocr_err}")
                    new_status = doc.processing_status
                    message = f"Retry OCR triggered; current status: {new_status}"

            elif action_taken == "RETRY_CHUNKING":
                doc.processing_status = "READY_FOR_CHUNKING"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                new_status = "READY_FOR_CHUNKING"
                message = "Document reset to READY_FOR_CHUNKING."

            elif action_taken == "RETRY_EXTRACTION":
                doc.processing_status = "READY_FOR_EXTRACTION"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                new_status = "READY_FOR_EXTRACTION"
                message = "Document reset to READY_FOR_EXTRACTION."

            elif action_taken == "RETRY_NORMALIZATION":
                doc.processing_status = "READY_FOR_NORMALIZATION"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                new_status = "READY_FOR_NORMALIZATION"
                message = "Document reset to READY_FOR_NORMALIZATION."

            elif action_taken == "RETRY_VALIDATION":
                doc.processing_status = "READY_FOR_VALIDATION"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                new_status = "READY_FOR_VALIDATION"
                message = "Document reset to READY_FOR_VALIDATION."

            else:
                doc.processing_status = "READY_FOR_PARSING"
                doc.failure_reason = None
                db.commit()
                db.refresh(doc)
                new_status = "READY_FOR_PARSING"
                message = "Document reset to READY_FOR_PARSING."

            # Record privileged admin operation audit
            audit_event = AdminOperationEvent(
                actor_id=actor_id,
                action_type="DOCUMENT_RETRY_TRIGGERED",
                target_type="DOCUMENT",
                target_id=str(doc.id),
                metadata_safe={
                    "document_code": doc.document_code,
                    "previous_status": curr_status,
                    "new_status": new_status,
                    "action_taken": action_taken,
                },
            )
            db.add(audit_event)
            db.commit()

            return DocumentRetryResponse(
                document_id=str(doc.id),
                action_taken=action_taken,
                new_status=new_status,
                message=message or f"Document successfully retried via {action_taken}.",
            )

        except Exception as err:
            logger.error(f"Error retrying document {document_id}: {err}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retry document: {str(err)}",
            )
