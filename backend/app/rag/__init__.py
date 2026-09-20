"""
JanSetu Document RAG (Retrieval-Augmented Generation) Module.
Provides grounded, verifiable retrieval over Rajasthan official gazetted circulars and scheme guidelines.
"""
from app.rag.retriever import CircularDocumentRetriever, RetrievedChunk

__all__ = ["CircularDocumentRetriever", "RetrievedChunk"]
