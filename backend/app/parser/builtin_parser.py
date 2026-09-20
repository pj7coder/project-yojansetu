import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymupdf

from app.parser.interface import (
    BaseParser,
    BlockType,
    ParserRawResult,
    RawBlockData,
    RawPageData,
    RawTableData,
    ParserExecutionException,
    DocumentPageLimitExceededException,
)

logger = logging.getLogger("jansetu.parser.builtin")


class BuiltinLayoutParser(BaseParser):
    """
    Built-in high-performance layout parser using PyMuPDF.

    Provides reliable, zero-network, local offline parsing of government PDFs.
    Extracts pages, font-size-based headings, paragraphs, bulleted/numbered lists,
    tables (via PyMuPDF find_tables), headers, and footers with 1-based canonical page numbers.
    """

    @property
    def name(self) -> str:
        return "builtin"

    @property
    def version(self) -> str:
        return f"pymupdf-{pymupdf.__version__}"

    def parse(
        self,
        file_path: Path,
        raw_output_dir: Path,
        max_pages: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        device: str = "auto",
        **kwargs: Any,
    ) -> ParserRawResult:
        start_time = time.perf_counter()
        raw_output_dir.mkdir(parents=True, exist_ok=True)

        if not file_path.exists():
            raise ParserExecutionException(f"Target PDF file not found at: {file_path}")

        try:
            doc = pymupdf.open(str(file_path))
        except Exception as e:
            raise ParserExecutionException(f"Failed to open PDF document: {e}")

        total_pages = len(doc)
        if max_pages and total_pages > max_pages:
            doc.close()
            raise DocumentPageLimitExceededException(total_pages, max_pages)

        raw_pages: List[RawPageData] = []
        raw_blocks_dump: List[Dict[str, Any]] = []

        current_section_path: List[str] = []

        try:
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1  # 1-based canonical physical page number
                page_height = page.rect.height
                page_width = page.rect.width

                page_blocks: List[RawBlockData] = []
                order_index = 0

                # 1. Identify and extract tables on page
                tables_on_page = []
                try:
                    table_finder = page.find_tables()
                    for t in table_finder:
                        df_rows = t.extract()
                        if df_rows and len(df_rows) >= 1:
                            headers = [str(c or "").strip() for c in df_rows[0]]
                            rows = []
                            for row in df_rows[1:]:
                                rows.append([str(c or "").strip() for c in row])
                            tables_on_page.append({
                                "bbox": list(t.bbox),
                                "headers": headers,
                                "rows": rows,
                            })
                except Exception as e:
                    logger.debug("Table extraction skipped on page %d: %s", page_num, e)

                # Track table bounding boxes to avoid duplicate text block emission
                table_bboxes = [t["bbox"] for t in tables_on_page]

                # 2. Extract structured text blocks with font information
                text_page = page.get_text("dict")
                blocks = text_page.get("blocks", [])

                for b in blocks:
                    # Ignore image blocks for text extraction (track count separately)
                    if b.get("type") != 0:
                        continue

                    bbox = b.get("bbox", [0, 0, 0, 0])
                    y0, y1 = bbox[1], bbox[3]

                    # Check if block falls inside an extracted table
                    in_table = False
                    for tb in table_bboxes:
                        if tb[0] <= bbox[0] and tb[1] <= bbox[1] and tb[2] >= bbox[2] and tb[3] >= bbox[3]:
                            in_table = True
                            break
                    if in_table:
                        continue

                    # Concatenate lines and determine dominant font size
                    block_lines: List[str] = []
                    font_sizes: List[float] = []

                    for line in b.get("lines", []):
                        line_text = "".join(span.get("text", "") for span in line.get("spans", "")).strip()
                        if line_text:
                            block_lines.append(line_text)
                            for span in line.get("spans", []):
                                if "size" in span:
                                    font_sizes.append(span["size"])

                    block_text = " ".join(block_lines).strip()
                    if not block_text:
                        continue

                    avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10.0

                    # Classify block type
                    block_type = BlockType.PARAGRAPH

                    # Header/Footer detection based on vertical page position
                    if y1 < page_height * 0.08:
                        block_type = BlockType.HEADER
                    elif y0 > page_height * 0.92:
                        block_type = BlockType.FOOTER
                    elif avg_font_size >= 16.0 or (avg_font_size >= 14.0 and len(block_text) < 120):
                        block_type = BlockType.TITLE if page_num == 1 and order_index == 0 else BlockType.HEADING
                        # Update section hierarchy
                        current_section_path = [block_text[:80].strip()]
                    elif avg_font_size >= 12.5 and len(block_text) < 150:
                        block_type = BlockType.HEADING
                        if current_section_path:
                            current_section_path = [current_section_path[0], block_text[:80].strip()]
                        else:
                            current_section_path = [block_text[:80].strip()]
                    elif re.match(r"^\s*([0-9]+|[a-zA-Z]|[१-९]|[क-ह])[\.\)\-]\s+", block_text) or block_text.startswith(("- ", "• ", "* ")):
                        block_type = BlockType.LIST_ITEM

                    raw_block = RawBlockData(
                        page_number=page_num,
                        order_index=order_index,
                        block_type=block_type,
                        text=block_text,
                        section_path=list(current_section_path),
                        bbox=list(bbox),
                        metadata={"font_size": round(avg_font_size, 1)},
                    )
                    page_blocks.append(raw_block)
                    order_index += 1

                # 3. Add table blocks
                for t in tables_on_page:
                    table_data = RawTableData(
                        headers=t["headers"],
                        rows=t["rows"],
                    )
                    raw_block = RawBlockData(
                        page_number=page_num,
                        order_index=order_index,
                        block_type=BlockType.TABLE,
                        text=f"Table: {', '.join(t['headers'])}",
                        section_path=list(current_section_path),
                        table_data=table_data,
                        bbox=t["bbox"],
                        metadata={"row_count": len(t["rows"]), "col_count": len(t["headers"])},
                    )
                    page_blocks.append(raw_block)
                    order_index += 1

                # Sort blocks by vertical reading order (y0, then x0)
                page_blocks.sort(key=lambda x: (x.bbox[1] if x.bbox else 0, x.bbox[0] if x.bbox else 0))
                for idx, blk in enumerate(page_blocks):
                    blk.order_index = idx

                raw_page_text = page.get_text()
                raw_pages.append(
                    RawPageData(
                        page_number=page_num,
                        blocks=page_blocks,
                        raw_text=raw_page_text,
                        image_count=len(page.get_images()),
                    )
                )

                # Prepare dump for raw JSON artifact
                raw_blocks_dump.append({
                    "page_number": page_num,
                    "block_count": len(page_blocks),
                    "blocks": [
                        {
                            "order_index": blk.order_index,
                            "block_type": blk.block_type,
                            "text": blk.text,
                            "section_path": blk.section_path,
                            "bbox": blk.bbox,
                            "has_table": blk.table_data is not None,
                        }
                        for blk in page_blocks
                    ],
                })

            doc.close()

        except Exception as e:
            doc.close()
            raise ParserExecutionException(f"Error during PDF layout parsing: {e}")

        # Write raw parser dump to mineru_raw/raw_blocks.json
        raw_json_path = raw_output_dir / "raw_blocks.json"
        raw_dump_data = {
            "parser": self.name,
            "version": self.version,
            "page_count": total_pages,
            "pages": raw_blocks_dump,
        }
        with open(raw_json_path, "w", encoding="utf-8") as f:
            json.dump(raw_dump_data, f, ensure_ascii=False, indent=2)

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ParserRawResult(
            success=True,
            parser_name=self.name,
            parser_version=self.version,
            page_count=total_pages,
            pages=raw_pages,
            raw_output_dir=raw_output_dir,
            raw_json=raw_dump_data,
            duration_ms=duration_ms,
        )
