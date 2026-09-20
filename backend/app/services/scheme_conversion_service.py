"""
Scheme Conversion Service
=========================
Converts extracted, normalized, and verified SchemeDraft records (or raw canonical JSON)
into the primary production storage format:
  1. `schemes` table (canonical entity)
  2. `scheme_versions` table (immutable version 1 with canonical_data rule tree)
  3. `storage/schemes/<scheme_id>/versions/v1/scheme.json` and `storage/verified/<draft_id>/verified_scheme.json`
  4. `scheme_search_metadata` and `scheme_embeddings` (for SQL filter & vector discovery)
  5. Local verified RAM rule cache refresh
"""

from datetime import date, datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache.verified_rule_cache import get_rule_cache
from app.core.config import get_settings
from app.database.models.category import Category
from app.database.models.department import Department
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_draft import SchemeDraft
from app.search.indexer import SchemeSearchIndexService

logger = logging.getLogger("yojansetu.services.scheme_conversion")


class SchemeConversionService:
    """
    Coordinates converting SchemeDraft artifacts into verified production schemes.
    """

    @classmethod
    def convert_draft_to_scheme(
        cls,
        session: Session,
        draft_id_or_model: Union[uuid.UUID, str, SchemeDraft],
        reviewer_id: str = "ADMIN_PIPELINE",
        auto_activate: bool = True,
    ) -> Tuple[Scheme, SchemeVersion]:
        """
        Loads a SchemeDraft, derives canonical scheme attributes, persists Scheme & SchemeVersion,
        writes sealed JSON artifacts to storage, and indexes into search metadata.
        """
        settings = get_settings()

        # 1. Resolve Draft
        if isinstance(draft_id_or_model, SchemeDraft):
            draft = draft_id_or_model
        else:
            d_uuid = uuid.UUID(str(draft_id_or_model))
            draft = session.get(SchemeDraft, d_uuid)
            if not draft:
                raise ValueError(f"SchemeDraft with ID '{draft_id_or_model}' not found.")

        # 2. Load canonical JSON data
        canonical_data = cls._load_canonical_payload(draft)

        # 3. Resolve Department
        department = cls._resolve_department(session, draft, canonical_data)

        # 4. Resolve Category
        category = cls._resolve_category(session, draft, canonical_data)

        # 5. Determine Scheme Identity & Codes
        name_en, name_hi, short_name, scheme_code, description = cls._extract_identity(
            draft, canonical_data, department
        )

        # 6. Create or Update Scheme record
        existing_scheme = session.execute(
            select(Scheme).where(Scheme.scheme_code == scheme_code)
        ).scalar_one_or_none()

        if existing_scheme:
            scheme = existing_scheme
            scheme.name_en = name_en
            scheme.name_hi = name_hi or scheme.name_hi
            scheme.short_name = short_name or scheme.short_name
            scheme.short_description = description or scheme.short_description
            scheme.department_id = department.id
            scheme.category_id = category.id
            scheme.status = "HUMAN_VERIFIED"
            logger.info("Updating existing Scheme record | id=%s | code=%s", scheme.id, scheme_code)
        else:
            scheme = Scheme(
                scheme_code=scheme_code,
                name_en=name_en,
                name_hi=name_hi,
                short_name=short_name,
                department_id=department.id,
                category_id=category.id,
                short_description=description,
                status="HUMAN_VERIFIED",
                jurisdiction="RAJASTHAN",
                scheme_origin="RAJASTHAN_STATE",
            )
            session.add(scheme)
            session.flush()
            logger.info("Created new Scheme record | id=%s | code=%s", scheme.id, scheme_code)

        # 7. Construct Full Canonical Snapshot for Version & Search
        prepared_canonical = cls._build_production_canonical(
            scheme=scheme,
            draft=draft,
            raw_canonical=canonical_data,
            department=department,
            category=category,
        )

        # 8. Save Version JSON Artifacts to Storage
        scheme_id_str = str(scheme.id)
        draft_id_str = str(draft.id)
        version_dir = settings.storage_path / "schemes" / scheme_id_str / "versions" / "v1"
        version_dir.mkdir(parents=True, exist_ok=True)
        version_file = version_dir / "scheme.json"

        canonical_json_bytes = json.dumps(prepared_canonical, indent=2, ensure_ascii=False).encode("utf-8")
        version_file.write_bytes(canonical_json_bytes)
        artifact_sha256 = hashlib.sha256(canonical_json_bytes).hexdigest()

        # Also write to storage/verified/<draft_id>/verified_scheme.json
        verified_dir = settings.storage_path / "verified" / draft_id_str
        verified_dir.mkdir(parents=True, exist_ok=True)
        verified_file = verified_dir / "verified_scheme.json"
        verified_payload = {
            "schema_version": "1.0",
            "verifier_version": "1.0",
            "scheme_draft_id": draft_id_str,
            "scheme_id": scheme_id_str,
            "scheme_code": scheme_code,
            "review": {
                "status": "HUMAN_VERIFIED",
                "reviewer_id": reviewer_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "notes": "Verified and promoted from draft",
            },
            "canonical_scheme": prepared_canonical,
            "scheme": prepared_canonical,
        }
        verified_file.write_text(json.dumps(verified_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # 9. Create or Update SchemeVersion record
        existing_version = session.execute(
            select(SchemeVersion).where(
                SchemeVersion.scheme_id == scheme.id,
                SchemeVersion.version_number == 1,
            )
        ).scalar_one_or_none()

        rel_artifact_path = f"storage/schemes/{scheme_id_str}/versions/v1/scheme.json"

        if existing_version:
            version = existing_version
            version.canonical_data = prepared_canonical
            version.artifact_path = rel_artifact_path
            version.artifact_sha256 = artifact_sha256
            version.status = "ACTIVE" if auto_activate else "HUMAN_VERIFIED"
            version.is_current = True
            version.source_document_id = draft.document_id
        else:
            version = SchemeVersion(
                scheme_id=scheme.id,
                version_number=1,
                version_label="v1.0 (Official)",
                status="ACTIVE" if auto_activate else "HUMAN_VERIFIED",
                valid_from=date.today(),
                valid_until=None,
                effective_date=date.today(),
                source_document_id=draft.document_id,
                canonical_data=prepared_canonical,
                artifact_path=rel_artifact_path,
                artifact_sha256=artifact_sha256,
                source_summary=f"Extracted from document {draft.document_id}",
                change_summary="Initial verified baseline version",
                is_current=True,
            )
            session.add(version)

        # 10. Update Draft Status
        draft.status = "HUMAN_VERIFIED"
        session.flush()

        # 11. Index for Search & Discovery (SchemeSearchMetadata & SchemeEmbedding)
        try:
            SchemeSearchIndexService.index_verified_scheme(
                session=session,
                raw_verified_data=verified_payload,
            )
            logger.info("Indexed scheme '%s' into search metadata and vector embedding", scheme.scheme_code)
        except Exception as e:
            logger.error("Failed indexing scheme search metadata: %s", e, exc_info=True)

        session.commit()

        # 12. Refresh In-Memory Rule Cache
        try:
            cache = get_rule_cache()
            cache.refresh_scheme(str(scheme.id), session=session)
            cache.refresh_scheme(scheme.scheme_code, session=session)
            cache.refresh_scheme(draft_id_str, session=session)
        except Exception as e:
            logger.warning("Could not refresh RAM rule cache: %s", e)

        return scheme, version

    @classmethod
    def _load_canonical_payload(cls, draft: SchemeDraft) -> Dict[str, Any]:
        """Loads canonical.json for the draft from disk or returns sensible fallback."""
        settings = get_settings()
        if draft.artifact_path:
            p = settings.storage_path.parent / draft.artifact_path
            if not p.exists():
                p = settings.storage_path / draft.artifact_path.replace("storage/", "")
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning("Failed loading canonical JSON from %s: %s", p, e)

        # Direct search in normalized folder
        doc_id_str = str(draft.document_id)
        draft_id_str = str(draft.id)
        cand = settings.normalized_dir / doc_id_str / draft_id_str / "canonical.json"
        if cand.exists():
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed loading canonical JSON from %s: %s", cand, e)

        return {}

    @classmethod
    def _resolve_department(
        cls,
        session: Session,
        draft: SchemeDraft,
        canonical: Dict[str, Any],
    ) -> Department:
        """Finds or matches appropriate Department record."""
        if draft.department_id:
            dept = session.get(Department, draft.department_id)
            if dept:
                return dept

        # Try match from canonical or draft text
        dept_name = draft.department_name_raw or ""
        identity = canonical.get("scheme_identity", {})
        if not dept_name:
            dept_name = identity.get("department_raw") or identity.get("department") or ""

        dept_name_lower = dept_name.lower()

        # Match known keywords
        code_map = {
            "sje": ["social justice", "सामाजिक न्याय", "pension", "vridhjan", "samman"],
            "agri": ["agriculture", "कृषि", "kisan", "farmer", "urja", "kusum"],
            "energy": ["energy", "renewable", "ऊर्जा", "solar"],
            "tribal": ["tribal", "जनजाति", "fellowship", "st students", "higher education of st"],
            "finance": ["mudra", "वित्त", "finance", "micro units", "loan", "bank", "refinance"],
            "health": ["health", "swasthya", "arogya", "chiranjeevi", "चिकित्सा"],
            "education": ["education", "coaching", "anuprati", "शिक्षा"],
        }

        search_text = f"{dept_name_lower} {draft.detected_name.lower()}"
        matched_code = None
        for code, keywords in code_map.items():
            if any(k in search_text for k in keywords):
                matched_code = code.upper()
                break

        if matched_code:
            dept = session.execute(
                select(Department).where(Department.code == matched_code)
            ).scalar_one_or_none()
            if dept:
                return dept

        # Fallback to first active department
        fallback = session.execute(select(Department).where(Department.active == True)).scalars().first()
        if not fallback:
            # Create emergency department
            fallback = Department(
                code="GEN",
                name_en="General Administration Department",
                name_hi="सामान्य प्रशासन विभाग",
                active=True,
            )
            session.add(fallback)
            session.flush()
        return fallback

    @classmethod
    def _resolve_category(
        cls,
        session: Session,
        draft: SchemeDraft,
        canonical: Dict[str, Any],
    ) -> Category:
        """Finds or matches appropriate Category record."""
        name_lower = draft.detected_name.lower()
        cat_code = "PENSION"

        if any(k in name_lower for k in ["mudra", "loan", "refinance", "credit"]):
            cat_code = "FINANCIAL_LOAN"
        elif any(k in name_lower for k in ["kusum", "solar", "kisan", "agri", "farm"]):
            cat_code = "AGRICULTURE"
        elif any(k in name_lower for k in ["fellowship", "scholarship", "education", "coaching", "student"]):
            cat_code = "SCHOLARSHIP"
        elif any(k in name_lower for k in ["health", "arogya", "medical", "hospital"]):
            cat_code = "HEALTHCARE"
        elif any(k in name_lower for k in ["woman", "women", "child", "maternity"]):
            cat_code = "WOMEN_CHILD"
        elif any(k in name_lower for k in ["housing", "awas"]):
            cat_code = "HOUSING"

        cat = session.execute(select(Category).where(Category.code == cat_code)).scalar_one_or_none()
        if cat:
            return cat

        fallback = session.execute(select(Category).where(Category.active == True)).scalars().first()
        if not fallback:
            fallback = Category(
                code="GENERAL",
                name_en="General Social Welfare",
                name_hi="सामान्य सामाजिक कल्याण",
                active=True,
            )
            session.add(fallback)
            session.flush()
        return fallback

    @classmethod
    def _extract_identity(
        cls,
        draft: SchemeDraft,
        canonical: Dict[str, Any],
        department: Department,
    ) -> Tuple[str, Optional[str], Optional[str], str, Optional[str]]:
        """Derives clean English, Hindi, code, and description from draft & canonical."""
        identity = canonical.get("scheme_identity", {})
        name_en = (
            identity.get("official_name_en")
            or draft.official_name_en
            or draft.detected_name
            or "Rajasthan Welfare Scheme"
        )
        name_hi = (
            identity.get("official_name_hi")
            or draft.official_name_hi
            or None
        )
        short_name = identity.get("short_name")

        # Generate unique readable scheme_code
        prefix = f"RJ-{department.code}"
        # Derive slug from name_en
        clean_name = "".join(c for c in name_en.upper() if c.isalnum() or c == " ")
        words = [w for w in clean_name.split() if w not in ("RAJASTHAN", "SCHEME", "YOJANA", "DEPARTMENT", "OF", "AND", "FOR")]
        slug = "-".join(words[:2]) if words else uuid.uuid4().hex[:6].upper()
        raw_code = f"{prefix}-{slug}"[:32]

        desc = (
            canonical.get("description")
            or f"Official Rajasthan Government welfare scheme administered by {department.name_en}."
        )

        return name_en, name_hi, short_name, raw_code, desc

    @classmethod
    def _build_production_canonical(
        cls,
        scheme: Scheme,
        draft: SchemeDraft,
        raw_canonical: Dict[str, Any],
        department: Department,
        category: Category,
    ) -> Dict[str, Any]:
        """Constructs standardized canonical scheme dictionary for execution and presentation."""
        # Deep clone or wrap
        canonical = dict(raw_canonical)

        canonical["schema_version"] = "1.0"
        canonical["scheme_id"] = scheme.scheme_code
        canonical["scheme_uuid"] = str(scheme.id)

        # Standardized Metadata block
        canonical["metadata"] = {
            "scheme_id": scheme.scheme_code,
            "scheme_uuid": str(scheme.id),
            "name": {
                "en": scheme.name_en,
                "hi": scheme.name_hi or scheme.name_en,
            },
            "short_name": scheme.short_name,
            "department": department.name_en,
            "department_code": department.code,
            "category": category.name_en,
            "category_code": category.code,
            "description": scheme.short_description,
            "jurisdiction": scheme.jurisdiction,
            "scheme_origin": scheme.scheme_origin,
        }

        # Scheme Identity block
        canonical["scheme_identity"] = {
            "scheme_id": scheme.scheme_code,
            "name": {
                "en": scheme.name_en,
                "hi": scheme.name_hi,
            },
            "official_name_raw": scheme.name_en,
            "official_name_en": scheme.name_en,
            "official_name_hi": scheme.name_hi,
            "department": department.name_en,
            "department_id": str(department.id),
            "category": category.name_en,
            "category_id": str(category.id),
            "scheme_origin": scheme.scheme_origin,
            "jurisdiction": scheme.jurisdiction,
        }

        # Ensure eligibility block has root_rule
        if "eligibility" not in canonical or not isinstance(canonical["eligibility"], dict):
            canonical["eligibility"] = {}

        if "root_rule" not in canonical["eligibility"]:
            # Build default AND root rule
            canonical["eligibility"]["root_rule"] = {
                "type": "AND",
                "children": [
                    {
                        "field": "domicile",
                        "operator": "EQ",
                        "value": "RAJASTHAN",
                        "raw_text": "Resident of Rajasthan",
                    }
                ],
            }

        # Ensure benefits block
        if "benefits" not in canonical:
            canonical["benefits"] = []

        # Ensure exclusions
        if "exclusions" not in canonical:
            canonical["exclusions"] = []

        # Ensure required_documents
        if "required_documents" not in canonical:
            canonical["required_documents"] = []

        return canonical
