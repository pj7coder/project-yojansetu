import json
import logging
import math
from pathlib import Path
from typing import Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.scheme import Scheme, SchemeVersion
from app.repositories.category_repository import CategoryRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.scheme_repository import SchemeRepository
from app.schemas.scheme import (
    SchemeCreate,
    SchemeDetailResponse,
    SchemeFullUpdate,
    SchemeListResponse,
    SchemeResponse,
    SchemeUpdate,
    SchemeVersionResponse,
)

logger = logging.getLogger("yojansetu.schemes")

VALID_STATUSES = {
    "DRAFT",
    "REVIEW_REQUIRED",
    "HUMAN_VERIFIED",
    "ACTIVE",
    "PRODUCTION",
    "INACTIVE",
    "ARCHIVED",
}

VALID_JURISDICTIONS = {
    "RAJASTHAN",
    "INDIA",
    "OTHER",
}

VALID_ORIGINS = {
    "RAJASTHAN_STATE",
    "CENTRAL",
    "CENTRALLY_SPONSORED",
    "RAJASTHAN_MODIFIED_CSS",
    "UNKNOWN",
}


class SchemeService:
    """Service layer coordinating scheme business rules, relational validations, and persistence."""

    def __init__(
        self,
        scheme_repo: Optional[SchemeRepository] = None,
        dept_repo: Optional[DepartmentRepository] = None,
        cat_repo: Optional[CategoryRepository] = None,
    ):
        self.scheme_repo = scheme_repo or SchemeRepository()
        self.dept_repo = dept_repo or DepartmentRepository()
        self.cat_repo = cat_repo or CategoryRepository()

    def create_scheme(self, db: Session, scheme_in: SchemeCreate) -> Scheme:
        """Validate relational integrity and business constraints before persisting scheme."""
        # 1. Validate controlled enum values
        status_val = scheme_in.status.strip().upper()
        if status_val not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{scheme_in.status}'. Allowed: {', '.join(sorted(VALID_STATUSES))}",
            )

        jurisdiction_val = scheme_in.jurisdiction.strip().upper()
        if jurisdiction_val not in VALID_JURISDICTIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid jurisdiction '{scheme_in.jurisdiction}'. Allowed: {', '.join(sorted(VALID_JURISDICTIONS))}",
            )

        origin_val = scheme_in.scheme_origin.strip().upper()
        if origin_val not in VALID_ORIGINS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid scheme_origin '{scheme_in.scheme_origin}'. Allowed: {', '.join(sorted(VALID_ORIGINS))}",
            )

        # 2. Validate Foreign Keys (Relational integrity)
        department = self.dept_repo.get_by_id(db, scheme_in.department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with id '{scheme_in.department_id}' does not exist",
            )

        category = self.cat_repo.get_by_id(db, scheme_in.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with id '{scheme_in.category_id}' does not exist",
            )

        # 3. Check scheme_code uniqueness
        existing_scheme = self.scheme_repo.get_by_code(db, scheme_in.scheme_code)
        if existing_scheme:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scheme with code '{scheme_in.scheme_code.upper()}' already exists",
            )

        # 4. Persist scheme and initial version
        scheme = self.scheme_repo.create(db, scheme_in)
        logger.info(
            "Scheme created successfully | id=%s | code=%s | status=%s",
            scheme.id,
            scheme.scheme_code,
            scheme.status,
        )
        return scheme

    def get_scheme(self, db: Session, scheme_id: uuid.UUID) -> Scheme:
        """Fetch scheme by UUID or raise HTTP 404."""
        scheme = self.scheme_repo.get_by_id(db, scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme with id '{scheme_id}' not found",
            )
        return scheme

    def list_schemes(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None,
        department_id: Optional[uuid.UUID] = None,
        category_id: Optional[uuid.UUID] = None,
        scheme_origin: Optional[str] = None,
    ) -> SchemeListResponse:
        """Query paginated scheme list with calculated pagination metadata."""
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20

        items, total = self.scheme_repo.list(
            db,
            page=page,
            page_size=page_size,
            status=status_filter,
            department_id=department_id,
            category_id=category_id,
            scheme_origin=scheme_origin,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return SchemeListResponse(
            items=[SchemeResponse.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def update_scheme(
        self, db: Session, scheme_id: uuid.UUID, update_in: SchemeUpdate
    ) -> Scheme:
        """Update mutable fields of a scheme with relational validation."""
        scheme = self.get_scheme(db, scheme_id)

        # Validate relational updates if requested
        if update_in.department_id:
            dept = self.dept_repo.get_by_id(db, update_in.department_id)
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Department with id '{update_in.department_id}' does not exist",
                )

        if update_in.category_id:
            cat = self.cat_repo.get_by_id(db, update_in.category_id)
            if not cat:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Category with id '{update_in.category_id}' does not exist",
                )

        if update_in.status:
            status_val = update_in.status.strip().upper()
            if status_val not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid status '{update_in.status}'",
                )

        updated = self.scheme_repo.update(db, scheme, update_in)
        logger.info("Scheme updated successfully | id=%s | code=%s", updated.id, updated.scheme_code)
        return updated

    def get_scheme_detail(self, db: Session, scheme_id: uuid.UUID) -> SchemeDetailResponse:
        """Retrieve full scheme detail including active canonical data and relational names."""
        scheme = self.get_scheme(db, scheme_id)
        settings = get_settings()

        # Resolve department & category names
        dept = self.dept_repo.get_by_id(db, scheme.department_id) if scheme.department_id else None
        cat = self.cat_repo.get_by_id(db, scheme.category_id) if scheme.category_id else None

        # Resolve current or active version
        active_ver = None
        if scheme.versions:
            active_ver = next(
                (v for v in scheme.versions if v.is_current or v.status in ("ACTIVE", "HUMAN_VERIFIED")),
                scheme.versions[0]
            )

        canonical_data = None
        source_filename = None
        source_doc_id = None

        if active_ver:
            canonical_data = active_ver.canonical_data
            source_doc_id = active_ver.source_document_id

            if not canonical_data and active_ver.artifact_path:
                art_path = Path(active_ver.artifact_path)
                if not art_path.is_absolute():
                    art_path = settings.storage_path.parent / art_path
                if art_path.exists():
                    try:
                        canonical_data = json.loads(art_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass

            if source_doc_id:
                doc = db.get(Document, source_doc_id)
                if doc:
                    source_filename = doc.original_filename

        if not canonical_data:
            canonical_data = {
                "scheme_identity": {
                    "name": {
                        "raw": scheme.name_en,
                        "en": scheme.name_en,
                        "hi": scheme.name_hi,
                        "short_name": scheme.short_name,
                    },
                    "scheme_code": scheme.scheme_code,
                    "department": dept.name_en if dept else None,
                    "category": cat.name_en if cat else None,
                    "description": scheme.short_description,
                },
                "benefits": [],
                "eligibility": {
                    "simple_fields": {},
                    "conditions": [],
                    "exclusions": [],
                },
                "required_documents": [],
                "application": {
                    "channels": ["ONLINE", "EMITRA"],
                    "steps": [],
                },
                "important_dates": [],
                "evidence_registry": [],
            }

        return SchemeDetailResponse(
            id=scheme.id,
            scheme_code=scheme.scheme_code,
            name_en=scheme.name_en,
            name_hi=scheme.name_hi,
            short_name=scheme.short_name,
            department_id=scheme.department_id,
            category_id=scheme.category_id,
            short_description=scheme.short_description,
            status=scheme.status,
            jurisdiction=scheme.jurisdiction,
            scheme_origin=scheme.scheme_origin,
            created_at=scheme.created_at,
            updated_at=scheme.updated_at,
            versions=[SchemeVersionResponse.model_validate(v) for v in scheme.versions],
            department_name=dept.name_en if dept else None,
            category_name=cat.name_en if cat else None,
            active_version_number=active_ver.version_number if active_ver else 1,
            canonical_data=canonical_data,
            source_filename=source_filename,
            source_document_id=source_doc_id,
        )

    def update_scheme_full(
        self, db: Session, scheme_id: uuid.UUID, update_in: SchemeFullUpdate
    ) -> SchemeDetailResponse:
        """Update both scheme metadata and canonical extracted rules, reindexing search and refreshing cache."""
        scheme = self.get_scheme(db, scheme_id)
        settings = get_settings()

        # Validate department & category if provided
        if update_in.department_id:
            dept = self.dept_repo.get_by_id(db, update_in.department_id)
            if not dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Department with id '{update_in.department_id}' does not exist",
                )
            scheme.department_id = update_in.department_id

        if update_in.category_id:
            cat = self.cat_repo.get_by_id(db, update_in.category_id)
            if not cat:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Category with id '{update_in.category_id}' does not exist",
                )
            scheme.category_id = update_in.category_id

        # Check scheme_code uniqueness if changed
        if update_in.scheme_code and update_in.scheme_code.strip() != scheme.scheme_code:
            existing = self.scheme_repo.get_by_code(db, update_in.scheme_code.strip())
            if existing and existing.id != scheme.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Scheme with code '{update_in.scheme_code.strip()}' already exists",
                )
            scheme.scheme_code = update_in.scheme_code.strip()

        if update_in.name_en:
            scheme.name_en = update_in.name_en.strip()
        if update_in.name_hi is not None:
            scheme.name_hi = update_in.name_hi.strip() if update_in.name_hi else None
        if update_in.short_name is not None:
            scheme.short_name = update_in.short_name.strip() if update_in.short_name else None
        if update_in.short_description is not None:
            scheme.short_description = update_in.short_description.strip()
        if update_in.status:
            st_val = update_in.status.strip().upper()
            if st_val not in VALID_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid status '{update_in.status}'",
                )
            scheme.status = st_val
        if update_in.jurisdiction:
            scheme.jurisdiction = update_in.jurisdiction.strip().upper()
        if update_in.scheme_origin:
            scheme.scheme_origin = update_in.scheme_origin.strip().upper()

        # Resolve active version
        active_ver = None
        if scheme.versions:
            active_ver = next((v for v in scheme.versions if v.is_current), scheme.versions[0])
        else:
            active_ver = SchemeVersion(
                scheme_id=scheme.id,
                version_number=1,
                version_label="v1.0 (Official)",
                status="ACTIVE",
                is_current=True,
                canonical_data={},
            )
            db.add(active_ver)
            db.flush()

        canonical = dict(active_ver.canonical_data or {})

        # Merge updates
        if update_in.canonical_data:
            canonical.update(update_in.canonical_data)

        if update_in.benefits is not None:
            canonical["benefits"] = update_in.benefits

        if update_in.eligibility is not None:
            canonical["eligibility"] = update_in.eligibility

        if update_in.required_documents is not None:
            canonical["required_documents"] = update_in.required_documents

        if update_in.application is not None:
            canonical["application"] = update_in.application

        if update_in.important_dates is not None:
            canonical["important_dates"] = update_in.important_dates

        # Synchronize identity inside canonical snapshot
        identity = canonical.get("scheme_identity", {})
        if not isinstance(identity, dict):
            identity = {}
        name_dict = identity.get("name", {})
        if not isinstance(name_dict, dict):
            name_dict = {}
        name_dict["en"] = scheme.name_en
        name_dict["hi"] = scheme.name_hi
        name_dict["short_name"] = scheme.short_name
        name_dict["raw"] = scheme.name_en
        identity["name"] = name_dict
        identity["scheme_code"] = scheme.scheme_code
        identity["description"] = scheme.short_description
        canonical["scheme_identity"] = identity
        canonical["scheme_code"] = scheme.scheme_code

        active_ver.canonical_data = canonical

        # Persist version JSON artifact to disk
        scheme_id_str = str(scheme.id)
        version_dir = settings.storage_path / "schemes" / scheme_id_str / "versions" / "v1"
        version_dir.mkdir(parents=True, exist_ok=True)
        version_file = version_dir / "scheme.json"
        canonical_bytes = json.dumps(canonical, indent=2, ensure_ascii=False).encode("utf-8")
        version_file.write_bytes(canonical_bytes)
        active_ver.artifact_path = f"storage/schemes/{scheme_id_str}/versions/v1/scheme.json"

        db.commit()
        db.refresh(scheme)

        # Re-index search metadata and vector embedding
        try:
            from app.search.indexer import SchemeSearchIndexService
            verified_payload = {
                "schema_version": "1.0",
                "verifier_version": "1.0",
                "scheme_id": scheme_id_str,
                "scheme_code": scheme.scheme_code,
                "canonical_scheme": canonical,
                "scheme": canonical,
            }
            SchemeSearchIndexService.index_verified_scheme(
                session=db,
                raw_verified_data=verified_payload,
            )
            logger.info("Re-indexed scheme '%s' search metadata after edit", scheme.scheme_code)
        except Exception as ex:
            logger.error("Failed re-indexing scheme search metadata: %s", ex)

        # Refresh in-memory rule cache
        try:
            from app.cache.verified_rule_cache import get_rule_cache
            cache = get_rule_cache()
            cache.refresh_scheme(str(scheme.id), session=db)
            cache.refresh_scheme(scheme.scheme_code, session=db)
        except Exception as ex:
            logger.warning("Could not refresh RAM rule cache after scheme edit: %s", ex)

        return self.get_scheme_detail(db, scheme.id)

    def delete_scheme(self, db: Session, scheme_id: uuid.UUID) -> bool:
        """Permanently delete a scheme record and its versions."""
        scheme = self.get_scheme(db, scheme_id)
        db.delete(scheme)
        db.commit()
        logger.info("Deleted scheme | id=%s | code=%s", scheme.id, scheme.scheme_code)
        return True

