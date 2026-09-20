import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache.verified_rule_cache import VerifiedRuleCache, get_rule_cache
from app.database.base import utc_now
from app.database.models.document import Document
from app.database.models.document_relationship import DocumentRelationship
from app.database.models.scheme import Scheme, SchemeVersion
from app.database.models.scheme_change_item import SchemeChangeItem
from app.database.models.scheme_change_set import SchemeChangeSet
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.versioning.canonical_diff import CanonicalSchemeDiffService
from app.versioning.change_set_builder import SchemeChangeSetBuilder
from app.versioning.timeline import SchemeTimelineService
from app.versioning.version_builder import SchemeVersionBuilder

logger = logging.getLogger("jansetu.versioning.service")


class SchemeVersionService:
    """
    Central orchestrator for the Day 19 scheme versioning lifecycle.
    Manages proposed change sets, human reviews, immutable version creation,
    temporal activations, cache invalidation, and search index refresh.
    """

    def __init__(
        self,
        diff_service: Optional[CanonicalSchemeDiffService] = None,
        change_builder: Optional[SchemeChangeSetBuilder] = None,
        version_builder: Optional[SchemeVersionBuilder] = None,
        timeline_service: Optional[SchemeTimelineService] = None,
    ):
        self.diff_service = diff_service or CanonicalSchemeDiffService()
        self.change_builder = change_builder or SchemeChangeSetBuilder()
        self.version_builder = version_builder or SchemeVersionBuilder()
        self.timeline_service = timeline_service or SchemeTimelineService()

    def build_change_set_for_document(
        self,
        db: Session,
        scheme_id: uuid.UUID,
        base_version_id: uuid.UUID,
        source_document_id: uuid.UUID,
        candidate_canonical: Dict[str, Any],
        relationship_id: Optional[uuid.UUID] = None,
        effective_date: Optional[date] = None,
        publication_date: Optional[date] = None,
        is_partial_amendment: bool = True,
        evidence_refs: Optional[List[Dict[str, Any]]] = None,
        conflict_reason: Optional[str] = None,
    ) -> SchemeChangeSet:
        """
        Generate a proposed SchemeChangeSet comparing an existing verified base version
        against newly extracted/normalized document content.
        """
        base_ver = db.get(SchemeVersion, base_version_id)
        if not base_ver:
            raise ValueError(f"Base SchemeVersion {base_version_id} not found")

        base_canonical = base_ver.canonical_data or {}

        # Run structured diff
        diff_items = self.diff_service.diff_schemes(
            base_canonical=base_canonical,
            candidate_canonical=candidate_canonical,
            is_partial_amendment=is_partial_amendment,
            evidence_refs=evidence_refs,
        )

        # Build changeset model
        change_set = self.change_builder.build_change_set(
            scheme_id=scheme_id,
            base_version_id=base_version_id,
            source_document_id=source_document_id,
            change_items=diff_items,
            relationship_id=relationship_id,
            effective_date=effective_date,
            publication_date=publication_date,
            conflict_reason=conflict_reason,
            base_version_hash=base_ver.artifact_sha256,
        )

        db.add(change_set)
        db.commit()
        db.refresh(change_set)

        logger.info(
            f"Built SchemeChangeSet {change_set.id} with {change_set.changes_count} items "
            f"({change_set.critical_changes_count} critical) for scheme {scheme_id}"
        )
        return change_set

    def approve_change_set(
        self,
        db: Session,
        change_set_id: uuid.UUID,
        reviewer_id: Optional[str] = None,
        approved_item_ids: Optional[List[uuid.UUID]] = None,
    ) -> SchemeVersion:
        """
        Approve a change set, verify guards, apply patch to base version,
        and generate a new immutable SchemeVersion record.
        """
        cs = db.get(SchemeChangeSet, change_set_id)
        if not cs:
            raise ValueError(f"SchemeChangeSet {change_set_id} not found")

        if cs.status in ["HUMAN_APPROVED", "APPLIED_TO_VERSION"]:
            raise ValueError(f"ChangeSet {change_set_id} is already approved or applied")

        # Guard 1: Conflict guard
        if cs.conflict_reason and "UNRESOLVED_SOURCE_CONFLICT" in cs.conflict_reason:
            raise ValueError(f"Cannot approve ChangeSet with unresolved conflict: {cs.conflict_reason}")

        # Guard 2: Stale base version guard
        base_ver = db.get(SchemeVersion, cs.base_version_id)
        if not base_ver:
            raise ValueError(f"Base version {cs.base_version_id} does not exist")

        # Check if a newer version has already been created for this scheme
        latest_ver = (
            db.execute(
                select(SchemeVersion)
                .where(SchemeVersion.scheme_id == cs.scheme_id)
                .order_by(SchemeVersion.version_number.desc())
            )
            .scalars()
            .first()
        )
        if latest_ver and latest_ver.version_number > base_ver.version_number:
            cs.conflict_reason = "STALE_BASE_VERSION"
            db.commit()
            raise ValueError(
                f"STALE_BASE_VERSION: Base version is v{base_ver.version_number}, "
                f"but scheme already has v{latest_ver.version_number}. Re-diff required."
            )

        # Mark item statuses
        if approved_item_ids is not None:
            approved_set = set(approved_item_ids)
            for item in cs.items:
                item.status = "APPROVED" if item.id in approved_set else "REJECTED"
        else:
            for item in cs.items:
                item.status = "APPROVED"

        cs.status = "HUMAN_APPROVED"
        db.commit()

        # Build new version
        new_version = self.version_builder.create_new_version(
            base_version=base_ver,
            change_set=cs,
            approved_items_only=True,
        )

        db.add(new_version)
        cs.status = "APPLIED_TO_VERSION"
        db.commit()
        db.refresh(new_version)

        logger.info(
            f"Created immutable SchemeVersion v{new_version.version_number} (id={new_version.id}) "
            f"for scheme {cs.scheme_id} from change set {change_set_id}"
        )
        return new_version

    def reject_change_set(
        self,
        db: Session,
        change_set_id: uuid.UUID,
        reason: str,
    ) -> SchemeChangeSet:
        """
        Reject a change set with audit reason.
        """
        cs = db.get(SchemeChangeSet, change_set_id)
        if not cs:
            raise ValueError(f"SchemeChangeSet {change_set_id} not found")

        cs.status = "HUMAN_REJECTED"
        cs.change_summary = (cs.change_summary or "") + f" [REJECTED: {reason}]"
        for item in cs.items:
            item.status = "REJECTED"

        db.commit()
        db.refresh(cs)
        logger.info(f"Rejected SchemeChangeSet {change_set_id}: {reason}")
        return cs

    def activate_version(
        self,
        db: Session,
        version_id: uuid.UUID,
    ) -> SchemeVersion:
        """
        Activate a verified scheme version.
        Guards:
        - If effective_date > today, stays HUMAN_VERIFIED, NOT_YET_ACTIVE until effective date.
        - If effective, sets status=ACTIVE, supersedes previous active version,
          and invalidates Day 16 RAM Rule Cache and Day 15 pgvector search metadata.
        """
        ver = db.get(SchemeVersion, version_id)
        if not ver:
            raise ValueError(f"SchemeVersion {version_id} not found")

        today = date.today()
        if ver.effective_date and ver.effective_date > today:
            ver.status = "HUMAN_VERIFIED"
            ver.is_current = False
            db.commit()
            db.refresh(ver)
            logger.info(
                f"Version v{ver.version_number} is scheduled for future effective date {ver.effective_date}. "
                "Marked HUMAN_VERIFIED, NOT_YET_ACTIVE."
            )
            return ver

        # Find currently active versions to supersede
        current_active = (
            db.execute(
                select(SchemeVersion).where(
                    SchemeVersion.scheme_id == ver.scheme_id,
                    SchemeVersion.id != ver.id,
                    SchemeVersion.status == "ACTIVE",
                )
            )
            .scalars()
            .all()
        )

        for old_v in current_active:
            old_v.status = "SUPERSEDED"
            old_v.is_current = False
            if not old_v.valid_until:
                old_v.valid_until = ver.valid_from or today

        ver.status = "ACTIVE"
        ver.is_current = True
        db.commit()
        db.refresh(ver)

        # Invalidate Day 16 RAM Rule Cache
        try:
            cache = get_rule_cache()
            cache.refresh_scheme(str(ver.scheme_id), session=None)
            logger.info(f"Invalidated Day 16 rule cache for scheme {ver.scheme_id}")
        except Exception as e:
            logger.warning(f"Could not refresh VerifiedRuleCache: {e}")

        # Invalidate Day 15 Search Index if searchable content changed
        try:
            search_meta = (
                db.execute(
                    select(SchemeSearchMetadata).where(SchemeSearchMetadata.scheme_id == str(ver.scheme_id))
                )
                .scalars()
                .first()
            )
            if search_meta:
                # Update search metadata if canonical has new descriptions or benefits
                canon = ver.canonical_data or {}
                ident = canon.get("identity") or {}
                desc = ident.get("description")
                if desc:
                    search_meta.short_description = desc
                db.commit()
                logger.info(f"Updated Day 15 search metadata for scheme {ver.scheme_id}")
        except Exception as e:
            logger.warning(f"Could not update search metadata: {e}")

        logger.info(f"Activated SchemeVersion v{ver.version_number} (id={ver.id}) for scheme {ver.scheme_id}")
        return ver
