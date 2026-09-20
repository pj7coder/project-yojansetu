from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from app.chunking.tokenizer import estimate_tokens
from app.core.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.database.models.extraction_run import ExtractionRun
from app.extraction.evidence_validator import EvidenceValidator
from app.extraction.prompts import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
    SYSTEM_EXTRACTION_PROMPT,
    build_chunk_extraction_prompt,
    build_repair_prompt,
)
from app.extraction.schemas import ChunkExtractionResult
from app.llm.interface import (
    BaseLLMProvider,
    LLMProviderError,
    LLMSchemaValidationError,
    LLMUnavailableError,
    StructuredLLMResponse,
)
from app.llm.mock import MockLLMProvider
from app.llm.ollama import OllamaProvider
from app.repositories.chunk_repository import DocumentChunkRepository
from app.repositories.extraction_repository import ExtractionRunRepository

logger = logging.getLogger("yojansetu.extraction.service")


class SchemeExtractionService:
    """
    Orchestrates local LLM scheme extraction from a semantic document chunk.
    Coordinates prompting, provider invocation, retry/repair, evidence validation,
    and atomic artifact storage.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        chunk_repo: Optional[DocumentChunkRepository] = None,
        extraction_repo: Optional[ExtractionRunRepository] = None,
    ):
        if llm_provider is not None:
            self.llm_provider = llm_provider
        elif settings.llm_provider.lower() == "mock":
            self.llm_provider = MockLLMProvider()
        else:
            self.llm_provider = OllamaProvider()

        self.chunk_repo = chunk_repo or DocumentChunkRepository()
        self.extraction_repo = extraction_repo or ExtractionRunRepository()
        self._consecutive_failures: int = 0

    def _resolve_chunk(self, db: Session, chunk_identifier: Any) -> DocumentChunk:
        """Fetch chunk by UUID or string identifier."""
        chunk = None
        if isinstance(chunk_identifier, uuid.UUID):
            chunk = self.chunk_repo.get_by_id(db, chunk_identifier)
        elif isinstance(chunk_identifier, str):
            try:
                c_uuid = uuid.UUID(chunk_identifier)
                chunk = self.chunk_repo.get_by_id(db, c_uuid)
            except ValueError:
                pass
            if not chunk:
                chunk = self.chunk_repo.get_by_chunk_id_str(db, chunk_identifier)

        if not chunk:
            raise ValueError(f"DocumentChunk '{chunk_identifier}' not found")
        return chunk

    def _load_chunk_text_and_blocks(self, chunk: DocumentChunk) -> tuple[str, List[str]]:
        """Load rendered text artifact and source block IDs from filesystem."""
        base_dir = Path(settings.base_dir).resolve()
        txt_path = (base_dir / chunk.artifact_path).resolve()
        if not txt_path.exists():
            raise FileNotFoundError(f"Chunk text artifact not found at: {txt_path}")

        chunk_text = txt_path.read_text(encoding="utf-8")

        # Load source block IDs from master chunks.json
        master_json = Path(settings.chunks_dir) / str(chunk.document_id) / "chunks.json"
        source_bids: List[str] = []
        if master_json.exists():
            try:
                with open(master_json, "r", encoding="utf-8") as f:
                    master_data = json.load(f)
                    for item in master_data.get("chunks", []):
                        if item.get("chunk_id") == chunk.chunk_id_str or item.get("chunk_index") == chunk.chunk_index:
                            source_bids = item.get("source_block_ids", [])
                            break
            except Exception as e:
                logger.warning("Could not read source_block_ids from chunks.json: %s", e)

        return chunk_text, source_bids

    def extract_chunk(
        self,
        db: Session,
        chunk_identifier: Any,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute evidence-backed LLM extraction on a single document chunk.

        Args:
            db: Database session
            chunk_identifier: UUID or chunk_id_str
            force: If True, overwrite previous extraction run for this chunk

        Returns:
            Summary dict with extraction status, diagnostics, and artifact path.
        """
        chunk = self._resolve_chunk(db, chunk_identifier)
        doc_id_str = str(chunk.document_id)
        chunk_id_str = chunk.chunk_id_str

        # Idempotency check: return existing successful run if force is False
        existing_run = self.extraction_repo.get_by_chunk_id(db, chunk.id)
        if existing_run and existing_run.status == "EXTRACTED" and not force:
            logger.info("Chunk %s already extracted. Returning cached run %s", chunk_id_str, existing_run.id)
            return {
                "success": True,
                "status": existing_run.status,
                "chunk_id": chunk_id_str,
                "run_id": str(existing_run.id),
                "artifact_path": existing_run.artifact_path,
                "diagnostics": existing_run.diagnostics,
                "cached": True,
            }

        # Prepare filesystem storage
        extract_dir = Path(settings.extracted_dir) / doc_id_str / chunk_id_str
        extract_dir.mkdir(parents=True, exist_ok=True)

        chunk_text, source_bids = self._load_chunk_text_and_blocks(chunk)
        input_tokens = estimate_tokens(chunk_text)

        from app.extraction.fallback_extractor import FallbackChunkExtractor
        from app.llm.interface import LLMResponseMetadata

        response: Optional[StructuredLLMResponse] = None
        last_error: Optional[str] = None
        raw_response_text = ""
        max_retries = settings.llm_extraction_max_retries

        # Fast-path 1: Check if chunk contains any scheme indicators
        is_scheme_candidate = FallbackChunkExtractor.can_extract(chunk_text)
        if not is_scheme_candidate:
            logger.debug("Chunk %s has no scheme indicators. Fast-skipping LLM extraction.", chunk_id_str)
            empty_result = ChunkExtractionResult(
                document_id=doc_id_str,
                chunk_id=chunk_id_str,
                section_type=chunk.section_type,
                schemes=[],
            )
            empty_meta = LLMResponseMetadata(
                provider="fast_skip",
                model_name="rule_filter",
                raw_response="NO_SCHEME_INDICATORS_FAST_SKIP",
                duration_ms=0,
                input_tokens=input_tokens,
                output_tokens=0,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            response = StructuredLLMResponse(data=empty_result, metadata=empty_meta)
            raw_response_text = "NO_SCHEME_INDICATORS_FAST_SKIP"
        elif self._consecutive_failures >= 2:
            # Circuit breaker active: avoid 45s timeouts on every subsequent chunk
            logger.info("Circuit breaker active for chunk %s; using FallbackChunkExtractor directly", chunk_id_str)
            try:
                fallback_data = FallbackChunkExtractor.extract(
                    chunk_text=chunk_text,
                    document_id=doc_id_str,
                    chunk_id=chunk_id_str,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    source_bids=source_bids,
                )
                fallback_meta = LLMResponseMetadata(
                    provider="fallback",
                    model_name="deterministic_regex",
                    raw_response="DETERMINISTIC_FALLBACK_EXTRACTION",
                    duration_ms=0,
                    input_tokens=input_tokens,
                    output_tokens=100,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )
                response = StructuredLLMResponse(data=fallback_data, metadata=fallback_meta)
                raw_response_text = "DETERMINISTIC_FALLBACK_EXTRACTION"
            except Exception as fb_err:
                logger.error("FallbackChunkExtractor failed for chunk %s: %s", chunk_id_str, fb_err)
                last_error = str(fb_err)
        else:
            logger.info(
                "Starting LLM extraction for chunk %s (%s, ~%d tokens) with model %s",
                chunk_id_str,
                chunk.section_type,
                input_tokens,
                getattr(self.llm_provider, "model_name", "llm"),
            )

            prompt = build_chunk_extraction_prompt(
                document_id=doc_id_str,
                chunk_id=chunk_id_str,
                section_type=chunk.section_type,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                chunk_text=chunk_text,
            )

            for attempt in range(1 + max_retries):
                try:
                    if attempt == 0:
                        current_prompt = prompt
                    else:
                        logger.info("Retrying extraction for chunk %s (attempt %d/%d)...", chunk_id_str, attempt + 1, 1 + max_retries)
                        current_prompt = build_repair_prompt(
                            chunk_text=chunk_text,
                            previous_raw_response=raw_response_text,
                            error_message=last_error or "Invalid format",
                        )

                    response = self.llm_provider.generate_structured(
                        prompt=current_prompt,
                        schema=ChunkExtractionResult,
                        system_prompt=SYSTEM_EXTRACTION_PROMPT,
                    )
                    raw_response_text = response.metadata.raw_response
                    self._consecutive_failures = 0
                    break  # Success

                except LLMSchemaValidationError as e:
                    last_error = str(e)
                    raw_response_text = e.raw_response or ""
                    logger.warning("Attempt %d failed schema validation on chunk %s: %s", attempt + 1, chunk_id_str, e)
                    if attempt >= max_retries:
                        self._consecutive_failures += 1
                        break
                except LLMUnavailableError as e:
                    # Immediate exit on server/model unreachability
                    last_error = f"MODEL_UNAVAILABLE: {e}"
                    logger.error("LLM provider unavailable for chunk %s: %s", chunk_id_str, e)
                    self._consecutive_failures += 1
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.error("Unexpected extraction failure on chunk %s: %s", chunk_id_str, e)
                    self._consecutive_failures += 1
                    break

            # Fallback if LLM failed on scheme candidate chunk
            if response is None:
                logger.info("LLM unavailable for chunk %s; engaging FallbackChunkExtractor", chunk_id_str)
                try:
                    fallback_data = FallbackChunkExtractor.extract(
                        chunk_text=chunk_text,
                        document_id=doc_id_str,
                        chunk_id=chunk_id_str,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        source_bids=source_bids,
                    )
                    fallback_meta = LLMResponseMetadata(
                        provider="fallback",
                        model_name="deterministic_regex",
                        raw_response="DETERMINISTIC_FALLBACK_EXTRACTION",
                        duration_ms=0,
                        input_tokens=input_tokens,
                        output_tokens=100,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                    )
                    response = StructuredLLMResponse(data=fallback_data, metadata=fallback_meta)
                    raw_response_text = "DETERMINISTIC_FALLBACK_EXTRACTION"
                except Exception as fb_err:
                    logger.error("FallbackChunkExtractor failed for chunk %s: %s", chunk_id_str, fb_err)

        # Record raw response on disk
        with open(extract_dir / "raw_response.txt", "w", encoding="utf-8") as f:
            f.write(raw_response_text or "")

        if response is None:
            failed_run = ExtractionRun(
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                chunk_id_str=chunk_id_str,
                model_provider=getattr(self.llm_provider, "provider", "ollama"),
                model_name=getattr(self.llm_provider, "model_name", settings.ollama_model),
                prompt_version=EXTRACTION_PROMPT_VERSION,
                schema_version=EXTRACTION_SCHEMA_VERSION,
                status="EXTRACTION_FAILED",
                artifact_path=f"storage/extracted/{doc_id_str}/{chunk_id_str}/raw_response.txt",
                input_token_estimate=input_tokens,
                failure_reason=last_error,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            self.extraction_repo.create(db, failed_run)
            return {
                "success": False,
                "status": "EXTRACTION_FAILED",
                "chunk_id": chunk_id_str,
                "failure_reason": last_error,
            }

        # Step 2: Evidence verification against source chunk
        extraction_result: ChunkExtractionResult = response.data
        extraction_result.document_id = doc_id_str
        extraction_result.chunk_id = chunk_id_str
        extraction_result.section_type = chunk.section_type

        evidence_diagnostics = EvidenceValidator.validate_chunk_result(
            extraction_result=extraction_result,
            chunk_text=chunk_text,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            valid_block_ids=source_bids,
        )

        final_status = "EXTRACTED" if evidence_diagnostics["all_passed"] else "EXTRACTION_REVIEW_REQUIRED"

        # Step 3: Write artifacts atomically to storage/extracted/<doc_id>/<chunk_id>/
        rel_extraction_path = f"storage/extracted/{doc_id_str}/{chunk_id_str}/extraction.json"

        # Write extraction.json
        extraction_json_path = extract_dir / "extraction.json"
        with tempfile.NamedTemporaryFile("w", dir=str(extract_dir), delete=False, encoding="utf-8") as tf:
            tf.write(extraction_result.model_dump_json(indent=2))
            temp_json = tf.name
        os.replace(temp_json, str(extraction_json_path))

        # Write validation.json
        validation_json_path = extract_dir / "validation.json"
        with tempfile.NamedTemporaryFile("w", dir=str(extract_dir), delete=False, encoding="utf-8") as tf:
            json.dump(evidence_diagnostics, tf, indent=2, ensure_ascii=False)
            temp_val = tf.name
        os.replace(temp_val, str(validation_json_path))

        # Write request_metadata.json
        meta_dict = {
            "chunk_id": chunk_id_str,
            "document_id": doc_id_str,
            "model_provider": response.metadata.provider,
            "model_name": response.metadata.model_name,
            "prompt_version": EXTRACTION_PROMPT_VERSION,
            "schema_version": EXTRACTION_SCHEMA_VERSION,
            "duration_ms": response.metadata.duration_ms,
            "input_tokens": response.metadata.input_tokens or input_tokens,
            "output_tokens": response.metadata.output_tokens,
            "started_at": response.metadata.started_at.isoformat() if response.metadata.started_at else None,
            "completed_at": response.metadata.completed_at.isoformat() if response.metadata.completed_at else None,
            "evidence_diagnostics": evidence_diagnostics,
        }
        with open(extract_dir / "request_metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)

        # Step 4: Record in database
        run_record = ExtractionRun(
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            chunk_id_str=chunk_id_str,
            model_provider=response.metadata.provider,
            model_name=response.metadata.model_name,
            prompt_version=EXTRACTION_PROMPT_VERSION,
            schema_version=EXTRACTION_SCHEMA_VERSION,
            status=final_status,
            artifact_path=rel_extraction_path,
            input_token_estimate=input_tokens,
            output_tokens=response.metadata.output_tokens,
            duration_ms=response.metadata.duration_ms,
            diagnostics=evidence_diagnostics,
            started_at=response.metadata.started_at,
            completed_at=response.metadata.completed_at,
        )
        saved_run = self.extraction_repo.create(db, run_record)

        logger.info(
            "Extraction completed for chunk %s: status=%s, facts=%d, valid_evidence=%d, failed_evidence=%d",
            chunk_id_str,
            final_status,
            evidence_diagnostics["facts_extracted"],
            evidence_diagnostics["facts_with_valid_evidence"],
            evidence_diagnostics["facts_evidence_failed"],
        )

        return {
            "success": True,
            "status": final_status,
            "chunk_id": chunk_id_str,
            "run_id": str(saved_run.id),
            "artifact_path": rel_extraction_path,
            "diagnostics": evidence_diagnostics,
            "schemes_count": len(extraction_result.schemes),
        }

    def extract_snippet_in_memory(
        self,
        chunk_text: str,
        document_id: str = "doc-eval",
        chunk_id: str = "chunk-eval",
        section_type: str = "ELIGIBILITY",
        page_start: int = 1,
        page_end: int = 1,
        source_block_ids: Optional[List[str]] = None,
    ) -> Tuple[Optional[ChunkExtractionResult], Dict[str, Any]]:
        """
        Execute LLM extraction and deterministic evidence validation in-memory
        without mutating database tables or writing production artifacts.
        Ideal for evaluation benchmarks, unit tests, and live preview.
        """
        source_bids = source_block_ids or []
        input_tokens = estimate_tokens(chunk_text)

        prompt = build_chunk_extraction_prompt(
            document_id=document_id,
            chunk_id=chunk_id,
            section_type=section_type,
            page_start=page_start,
            page_end=page_end,
            chunk_text=chunk_text,
        )

        response: Optional[StructuredLLMResponse] = None
        last_error: Optional[str] = None
        raw_response_text = ""
        max_retries = settings.llm_extraction_max_retries

        for attempt in range(1 + max_retries):
            try:
                if attempt == 0:
                    current_prompt = prompt
                else:
                    current_prompt = build_repair_prompt(
                        chunk_text=chunk_text,
                        previous_raw_response=raw_response_text,
                        error_message=last_error or "Invalid format",
                    )

                response = self.llm_provider.generate_structured(
                    prompt=current_prompt,
                    schema=ChunkExtractionResult,
                    system_prompt=SYSTEM_EXTRACTION_PROMPT,
                )
                raw_response_text = response.metadata.raw_response
                break

            except LLMSchemaValidationError as e:
                last_error = str(e)
                raw_response_text = e.raw_response or ""
                if attempt >= max_retries:
                    break
            except LLMUnavailableError as e:
                last_error = f"MODEL_UNAVAILABLE: {e}"
                break
            except Exception as e:
                last_error = str(e)
                break

        if response is None:
            return None, {
                "success": False,
                "status": "EXTRACTION_FAILED",
                "failure_reason": last_error,
                "input_tokens": input_tokens,
                "raw_response": raw_response_text,
            }

        extraction_result: ChunkExtractionResult = response.data
        extraction_result.document_id = document_id
        extraction_result.chunk_id = chunk_id
        extraction_result.section_type = section_type

        evidence_diagnostics = EvidenceValidator.validate_chunk_result(
            extraction_result=extraction_result,
            chunk_text=chunk_text,
            page_start=page_start,
            page_end=page_end,
            valid_block_ids=source_bids,
        )

        diagnostics = {
            "success": True,
            "status": "EXTRACTED" if evidence_diagnostics.get("all_passed", False) else "EXTRACTION_REVIEW_REQUIRED",
            "evidence_diagnostics": evidence_diagnostics,
            "duration_ms": response.metadata.duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": response.metadata.output_tokens,
            "raw_response": raw_response_text,
        }
        return extraction_result, diagnostics

