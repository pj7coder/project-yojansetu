"""
Core Circular Document Retriever for Grounded RAG.
Wires PDF/chunk loaders, FastEmbed dense vector representations, BM25 keyword matching,
and verifiable citation generation to ensure 100% grounded, traceable responses.
"""

from dataclasses import dataclass
import json
import logging
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.embeddings.interface import EmbeddingProvider
from app.embeddings.local_provider import LocalFastEmbedProvider

logger = logging.getLogger("yojansetu.rag.retriever")


@dataclass
class RetrievedChunk:
    """Structure representing a retrieved document chunk with full citation metadata."""
    chunk_id: str
    document_id: str
    document_code: str
    document_title: str
    circular_number: Optional[str]
    section_type: str
    chunk_title: str
    page_start: int
    page_end: int
    text: str
    relevance_score: float
    citation_tag: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_code": self.document_code,
            "document_title": self.document_title,
            "circular_number": self.circular_number,
            "section_type": self.section_type,
            "chunk_title": self.chunk_title,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "text": self.text,
            "relevance_score": round(self.relevance_score, 4),
            "citation_tag": self.citation_tag,
        }


class CircularDocumentRetriever:
    """
    Production-grade hybrid retriever combining dense semantic similarity
    and BM25 keyword matching across Rajasthan government circular chunks.
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        self.provider = embedding_provider or LocalFastEmbedProvider()
        self.settings = get_settings()

    def _read_chunk_text(self, chunk: DocumentChunk, base_dir: Path) -> str:
        """Safely reads rendered chunk text from filesystem or fallback."""
        if chunk.artifact_path:
            full_path = (base_dir / chunk.artifact_path).resolve()
            if full_path.exists() and full_path.is_file():
                try:
                    return full_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning("Failed to read chunk artifact at %s: %s", full_path, e)

        # Fallback to master chunks.json
        master_json = Path(self.settings.chunks_dir) / str(chunk.document_id) / "chunks.json"
        if master_json.exists():
            try:
                data = json.loads(master_json.read_text(encoding="utf-8"))
                for item in data.get("chunks", []):
                    if item.get("chunk_id") == chunk.chunk_id_str or item.get("chunk_index") == chunk.chunk_index:
                        return item.get("text", "")
            except Exception as e:
                logger.warning("Failed to read chunks.json for %s: %s", chunk.document_id, e)

        return chunk.chunk_title or ""

    def _tokenize(self, text: str) -> List[str]:
        """Simple bilingual tokenizer for Hindi & English."""
        cleaned = re.sub(r"[^\w\s\u0900-\u097F]", " ", text.lower())
        tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 1]
        return tokens

    def _compute_bm25_score(self, query_tokens: List[str], doc_tokens: List[str], avg_doc_len: float) -> float:
        """Calculates lightweight BM25 lexical match score."""
        if not query_tokens or not doc_tokens:
            return 0.0

        k1 = 1.5
        b = 0.75
        doc_len = len(doc_tokens)
        score = 0.0

        doc_token_counts: Dict[str, int] = {}
        for t in doc_tokens:
            doc_token_counts[t] = doc_token_counts.get(t, 0) + 1

        for q in query_tokens:
            count = doc_token_counts.get(q, 0)
            if count > 0:
                tf = (count * (k1 + 1)) / (count + k1 * (1 - b + b * (doc_len / (avg_doc_len or 1.0))))
                score += tf

        return score

    def retrieve(
        self,
        db_session: Session,
        query: str,
        top_k: int = 4,
        section_filter: Optional[str] = None,
        document_code_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieves top_k most relevant chunks for a user query.
        Returns verifiable chunks with page numbers and citations.
        """
        if not query or not query.strip():
            return []

        base_dir = Path(self.settings.base_dir).resolve()

        # 1. Fetch chunks with associated document
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.artifact_path.isnot(None))
        )

        if section_filter:
            stmt = stmt.where(DocumentChunk.section_type == section_filter.upper())
        if document_code_filter:
            stmt = stmt.where(Document.document_code.ilike(f"%{document_code_filter}%"))

        rows = db_session.execute(stmt).all()
        if not rows:
            return []

        query_tokens = self._tokenize(query)

        # 2. Extract texts and metadata
        chunk_items = []
        doc_tokens_list = []
        texts_for_embedding = []

        for chunk, doc in rows:
            text = self._read_chunk_text(chunk, base_dir)
            tokens = self._tokenize(text)
            doc_tokens_list.append(tokens)
            texts_for_embedding.append(text)
            chunk_items.append((chunk, doc, text, tokens))

        avg_doc_len = sum(len(toks) for toks in doc_tokens_list) / max(1, len(doc_tokens_list))

        # 3. Dense vector embeddings (if provider available)
        dense_scores: List[float] = [0.0] * len(chunk_items)
        if self.provider and self.provider.is_available():
            try:
                q_emb = self.provider.embed_text(query)
                c_embs = self.provider.embed_batch([t[:512] for t in texts_for_embedding])

                for i, c_emb in enumerate(c_embs):
                    # Cosine similarity of normalized vectors is dot product
                    dot_product = sum(a * b for a, b in zip(q_emb, c_emb))
                    dense_scores[i] = max(0.0, float(dot_product))
            except Exception as e:
                logger.warning("Dense embedding failed during RAG retrieve: %s. Falling back to BM25.", e)

        # 4. Hybrid Scoring: 60% Dense Semantic + 40% BM25 Lexical
        scored_results: List[RetrievedChunk] = []

        max_bm25 = 1.0
        bm25_scores = [
            self._compute_bm25_score(query_tokens, tokens, avg_doc_len)
            for _, _, _, tokens in chunk_items
        ]
        if bm25_scores:
            max_bm25 = max(max(bm25_scores), 1.0)

        for i, (chunk, doc, text, _) in enumerate(chunk_items):
            bm25_norm = bm25_scores[i] / max_bm25
            dense_norm = dense_scores[i]

            if any(dense_scores):
                hybrid_score = 0.65 * dense_norm + 0.35 * bm25_norm
            else:
                hybrid_score = bm25_norm

            # Build Citation Tag: e.g. [Circular: F.1(3)/PENS/2023, Page 2]
            circular_str = doc.title or doc.original_filename
            citation_tag = f"[Circular: {circular_str}, Page: {chunk.page_start}]"

            scored_results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id_str,
                    document_id=str(doc.id),
                    document_code=doc.document_code,
                    document_title=doc.title or doc.original_filename,
                    circular_number=doc.document_code,
                    section_type=chunk.section_type,
                    chunk_title=chunk.chunk_title or f"Section {chunk.section_type}",
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=text,
                    relevance_score=hybrid_score,
                    citation_tag=citation_tag,
                )
            )

        # 5. Sort by relevance score descending
        scored_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_results[:top_k]

    @classmethod
    def format_context_for_prompt(cls, chunks: List[RetrievedChunk]) -> str:
        """Formats retrieved chunks into clean traceable prompt context."""
        if not chunks:
            return "No relevant circular documents retrieved."

        lines = ["=== OFFICIAL RAJASTHAN GOVERNMENT CIRCULAR EXCERPTS ==="]
        for i, chk in enumerate(chunks, 1):
            lines.append(f"\n--- SOURCE [{i}]: {chk.citation_tag} ---")
            lines.append(f"Topic: {chk.chunk_title} | Section: {chk.section_type}")
            lines.append(f"Verbatim Content:\n{chk.text}")
        lines.append("\n=== END OF OFFICIAL EXCERPTS ===")
        return "\n".join(lines)
