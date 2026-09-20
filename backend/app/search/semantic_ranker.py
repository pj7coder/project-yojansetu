import logging
from typing import Dict, List, Optional
import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.scheme_embedding import SchemeEmbedding
from app.embeddings.interface import EmbeddingProvider

logger = logging.getLogger("yojansetu.search.semantic_ranker")

_PGVECTOR_AVAILABLE_CACHE: Optional[bool] = None


def is_pgvector_available(session: Session) -> bool:
    """Checks whether the PostgreSQL vector extension is active in the database."""
    global _PGVECTOR_AVAILABLE_CACHE
    if _PGVECTOR_AVAILABLE_CACHE is not None:
        return _PGVECTOR_AVAILABLE_CACHE

    try:
        res = session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        _PGVECTOR_AVAILABLE_CACHE = bool(res)
    except Exception:
        _PGVECTOR_AVAILABLE_CACHE = False

    return _PGVECTOR_AVAILABLE_CACHE


class SemanticSchemeRanker:
    """
    Ranks pre-filtered candidate schemes by semantic similarity to citizen need text.
    Restricted strictly to the candidate set; never searches over unrelated schemes.
    Does NOT decide eligibility; produces relevance scores only.
    """

    @classmethod
    def rank_candidates(
        cls,
        session: Session,
        need_text: str,
        candidate_scheme_ids: List[str],
        embedding_provider: EmbeddingProvider,
    ) -> Dict[str, float]:
        """
        Computes cosine similarity between citizen need text and candidate scheme embeddings.
        Returns:
            Dictionary mapping scheme_id -> semantic_similarity (0.0 to 1.0).
        """
        if not candidate_scheme_ids or not need_text or not need_text.strip():
            return {}

        settings = get_settings()
        if not settings.semantic_ranking_enabled or not embedding_provider.is_available():
            logger.info("Semantic ranking skipped: provider unavailable or feature disabled")
            return {}

        # 1. Generate query embedding vector
        try:
            query_vec = embedding_provider.embed_text(need_text)
            query_np = np.array(query_vec, dtype=np.float32)
            norm_q = np.linalg.norm(query_np)
            if norm_q > 0:
                query_np = query_np / norm_q
        except Exception as e:
            logger.error(f"Failed to generate query embedding for need text: {e}")
            return {}

        # 2. Check pgvector extension availability
        use_native_pgvector = is_pgvector_available(session)

        # 3. Retrieve embeddings for candidate scheme IDs
        # To handle both native pgvector and standard fallback environments robustly:
        stmt = (
            select(
                SchemeEmbedding.scheme_id,
                SchemeEmbedding.embedding,
            )
            .where(
                SchemeEmbedding.scheme_id.in_(candidate_scheme_ids),
                SchemeEmbedding.embedding_model == embedding_provider.model_name,
            )
        )
        rows = session.execute(stmt).fetchall()

        scores: Dict[str, float] = {}
        for row in rows:
            sid = row.scheme_id
            emb = row.embedding

            if isinstance(emb, list):
                doc_np = np.array(emb, dtype=np.float32)
            else:
                try:
                    doc_np = np.array(list(emb), dtype=np.float32)
                except Exception:
                    continue

            norm_d = np.linalg.norm(doc_np)
            if norm_d > 0:
                doc_np = doc_np / norm_d

            # Cosine similarity is dot product of normalized vectors
            sim = float(np.dot(query_np, doc_np))
            # Bound within [0.0, 1.0] for clean reporting
            sim = max(0.0, min(1.0, sim))
            scores[sid] = round(sim, 4)

        return scores
