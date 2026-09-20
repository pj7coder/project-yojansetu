import datetime
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database.models.document import Document
from app.ingestion.hashing import calculate_sha256
from app.ingestion.storage import StorageManager
from app.ingestion.validator import DocumentValidationService, DocumentValidationResult
from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger("yojansetu.ingestion.service")


class DocumentIngestionError(Exception):
    """Exception raised when document ingestion fails."""

    def __init__(
        self,
        message: str,
        errors: Optional[List[str]] = None,
        document: Optional[Document] = None,
    ):
        super().__init__(message)
        self.message = message
        self.errors = errors or [message]
        self.document = document


@dataclass
class IngestionResult:
    """Structured result returned by DocumentIngestionService."""

    document: Document
    success: bool
    errors: List[str] = field(default_factory=list)


class DocumentIngestionService:
    """
    Central unified service for ingesting Rajasthan government documents.

    All document inputs (manual upload, folder watcher, future crawler)
    MUST pass through this service to ensure consistent validation,
    deterministic storage, chunked hashing, and database tracking.
    """

    def __init__(
        self,
        validator: Optional[DocumentValidationService] = None,
        storage_manager: Optional[StorageManager] = None,
        repository: Optional[DocumentRepository] = None,
    ):
        self.validator = validator or DocumentValidationService()
        self.storage = storage_manager or StorageManager()
        self.repository = repository or DocumentRepository()

    def ingest_document(
        self,
        db: Session,
        file_path: Path,
        original_filename: str,
        ingestion_method: str = "MANUAL_UPLOAD",
        source_id: Optional[uuid.UUID] = None,
        source_url_id: Optional[uuid.UUID] = None,
        title: Optional[str] = None,
        move_file: bool = True,
    ) -> Document:
        """
        Ingest a candidate document into YojanSetu.

        :param db: Active SQLAlchemy database session.
        :param file_path: Path to the temporary or incoming document file.
        :param original_filename: Original filename from the user/crawler (preserved).
        :param ingestion_method: MANUAL_UPLOAD, FOLDER_WATCHER, WEB_MONITOR, API.
        :param source_id: Optional UUID reference to Day 3 government source.
        :param source_url_id: Optional UUID reference to source URL.
        :param title: Optional descriptive document title.
        :param move_file: Whether to move or copy the original file into storage.
        :return: Persisted Document entity.
        :raises DocumentIngestionError: If validation or persistence fails.
        """
        doc_id = uuid.uuid4()
        doc_code = self.storage.generate_document_code()
        clean_original_filename = self.storage.sanitize_filename(original_filename)

        logger.info(
            "Starting ingestion | doc_code='%s' | file='%s' | method='%s'",
            doc_code,
            clean_original_filename,
            ingestion_method,
        )

        # 1. Validation
        validation_result: DocumentValidationResult = self.validator.validate(
            file_path=file_path,
            original_filename=clean_original_filename,
        )

        if not validation_result.valid:
            error_summary = "; ".join(validation_result.errors)
            logger.warning(
                "Document validation failed | doc_code='%s' | errors='%s'",
                doc_code,
                error_summary,
            )

            # Move invalid file to storage/failed/ for audit and diagnosis
            failed_path = self.storage.store_failed(
                source_path=file_path,
                document_id=doc_id,
                original_filename=clean_original_filename,
                move=move_file,
            )
            rel_failed_path = self.storage.get_relative_path(failed_path)

            # Record failure in database
            failed_doc = Document(
                id=doc_id,
                document_code=doc_code,
                original_filename=original_filename,
                stored_filename=failed_path.name,
                file_extension=validation_result.file_extension or ".pdf",
                mime_type=validation_result.mime_type or "application/octet-stream",
                file_size_bytes=validation_result.file_size_bytes,
                storage_path=rel_failed_path,
                source_id=source_id,
                source_url_id=source_url_id,
                ingestion_method=ingestion_method.strip().upper(),
                processing_status="INVALID",
                failure_reason=error_summary,
                uploaded_at=datetime.datetime.now(datetime.timezone.utc),
            )
            try:
                self.repository.create(db, failed_doc)
            except Exception as e:
                db.rollback()
                logger.error("Failed to record invalid document in database: %s", str(e))

            raise DocumentIngestionError(
                message=f"Document validation failed: {error_summary}",
                errors=validation_result.errors,
                document=failed_doc,
            )

        # 2. SHA-256 Hash Calculation (chunked streaming)
        try:
            sha256_hash = calculate_sha256(file_path)
            logger.info("Calculated SHA-256 for %s: %s", doc_code, sha256_hash)
        except Exception as e:
            logger.error("Failed to compute SHA-256 hash for %s: %s", doc_code, str(e))
            raise DocumentIngestionError(f"Failed to calculate document checksum: {str(e)}")

        # 3. Store untouched original document/spreadsheet in storage/originals/<document_id>/original.<ext>
        stored_file_path: Optional[Path] = None
        try:
            stored_file_path = self.storage.store_original(
                source_path=file_path,
                document_id=doc_id,
                file_extension=validation_result.file_extension or ".pdf",
                move=move_file,
            )
        except Exception as e:
            logger.error("Storage operation failed for document %s: %s", doc_code, str(e))
            raise DocumentIngestionError(f"Filesystem storage error: {str(e)}")

        # Calculate relative path for database
        rel_storage_path = self.storage.get_relative_path(stored_file_path)

        # 4. Create database record with status READY_FOR_DUPLICATE_CHECK
        document_record = Document(
            id=doc_id,
            document_code=doc_code,
            original_filename=original_filename,
            stored_filename=stored_file_path.name,
            file_extension=validation_result.file_extension,
            mime_type=validation_result.mime_type,
            file_size_bytes=validation_result.file_size_bytes,
            storage_path=rel_storage_path,
            source_id=source_id,
            source_url_id=source_url_id,
            ingestion_method=ingestion_method.strip().upper(),
            processing_status="READY_FOR_DUPLICATE_CHECK",
            sha256=sha256_hash,
            title=title.strip() if title else None,
            uploaded_at=datetime.datetime.now(datetime.timezone.utc),
        )

        try:
            saved_document = self.repository.create(db, document_record)
            logger.info(
                "Document ingested successfully | code='%s' | id='%s' | status='%s'",
                saved_document.document_code,
                saved_document.id,
                saved_document.processing_status,
            )
            return saved_document
        except Exception as e:
            db.rollback()
            logger.critical(
                "Database insertion failed for stored document %s (%s). Attempting rollback cleanup: %s",
                doc_code,
                stored_file_path,
                str(e),
            )
            # Rollback file move if database insert failed to avoid orphaned records
            if stored_file_path and stored_file_path.exists():
                try:
                    self.storage.store_failed(
                        source_path=stored_file_path,
                        document_id=doc_id,
                        original_filename=clean_original_filename,
                        move=True,
                    )
                except Exception as cleanup_err:
                    logger.error("Failed to move failed document during rollback: %s", str(cleanup_err))

            raise DocumentIngestionError(f"Database insertion failed: {str(e)}")
