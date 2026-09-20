from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.scheme_embedding import SchemeEmbedding
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.embeddings.interface import EmbeddingProvider
from app.embeddings.local_provider import LocalFastEmbedProvider
from app.search.metadata_builder import SearchMetadataBuilder
from app.search.semantic_ranker import is_pgvector_available

logger = logging.getLogger("jansetu.search.indexer")


class SchemeSearchIndexService:
    """
    Maintains derived search metadata and dense vector embeddings for verified schemes.
    Performs stale embedding detection using SHA-256 hashes and batch embedding updates.
    """

    @classmethod
    def index_verified_scheme(
        cls,
        session: Session,
        raw_verified_data: Dict[str, Any],
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> SchemeSearchMetadata:
        """
        Indexes a single verified scheme into SchemeSearchMetadata and SchemeEmbedding.
        Idempotent: updates existing records if hash changed; skips embedding if identical.
        """
        provider = embedding_provider or LocalFastEmbedProvider()
        settings = get_settings()

        # 1. Build metadata record
        meta = SearchMetadataBuilder.build_metadata(raw_verified_data)

        # 2. Check existing search metadata in DB
        existing_meta = session.execute(
            select(SchemeSearchMetadata).where(SchemeSearchMetadata.scheme_id == meta.scheme_id)
        ).scalar_one_or_none()

        if existing_meta:
            existing_meta.scheme_name = meta.scheme_name
            existing_meta.scheme_name_hi = meta.scheme_name_hi
            existing_meta.state = meta.state
            existing_meta.districts = meta.districts
            existing_meta.rural_urban = meta.rural_urban
            existing_meta.scheme_origin = meta.scheme_origin
            existing_meta.category = meta.category
            existing_meta.beneficiary_tags = meta.beneficiary_tags
            existing_meta.occupation_tags = meta.occupation_tags
            existing_meta.valid_from = meta.valid_from
            existing_meta.valid_until = meta.valid_until
            existing_meta.is_active = meta.is_active
            existing_meta.is_verified = meta.is_verified
            existing_meta.search_text = meta.search_text
            existing_meta.search_text_hash = meta.search_text_hash
            meta_record = existing_meta
        else:
            session.add(meta)
            meta_record = meta

        session.flush()

        # 3. Check existing embedding in DB
        existing_emb = session.execute(
            select(SchemeEmbedding).where(
                SchemeEmbedding.scheme_id == meta.scheme_id,
                SchemeEmbedding.embedding_model == provider.model_name,
            )
        ).scalar_one_or_none()

        # Generate embedding if missing or if search text hash changed
        if not existing_emb or existing_emb.search_text_hash != meta.search_text_hash:
            if provider.is_available():
                try:
                    vec = provider.embed_text(meta.search_text)
                    if existing_emb:
                        existing_emb.embedding = vec
                        existing_emb.search_text_hash = meta.search_text_hash
                        existing_emb.embedding_version = settings.search_index_version
                    else:
                        new_emb = SchemeEmbedding(
                            scheme_id=meta.scheme_id,
                            embedding_model=provider.model_name,
                            embedding_version=settings.search_index_version,
                            search_text_hash=meta.search_text_hash,
                            embedding=vec,
                        )
                        session.add(new_emb)
                    session.flush()
                    logger.info(f"Generated embedding for scheme '{meta.scheme_id}'")
                except Exception as e:
                    logger.error(f"Failed to generate embedding for '{meta.scheme_id}': {e}")
            else:
                logger.warning(f"Embedding provider unavailable; embedding deferred for '{meta.scheme_id}'")

        session.commit()
        return meta_record

    @classmethod
    def rebuild_index(
        cls,
        session: Session,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> Dict[str, int]:
        """
        Scans storage/verified/ directory and HUMAN_VERIFIED SchemeDrafts,
        rebuilding search metadata and missing/stale vector embeddings.
        """
        provider = embedding_provider or LocalFastEmbedProvider()
        settings = get_settings()
        indexed_count = 0
        embeddings_generated = 0

        # 1. Scan filesystem verified directories
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        verified_scan_dirs = [settings.verified_dir, repo_root / "storage" / "verified"]
        seen_paths = set()

        for vdir in verified_scan_dirs:
            if vdir.exists():
                for child in vdir.iterdir():
                    if child.is_dir():
                        artifact_file = child / "verified_scheme.json"
                        if artifact_file.exists():
                            resolved_str = str(artifact_file.resolve())
                            if resolved_str not in seen_paths:
                                seen_paths.add(resolved_str)
                                try:
                                    with open(artifact_file, "r", encoding="utf-8") as f:
                                        data = json.load(f)
                                    cls.index_verified_scheme(session, data, provider)
                                    indexed_count += 1
                                except Exception as e:
                                    logger.error(f"Error indexing verified artifact at {artifact_file}: {e}")

        # 2. Query DB SchemeDraft records with status == 'HUMAN_VERIFIED'
        stmt = select(SchemeDraft).where(SchemeDraft.status == "HUMAN_VERIFIED")
        verified_drafts = session.execute(stmt).scalars().all()
        for draft in verified_drafts:
            for vdir in verified_scan_dirs:
                verified_file = vdir / str(draft.id) / "verified_scheme.json"
                if verified_file.exists():
                    resolved_str = str(verified_file.resolve())
                    if resolved_str not in seen_paths:
                        seen_paths.add(resolved_str)
                        try:
                            with open(verified_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            cls.index_verified_scheme(session, data, provider)
                            indexed_count += 1
                        except Exception as e:
                            logger.error(f"Error indexing draft {draft.id}: {e}")

        return {
            "indexed_count": indexed_count,
        }

    @classmethod
    def get_index_status(cls, session: Session) -> Dict[str, Any]:
        """Returns diagnostic counts and health of the search index."""
        settings = get_settings()

        verified_count = session.execute(
            select(func.count()).select_from(SchemeDraft).where(SchemeDraft.status == "HUMAN_VERIFIED")
        ).scalar() or 0

        meta_count = session.execute(
            select(func.count()).select_from(SchemeSearchMetadata)
        ).scalar() or 0

        emb_count = session.execute(
            select(func.count()).select_from(SchemeEmbedding)
        ).scalar() or 0

        # Stale embeddings check: metadata hash != embedding hash
        stale_stmt = (
            select(func.count())
            .select_from(SchemeSearchMetadata)
            .join(
                SchemeEmbedding,
                SchemeSearchMetadata.scheme_id == SchemeEmbedding.scheme_id,
            )
            .where(
                SchemeSearchMetadata.search_text_hash != SchemeEmbedding.search_text_hash
            )
        )
        stale_count = session.execute(stale_stmt).scalar() or 0

        pgv_available = is_pgvector_available(session)

        return {
            "verified_schemes_count": verified_count,
            "search_metadata_count": meta_count,
            "embeddings_count": emb_count,
            "stale_embeddings_count": stale_count,
            "embedding_model": settings.embedding_model_name,
            "embedding_dimension": settings.embedding_dimension,
            "pgvector_available": pgv_available,
        }
