import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.models.scheme import Scheme
from app.database.session import get_db
from app.repositories.versioning_repository import VersioningRepository
from app.versioning.schemas import (
    ChangeSetResponse,
    SchemeTimelineResponse,
    SchemeVersionResponse,
    VersionTimelineItem,
)
from app.versioning.service import SchemeVersionService
from app.versioning.timeline import SchemeTimelineService

logger = logging.getLogger("jansetu.api.routes.versioning")

router = APIRouter(tags=["versioning"])

version_repo = VersioningRepository()
version_service = SchemeVersionService()
timeline_service = SchemeTimelineService()


class ApproveChangeSetRequest(BaseModel):
    reviewer_id: Optional[str] = None
    approved_item_ids: Optional[List[uuid.UUID]] = None


class RejectChangeSetRequest(BaseModel):
    reason: str
    reviewer_id: Optional[str] = None


# 1. Version Timeline
@router.get(
    "/admin/schemes/{scheme_id}/versions",
    response_model=SchemeTimelineResponse,
    summary="Get version timeline and anomalies for a scheme",
)
def get_scheme_versions_timeline(
    scheme_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    scheme = db.get(Scheme, scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    versions = version_repo.list_versions_for_scheme(db, scheme_id)
    anomalies = timeline_service.detect_timeline_anomalies(db, scheme_id)

    items = [
        VersionTimelineItem(
            version_id=v.id,
            version_number=v.version_number,
            version_label=v.version_label,
            status=v.status,
            valid_from=v.valid_from,
            valid_until=v.valid_until,
            effective_date=v.effective_date,
            is_current=v.is_current,
            source_document_id=v.source_document_id,
            change_summary=v.change_summary,
        )
        for v in versions
    ]

    return SchemeTimelineResponse(
        scheme_id=scheme_id,
        scheme_name=scheme.name_en,
        versions=items,
        anomalies=anomalies,
    )


# 2. Version Detail
@router.get(
    "/admin/scheme-versions/{version_id}",
    response_model=SchemeVersionResponse,
    summary="Get complete details, canonical data, and provenance for a SchemeVersion",
)
def get_scheme_version_detail(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    ver = version_repo.get_version(db, version_id)
    if not ver:
        raise HTTPException(status_code=404, detail="SchemeVersion not found")
    return ver


# 3. List Change Sets
@router.get(
    "/admin/scheme-change-sets",
    response_model=List[ChangeSetResponse],
    summary="List proposed scheme change sets with optional status and risk filters",
)
def list_change_sets(
    status: Optional[str] = Query(None, description="DETECTED, REVIEW_REQUIRED, HUMAN_APPROVED, HUMAN_REJECTED, APPLIED_TO_VERSION"),
    scheme_id: Optional[uuid.UUID] = Query(None),
    critical_only: bool = Query(False, description="Filter only changesets with CRITICAL risk items"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    sets = version_repo.list_change_sets(
        db=db,
        status=status,
        scheme_id=scheme_id,
        critical_only=critical_only,
        skip=skip,
        limit=limit,
    )
    result = []
    for cs in sets:
        items_json = [
            {
                "id": str(i.id),
                "field_path": i.field_path,
                "change_type": i.change_type,
                "old_value": i.old_value_json,
                "new_value": i.new_value_json,
                "risk_level": i.risk_level,
                "evidence_refs": i.evidence_refs,
                "clause_reference": i.clause_reference,
                "status": i.status,
            }
            for i in cs.items
        ]
        cs_dict = {
            "id": cs.id,
            "scheme_id": cs.scheme_id,
            "base_version_id": cs.base_version_id,
            "source_document_id": cs.source_document_id,
            "relationship_id": cs.relationship_id,
            "status": cs.status,
            "effective_date": cs.effective_date,
            "publication_date": cs.publication_date,
            "changes_count": cs.changes_count,
            "critical_changes_count": cs.critical_changes_count,
            "change_summary": cs.change_summary,
            "conflict_reason": cs.conflict_reason,
            "change_set_hash": cs.change_set_hash,
            "created_at": cs.created_at,
            "updated_at": cs.updated_at,
            "items": items_json,
        }
        result.append(cs_dict)
    return result


# 4. Change Set Detail
@router.get(
    "/admin/scheme-change-sets/{id}",
    response_model=ChangeSetResponse,
    summary="Get side-by-side diff details and evidence links for a change set",
)
def get_change_set_detail(
    id: uuid.UUID,
    db: Session = Depends(get_db),
):
    cs = version_repo.get_change_set(db, id)
    if not cs:
        raise HTTPException(status_code=404, detail="SchemeChangeSet not found")

    items_json = [
        {
            "id": str(i.id),
            "field_path": i.field_path,
            "change_type": i.change_type,
            "old_value": i.old_value_json,
            "new_value": i.new_value_json,
            "risk_level": i.risk_level,
            "evidence_refs": i.evidence_refs,
            "clause_reference": i.clause_reference,
            "status": i.status,
        }
        for i in cs.items
    ]
    return {
        "id": cs.id,
        "scheme_id": cs.scheme_id,
        "base_version_id": cs.base_version_id,
        "source_document_id": cs.source_document_id,
        "relationship_id": cs.relationship_id,
        "status": cs.status,
        "effective_date": cs.effective_date,
        "publication_date": cs.publication_date,
        "changes_count": cs.changes_count,
        "critical_changes_count": cs.critical_changes_count,
        "change_summary": cs.change_summary,
        "conflict_reason": cs.conflict_reason,
        "change_set_hash": cs.change_set_hash,
        "created_at": cs.created_at,
        "updated_at": cs.updated_at,
        "items": items_json,
    }


# 5. Approve Change Set
@router.post(
    "/admin/scheme-change-sets/{id}/approve",
    response_model=SchemeVersionResponse,
    summary="Approve a change set and construct a new immutable SchemeVersion",
)
def approve_change_set(
    id: uuid.UUID,
    req: Optional[ApproveChangeSetRequest] = None,
    db: Session = Depends(get_db),
):
    try:
        new_ver = version_service.approve_change_set(
            db=db,
            change_set_id=id,
            reviewer_id=req.reviewer_id if req else None,
            approved_item_ids=req.approved_item_ids if req else None,
        )
        return new_ver
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 6. Reject Change Set
@router.post(
    "/admin/scheme-change-sets/{id}/reject",
    summary="Reject a change set with audit reason",
)
def reject_change_set(
    id: uuid.UUID,
    req: RejectChangeSetRequest,
    db: Session = Depends(get_db),
):
    try:
        cs = version_service.reject_change_set(
            db=db,
            change_set_id=id,
            reason=req.reason,
        )
        return {"status": "REJECTED", "change_set_id": cs.id, "reason": req.reason}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 7. Activate Version
@router.post(
    "/admin/scheme-versions/{version_id}/activate",
    response_model=SchemeVersionResponse,
    summary="Activate a verified SchemeVersion and invalidate RAM rule cache and search index",
)
def activate_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        ver = version_service.activate_version(db=db, version_id=version_id)
        return ver
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 8. Query Active Version for Citizens
@router.get(
    "/schemes/{scheme_id}/active-version",
    response_model=Optional[SchemeVersionResponse],
    summary="Retrieve the legally active verified version of a scheme at a given evaluation date",
)
def get_active_version(
    scheme_id: uuid.UUID,
    evaluation_date: Optional[date] = Query(None, description="Target date for eligibility check, defaults to today"),
    db: Session = Depends(get_db),
):
    ver = timeline_service.get_active_scheme_version(
        db=db,
        scheme_id=scheme_id,
        evaluation_date=evaluation_date,
    )
    if not ver:
        raise HTTPException(status_code=404, detail="No active version found for scheme on specified date")
    return ver
