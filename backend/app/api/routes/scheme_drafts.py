import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.normalization.service import SchemeNormalizationService
from app.repositories.document_repository import DocumentRepository
from app.repositories.scheme_draft_repository import SchemeDraftRepository

logger = logging.getLogger("yojansetu.api.scheme_drafts")

router = APIRouter()


@router.post(
    "/documents/{document_id}/normalize",
    status_code=status.HTTP_200_OK,
    summary="Trigger canonical scheme normalization for a document",
)
def normalize_document(
    document_id: uuid.UUID,
    force: bool = Query(default=False, description="Force normalization even if not in READY_FOR_NORMALIZATION"),
    db: Session = Depends(get_db),
):
    """
    Execute deterministic normalization of raw extractions into canonical scheme drafts.
    Produces machine-readable eligibility rules, detects conflicts, and registers audit evidence.
    """
    service = SchemeNormalizationService(db)
    try:
        result = service.normalize_document(document_id, force=force)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Normalization failed for document %s: %s", document_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/documents/{document_id}/scheme-drafts",
    status_code=status.HTTP_200_OK,
    summary="List all canonical scheme drafts produced for a document",
)
def list_document_scheme_drafts(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve all canonical scheme draft records associated with a document."""
    doc_repo = DocumentRepository()
    doc = doc_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {document_id} not found")

    draft_repo = SchemeDraftRepository()
    drafts = draft_repo.get_all_by_document_id(db, document_id)

    return {
        "document_id": str(document_id),
        "document_code": doc.document_code,
        "processing_status": doc.processing_status,
        "count": len(drafts),
        "drafts": [
            {
                "id": str(d.id),
                "internal_scheme_code": d.internal_scheme_code,
                "detected_name": d.detected_name,
                "normalized_name": d.normalized_name_for_matching,
                "department_id": str(d.department_id) if d.department_id else None,
                "department_name_raw": d.department_name_raw,
                "status": d.status,
                "schema_version": d.schema_version,
                "normalizer_version": d.normalizer_version,
                "conflict_count": d.conflict_count,
                "unresolved_field_count": d.unresolved_field_count,
                "artifact_path": d.artifact_path,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in drafts
        ],
    }


@router.get(
    "/scheme-drafts/{draft_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete canonical scheme draft detail and JSON representation",
)
def get_scheme_draft(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve canonical scheme draft metadata and full typed JSON artifact."""
    draft_repo = SchemeDraftRepository()
    draft = draft_repo.get_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scheme draft {draft_id} not found")

    settings = get_settings()
    artifact_full_path = settings.storage_path / draft.artifact_path.replace("storage/", "")
    canonical_data = None

    if artifact_full_path.exists():
        try:
            with open(artifact_full_path, "r", encoding="utf-8") as f:
                canonical_data = json.load(f)
        except Exception as e:
            logger.warning("Could not read canonical JSON from %s: %s", artifact_full_path, e)

    return {
        "id": str(draft.id),
        "internal_scheme_code": draft.internal_scheme_code,
        "document_id": str(draft.document_id),
        "detected_name": draft.detected_name,
        "official_name_raw": draft.official_name_raw,
        "normalized_name": draft.normalized_name_for_matching,
        "department_id": str(draft.department_id) if draft.department_id else None,
        "department_name_raw": draft.department_name_raw,
        "status": draft.status,
        "conflict_count": draft.conflict_count,
        "unresolved_field_count": draft.unresolved_field_count,
        "artifact_path": draft.artifact_path,
        "canonical": canonical_data,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }


@router.get(
    "/scheme-drafts/{draft_id}/conflicts",
    status_code=status.HTTP_200_OK,
    summary="Retrieve conflict records and contradictions flagged during normalization",
)
def get_scheme_draft_conflicts(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve detailed contradiction records flagged for this scheme draft."""
    draft_repo = SchemeDraftRepository()
    draft = draft_repo.get_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scheme draft {draft_id} not found")

    settings = get_settings()
    conflicts_path = settings.normalized_dir / str(draft.document_id) / str(draft.id) / "conflicts.json"
    conflicts_data = []

    if conflicts_path.exists():
        try:
            with open(conflicts_path, "r", encoding="utf-8") as f:
                conflicts_data = json.load(f)
        except Exception as e:
            logger.warning("Could not read conflicts JSON: %s", e)

    return {
        "draft_id": str(draft.id),
        "internal_scheme_code": draft.internal_scheme_code,
        "conflict_count": len(conflicts_data),
        "conflicts": conflicts_data,
    }
