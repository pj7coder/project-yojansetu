import json
import logging
from pathlib import Path
from typing import Any, Dict
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.ocr.service import OCRService
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_repository import OCRRunRepository
from app.schemas.ocr import (
    OCRCheckTriggerResponse,
    OCRPageDetailResponse,
    OCRRunResponse,
)

logger = logging.getLogger("jansetu.api.ocr")

router = APIRouter()


@router.post(
    "/{document_id}/ocr-check",
    response_model=OCRCheckTriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger page-level OCR requirement detection and selective fallback",
)
def check_and_run_ocr(
    document_id: uuid.UUID,
    force: bool = Query(default=False, description="Force re-OCR even if already completed"),
    db: Session = Depends(get_db),
):
    """
    Evaluate page diagnostics for a document in READY_FOR_OCR_CHECK.
    Selectively executes local PaddleOCR only on scanned/bad pages, merges
    outputs with clean MinerU pages, and advances to READY_FOR_CHUNKING.
    """
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    service = OCRService()
    try:
        ocr_run = service.process_document(db, document_id, force=force)
        return OCRCheckTriggerResponse(
            document_id=document_id,
            status=doc.processing_status,
            message="OCR detection and processing completed successfully.",
            ocr_run=OCRRunResponse.model_validate(ocr_run),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("OCR execution error on API call for %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=f"OCR execution error: {e}")


@router.get(
    "/{document_id}/ocr",
    response_model=OCRRunResponse,
    summary="Get latest OCR run metadata and quality summary",
)
def get_ocr_metadata(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve latest OCR run metadata, including page count, pages requiring OCR,
    success/failure counts, low confidence numeric regions, and chunking source path.
    """
    ocr_repo = OCRRunRepository()
    ocr_run = ocr_repo.get_latest_by_document_id(db, document_id)
    if not ocr_run:
        raise HTTPException(
            status_code=404,
            detail=f"No OCR run record found for document {document_id}.",
        )
    return ocr_run


@router.get(
    "/{document_id}/ocr/pages/{page_number}",
    response_model=OCRPageDetailResponse,
    summary="Get normalized OCR result for a specific physical page",
)
def get_ocr_page_result(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve normalized OCR regions, text, and bounding boxes for a specific page.
    """
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    settings = get_settings()
    doc_ocr_dir = settings.ocr_dir / str(doc.id)
    if not doc_ocr_dir.exists():
        doc_ocr_dir = settings.ocr_dir / doc.document_code

    # First check raw OCR page file
    raw_path = doc_ocr_dir / "raw" / f"page_{page_number:03d}.json"
    if raw_path.exists():
        with open(raw_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        regions = data.get("regions", [])
        low_conf_num = sum(1 for r in regions if r.get("low_confidence_numeric"))
        return OCRPageDetailResponse(
            document_id=document_id,
            page_number=page_number,
            engine=data.get("engine", "paddleocr"),
            success=data.get("success", True),
            regions_count=len(regions),
            regions=regions,
            raw_text="\n".join(r.get("text", "") for r in regions),
            low_confidence_numeric_regions=low_conf_num,
        )

    # If raw page not found, check merged_document.json
    merged_path = doc_ocr_dir / "merged_document.json"
    if merged_path.exists():
        with open(merged_path, "r", encoding="utf-8") as f:
            merged_data = json.load(f)

        for p in merged_data.get("pages", []):
            if p.get("page_number") == page_number:
                blocks = p.get("blocks", [])
                return OCRPageDetailResponse(
                    document_id=document_id,
                    page_number=page_number,
                    engine=merged_data.get("processing", {}).get("ocr", "paddleocr"),
                    success=True,
                    regions_count=len(blocks),
                    regions=blocks,
                    raw_text="\n".join(b.get("text", "") for b in blocks),
                    low_confidence_numeric_regions=0,
                )

    raise HTTPException(
        status_code=404,
        detail=f"No OCR output found for page {page_number} of document {document_id}.",
    )


@router.get(
    "/{document_id}/ocr/merged",
    summary="Download or inspect merged document JSON artifact",
)
def download_merged_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Safely download the canonical merged_document.json artifact.
    """
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    settings = get_settings()
    doc_ocr_dir = settings.ocr_dir / str(doc.id)
    if not doc_ocr_dir.exists():
        doc_ocr_dir = settings.ocr_dir / doc.document_code

    merged_path = (doc_ocr_dir / "merged_document.json").resolve()

    # Path traversal protection
    if not str(merged_path).startswith(str(settings.ocr_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied: Invalid artifact path.")

    if not merged_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Merged OCR document not found for document {document_id}.",
        )

    return FileResponse(
        path=merged_path,
        media_type="application/json",
        filename=f"{doc.document_code}_merged_document.json",
    )
