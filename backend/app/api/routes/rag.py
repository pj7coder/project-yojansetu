import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.rag.retriever import CircularDocumentRetriever
from app.database.models.document_chunk import DocumentChunk
from app.database.models.document import Document
from app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RetrievedChunkResponse,
)

logger = logging.getLogger("jansetu.api.rag")

router = APIRouter(prefix="/rag", tags=["Circular RAG & Evidence Retrieval"])


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    summary="Retrieve grounded Gazetted circular chunks",
    description="Hybrid dense vector + BM25 keyword search across official Rajasthan government circulars with citation metadata.",
)
def query_rag(
    request: RAGQueryRequest,
    session: Session = Depends(get_db),
) -> RAGQueryResponse:
    try:
        retriever = CircularDocumentRetriever()
        chunks = retriever.retrieve(
            db_session=session,
            query=request.query,
            top_k=request.top_k,
            document_code_filter=request.scheme_id,
        )

        response_chunks = [
            RetrievedChunkResponse(
                chunk_id=c.chunk_id,
                circular_id=c.document_code or c.document_id,
                title=c.chunk_title,
                page_number=c.page_start,
                text=c.text,
                score=c.relevance_score,
                citation_tag=c.citation_tag,
                metadata={
                    "document_title": c.document_title,
                    "circular_number": c.circular_number,
                    "section_type": c.section_type,
                    "page_end": c.page_end,
                },
            )
            for c in chunks
        ]

        return RAGQueryResponse(
            query=request.query,
            chunks=response_chunks,
            total_retrieved=len(response_chunks),
        )
    except Exception as e:
        logger.error(f"RAG retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG retrieval failed: {str(e)}",
        )


@router.get(
    "/chunks",
    summary="List official circular chunks for inspection",
    description="Returns list of gazetted circular chunks with page numbers and text snippets for transparent evidence auditing.",
)
def list_chunks(
    limit: int = Query(20, ge=1, le=100),
    scheme_id: Optional[str] = None,
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        query = session.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
        if scheme_id:
            query = query.filter(DocumentChunk.chunk_title.ilike(f"%{scheme_id}%"))
        
        results = query.limit(limit).all()
        chunks_data = []
        for chunk, doc in results:
            chunks_data.append({
                "chunk_id": str(chunk.id),
                "chunk_id_str": chunk.chunk_id_str,
                "document_title": doc.title,
                "document_code": getattr(doc, "document_code", None),
                "source_id": str(doc.source_id) if getattr(doc, "source_id", None) else None,
                "chunk_title": chunk.chunk_title,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "token_count": chunk.token_count,
                "section_type": chunk.section_type,
            })
        return {
            "total": len(chunks_data),
            "chunks": chunks_data,
        }
    except Exception as e:
        logger.error(f"Error listing chunks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list circular chunks: {str(e)}",
        )
