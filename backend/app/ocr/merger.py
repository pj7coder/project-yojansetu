import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Tuple

from app.ocr.interface import (
    ExtractionMethod,
    OCRMergeException,
    OCRPageResult,
)

logger = logging.getLogger("yojansetu.ocr.merger")


class OCRMergeService:
    """Combines MinerU structured output with page-level OCR outputs into a canonical merged document."""

    def merge(
        self,
        document_id: str,
        parsed_doc_data: Dict[str, Any],
        ocr_results: Dict[int, OCRPageResult],
        ocr_engine_name: str = "paddleocr",
        ocr_engine_version: str = "2.7.0",
    ) -> Dict[str, Any]:
        """
        Merge OCR pages into parsed document data.

        Args:
            document_id: Unique document code/UUID string
            parsed_doc_data: Full JSON loaded from storage/parsed/<doc_id>/document.json
            ocr_results: Dict mapping page_number -> OCRPageResult for OCR'd pages
            ocr_engine_name: Name of OCR engine used
            ocr_engine_version: Version of OCR engine

        Returns:
            Dict representing the canonical merged structured document
        """
        original_pages = parsed_doc_data.get("pages", [])
        original_page_count = len(original_pages)

        merged_pages: List[Dict[str, Any]] = []
        low_confidence_numeric_count = 0
        total_ocr_blocks = 0
        total_mineru_blocks = 0

        # Process each physical page in strict 1-based sequential order
        for page_data in original_pages:
            p_num = page_data.get("page_number", 1)

            if p_num in ocr_results:
                # This page was targeted for OCR fallback
                ocr_res = ocr_results[p_num]
                if not ocr_res.success:
                    raise OCRMergeException(
                        f"Cannot merge document {document_id}: OCR failed for page {p_num} ({ocr_res.error_message})"
                    )

                blocks_list: List[Dict[str, Any]] = []
                page_low_conf_regions = 0

                for idx, reg in enumerate(ocr_res.regions):
                    block_id = f"blk_ocr_p{p_num}_{idx:03d}"
                    if reg.low_confidence_numeric:
                        low_confidence_numeric_count += 1
                        page_low_conf_regions += 1

                    # Heuristic metadata
                    is_header = idx == 0 and ("Government" in reg.text or "राजस्थान" in reg.text or "शासन" in reg.text)
                    is_footer = idx == (len(ocr_res.regions) - 1) and ("Page" in reg.text or "पृष्ठ" in reg.text)
                    is_table = reg.block_type == "TABLE_TEXT"

                    meta: Dict[str, Any] = {
                        "bbox": reg.bbox,
                        "ocr_confidence": reg.ocr_confidence,
                        "is_numeric": reg.is_numeric,
                        "low_confidence_numeric": reg.low_confidence_numeric,
                        "is_header": is_header,
                        "is_footer": is_footer,
                    }

                    if is_table:
                        meta["table_structure_uncertain"] = True

                    block_dict: Dict[str, Any] = {
                        "block_id": block_id,
                        "document_id": document_id,
                        "page_number": p_num,
                        "order_index": idx,
                        "block_type": reg.block_type,
                        "text": reg.text,
                        "section_path": "OCR_EXTRACTION",
                        "extraction_method": ExtractionMethod.PADDLEOCR.value,
                        "ocr_confidence": reg.ocr_confidence,
                        "metadata": meta,
                    }
                    blocks_list.append(block_dict)

                total_ocr_blocks += len(blocks_list)

                # Page-level confidence assessment
                avg_conf = (
                    sum(r.ocr_confidence for r in ocr_res.regions) / len(ocr_res.regions)
                    if ocr_res.regions
                    else 0.0
                )
                low_conf_page = avg_conf < 0.60 or page_low_conf_regions > 3

                merged_pages.append({
                    "page_number": p_num,
                    "status": "TEXT_OK" if blocks_list else "NO_TEXT",
                    "text_character_count": sum(len(b["text"]) for b in blocks_list),
                    "block_count": len(blocks_list),
                    "extraction_method": ExtractionMethod.PADDLEOCR.value,
                    "low_ocr_confidence": low_conf_page,
                    "average_ocr_confidence": round(avg_conf, 3),
                    "blocks": blocks_list,
                })

            else:
                # Good MinerU page: preserve unchanged and stamp extraction_method
                mineru_blocks = page_data.get("blocks", [])
                stamped_blocks: List[Dict[str, Any]] = []

                for b in mineru_blocks:
                    b_copy = dict(b)
                    b_copy["extraction_method"] = ExtractionMethod.MINERU.value
                    stamped_blocks.append(b_copy)

                total_mineru_blocks += len(stamped_blocks)

                merged_pages.append({
                    "page_number": p_num,
                    "status": page_data.get("status", "TEXT_OK"),
                    "text_character_count": page_data.get("text_character_count", 0),
                    "block_count": len(stamped_blocks),
                    "extraction_method": ExtractionMethod.MINERU.value,
                    "blocks": stamped_blocks,
                })

        # CRITICAL INTEGRITY CHECK: Page count invariance
        if len(merged_pages) != original_page_count:
            raise OCRMergeException(
                f"Page count mismatch during merge for document {document_id}. "
                f"Original had {original_page_count} pages, merged output has {len(merged_pages)} pages."
            )

        # Build merged document artifact
        parser_info = parsed_doc_data.get("parser", {})
        merged_document = {
            "schema_version": "1.0",
            "document_id": document_id,
            "processing": {
                "parser": parser_info.get("name", "mineru"),
                "parser_version": parser_info.get("version", "1.0"),
                "ocr": ocr_engine_name,
                "ocr_version": ocr_engine_version,
            },
            "page_count": len(merged_pages),
            "pages": merged_pages,
            "diagnostics": {
                "pages_total": len(merged_pages),
                "pages_mineru": original_page_count - len(ocr_results),
                "pages_ocr": len(ocr_results),
                "total_blocks_mineru": total_mineru_blocks,
                "total_blocks_ocr": total_ocr_blocks,
                "low_confidence_numeric_regions": low_confidence_numeric_count,
            },
        }

        return merged_document

    def save_raw_ocr_pages(
        self,
        ocr_dir: Path,
        ocr_results: Dict[int, OCRPageResult],
    ) -> None:
        """Persist raw OCR engine outputs under storage/ocr/<doc_id>/raw/."""
        raw_dir = ocr_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        for p_num, res in ocr_results.items():
            raw_path = raw_dir / f"page_{p_num:03d}.json"
            raw_data = {
                "page_number": p_num,
                "engine": res.engine,
                "success": res.success,
                "duration_ms": res.duration_ms,
                "regions": [
                    {
                        "text": r.text,
                        "bbox": r.bbox,
                        "ocr_confidence": r.ocr_confidence,
                        "is_numeric": r.is_numeric,
                        "low_confidence_numeric": r.low_confidence_numeric,
                        "order_index": r.order_index,
                        "block_type": r.block_type,
                    }
                    for r in res.regions
                ],
                "error_message": res.error_message,
            }
            # Atomic write
            tmp_path = raw_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, raw_path)

    def save_merged_document(
        self,
        ocr_dir: Path,
        merged_document: Dict[str, Any],
    ) -> Tuple[Path, str]:
        """
        Atomically write merged_document.json and calculate its SHA-256.

        Returns:
            Tuple of (final_path, sha256_hex)
        """
        ocr_dir.mkdir(parents=True, exist_ok=True)
        final_path = ocr_dir / "merged_document.json"
        tmp_path = ocr_dir / "merged_document.json.tmp"

        json_bytes = json.dumps(
            merged_document,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        sha256_hash = hashlib.sha256(json_bytes).hexdigest()

        with open(tmp_path, "wb") as f:
            f.write(json_bytes)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, final_path)
        logger.info(
            "Saved atomic merged document -> %s (SHA-256=%s, bytes=%d)",
            final_path.name,
            sha256_hash,
            len(json_bytes),
        )
        return final_path, sha256_hash
