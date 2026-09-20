from typing import Any, Dict, List, Optional

from app.chunking.section_patterns import BOILERPLATE_REGEX


class ChunkFormatter:
    """Formats structured blocks into clean, structured prompt text for LLM consumption."""

    @staticmethod
    def is_boilerplate(block: Dict[str, Any]) -> bool:
        """Identify administrative headers, footers, and repeated boilerplate."""
        block_type = block.get("block_type", "")
        if block_type == "TABLE":
            return False

        if block_type in ("HEADER", "FOOTER"):
            return True

        text = block.get("text", "").strip()
        if not text:
            return True

        # Short URL or page number patterns
        if len(text) < 40 and BOILERPLATE_REGEX.search(text):
            return True

        return False

    @staticmethod
    def render_table_markdown(block: Dict[str, Any]) -> str:
        """Format table block into aligned Markdown table."""
        if block.get("table_markdown"):
            return block["table_markdown"].strip()

        headers = block.get("headers", [])
        rows = block.get("rows", [])

        if not headers and not rows:
            return block.get("text", "").strip()

        lines: List[str] = []
        if headers:
            header_str = " | ".join(str(h).strip().replace("|", "\\|") for h in headers)
            sep_str = " | ".join("---" for _ in headers)
            lines.append(f"| {header_str} |")
            lines.append(f"| {sep_str} |")

        for r in rows:
            if isinstance(r, list):
                row_str = " | ".join(str(c).strip().replace("|", "\\|") for c in r)
                lines.append(f"| {row_str} |")

        return "\n".join(lines)

    @classmethod
    def format_chunk_text(
        cls,
        section_type: str,
        section_path: List[str],
        page_start: int,
        page_end: int,
        blocks: List[Dict[str, Any]],
    ) -> str:
        """
        Build standardized prompt text containing structural metadata header
        and sequentially formatted block content.
        """
        header_lines = [
            f"[Section: {section_type}]",
        ]
        if section_path:
            path_str = " > ".join(section_path)
            header_lines.append(f"[Section Path: {path_str}]")

        pages_str = f"{page_start}" if page_start == page_end else f"{page_start}-{page_end}"
        header_lines.append(f"[Pages: {pages_str}]")
        header_lines.append("")

        body_blocks: List[str] = []
        for b in blocks:
            # Exclude trivial boilerplate lines from semantic text
            if cls.is_boilerplate(b):
                continue

            b_type = b.get("block_type", "PARAGRAPH")
            if b_type == "TABLE":
                body_blocks.append(cls.render_table_markdown(b))
            else:
                body_blocks.append(b.get("text", "").strip())

        return "\n".join(header_lines) + "\n\n".join(body_blocks)
