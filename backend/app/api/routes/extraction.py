import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.extraction.service import SchemeExtractionService
from app.llm.ollama import OllamaProvider
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_repository import ExtractionRunRepository
from app.schemas.extraction import (
    ChunkExtractionDetailResponse,
    DocumentExtractionsListResponse,
    ExtractionRunResponse,
    LLMHealthResponse,
)

logger = logging.getLogger("yojansetu.api.extraction")

router = APIRouter()


@router.get(
    "/system/llm-health",
    response_model=LLMHealthResponse,
    summary="Check local LLM service connectivity and model availability",
)
def get_llm_health():
    """Verify that the local LLM server (Ollama) is running and model is loaded."""
    provider = OllamaProvider()
    health = provider.check_health()
    return LLMHealthResponse(
        status=health.get("status", "error"),
        provider=health.get("provider", "ollama"),
        model=health.get("model", settings.ollama_model),
        model_available=health.get("model_available", False),
        installed_models=health.get("installed_models"),
    )


@router.post(
    "/chunks/{chunk_id}/extract",
    response_model=ExtractionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger local LLM extraction for a single document chunk",
)
def extract_chunk(
    chunk_id: str,
    force: bool = Query(default=False, description="Force re-extraction even if already completed"),
    db: Session = Depends(get_db),
):
    """
    Execute evidence-backed LLM extraction on a single document chunk.
    Extracts raw scheme conditions, benefits, and required documents.
    """
    service = SchemeExtractionService()
    try:
        res = service.extract_chunk(db, chunk_id, force=force)
        run_repo = ExtractionRunRepository()
        run = run_repo.get_by_chunk_id_str(db, res["chunk_id"])
        if not run:
            raise HTTPException(status_code=500, detail="Extraction completed but run record not found")
        return ExtractionRunResponse.model_validate(run)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Extraction failed for chunk %s: %s", chunk_id, e)
        raise HTTPException(status_code=500, detail=f"Extraction execution error: {e}")


@router.post(
    "/chunks/{chunk_id}/reextract",
    response_model=ExtractionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Force re-extraction for a single document chunk",
)
def reextract_chunk(
    chunk_id: str,
    db: Session = Depends(get_db),
):
    """Explicitly force re-extraction for a chunk, purging previous result."""
    return extract_chunk(chunk_id=chunk_id, force=True, db=db)


@router.get(
    "/chunks/{chunk_id}/extraction",
    response_model=ChunkExtractionDetailResponse,
    summary="Get detailed extraction results for a single chunk",
)
def get_chunk_extraction(
    chunk_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve latest extraction run record, full structured JSON payload,
    and raw model response text for a chunk.
    """
    run_repo = ExtractionRunRepository()
    run = None

    # Try UUID lookup first
    try:
        c_uuid = uuid.UUID(chunk_id)
        run = run_repo.get_by_chunk_id(db, c_uuid)
    except ValueError:
        pass

    if not run:
        run = run_repo.get_by_chunk_id_str(db, chunk_id)

    if not run:
        raise HTTPException(status_code=404, detail=f"No extraction run found for chunk '{chunk_id}'")

    # Read extraction.json artifact if present
    base_dir = Path(settings.base_dir).resolve()
    json_path = (base_dir / run.artifact_path).resolve()
    extraction_payload = None
    if json_path.exists() and json_path.is_file():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                extraction_payload = json.load(f)
        except Exception as e:
            logger.warning("Failed reading extraction JSON %s: %s", json_path, e)

    # Read raw_response.txt if present
    raw_response_path = json_path.parent / "raw_response.txt"
    raw_text = None
    if raw_response_path.exists() and raw_response_path.is_file():
        try:
            raw_text = raw_response_path.read_text(encoding="utf-8")
        except Exception:
            pass

    return ChunkExtractionDetailResponse(
        id=run.id,
        document_id=run.document_id,
        chunk_id=run.chunk_id,
        chunk_id_str=run.chunk_id_str,
        model_provider=run.model_provider,
        model_name=run.model_name,
        prompt_version=run.prompt_version,
        schema_version=run.schema_version,
        status=run.status,
        artifact_path=run.artifact_path,
        input_token_estimate=run.input_token_estimate,
        output_tokens=run.output_tokens,
        duration_ms=run.duration_ms,
        failure_reason=run.failure_reason,
        diagnostics=run.diagnostics,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        extraction_payload=extraction_payload,
        raw_response_text=raw_text,
    )


@router.get(
    "/documents/{document_id}/extractions",
    response_model=DocumentExtractionsListResponse,
    summary="Get all chunk extraction runs and master aggregation for a document",
)
def get_document_extractions(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve all chunk extraction runs for a document along with the compiled
    master document_extractions.json summary.
    """
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    run_repo = ExtractionRunRepository()
    runs = run_repo.get_all_by_document_id(db, document_id)

    master_path = Path(settings.extracted_dir) / str(document_id) / "document_extractions.json"
    master_summary = None
    if master_path.exists():
        try:
            with open(master_path, "r", encoding="utf-8") as f:
                master_summary = json.load(f)
        except Exception:
            pass

    return DocumentExtractionsListResponse(
        document_id=document_id,
        status=doc.processing_status,
        total_runs=len(runs),
        runs=[ExtractionRunResponse.model_validate(r) for r in runs],
        master_summary=master_summary,
    )
