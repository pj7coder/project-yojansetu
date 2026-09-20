import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.duplicate_detection.diff import analyze_document_diff
from app.duplicate_detection.fingerprint import extract_text_fingerprint
from app.duplicate_detection.service import DuplicateDetectionService
from app.duplicate_detection.similarity import (
    calculate_jaccard_similarity,
    calculate_title_similarity,
)
from app.ingestion.storage import StorageManager
from app.repositories.document_relationship_repository import DocumentRelationshipRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentResponse
from app.schemas.duplicate import (
    DocumentComparisonResponse,
    DuplicateAnalysisResponse,
    DuplicateRelationshipResponse,
    DuplicateResolutionRequest,
)

logger = logging.getLogger("yojansetu.api.document_duplicates")
router = APIRouter()

duplicate_service = DuplicateDetectionService()
document_repo = DocumentRepository()
relationship_repo = DocumentRelationshipRepository()
storage_manager = StorageManager()


@router.get(
    "/{document_id}/duplicate-analysis",
    response_model=DuplicateAnalysisResponse,
    summary="Get Document Duplicate Analysis",
    description="Retrieve duplicate and version classification results, matched canonical references, and reasons.",
)
def get_duplicate_analysis(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DuplicateAnalysisResponse:
    """Retrieve duplicate detection findings, evaluating on-demand if not yet processed."""
    doc = document_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    # If pending check, run detection now
    if doc.processing_status == "READY_FOR_DUPLICATE_CHECK" or doc.duplicate_status is None:
        result = duplicate_service.detect_duplicates(db, doc.id)
    else:
        result = duplicate_service.detect_duplicates(db, doc.id, force_recheck=False)

    relationships = relationship_repo.get_by_document_id(db, doc.id)

    return DuplicateAnalysisResponse(
        document_id=doc.id,
        document_code=doc.document_code,
        original_filename=doc.original_filename,
        classification=doc.duplicate_status or "NEW_DOCUMENT",
        matched_document_id=doc.duplicate_of_document_id or doc.possible_version_of_document_id,
        canonical_document_id=doc.canonical_document_id,
        similarity_score=doc.similarity_score,
        reasons=[doc.duplicate_check_reason] if doc.duplicate_check_reason else [],
        diff_summary=result.diff_summary,
        processing_status=doc.processing_status,
        relationships=[DuplicateRelationshipResponse.model_validate(r) for r in relationships],
    )


@router.post(
    "/{document_id}/duplicate-resolution",
    response_model=DocumentResponse,
    summary="Resolve Document Duplicate Status",
    description="Administratively resolve an ambiguous duplicate or version document, setting legal classification.",
)
def resolve_duplicate_status(
    document_id: uuid.UUID,
    payload: DuplicateResolutionRequest,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Administratively confirm or override duplicate/version status."""
    doc = document_repo.get_by_id(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found",
        )

    decision = payload.decision.strip().upper()
    notes = payload.notes or "Administrative manual resolution"

    if decision == "MARK_NEW_DOCUMENT":
        doc.duplicate_status = "NEW_DOCUMENT"
        doc.processing_status = "READY_FOR_PARSING"
        doc.duplicate_check_reason = f"Manually resolved as new document. {notes}"

    elif decision == "MARK_DUPLICATE":
        if not payload.target_document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_document_id is required when marking as duplicate",
            )
        target = document_repo.get_by_id(db, payload.target_document_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target canonical document '{payload.target_document_id}' not found",
            )

        canonical_id = duplicate_service.resolve_canonical_root(db, target.id)
        doc.duplicate_status = "EXACT_DUPLICATE"
        doc.canonical_document_id = canonical_id
        doc.duplicate_of_document_id = target.id
        doc.processing_status = "DUPLICATE"
        doc.duplicate_check_reason = f"Manually resolved as duplicate of {target.document_code}. {notes}"

    elif decision == "MARK_VERSION":
        if not payload.target_document_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_document_id is required when marking as version",
            )
        target = document_repo.get_by_id(db, payload.target_document_id)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target document '{payload.target_document_id}' not found",
            )

        doc.duplicate_status = "CONFIRMED_VERSION"
        doc.possible_version_of_document_id = target.id
        doc.processing_status = "READY_FOR_PARSING"
        doc.duplicate_check_reason = f"Manually confirmed as updated version/amendment of {target.document_code}. {notes}"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{decision}'. Expected: MARK_NEW_DOCUMENT, MARK_DUPLICATE, or MARK_VERSION",
        )

    db.commit()
    db.refresh(doc)
    logger.info("Document %s manually resolved: %s -> %s", doc.document_code, decision, doc.processing_status)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/compare/{other_id}",
    response_model=DocumentComparisonResponse,
    summary="Compare Two Documents Side-by-Side",
    description="Compare binary checksums, normalized rough text hashes, shingle similarity, and text differences.",
)
def compare_documents(
    document_id: uuid.UUID,
    other_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentComparisonResponse:
    """Compare two documents side-by-side."""
    doc_a = document_repo.get_by_id(db, document_id)
    if not doc_a:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")

    doc_b = document_repo.get_by_id(db, other_id)
    if not doc_b:
        raise HTTPException(status_code=404, detail=f"Document '{other_id}' not found")

    path_a = storage_manager.resolve_storage_path(doc_a.storage_path)
    path_b = storage_manager.resolve_storage_path(doc_b.storage_path)

    if not path_a or not path_a.exists():
        raise HTTPException(status_code=404, detail=f"File for document '{doc_a.document_code}' not found on disk")
    if not path_b or not path_b.exists():
        raise HTTPException(status_code=404, detail=f"File for document '{doc_b.document_code}' not found on disk")

    # Extract fingerprints
    fp_a = extract_text_fingerprint(path_a, document_id=str(doc_a.id))
    fp_b = extract_text_fingerprint(path_b, document_id=str(doc_b.id))

    # Calculate metrics
    exact_hash_match = bool(doc_a.sha256 and doc_b.sha256 and doc_a.sha256 == doc_b.sha256)
    norm_hash_match = bool(fp_a.normalized_hash and fp_b.normalized_hash and fp_a.normalized_hash == fp_b.normalized_hash)

    text_similarity = calculate_jaccard_similarity(fp_a.normalized_text, fp_b.normalized_text, shingle_size=3)
    title_similarity = calculate_title_similarity(doc_a.original_filename, doc_b.original_filename)

    diff_analysis = analyze_document_diff(
        text_old=fp_b.normalized_text,
        text_new=fp_a.normalized_text,
        title_old=doc_b.original_filename,
        title_new=doc_a.original_filename,
    )

    return DocumentComparisonResponse(
        document_a_id=doc_a.id,
        document_a_code=doc_a.document_code,
        document_b_id=doc_b.id,
        document_b_code=doc_b.document_code,
        exact_hash_match=exact_hash_match,
        normalized_hash_match=norm_hash_match,
        text_similarity=text_similarity,
        title_similarity=title_similarity,
        page_count_a=fp_a.page_count,
        page_count_b=fp_b.page_count,
        diff_summary=diff_analysis.diff_summary,
        version_keywords_detected=diff_analysis.version_keywords_found,
    )
