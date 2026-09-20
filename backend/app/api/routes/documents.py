import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.pipeline.auto_runner import run_full_pipeline
from app.ingestion.service import DocumentIngestionError, DocumentIngestionService
from app.ingestion.storage import StorageManager
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentListResponse, DocumentResponse

logger = logging.getLogger("jansetu.api.documents")
router = APIRouter()

ingestion_service = DocumentIngestionService()
document_repository = DocumentRepository()
storage_manager = StorageManager()
settings = get_settings()


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Government Document or Spreadsheet",
    description="Upload a government document or spreadsheet (PDF, XLSX, XLS, CSV). Preserves original file and validates integrity.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Government document or spreadsheet file (PDF, XLSX, XLS, CSV)"),
    source_id: Optional[uuid.UUID] = Form(default=None, description="Optional associated official source UUID"),
    title: Optional[str] = Form(default=None, description="Optional descriptive document title"),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Upload and ingest a government document or spreadsheet."""
    original_filename = file.filename or "uploaded_document"

    # Save uploaded chunks safely into a temporary landing file in incoming_dir
    settings.ensure_storage_dirs()
    temp_suffix = Path(original_filename).suffix or ".pdf"
    temp_fd, temp_path_str = tempfile.mkstemp(
        dir=settings.incoming_dir,
        prefix="upload_",
        suffix=temp_suffix,
    )
    os.close(temp_fd)
    temp_path = Path(temp_path_str)

    try:
        # Stream file to disk in chunks to avoid memory spikes
        with open(temp_path, "wb") as buffer:
            while content := await file.read(65536):
                buffer.write(content)

        # Ingest through the single unified ingestion pipeline
        document = ingestion_service.ingest_document(
            db=db,
            file_path=temp_path,
            original_filename=original_filename,
            ingestion_method="MANUAL_UPLOAD",
            source_id=source_id,
            title=title,
            move_file=True,
        )

        # Automatically run the full processing pipeline in the background:
        # duplicate check → parse → OCR → chunk → extract → normalize → validate
        background_tasks.add_task(run_full_pipeline, document.id)
        logger.info("Scheduled full auto-pipeline for document %s (%s)", document.document_code, document.id)

        return DocumentResponse.model_validate(document)

    except DocumentIngestionError as e:
        logger.warning("Upload ingestion failed for '%s': %s", original_filename, e.message)
        # Check if error is due to file size
        if any("exceeds maximum allowed limit" in err for err in e.errors):
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=e.message,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during document upload for '%s': %s", original_filename, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while storing the uploaded document.",
        )
    finally:
        # Cleanup temporary file if it was not moved or remained on disk
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List Documents",
    description="Retrieve a paginated list of ingested documents with optional status and source filtering.",
)
def list_documents(
    page: int = Query(default=1, ge=1, description="Page number starting from 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    processing_status: Optional[str] = Query(default=None, description="Filter by status, e.g. READY_FOR_DUPLICATE_CHECK, INVALID"),
    ingestion_method: Optional[str] = Query(default=None, description="Filter by method, e.g. MANUAL_UPLOAD, FOLDER_WATCHER"),
    source_id: Optional[uuid.UUID] = Query(default=None, description="Filter by source UUID"),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """List documents with pagination and status/source filters."""
    items, total = document_repository.list(
        db=db,
        page=page,
        page_size=page_size,
        processing_status=processing_status,
        ingestion_method=ingestion_method,
        source_id=source_id,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/watch-folder/status",
    summary="Get Watch Folder Status",
    description="Retrieve operational status, directory path, and pending files in the watch folder.",
)
def get_watch_folder_status() -> dict:
    """Retrieve hot folder status and pending files."""
    from app.ingestion.folder_watcher import get_folder_watcher
    return get_folder_watcher().get_status()


@router.post(
    "/watch-folder/scan",
    summary="Scan Watch Folder Now",
    description="Trigger an immediate scan of the watch folder and process any newly detected PDFs.",
)
def scan_watch_folder_now(background_tasks: BackgroundTasks) -> dict:
    """Trigger on-demand watch folder scan."""
    from app.ingestion.folder_watcher import get_folder_watcher
    watcher = get_folder_watcher()
    ingested_ids = watcher.scan_and_process()
    return {
        "status": "success",
        "scanned_at": time.time(),
        "ingested_count": len(ingested_ids),
        "ingested_document_ids": [str(d) for d in ingested_ids],
    }


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Detail",
    description="Retrieve metadata for a specific document by its UUID.",
)
def get_document_detail(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Retrieve document metadata by UUID."""
    document = document_repository.get_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )
    return DocumentResponse.model_validate(document)


@router.get(
    "/{document_id}/file",
    summary="Download or View Document File",
    description="Safely stream the stored original PDF for admin verification.",
)
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Safely stream the stored original PDF file."""
    document = document_repository.get_by_id(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    resolved_path = storage_manager.resolve_storage_path(document.storage_path)
    if not resolved_path:
        logger.error(
            "Document file missing on disk for ID %s | path='%s'",
            document_id,
            document.storage_path,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested document file could not be located on the server.",
        )

    # Safe headers preventing MIME sniffing
    return FileResponse(
        path=str(resolved_path),
        media_type=document.mime_type or "application/octet-stream",
        filename=document.original_filename,
        content_disposition_type="inline",
    )
