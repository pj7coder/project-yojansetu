from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models.document import Document
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.extraction_repository import ExtractionRunRepository

logger = logging.getLogger("yojansetu.extraction.aggregator")


class DocumentExtractionAggregator:
    """
    Consolidates chunk-level extraction runs for a document into a master
    document_extractions.json artifact and advances lifecycle status to READY_FOR_NORMALIZATION.
    """

    def __init__(
        self,
        doc_repo: Optional[DocumentRepository] = None,
        chunk_repo: Optional[DocumentChunkRepository] = None,
        extraction_repo: Optional[ExtractionRunRepository] = None,
    ):
        self.doc_repo = doc_repo or DocumentRepository()
        self.chunk_repo = chunk_repo or DocumentChunkRepository()
        self.extraction_repo = extraction_repo or ExtractionRunRepository()

    def aggregate_document(self, db: Session, document_id: uuid.UUID) -> Dict[str, Any]:
        """
        Scan all chunks for a document, collect extraction runs, and compile master index.
        """
        doc = self.doc_repo.get_by_id(db, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc_id_str = str(document_id)
        chunks = self.chunk_repo.get_by_document_id(db, document_id)
        if not chunks:
            raise ValueError(f"No chunks found for document {document_id}")

        runs = self.extraction_repo.get_all_by_document_id(db, document_id)
        runs_by_chunk = {run.chunk_id: run for run in runs}

        chunks_total = len(chunks)
        chunks_successful = 0
        chunks_failed = 0
        chunks_review_required = 0
        total_facts = 0
        valid_evidence_facts = 0
        failed_evidence_facts = 0
        scheme_names: List[str] = []

        chunk_summaries: List[Dict[str, Any]] = []
        base_dir = Path(settings.base_dir).resolve()

        for c in chunks:
            run = runs_by_chunk.get(c.id)
            if not run or run.status == "EXTRACTION_FAILED":
                chunks_failed += 1
                chunk_summaries.append({
                    "chunk_id": c.chunk_id_str,
                    "status": run.status if run else "NOT_STARTED",
                    "error": run.failure_reason if run else "Missing extraction run",
                })
            else:
                if run.status == "EXTRACTED":
                    chunks_successful += 1
                elif run.status == "EXTRACTION_REVIEW_REQUIRED":
                    chunks_review_required += 1
                    chunks_successful += 1

                diag = run.diagnostics or {}
                total_facts += diag.get("facts_extracted", 0)
                valid_evidence_facts += diag.get("facts_with_valid_evidence", 0)
                failed_evidence_facts += diag.get("facts_evidence_failed", 0)

                # Read extraction.json content
                ext_file = (base_dir / run.artifact_path).resolve()
                payload = None
                if ext_file.exists():
                    try:
                        with open(ext_file, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            for s in payload.get("schemes", []):
                                s_name = s.get("scheme_name")
                                if s_name and s_name not in scheme_names:
                                    scheme_names.append(s_name)
                    except Exception as e:
                        logger.warning("Could not read chunk extraction file %s: %s", ext_file, e)

                chunk_summaries.append({
                    "chunk_id": c.chunk_id_str,
                    "section_type": c.section_type,
                    "status": run.status,
                    "artifact_path": run.artifact_path,
                    "duration_ms": run.duration_ms,
                    "diagnostics": diag,
                    "schemes_extracted": len(payload.get("schemes", [])) if payload else 0,
                })

        # Determine document lifecycle status
        if chunks_failed > 0:
            doc_status = "EXTRACTION_PARTIAL_FAILURE"
        else:
            doc_status = "READY_FOR_NORMALIZATION"

        # Prepare master document_extractions.json
        doc_extract_dir = Path(settings.extracted_dir) / doc_id_str
        doc_extract_dir.mkdir(parents=True, exist_ok=True)
        master_path = doc_extract_dir / "document_extractions.json"

        master_data = {
            "document_id": doc_id_str,
            "status": doc_status,
            "aggregated_at": datetime.now(timezone.utc).isoformat(),
            "chunks_total": chunks_total,
            "chunks_successful": chunks_successful,
            "chunks_failed": chunks_failed,
            "chunks_review_required": chunks_review_required,
            "facts_extracted": total_facts,
            "facts_with_valid_evidence": valid_evidence_facts,
            "facts_evidence_failed": failed_evidence_facts,
            "scheme_names_detected": scheme_names,
            "chunk_summaries": chunk_summaries,
        }

        with tempfile.NamedTemporaryFile("w", dir=str(doc_extract_dir), delete=False, encoding="utf-8") as tf:
            json.dump(master_data, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name
        os.replace(temp_name, str(master_path))

        # Update document model status
        doc.processing_status = doc_status
        db.commit()

        logger.info(
            "Aggregated extraction for document %s: status=%s, chunks=%d/%d, facts=%d",
            doc_id_str,
            doc_status,
            chunks_successful,
            chunks_total,
            total_facts,
        )

        return master_data
