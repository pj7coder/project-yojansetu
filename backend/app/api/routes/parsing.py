import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.parser.service import DocumentParserService
from app.repositories.document_repository import DocumentRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.parsed_document import (
    ParsedDocumentResponse,
    ParsedPageResponse,
    ParseTriggerResponse,
)

logger = logging.getLogger("yojansetu.api.parsing")

router = APIRouter()


@router.post(
    "/{document_id}/parse",
    response_model=ParseTriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger document parsing with MinerU / layout engine",
)
def parse_document(
    document_id: uuid.UUID,
    force: bool = Query(default=False, description="Force reparse even if already parsed"),
    db: Session = Depends(get_db),
):
    """
    Trigger structured layout parsing for a document in READY_FOR_PARSING state.
    Produces page-aware blocks, headings, paragraphs, lists, tables, and diagnostics.
    """
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    service = DocumentParserService()
    try:
        parsed_record = service.parse_document(db, document_id, force=force)
        return ParseTriggerResponse(
            document_id=document_id,
            status=doc.processing_status,
            message="Document parsed successfully into structured page blocks.",
            parsed_record=ParsedDocumentResponse.model_validate(parsed_record),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Parsing failure on API invocation for %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=f"Parsing error: {e}")


@router.get(
    "/{document_id}/parsed",
    response_model=ParsedDocumentResponse,
    summary="Get document parsing metadata and diagnostics",
)
def get_parsed_metadata(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve latest parsing record, page metrics, and OCR diagnostic signals for a document.
    """
    parsed_repo = ParsedDocumentRepository()
    parsed_record = parsed_repo.get_latest_by_document_id(db, document_id)
    if not parsed_record:
        raise HTTPException(
            status_code=404,
            detail=f"No parsed metadata found for document {document_id}. Document may not be parsed yet.",
        )
    return parsed_record


@router.get(
    "/{document_id}/pages/{page_number}",
    response_model=ParsedPageResponse,
    summary="Get normalized blocks for a specific physical page",
)
def get_page_blocks(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve structured text blocks, headings, and tables for a single physical page (1-based index).
    Useful for evidence inspection and admin review.
    """
    service = DocumentParserService()
    page_data = service.get_page_blocks(document_id, page_number)
    if not page_data:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_number} not found for document {document_id}.",
        )

    return ParsedPageResponse(
        document_id=document_id,
        page_number=page_data.get("page_number", page_number),
        status=page_data.get("status", "TEXT_OK"),
        text_character_count=page_data.get("text_character_count", 0),
        block_count=page_data.get("block_count", 0),
        blocks=page_data.get("blocks", []),
    )


@router.get(
    "/{document_id}/parsed-artifact",
    summary="Download or stream the full normalized parsed JSON artifact",
)
def download_parsed_artifact(
    document_id: uuid.UUID,
    format: str = Query(default="json", description="Artifact format: 'json' or 'md'"),
    db: Session = Depends(get_db),
):
    """
    Safely download the normalized document.json or document.md artifact for a parsed document.
    """
    settings = get_settings()
    target_filename = "document.md" if format.lower() == "md" else "document.json"
    artifact_path = (settings.parsed_dir / str(document_id) / target_filename).resolve()

    # Path traversal protection: ensure resolved path is inside parsed_dir
    if not str(artifact_path).startswith(str(settings.parsed_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied: Invalid artifact path.")

    if not artifact_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Parsed artifact ({target_filename}) not found for document {document_id}.",
        )

    media_type = "text/markdown" if format.lower() == "md" else "application/json"
    return FileResponse(
        path=artifact_path,
        media_type=media_type,
        filename=f"{document_id}_{target_filename}",
    )
