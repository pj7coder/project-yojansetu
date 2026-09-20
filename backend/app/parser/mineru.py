import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.parser.builtin_parser import BuiltinLayoutParser
from app.parser.interface import (
    BaseParser,
    BlockType,
    MinerUUnavailableException,
    ParserExecutionException,
    ParserRawResult,
    ParserTimeoutException,
    RawBlockData,
    RawPageData,
    RawTableData,
)

logger = logging.getLogger("yojansetu.parser.mineru")


class MinerUAdapter(BaseParser):
    """
    MinerU layout analysis and document parser adapter.

    Executes local MinerU CLI (magic-pdf / mineru) or falls back to BuiltinLayoutParser
    when heavy model dependencies are unavailable and fallback is enabled.
    Enforces process timeouts, argument arrays (no shell=True), and hardware awareness.
    """

    def __init__(self, fallback_enabled: bool = True):
        self.settings = get_settings()
        self.fallback_enabled = fallback_enabled
        self.builtin_fallback = BuiltinLayoutParser()

    @property
    def name(self) -> str:
        return "mineru"

    @property
    def version(self) -> str:
        # Check CLI version or report standard specification
        cmd = self._resolve_mineru_command()
        if cmd:
            try:
                res = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    return res.stdout.strip()
            except Exception:
                pass
        return "1.3.0"

    def _resolve_mineru_command(self) -> Optional[str]:
        """Check PATH for magic-pdf or mineru CLI binary."""
        for candidate in [self.settings.mineru_cmd, "magic-pdf", "mineru"]:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def is_available(self) -> bool:
        """Check if MinerU executable or Python module is available on the system."""
        return self._resolve_mineru_command() is not None

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

        cmd = self._resolve_mineru_command()
        timeout = timeout_seconds or self.settings.parser_timeout_seconds

        if not cmd:
            if not self.fallback_enabled:
                logger.error("MinerU CLI (magic-pdf / mineru) not installed and fallback is disabled.")
                raise MinerUUnavailableException(
                    "MinerU executable ('magic-pdf' or 'mineru') not found in PATH. "
                    "Install dependencies from requirements-parser.txt or configure PARSER_FALLBACK_ENABLED=true."
                )

            logger.info("MinerU not found in PATH; delegating to BuiltinLayoutParser (fallback enabled)")
            res = self.builtin_fallback.parse(
                file_path=file_path,
                raw_output_dir=raw_output_dir,
                max_pages=max_pages,
                timeout_seconds=timeout,
                device=device,
                **kwargs,
            )
            # Annotate parser name to reflect fallback
            res.parser_name = "mineru"
            res.parser_version = f"mineru-fallback ({self.builtin_fallback.version})"
            return res

        # MinerU CLI execution via subprocess
        # Format: magic-pdf -p <pdf_path> -o <output_dir> -m <method: auto/ocr/txt>
        method = "auto"
        args = [
            cmd,
            "-p", str(file_path),
            "-o", str(raw_output_dir),
            "-m", method,
        ]

        logger.info("Executing MinerU CLI: %s (timeout=%ds, device=%s)", " ".join(args), timeout, device)

        env = os.environ.copy()
        if device == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = ""

        try:
            process = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.error("MinerU execution timed out after %d seconds for %s", timeout, file_path.name)
            raise ParserTimeoutException(f"MinerU execution timed out after {timeout} seconds")
        except Exception as e:
            logger.error("MinerU process invocation error: %s", e)
            raise ParserExecutionException(f"MinerU process invocation failed: {e}")

        if process.returncode != 0:
            err_msg = process.stderr or process.stdout or f"Exited with code {process.returncode}"
            logger.error("MinerU execution failed: %s", err_msg)
            raise ParserExecutionException(f"MinerU execution failed (code {process.returncode}): {err_msg[:300]}")

        # Parse MinerU output directory
        # MinerU generates subfolder: <raw_output_dir>/<doc_name>/auto/<doc_name>_middle.json
        doc_stem = file_path.stem
        middle_json_candidates = list(raw_output_dir.rglob("*_middle.json")) + list(raw_output_dir.rglob("*.json"))

        if not middle_json_candidates:
            logger.warning("MinerU finished with code 0 but no output JSON found; attempting fallback")
            if self.fallback_enabled:
                return self.builtin_fallback.parse(file_path=file_path, raw_output_dir=raw_output_dir)
            raise ParserExecutionException("MinerU completed but produced no structured output JSON")

        middle_json_path = middle_json_candidates[0]
        try:
            with open(middle_json_path, "r", encoding="utf-8") as f:
                mineru_data = json.load(f)
        except Exception as e:
            raise ParserExecutionException(f"Failed to read MinerU output JSON: {e}")

        # Transform MinerU JSON into RawPageData and RawBlockData
        raw_pages = self._convert_mineru_json(mineru_data)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ParserRawResult(
            success=True,
            parser_name="mineru",
            parser_version=self.version,
            page_count=len(raw_pages),
            pages=raw_pages,
            raw_output_dir=raw_output_dir,
            raw_json=mineru_data,
            duration_ms=duration_ms,
        )

    def _convert_mineru_json(self, data: Dict[str, Any]) -> List[RawPageData]:
        """Convert MinerU middle.json schema into canonical RawPageData."""
        raw_pages: List[RawPageData] = []
        pdf_info = data.get("pdf_info", [])

        current_section = []

        for page_idx, p_data in enumerate(pdf_info):
            page_num = page_idx + 1
            raw_blocks: List[RawBlockData] = []
            order_idx = 0

            blocks = p_data.get("blocks", [])
            for b in blocks:
                b_type_str = str(b.get("type", "")).lower()
                text = ""
                table_data = None

                if b_type_str in ["title", "header", "heading"]:
                    b_type = BlockType.HEADING
                    lines = b.get("lines", [])
                    text = " ".join("".join(s.get("text", "") for s in l.get("spans", [])) for l in lines).strip()
                    if text:
                        current_section = [text[:80]]
                elif b_type_str == "table":
                    b_type = BlockType.TABLE
                    # Table extraction from MinerU table block
                    html_table = b.get("table_body", "")
                    text = f"Table on page {page_num}"
                    table_data = RawTableData(headers=[], rows=[])
                elif b_type_str in ["list", "list_item"]:
                    b_type = BlockType.LIST_ITEM
                    lines = b.get("lines", [])
                    text = " ".join("".join(s.get("text", "") for s in l.get("spans", [])) for l in lines).strip()
                elif b_type_str == "footer":
                    b_type = BlockType.FOOTER
                    lines = b.get("lines", [])
                    text = " ".join("".join(s.get("text", "") for s in l.get("spans", [])) for l in lines).strip()
                else:
                    b_type = BlockType.PARAGRAPH
                    lines = b.get("lines", [])
                    text = " ".join("".join(s.get("text", "") for s in l.get("spans", [])) for l in lines).strip()

                if text or table_data:
                    raw_blocks.append(
                        RawBlockData(
                            page_number=page_num,
                            order_index=order_idx,
                            block_type=b_type,
                            text=text,
                            section_path=list(current_section),
                            table_data=table_data,
                            bbox=b.get("bbox"),
                        )
                    )
                    order_idx += 1

            page_full_text = " ".join(blk.text for blk in raw_blocks)
            raw_pages.append(
                RawPageData(
                    page_number=page_num,
                    blocks=raw_blocks,
                    raw_text=page_full_text,
                )
            )

        return raw_pages
