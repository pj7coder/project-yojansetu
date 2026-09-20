import datetime
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.document import Document
from app.database.models.parsed_document import ParsedDocument
from app.ingestion.storage import StorageManager
from app.parser.excel_parser import ExcelLayoutParser
from app.parser.builtin_parser import BuiltinLayoutParser
from app.parser.interface import (
    BaseParser,
    DocumentPageLimitExceededException,
    MinerUUnavailableException,
    ParserException,
    ParserExecutionException,
    ParserTimeoutException,
)
from app.parser.mineru import MinerUAdapter
from app.parser.normalizer import (
    build_normalized_document,
    write_parsed_artifacts_atomically,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository

logger = logging.getLogger("jansetu.parser.service")


class DocumentParserService:
    """
    Central orchestration service for document layout parsing.

    Takes a trusted document_id, verifies state, invokes the configured parser engine
    (Builtin/MinerU for PDFs, ExcelLayoutParser for spreadsheets),
    normalizes output into page/block schema, records diagnostics, and advances document
    lifecycle from READY_FOR_PARSING to READY_FOR_OCR_CHECK.
    """

    def __init__(
        self,
        parser: Optional[BaseParser] = None,
        doc_repo: Optional[DocumentRepository] = None,
        parsed_repo: Optional[ParsedDocumentRepository] = None,
        storage: Optional[StorageManager] = None,
    ):
        self.settings = get_settings()
        self.doc_repo = doc_repo or DocumentRepository()
        self.parsed_repo = parsed_repo or ParsedDocumentRepository()
        self.storage = storage or StorageManager()

        # Select parser engine according to configuration
        if parser:
            self.parser = parser
        elif self.settings.parser_type == "builtin":
            self.parser = BuiltinLayoutParser()
        else:
            self.parser = MinerUAdapter(fallback_enabled=self.settings.parser_fallback_enabled)

    def parse_document(
        self,
        db: Session,
        document_id: uuid.UUID,
        force: bool = False,
        **kwargs: Any,
    ) -> ParsedDocument:
        """
        Execute parsing pipeline for a single document.
        """
        doc = self.doc_repo.get_by_id(db, document_id)
        if not doc:
            raise ValueError(f"Document with ID {document_id} does not exist.")

        # If already parsed and not forced, return existing parsed record
        if doc.processing_status in ["READY_FOR_OCR_CHECK", "PARSED"] and not force:
            existing = self.parsed_repo.get_latest_by_document_id(db, document_id)
            if existing:
                logger.info("Document %s already parsed; returning existing record", doc.document_code)
                return existing

        # Validate lifecycle state
        valid_initial_states = ["READY_FOR_PARSING", "PARSING_FAILED"]
        if force:
            valid_initial_states.extend(["READY_FOR_OCR_CHECK", "PARSED"])

        if doc.processing_status not in valid_initial_states:
            raise ValueError(
                f"Document {doc.document_code} is in status '{doc.processing_status}'. "
                f"Only documents in {valid_initial_states} can be parsed."
            )

        # Resolve trusted original file path
        resolved_file = self.storage.resolve_storage_path(doc.storage_path)
        if not resolved_file or not resolved_file.exists():
            error_reason = f"Original document file missing at storage path: {doc.storage_path}"
            logger.error(error_reason)
            doc.processing_status = "PARSING_FAILED"
            doc.failure_reason = error_reason
            db.commit()
            raise FileNotFoundError(error_reason)

        started_at = datetime.datetime.now(datetime.timezone.utc)
        doc.processing_status = "PARSING"
        doc.failure_reason = None
        db.commit()

        logger.info("Commencing layout parsing for %s (%s)", doc.document_code, doc.original_filename)

        # Define destination paths
        doc_parsed_dir = self.settings.parsed_dir / str(doc.id)
        raw_output_dir = doc_parsed_dir / "mineru_raw"
        relative_output_path = f"storage/parsed/{doc.id}"

        try:
            # Route to ExcelLayoutParser if the document is an Excel or CSV spreadsheet
            ext = resolved_file.suffix.lower()
            if ext in [".xlsx", ".xls", ".csv"]:
                active_parser = ExcelLayoutParser()
            else:
                active_parser = self.parser

            # 1. Execute layout parser
            raw_result = active_parser.parse(
                file_path=resolved_file,
                raw_output_dir=raw_output_dir,
                max_pages=self.settings.max_parse_pages,
                timeout_seconds=self.settings.parser_timeout_seconds,
                device=self.settings.parser_device,
                **kwargs,
            )

            # 2. Transform into canonical JanSetu schema
            normalized_doc = build_normalized_document(
                document_id=doc.id,
                raw_result=raw_result,
            )

            # 3. Write atomic artifacts (document.json, document.md)
            json_path, artifact_sha256 = write_parsed_artifacts_atomically(
                output_dir=doc_parsed_dir,
                normalized_doc=normalized_doc,
            )

            completed_at = datetime.datetime.now(datetime.timezone.utc)
            diagnostics = normalized_doc["diagnostics"]

            # 4. Record ParsedDocument metadata in database
            parsed_record = ParsedDocument(
                document_id=doc.id,
                parser_name=raw_result.parser_name,
                parser_version=raw_result.parser_version,
                parse_status="PARSED",
                page_count=normalized_doc["page_count"],
                pages_with_text=diagnostics["pages_with_text"],
                pages_without_text=diagnostics["pages_without_text"],
                pages_low_text=diagnostics["pages_low_text"],
                total_text_characters=diagnostics["total_text_characters"],
                total_blocks=diagnostics["total_blocks"],
                total_tables=diagnostics["total_tables"],
                output_path=relative_output_path,
                artifact_sha256=artifact_sha256,
                duration_ms=raw_result.duration_ms,
                started_at=started_at,
                completed_at=completed_at,
            )
            self.parsed_repo.create(db, parsed_record)

            # 5. Advance document status to READY_FOR_OCR_CHECK
            doc.processing_status = "READY_FOR_OCR_CHECK"
            doc.page_count = normalized_doc["page_count"]
            db.commit()

            logger.info(
                "Successfully parsed %s | %d pages (%d with text, %d without) -> READY_FOR_OCR_CHECK",
                doc.document_code,
                normalized_doc["page_count"],
                diagnostics["pages_with_text"],
                diagnostics["pages_without_text"],
            )
            return parsed_record

        except DocumentPageLimitExceededException as e:
            error_msg = f"Document page count ({e.page_count}) exceeds limit ({e.max_pages})"
            logger.warning("Large document detected: %s (%s)", doc.document_code, error_msg)
            doc.processing_status = "REQUIRES_MANUAL_REVIEW"
            doc.failure_reason = error_msg
            db.commit()
            raise

        except ParserTimeoutException as e:
            error_msg = f"PARSER_TIMEOUT: {e}"
            logger.error("Timeout parsing %s: %s", doc.document_code, error_msg)
            self._handle_parse_failure(db, doc, error_msg, started_at, relative_output_path)
            raise

        except MinerUUnavailableException as e:
            error_msg = f"MINERU_UNAVAILABLE: {e}"
            logger.error("MinerU unavailable for %s: %s", doc.document_code, error_msg)
            self._handle_parse_failure(db, doc, error_msg, started_at, relative_output_path)
            raise

        except Exception as e:
            error_msg = f"PARSING_FAILED: {e}"
            logger.error("Error parsing %s: %s", doc.document_code, error_msg, exc_info=True)
            self._handle_parse_failure(db, doc, error_msg, started_at, relative_output_path)
            raise

    def _handle_parse_failure(
        self,
        db: Session,
        doc: Document,
        error_msg: str,
        started_at: datetime.datetime,
        relative_output_path: str,
    ) -> ParsedDocument:
        """Record failure state safely without losing document provenance."""
        completed_at = datetime.datetime.now(datetime.timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        doc.processing_status = "PARSING_FAILED"
        doc.failure_reason = error_msg
        db.commit()

        failed_record = ParsedDocument(
            document_id=doc.id,
            parser_name=self.parser.name,
            parser_version=self.parser.version,
            parse_status="PARSING_FAILED",
            page_count=0,
            pages_with_text=0,
            pages_without_text=0,
            pages_low_text=0,
            total_text_characters=0,
            total_blocks=0,
            total_tables=0,
            output_path=relative_output_path,
            duration_ms=duration_ms,
            failure_reason=error_msg,
            started_at=started_at,
            completed_at=completed_at,
        )
        return self.parsed_repo.create(db, failed_record)

    def reparse_document(
        self,
        db: Session,
        document_id: uuid.UUID,
        force: bool = True,
    ) -> ParsedDocument:
        """Reparse an existing document (e.g. after parser version upgrade or admin request)."""
        logger.info("Reparsing document: %s", document_id)
        return self.parse_document(db, document_id, force=force)

    def reset_stale_parsing_tasks(
        self,
        db: Session,
        timeout_minutes: int = 15,
    ) -> int:
        """Reset jobs stuck in 'PARSING' state past timeout threshold to READY_FOR_PARSING."""
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=timeout_minutes)
        stale_docs = db.execute(
            select(Document).where(
                Document.processing_status == "PARSING",
                Document.updated_at <= cutoff,
            )
        ).scalars().all()

        count = len(stale_docs)
        for doc in stale_docs:
            logger.warning("Resetting stale PARSING document: %s (stuck since %s)", doc.document_code, doc.updated_at)
            doc.processing_status = "READY_FOR_PARSING"
            doc.failure_reason = f"Reset after worker timeout ({timeout_minutes}m in PARSING state)"

        if count > 0:
            db.commit()
        return count

    def get_parsed_artifact(self, document_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Read normalized document.json from storage."""
        json_path = self.settings.parsed_dir / str(document_id) / "document.json"
        if not json_path.exists():
            return None
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load parsed artifact for %s: %s", document_id, e)
            return None

    def get_page_blocks(self, document_id: uuid.UUID, page_number: int) -> Optional[Dict[str, Any]]:
        """Fetch normalized blocks for a single 1-based physical page."""
        artifact = self.get_parsed_artifact(document_id)
        if not artifact:
            return None

        pages = artifact.get("pages", [])
        for p in pages:
            if p.get("page_number") == page_number:
                return p
        return None
