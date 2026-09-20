import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.chunking.service import DocumentChunkingService
from app.chunking.validator import ChunkValidationError
from app.core.config import settings
from app.database.session import get_db
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.chunk import (
    ChunkDetailResponse,
    ChunkListResponse,
    ChunkMetadataResponse,
    ChunkTriggerResponse,
)

logger = logging.getLogger("yojansetu.api.chunks")

router = APIRouter()


@router.post(
    "/documents/{document_id}/chunk",
    response_model=ChunkTriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger semantic chunking for a document",
)
def chunk_document(
    document_id: uuid.UUID,
    force: bool = Query(default=False, description="Force re-chunking even if already completed"),
    db: Session = Depends(get_db),
):
    """
    Perform deterministic structure-aware semantic chunking on a document in READY_FOR_CHUNKING.
    Groups blocks into logical section chunks (Eligibility, Benefits, etc.),
    enforces token constraints, bonds provisos, validates coverage, and transitions
    to READY_FOR_EXTRACTION.
    """
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    service = DocumentChunkingService()
    try:
        result = service.chunk_document(db, document_id, force=force)
        return ChunkTriggerResponse(
            document_id=document_id,
            status=result["status"],
            message="Semantic chunking completed successfully.",
            chunk_count=result["chunk_count"],
            quality_summary=result["quality_summary"],
        )
    except ChunkValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Chunking execution error for document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=f"Chunking execution error: {e}")


@router.get(
    "/documents/{document_id}/chunks",
    response_model=ChunkListResponse,
    summary="List all semantic chunks for a document",
)
def list_document_chunks(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Fetch all chunk metadata records for a document ordered by chunk_index."""
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

    chunk_repo = DocumentChunkRepository()
    chunks = chunk_repo.get_by_document_id(db, document_id)

    quality_summary = None
    master_json_path = Path(settings.chunks_dir) / str(document_id) / "chunks.json"
    if master_json_path.exists():
        try:
            with open(master_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                quality_summary = data.get("quality_summary")
        except Exception:
            pass

    return ChunkListResponse(
        document_id=document_id,
        total_chunks=len(chunks),
        quality_summary=quality_summary,
        chunks=[ChunkMetadataResponse.model_validate(c) for c in chunks],
    )


@router.get(
    "/chunks/{chunk_id}",
    response_model=ChunkDetailResponse,
    summary="Get single chunk details including full text and source block IDs",
)
def get_chunk_detail(
    chunk_id: str,
    db: Session = Depends(get_db),
):
    """
    Fetch a single semantic chunk by its UUID or stable chunk identifier (e.g. DOC-XXXX-CHUNK-0001).
    Returns chunk metadata along with the rendered prompt text from disk storage.
    """
    chunk_repo = DocumentChunkRepository()
    chunk = None

    # Try UUID lookup first
    try:
        chunk_uuid = uuid.UUID(chunk_id)
        chunk = chunk_repo.get_by_id(db, chunk_uuid)
    except ValueError:
        pass

    # Fallback to string chunk_id_str
    if not chunk:
        chunk = chunk_repo.get_by_chunk_id_str(db, chunk_id)

    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found.")

    # Safely read text artifact from filesystem
    text_content = None
    source_bids = None

    if chunk.artifact_path:
        base_dir = Path(settings.base_dir).resolve()
        candidate_path = (base_dir / chunk.artifact_path).resolve()
        chunks_storage_dir = Path(settings.chunks_dir).resolve()

        # Prevent directory traversal
        try:
            candidate_path.relative_to(chunks_storage_dir)
            if candidate_path.exists() and candidate_path.is_file():
                text_content = candidate_path.read_text(encoding="utf-8")
        except ValueError:
            logger.warning("Attempted unauthorized file access to path: %s", chunk.artifact_path)

    # Read source_block_ids from master chunks.json if present
    master_json_path = Path(settings.chunks_dir) / str(chunk.document_id) / "chunks.json"
    if master_json_path.exists():
        try:
            with open(master_json_path, "r", encoding="utf-8") as f:
                master_data = json.load(f)
                for item in master_data.get("chunks", []):
                    if item.get("chunk_id") == chunk.chunk_id_str or item.get("chunk_index") == chunk.chunk_index:
                        source_bids = item.get("source_block_ids")
                        if not text_content:
                            text_content = item.get("text")
                        break
        except Exception as e:
            logger.warning("Could not read master chunks.json for chunk %s: %s", chunk.chunk_id_str, e)

    detail_dict = {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_id_str": chunk.chunk_id_str,
        "chunk_index": chunk.chunk_index,
        "section_type": chunk.section_type,
        "section_path": chunk.section_path,
        "chunk_title": chunk.chunk_title,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "token_count": chunk.token_count,
        "contains_table": chunk.contains_table,
        "contains_ocr": chunk.contains_ocr,
        "source_block_count": chunk.source_block_count,
        "created_at": chunk.created_at,
        "text": text_content,
        "source_block_ids": source_bids,
    }

    return ChunkDetailResponse(**detail_dict)
