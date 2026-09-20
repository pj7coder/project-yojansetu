from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    query: str = Field(..., description="Query string for semantic + lexical retrieval against Gazetted circulars")
    top_k: int = Field(5, ge=1, le=20, description="Max chunks to return")
    scheme_id: Optional[str] = Field(None, description="Optional scheme ID filter")


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    circular_id: str
    title: str
    page_number: int
    text: str
    score: float
    citation_tag: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryResponse(BaseModel):
    query: str
    chunks: List[RetrievedChunkResponse]
    total_retrieved: int
