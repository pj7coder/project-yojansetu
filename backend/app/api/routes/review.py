from typing import Any, Dict, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.review.authorization import ReviewAuthorizationService
from app.review.schemas import (
    CompleteReviewRequest,
    ConflictResolutionRequest,
    HumanReviewItemResponse,
    ItemDecisionRequest,
    RejectSchemeRequest,
    ReopenReviewRequest,
    ReviewDecision,
    ReviewQueueResponse,
    ReviewSessionDetailResponse,
)
from app.review.service import HumanReviewService

router = APIRouter()


# ---------------------------------------------------------------------------
# Review Queue
# ---------------------------------------------------------------------------

@router.get(
    "/review/queue",
    response_model=ReviewQueueResponse,
    summary="Get prioritized human review queue",
    tags=["Human Review"],
)
def get_review_queue(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Draft status filter (e.g., READY_FOR_HUMAN_REVIEW)"),
    department_id: Optional[uuid.UUID] = Query(None, description="Filter by department UUID"),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    return service.get_review_queue(
        page=page,
        page_size=page_size,
        status_filter=status,
        department_id=department_id,
    )


# ---------------------------------------------------------------------------
# Review Sessions
# ---------------------------------------------------------------------------

@router.post(
    "/scheme-drafts/{draft_id}/review/start",
    summary="Start or retrieve active review session for a scheme draft",
    tags=["Human Review"],
)
def start_review_session(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        session = service.start_or_get_review_session(
            draft_id=draft_id,
            reviewer_id=reviewer_id,
        )
        return {
            "session_id": session.id,
            "scheme_draft_id": session.scheme_draft_id,
            "status": session.status,
            "reviewer_id": session.reviewer_id,
            "review_version": session.review_version,
            "started_at": session.started_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/scheme-drafts/{draft_id}/review",
    response_model=ReviewSessionDetailResponse,
    summary="Get consolidated review workspace detail for a draft",
    tags=["Human Review"],
)
def get_review_detail(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        return service.get_review_detail(draft_id=draft_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Field-Level Decisions
# ---------------------------------------------------------------------------

@router.post(
    "/review-items/{item_id}/decision",
    response_model=HumanReviewItemResponse,
    summary="Submit review decision on an atomic fact (APPROVE, EDIT, REJECT, NOT_APPLICABLE)",
    tags=["Human Review"],
)
def submit_item_decision(
    item_id: uuid.UUID,
    request: ItemDecisionRequest,
    review_version: Optional[int] = Query(None, description="Optimistic locking review version"),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        item = service.submit_item_decision(
            item_id=item_id,
            reviewer_id=reviewer_id,
            request=request,
            review_version=review_version,
        )
        return HumanReviewItemResponse.model_validate(item)
    except ValueError as e:
        err_msg = str(e)
        if "Optimistic lock conflict" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/review-items/{item_id}/approve",
    response_model=HumanReviewItemResponse,
    summary="Approve a review item",
    tags=["Human Review"],
)
def approve_item(
    item_id: uuid.UUID,
    reviewer_comment: Optional[str] = Query(None),
    override_reason: Optional[str] = Query(None),
    review_version: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    req = ItemDecisionRequest(
        decision=ReviewDecision.APPROVED,
        reviewer_comment=reviewer_comment,
        override_reason=override_reason,
    )
    return submit_item_decision(
        item_id=item_id,
        request=req,
        review_version=review_version,
        db=db,
        reviewer_id=reviewer_id,
    )


@router.post(
    "/review-items/{item_id}/reject",
    response_model=HumanReviewItemResponse,
    summary="Reject a review item",
    tags=["Human Review"],
)
def reject_item(
    item_id: uuid.UUID,
    reviewer_comment: Optional[str] = Query(None),
    review_version: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    req = ItemDecisionRequest(
        decision=ReviewDecision.REJECTED,
        reviewer_comment=reviewer_comment,
    )
    return submit_item_decision(
        item_id=item_id,
        request=req,
        review_version=review_version,
        db=db,
        reviewer_id=reviewer_id,
    )


# ---------------------------------------------------------------------------
# Conflict Resolution
# ---------------------------------------------------------------------------

@router.post(
    "/scheme-drafts/{draft_id}/conflicts/{conflict_id}/resolve",
    summary="Resolve an extraction contradiction or version conflict",
    tags=["Human Review"],
)
def resolve_conflict(
    draft_id: uuid.UUID,
    conflict_id: str,
    request: ConflictResolutionRequest,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        resolved = service.resolve_conflict(
            draft_id=draft_id,
            conflict_id=conflict_id,
            reviewer_id=reviewer_id,
            request=request,
        )
        return {"status": "RESOLVED", "conflict": resolved}
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


# ---------------------------------------------------------------------------
# Scheme Review Completion & Finalization
# ---------------------------------------------------------------------------

@router.post(
    "/scheme-drafts/{draft_id}/review/complete",
    summary="Finalize human review and seal verified scheme artifact",
    tags=["Human Review"],
)
def complete_review(
    draft_id: uuid.UUID,
    request: CompleteReviewRequest,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        summary = service.complete_review(
            draft_id=draft_id,
            reviewer_id=reviewer_id,
            request=request,
        )
        return {
            "status": "HUMAN_VERIFIED",
            "message": "Scheme draft has been successfully verified by human reviewer.",
            "summary": summary,
        }
    except ValueError as e:
        err_msg = str(e)
        if "Cannot complete human verification" in err_msg or "mismatch" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/scheme-drafts/{draft_id}/review/reject",
    summary="Reject scheme draft completely",
    tags=["Human Review"],
)
def reject_scheme(
    draft_id: uuid.UUID,
    request: RejectSchemeRequest,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        session = service.reject_scheme(
            draft_id=draft_id,
            reviewer_id=reviewer_id,
            reason=request.reason,
        )
        return {
            "status": "HUMAN_REJECTED",
            "session_id": session.id,
            "message": f"Scheme draft has been rejected: {request.reason}",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/scheme-drafts/{draft_id}/review/reopen",
    summary="Reopen a previously verified or rejected scheme draft review",
    tags=["Human Review"],
)
def reopen_review(
    draft_id: uuid.UUID,
    request: ReopenReviewRequest,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    service = HumanReviewService(db)
    try:
        session = service.reopen_review(
            draft_id=draft_id,
            reviewer_id=reviewer_id,
            reason=request.reason,
        )
        return {
            "status": "IN_HUMAN_REVIEW",
            "new_session_id": session.id,
            "review_version": session.review_version,
            "message": f"Review reopened: {request.reason}",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/scheme-drafts/{draft_id}/publish",
    summary="Publish draft directly into primary Scheme and SchemeVersion production tables",
    tags=["Human Review"],
)
def publish_draft_to_scheme(
    draft_id: uuid.UUID,
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    """Converts a SchemeDraft into Scheme, SchemeVersion, and indexes it for citizen search."""
    from app.services.scheme_conversion_service import SchemeConversionService
    try:
        scheme, version = SchemeConversionService.convert_draft_to_scheme(
            session=db,
            draft_id_or_model=draft_id,
            reviewer_id=reviewer_id,
            auto_activate=True,
        )
        return {
            "status": "PUBLISHED",
            "scheme_id": str(scheme.id),
            "scheme_code": scheme.scheme_code,
            "name_en": scheme.name_en,
            "version_number": version.version_number,
            "message": f"Scheme '{scheme.name_en}' ({scheme.scheme_code}) successfully published and indexed.",
        }
    except Exception as e:
        logger.error(f"Error publishing draft {draft_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/scheme-drafts/publish-all",
    summary="Publish all available drafts into production schemes",
    tags=["Human Review"],
)
def publish_all_drafts(
    db: Session = Depends(get_db),
    reviewer_id: str = Depends(ReviewAuthorizationService.get_current_reviewer),
):
    """Batch publishes all unverified/ready drafts into production schemes."""
    from app.database.models.scheme_draft import SchemeDraft
    from app.services.scheme_conversion_service import SchemeConversionService

    drafts = db.query(SchemeDraft).all()
    results = []
    for d in drafts:
        try:
            scheme, version = SchemeConversionService.convert_draft_to_scheme(
                session=db,
                draft_id_or_model=d,
                reviewer_id=reviewer_id,
                auto_activate=True,
            )
            results.append({
                "draft_id": str(d.id),
                "scheme_code": scheme.scheme_code,
                "name_en": scheme.name_en,
                "status": "PUBLISHED",
            })
        except Exception as e:
            results.append({
                "draft_id": str(d.id),
                "status": "FAILED",
                "error": str(e),
            })
    return {"total": len(drafts), "results": results}

