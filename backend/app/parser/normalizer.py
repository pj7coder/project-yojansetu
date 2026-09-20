import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.parser.diagnostics import evaluate_document_diagnostics
from app.parser.interface import BlockType, ParserRawResult

logger = logging.getLogger("yojansetu.parser.normalizer")


def build_normalized_document(
    document_id: uuid.UUID,
    raw_result: ParserRawResult,
) -> Dict[str, Any]:
    """
    Transform raw parser output into canonical YojanSetu structured document schema.
    Guarantees stable schema_version 1.0 with physical 1-based page indexing.
    """
    doc_id_str = str(document_id)
    diagnostics = evaluate_document_diagnostics(raw_result.pages)

    # Build page diagnostic lookup by page_number
    page_diag_map = {d.page_number: d for d in diagnostics.page_diagnostics}

    pages_list: List[Dict[str, Any]] = []

    for page_data in raw_result.pages:
        p_num = page_data.page_number
        p_diag = page_diag_map.get(p_num)

        blocks_list: List[Dict[str, Any]] = []
        for idx, blk in enumerate(page_data.blocks):
            block_id = f"blk_p{p_num}_{idx:03d}"

            block_dict: Dict[str, Any] = {
                "block_id": block_id,
                "document_id": doc_id_str,
                "page_number": p_num,
                "order_index": blk.order_index,
                "block_type": blk.block_type,
                "text": blk.text,
                "section_path": blk.section_path,
                "metadata": blk.metadata,
            }

            if blk.block_type == BlockType.TABLE and blk.table_data:
                block_dict["headers"] = blk.table_data.headers
                block_dict["rows"] = blk.table_data.rows
                if blk.table_data.markdown:
                    block_dict["table_markdown"] = blk.table_data.markdown

            blocks_list.append(block_dict)

        pages_list.append({
            "page_number": p_num,
            "status": p_diag.status if p_diag else "TEXT_OK",
            "text_character_count": p_diag.text_character_count if p_diag else 0,
            "image_count": p_diag.image_count if p_diag else 0,
            "block_count": len(blocks_list),
            "blocks": blocks_list,
        })

    normalized_doc = {
        "schema_version": "1.0",
        "document_id": doc_id_str,
        "parser": {
            "name": raw_result.parser_name,
            "version": raw_result.parser_version,
        },
        "page_count": len(pages_list),
        "pages": pages_list,
        "diagnostics": {
            "total_pages": diagnostics.total_pages,
            "pages_with_text": diagnostics.pages_with_text,
            "pages_without_text": diagnostics.pages_without_text,
            "pages_low_text": diagnostics.pages_low_text,
            "total_text_characters": diagnostics.total_text_characters,
            "total_blocks": diagnostics.total_blocks,
            "total_tables": diagnostics.total_tables,
            "needs_ocr": diagnostics.needs_ocr,
            "quality_assessment": diagnostics.quality_assessment,
        },
    }

    return normalized_doc


def generate_document_markdown(normalized_doc: Dict[str, Any]) -> str:
    """Generate human-readable Markdown output for visual inspection and debugging."""
    doc_id = normalized_doc.get("document_id", "")
    pages = normalized_doc.get("pages", [])

    lines: List[str] = [
        f"# Document: {doc_id}",
        f"**Parser:** {normalized_doc.get('parser', {}).get('name', 'unknown')} | "
        f"**Total Pages:** {normalized_doc.get('page_count', 0)}",
        "",
        "---",
        "",
    ]

    for page in pages:
        p_num = page.get("page_number", 1)
        p_status = page.get("status", "TEXT_OK")
        lines.append(f"## Page {p_num} `[{p_status}]`")
        lines.append("")

        for blk in page.get("blocks", []):
            b_type = blk.get("block_type", "")
            text = blk.get("text", "").strip()

            if b_type == BlockType.TITLE:
                lines.append(f"# {text}")
                lines.append("")
            elif b_type == BlockType.HEADING:
                depth = min(4, len(blk.get("section_path", [])) + 2)
                lines.append(f"{'#' * depth} {text}")
                lines.append("")
            elif b_type == BlockType.LIST_ITEM:
                lines.append(f"- {text}")
            elif b_type == BlockType.TABLE:
                headers = blk.get("headers", [])
                rows = blk.get("rows", [])
                if headers:
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        # Pad row if columns don't match
                        padded_row = (row + [""] * (len(headers) - len(row)))[:len(headers)]
                        lines.append("| " + " | ".join(padded_row) + " |")
                    lines.append("")
                else:
                    lines.append(f"*[Table: {text}]*")
                    lines.append("")
            elif b_type in [BlockType.HEADER, BlockType.FOOTER]:
                lines.append(f"> *{b_type}: {text}*")
                lines.append("")
            else:
                lines.append(text)
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def write_parsed_artifacts_atomically(
    output_dir: Path,
    normalized_doc: Dict[str, Any],
) -> Tuple[Path, str]:
    """
    Atomically write document.json and document.md to output_dir.
    Returns (path to document.json, sha256 of document.json).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "document.json"
    tmp_json_path = output_dir / "document.json.tmp"

    md_path = output_dir / "document.md"
    tmp_md_path = output_dir / "document.md.tmp"

    # Serialize JSON with clean indentation & Unicode support
    json_bytes = json.dumps(normalized_doc, ensure_ascii=False, indent=2).encode("utf-8")
    artifact_sha256 = hashlib.sha256(json_bytes).hexdigest()

    with open(tmp_json_path, "wb") as f:
        f.write(json_bytes)
        f.flush()
        os.fsync(f.fileno())

    # Generate and write Markdown
    markdown_content = generate_document_markdown(normalized_doc)
    with open(tmp_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        f.flush()
        os.fsync(f.fileno())

    # Atomic renames
    os.replace(tmp_json_path, json_path)
    os.replace(tmp_md_path, md_path)

    logger.debug("Atomically written parsed artifacts to %s (sha256: %s)", output_dir, artifact_sha256)
    return json_path, artifact_sha256
