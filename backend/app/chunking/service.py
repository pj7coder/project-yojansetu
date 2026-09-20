from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from app.chunking.formatter import ChunkFormatter
from app.chunking.section_patterns import SectionType
from app.chunking.splitter import SemanticSplitter
from app.chunking.validator import ChunkValidationError, ChunkValidator, ValidationReport
from app.core.config import settings
from app.database.models.document import Document
from app.database.models.document_chunk import DocumentChunk
from app.database.models.ocr_run import OCRRun
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.ocr_repository import OCRRunRepository

logger = logging.getLogger("jansetu.chunking.service")


class DocumentChunkingService:
    """
    Orchestrates deterministic semantic document chunking for government scheme documents.

    Workflow:
    1. Resolve canonical structured source (OCR-merged or MinerU-parsed).
    2. Group structured blocks into logical, heading-aware sections.
    3. Enforce token controls (~4000-6000 target, 8000 max, 300 min) while bonding provisos and tables.
    4. Validate complete block coverage (unassigned_blocks == 0), page bounds, and continuity.
    5. Write chunk artifacts to storage/chunks/<document_id>/ and persist DocumentChunk metadata to DB.
    6. Transition document lifecycle status to READY_FOR_EXTRACTION.
    """

    def __init__(
        self,
        chunk_repo: Optional[DocumentChunkRepository] = None,
        doc_repo: Optional[DocumentRepository] = None,
        ocr_repo: Optional[OCRRunRepository] = None,
    ):
        self.chunk_repo = chunk_repo or DocumentChunkRepository()
        self.doc_repo = doc_repo or DocumentRepository()
        self.ocr_repo = ocr_repo or OCRRunRepository()
        self.splitter = SemanticSplitter(
            target_tokens=settings.chunk_target_tokens,
            max_tokens=settings.chunk_max_tokens,
            min_tokens=settings.chunk_min_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )

    def resolve_source_path(self, db: Session, document: Document) -> Path:
        """
        Determine the canonical structured document JSON for chunking.
        Prefers merged OCR output if OCR was executed, otherwise MinerU parsed JSON.
        """
        # 1. Check OCRRun repository for latest chunking_source_path
        latest_ocr = self.ocr_repo.get_latest_by_document_id(db, document.id)
        if latest_ocr and latest_ocr.chunking_source_path:
            cand = Path(latest_ocr.chunking_source_path)
            if not cand.is_absolute():
                cand = Path(settings.base_dir) / cand
            if cand.exists():
                logger.info("Found OCRRun chunking source path: %s", cand)
                return cand

        doc_id_str = str(document.id)

        # 2. Check storage/ocr/<doc_id>/merged_document.json
        ocr_merged = Path(settings.ocr_storage_dir) / doc_id_str / "merged_document.json"
        if ocr_merged.exists():
            logger.info("Found merged OCR document at: %s", ocr_merged)
            return ocr_merged

        # 3. Check storage/parsed/<doc_id>/document.json
        parsed_path = Path(settings.parsed_storage_dir) / doc_id_str / "document.json"
        if parsed_path.exists():
            logger.info("Found parsed MinerU document at: %s", parsed_path)
            return parsed_path

        # 4. Check document.parsed_metadata
        if document.parsed_metadata and isinstance(document.parsed_metadata, dict):
            out_path = document.parsed_metadata.get("output_path")
            if out_path:
                cand = Path(out_path)
                if not cand.is_absolute():
                    cand = Path(settings.base_dir) / cand
                if cand.exists():
                    return cand

        raise FileNotFoundError(
            f"No valid structured source document found for document {document.id} in storage/ocr or storage/parsed"
        )

    def chunk_document(
        self,
        db: Session,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform semantic chunking on a document in READY_FOR_CHUNKING status.

        Args:
            db: Database session
            document_id: UUID of document to chunk
            force: If True, allow re-chunking documents already CHUNKED or READY_FOR_EXTRACTION

        Returns:
            Dict summary of generated chunks and validation diagnostics
        """
        document = self.doc_repo.get_by_id(db, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        current_status = document.processing_status
        allowed_statuses = ["READY_FOR_CHUNKING", "CHUNKING"]  # CHUNKING = transient state from a prior crashed run
        if force:
            allowed_statuses.extend(["READY_FOR_EXTRACTION", "CHUNKING_FAILED", "CHUNKED"])

        if current_status not in allowed_statuses:
            raise ValueError(
                f"Document {document_id} status is '{current_status}'. Expected one of {allowed_statuses}."
            )

        logger.info("Starting semantic document chunking for document %s (status: %s)", document_id, current_status)
        document.processing_status = "CHUNKING"
        db.commit()

        try:
            # 1. Resolve structured source artifact
            source_file = self.resolve_source_path(db, document)
            with open(source_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            pages = doc_data.get("pages", [])
            all_blocks: List[Dict[str, Any]] = []
            for p in pages:
                all_blocks.extend(p.get("blocks", []))

            if not all_blocks:
                raise ChunkValidationError(f"Document {document_id} has 0 blocks to chunk.")

            # 2. Build candidate chunks
            candidate_chunks = self.splitter.build_chunks(str(document_id), pages)
            if not candidate_chunks:
                raise ChunkValidationError(f"Semantic splitter produced 0 chunks for document {document_id}.")

            # 3. Validate chunk invariants and coverage
            validation_report = ChunkValidator.validate(
                all_blocks=all_blocks,
                candidate_chunks=candidate_chunks,
                hard_max_tokens=settings.chunk_max_tokens,
            )

            if not validation_report.is_valid:
                err_msg = "; ".join(validation_report.errors)
                raise ChunkValidationError(f"Chunk validation failed: {err_msg}")

            # 4. Prepare filesystem directories
            doc_id_str = str(document_id)
            doc_chunk_dir = Path(settings.chunks_dir) / doc_id_str
            individual_chunks_dir = doc_chunk_dir / "chunks"
            individual_chunks_dir.mkdir(parents=True, exist_ok=True)

            # Clean previous individual chunk txt files if re-chunking
            for existing_f in individual_chunks_dir.glob("*.txt"):
                try:
                    existing_f.unlink()
                except Exception:
                    pass

            # 5. Persist chunk text files and master chunks.json
            chunk_records: List[DocumentChunk] = []
            master_chunk_list: List[Dict[str, Any]] = []
            doc_id_short = doc_id_str[:8].upper()

            for idx, cand in enumerate(candidate_chunks):
                chunk_index = idx + 1
                chunk_id_str = f"DOC-{doc_id_short}-CHUNK-{chunk_index:04d}"
                txt_filename = f"chunk_{chunk_index:04d}.txt"
                txt_path = individual_chunks_dir / txt_filename
                rel_artifact_path = f"storage/chunks/{doc_id_str}/chunks/{txt_filename}"

                # Generate formatted prompt text
                prompt_text = ChunkFormatter.format_chunk_text(
                    section_type=cand.section_type,
                    section_path=cand.section_path,
                    page_start=cand.page_start,
                    page_end=cand.page_end,
                    blocks=cand.blocks,
                )

                # Atomic write of chunk text
                with tempfile.NamedTemporaryFile("w", dir=str(individual_chunks_dir), delete=False, encoding="utf-8") as tf:
                    tf.write(prompt_text)
                    temp_txt = tf.name
                os.replace(temp_txt, str(txt_path))

                # Collect source block IDs
                source_bids = [b["block_id"] for b in cand.blocks if "block_id" in b]

                # Create DB chunk model
                db_chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_id_str=chunk_id_str,
                    chunk_index=idx,  # 0-based for DB index
                    section_type=cand.section_type,
                    section_path=cand.section_path,
                    chunk_title=cand.chunk_title,
                    page_start=cand.page_start,
                    page_end=cand.page_end,
                    token_count=cand.token_count,
                    contains_table=cand.contains_table,
                    contains_ocr=cand.contains_ocr,
                    source_block_count=len(source_bids),
                    artifact_path=rel_artifact_path,
                )
                chunk_records.append(db_chunk)

                # Master JSON item
                master_chunk_list.append({
                    "chunk_id": chunk_id_str,
                    "chunk_index": idx,
                    "section_type": cand.section_type,
                    "section_path": cand.section_path,
                    "chunk_title": cand.chunk_title,
                    "page_start": cand.page_start,
                    "page_end": cand.page_end,
                    "token_count": cand.token_count,
                    "source_block_ids": source_bids,
                    "contains_table": cand.contains_table,
                    "contains_ocr": cand.contains_ocr,
                    "overlap_from_previous": cand.overlap_from_previous,
                    "artifact_path": rel_artifact_path,
                    "text": prompt_text,
                })

            # Atomic write of master chunks.json
            master_json_path = doc_chunk_dir / "chunks.json"
            master_data = {
                "document_id": doc_id_str,
                "chunk_schema_version": settings.chunk_schema_version,
                "chunking_strategy_version": settings.chunk_strategy_version,
                "source_file": str(source_file),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "quality_summary": validation_report.to_diagnostics_dict(),
                "chunks": master_chunk_list,
            }

            with tempfile.NamedTemporaryFile("w", dir=str(doc_chunk_dir), delete=False, encoding="utf-8") as tf:
                json.dump(master_data, tf, indent=2, ensure_ascii=False)
                temp_json = tf.name
            os.replace(temp_json, str(master_json_path))

            # 6. Database transaction: delete existing chunks and insert new
            self.chunk_repo.delete_by_document_id(db, document.id)
            self.chunk_repo.create_all(db, chunk_records)

            # 7. Update document lifecycle state
            document.processing_status = "READY_FOR_EXTRACTION"
            db.commit()

            logger.info(
                "Chunking completed successfully for document %s: %d chunks generated, status READY_FOR_EXTRACTION",
                document_id,
                len(chunk_records),
            )

            return {
                "success": True,
                "document_id": str(document_id),
                "status": "READY_FOR_EXTRACTION",
                "chunk_count": len(chunk_records),
                "quality_summary": validation_report.to_diagnostics_dict(),
                "artifact_path": f"storage/chunks/{doc_id_str}/chunks.json",
            }

        except Exception as exc:
            logger.exception("Chunking failed for document %s: %s", document_id, str(exc))
            db.rollback()
            try:
                doc = self.doc_repo.get_by_id(db, document_id)
                if doc:
                    doc.processing_status = "CHUNKING_FAILED"
                    db.commit()
            except Exception as e2:
                logger.error("Failed to update document status to CHUNKING_FAILED: %s", e2)
            raise
