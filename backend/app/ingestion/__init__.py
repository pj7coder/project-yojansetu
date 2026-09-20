"""JanSetu Document Ingestion Subsystem.

Unified pipeline for government document ingestion, validation, hashing, storage,
and automatic folder monitoring.
"""
from app.ingestion.hashing import calculate_sha256
from app.ingestion.validator import DocumentValidationService, DocumentValidationResult
from app.ingestion.storage import StorageManager
from app.ingestion.service import DocumentIngestionService, IngestionResult

__all__ = [
    "calculate_sha256",
    "DocumentValidationService",
    "DocumentValidationResult",
    "StorageManager",
    "DocumentIngestionService",
    "IngestionResult",
]
