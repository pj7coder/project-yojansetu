from datetime import datetime, timezone, timedelta
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminSystemStatusResponse,
    DatabaseHealth,
    OllamaHealth,
    RuleCacheHealth,
    SearchIndexHealth,
    StorageCountItem,
    WorkerHeartbeatItem,
)
from app.cache.verified_rule_cache import get_rule_cache
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.ocr_run import OCRRun
from app.database.models.parsed_document import ParsedDocument
from app.database.models.scheme_draft import SchemeDraft
from app.database.models.web_content_artifact import WebContentArtifact
from app.database.models.worker_heartbeat import WorkerHeartbeat
from app.database.session import engine
from app.llm.ollama import OllamaProvider
from app.search.indexer import SchemeSearchIndexService

logger = logging.getLogger("yojansetu.admin.system_health")


class AdminSystemHealthService:
    """Operations service providing multi-component operational health, cache, search index, and worker heartbeats."""

    WORKER_STALE_SECONDS = 120
    _cached_tts_info: Optional[Dict[str, Any]] = None
    _cached_tts_ts: float = 0.0

    def get_system_status(self, db: Session) -> AdminSystemStatusResponse:
        now = datetime.now(timezone.utc)
        overall_status = "HEALTHY"

        # 1. Database Health
        db_status = "HEALTHY"
        latency_ms: Optional[float] = None
        try:
            start_t = time.perf_counter()
            db.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        except Exception as e:
            logger.error(f"Database health probe failed: {e}")
            db_status = "UNAVAILABLE"
            overall_status = "CRITICAL"

        pool = engine.pool
        pool_size = getattr(pool, "size", lambda: 10)()
        overflow = getattr(pool, "overflow", lambda: 0)()

        database_health = DatabaseHealth(
            status=db_status,
            pool_size=pool_size,
            overflow=overflow,
            latency_ms=latency_ms,
        )

        # 2. Ollama LLM Health
        ollama_status = "HEALTHY"
        model_available = False
        model_name = "llama3.2:3b"
        provider_name = "ollama"

        try:
            ollama_prov = OllamaProvider()
            health_dict = ollama_prov.check_health()
            ollama_status = "HEALTHY" if health_dict.get("status") == "ok" else "UNAVAILABLE"
            model_available = bool(health_dict.get("model_available", False))
            model_name = health_dict.get("model", model_name)
            provider_name = health_dict.get("provider", provider_name)
            if ollama_status != "HEALTHY" and overall_status != "CRITICAL":
                overall_status = "WARNING"
        except Exception as e:
            logger.warning(f"Ollama health probe error: {e}")
            ollama_status = "UNAVAILABLE"
            if overall_status != "CRITICAL":
                overall_status = "WARNING"

        ollama_health = OllamaHealth(
            status=ollama_status,
            model=model_name,
            model_available=model_available,
            provider=provider_name,
        )

        # 3. Search Index & pgvector Health
        search_status = "HEALTHY"
        try:
            idx_dict = SchemeSearchIndexService.get_index_status(db)
            verified_count = idx_dict.get("verified_schemes_count", 0)
            meta_count = idx_dict.get("search_metadata_count", 0)
            emb_count = idx_dict.get("embeddings_count", 0)
            stale_count = idx_dict.get("stale_embeddings_count", 0)
            emb_model = idx_dict.get("embedding_model", "paraphrase-multilingual-MiniLM-L12-v2")
            pgv_avail = bool(idx_dict.get("pgvector_available", False))

            if not pgv_avail:
                search_status = "DEGRADED"
                if overall_status != "CRITICAL":
                    overall_status = "WARNING"
            elif stale_count > 0:
                search_status = "WARNING"
                if overall_status != "CRITICAL":
                    overall_status = "WARNING"
        except Exception as e:
            logger.error(f"Search index status probe error: {e}")
            search_status = "UNAVAILABLE"
            verified_count = 0
            meta_count = 0
            emb_count = 0
            stale_count = 0
            emb_model = "unknown"
            pgv_avail = False
            if overall_status != "CRITICAL":
                overall_status = "WARNING"

        search_index_health = SearchIndexHealth(
            status=search_status,
            verified_schemes_count=verified_count,
            search_metadata_count=meta_count,
            embeddings_count=emb_count,
            stale_embeddings_count=stale_count,
            embedding_model=emb_model,
            pgvector_available=pgv_avail,
        )

        # 4. Verified Rule Cache Health
        cache = get_rule_cache()
        c_dict = cache.get_metrics_dict()
        c_entries = c_dict["entries"]
        c_status = "HEALTHY" if c_entries > 0 else "EMPTY"

        rule_cache_health = RuleCacheHealth(
            status=c_status,
            entries=c_entries,
            hits=c_dict["hits"],
            misses=c_dict["misses"],
            compile_failures=c_dict["compile_failures"],
            refreshes=c_dict["refreshes"],
        )

        # 5. Worker Heartbeats
        worker_items: List[WorkerHeartbeatItem] = []
        try:
            heartbeats = db.execute(
                select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc())
            ).scalars().all()

            for wh in heartbeats:
                age_s = (now - wh.last_seen_at).total_seconds()
                is_stale = age_s > self.WORKER_STALE_SECONDS
                w_status = wh.status
                if is_stale and w_status != "STOPPED":
                    w_status = "STALE"
                    if overall_status != "CRITICAL":
                        overall_status = "WARNING"

                worker_items.append(
                    WorkerHeartbeatItem(
                        worker_type=wh.worker_type,
                        worker_instance_id=wh.worker_instance_id,
                        last_seen_at=wh.last_seen_at.isoformat(),
                        status=w_status,
                        is_stale=is_stale,
                        metadata_safe=wh.metadata_safe or {},
                    )
                )
        except Exception as e:
            logger.warning(f"Worker heartbeat check error: {e}")

        # 6. Storage Summary Counts
        orig_docs = db.scalar(select(func.count()).select_from(Document)) or 0
        parsed_docs = db.scalar(select(func.count()).select_from(ParsedDocument)) or 0
        ocr_runs = db.scalar(select(func.count()).select_from(OCRRun)) or 0
        doc_chunks = db.scalar(select(func.count()).select_from(DocumentChunk)) or 0
        scheme_drafts = db.scalar(select(func.count()).select_from(SchemeDraft)) or 0
        source_snapshots = db.scalar(select(func.count()).select_from(WebContentArtifact)) or 0
        verified_artifacts = db.scalar(
            select(func.count()).select_from(SchemeDraft).where(SchemeDraft.status == "HUMAN_VERIFIED")
        ) or 0

        storage_counts = StorageCountItem(
            original_documents=orig_docs,
            parsed_documents=parsed_docs,
            ocr_runs=ocr_runs,
            document_chunks=doc_chunks,
            scheme_drafts=scheme_drafts,
            source_snapshots=source_snapshots,
            verified_scheme_artifacts=verified_artifacts,
        )

        # 6. TTS Health (Cached for 60 seconds to prevent blocking requests)
        tts_info = None
        current_time = time.time()
        if (
            AdminSystemHealthService._cached_tts_info is not None
            and (current_time - AdminSystemHealthService._cached_tts_ts) < 60.0
        ):
            tts_info = AdminSystemHealthService._cached_tts_info
        else:
            try:
                from app.tts.service import get_speech_synthesis_service
                tts_info = get_speech_synthesis_service().get_status()
                AdminSystemHealthService._cached_tts_info = tts_info
                AdminSystemHealthService._cached_tts_ts = current_time
            except Exception as e:
                logger.warning(f"Could not retrieve TTS health: {e}")

        return AdminSystemStatusResponse(
            overall_status=overall_status,
            database=database_health,
            ollama=ollama_health,
            search_index=search_index_health,
            rule_cache=rule_cache_health,
            workers=worker_items,
            storage=storage_counts,
            tts=tts_info,
            generated_at=now.isoformat(),
        )

    def register_heartbeat(
        self,
        db: Session,
        worker_type: str,
        worker_instance_id: str,
        status_val: str = "HEALTHY",
        metadata_safe: Optional[Dict[str, Any]] = None,
    ) -> WorkerHeartbeat:
        now = datetime.now(timezone.utc)
        hb = db.execute(
            select(WorkerHeartbeat).where(
                and_(
                    WorkerHeartbeat.worker_type == worker_type,
                    WorkerHeartbeat.worker_instance_id == worker_instance_id,
                )
            )
        ).scalar_one_or_none()

        if hb:
            hb.last_seen_at = now
            hb.status = status_val
            hb.metadata_safe = metadata_safe or {}
        else:
            hb = WorkerHeartbeat(
                worker_type=worker_type,
                worker_instance_id=worker_instance_id,
                last_seen_at=now,
                status=status_val,
                metadata_safe=metadata_safe or {},
            )
            db.add(hb)

        db.commit()
        db.refresh(hb)
        return hb
