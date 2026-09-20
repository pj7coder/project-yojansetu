from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.chunking.formatter import ChunkFormatter
from app.chunking.section_detector import SectionDetector
from app.chunking.section_patterns import PROVISO_EXCEPTION_REGEX, SectionType
from app.chunking.tokenizer import estimate_tokens

logger = logging.getLogger("jansetu.chunking.splitter")


@dataclass
class CandidateChunk:
    """Intermediate chunk representation before final persistence."""
    section_type: str
    section_path: List[str]
    chunk_title: str
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    token_count: int = 0
    contains_table: bool = False
    contains_ocr: bool = False
    overlap_from_previous: bool = False


class SemanticSplitter:
    """
    Groups structured document blocks into logically coherent, token-controlled chunks
    while strictly preserving legal exceptions, provisos, tables, and lists.
    """

    def __init__(
        self,
        target_tokens: int = 5000,
        max_tokens: int = 8000,
        min_tokens: int = 300,
        overlap_tokens: int = 200,
    ):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens
        self.detector = SectionDetector()

    def is_proviso_or_exception(self, block: Dict[str, Any]) -> bool:
        """Check if block contains critical legal exception/proviso markers."""
        text = block.get("text", "")
        return bool(PROVISO_EXCEPTION_REGEX.search(text))

    def build_chunks(
        self,
        document_id: str,
        pages: List[Dict[str, Any]],
    ) -> List[CandidateChunk]:
        """
        Transform structured pages into validated semantic candidate chunks.

        Args:
            document_id: Unique document identifier
            pages: List of page objects containing blocks from merged_document.json or document.json

        Returns:
            List of CandidateChunk instances
        """
        # Flatten blocks in physical sequential order
        all_blocks: List[Dict[str, Any]] = []
        for p in pages:
            for b in p.get("blocks", []):
                all_blocks.append(b)

        if not all_blocks:
            return []

        # 1. Group contiguous blocks into initial section segments
        section_groups: List[Dict[str, Any]] = []
        current_type = SectionType.GENERAL
        current_path = ["General"]
        current_title = "General Overview"
        current_group_blocks: List[Dict[str, Any]] = []

        for b in all_blocks:
            # Skip administrative boilerplate (headers/footers/page numbers) from candidate chunks
            if ChunkFormatter.is_boilerplate(b):
                continue

            detected = self.detector.detect_section(b)

            # Check if this block shifts section
            # Proviso protection: If block is an exception/proviso, it CANNOT start a new section
            if detected and not self.is_proviso_or_exception(b):
                sec_type, title = detected
                sec_path = self.detector.update_hierarchy(sec_type, title, b.get("section_path"))

                # If we have accumulated blocks in the current group, seal it
                if current_group_blocks:
                    section_groups.append({
                        "section_type": current_type.value,
                        "section_path": list(current_path),
                        "chunk_title": current_title,
                        "blocks": list(current_group_blocks),
                    })
                    current_group_blocks = []

                current_type = sec_type
                current_path = sec_path
                current_title = title

            current_group_blocks.append(b)

        # Seal final group
        if current_group_blocks:
            section_groups.append({
                "section_type": current_type.value,
                "section_path": list(current_path),
                "chunk_title": current_title,
                "blocks": list(current_group_blocks),
            })

        # 2. Convert section groups into token-controlled chunks
        raw_chunks: List[CandidateChunk] = []

        for grp in section_groups:
            sec_type = grp["section_type"]
            sec_path = grp["section_path"]
            sec_title = grp["chunk_title"]
            grp_blocks = grp["blocks"]

            # Format text and measure tokens
            chunk_text = ChunkFormatter.format_chunk_text(
                section_type=sec_type,
                section_path=sec_path,
                page_start=grp_blocks[0].get("page_number", 1),
                page_end=grp_blocks[-1].get("page_number", 1),
                blocks=grp_blocks,
            )
            tokens = estimate_tokens(chunk_text)

            # Case A: Group fits within hard max token limit
            if tokens <= self.max_tokens:
                c = self._create_candidate_chunk(
                    sec_type, sec_path, sec_title, grp_blocks, tokens
                )
                raw_chunks.append(c)

            # Case B: Group exceeds max_tokens -> split safely at logical boundaries
            else:
                logger.info(
                    "Oversized section [%s] (%d tokens > %d max). Splitting at logical boundaries.",
                    sec_title,
                    tokens,
                    self.max_tokens,
                )
                split_chunks = self._split_oversized_group(
                    sec_type, sec_path, sec_title, grp_blocks
                )
                raw_chunks.extend(split_chunks)

        # 3. Post-process: Merge tiny trailing orphan chunks (< min_tokens) with preceding same-section chunk
        consolidated_chunks = self._merge_tiny_orphans(raw_chunks)
        return consolidated_chunks

    def _create_candidate_chunk(
        self,
        section_type: str,
        section_path: List[str],
        chunk_title: str,
        blocks: List[Dict[str, Any]],
        token_count: Optional[int] = None,
        overlap_from_previous: bool = False,
    ) -> CandidateChunk:
        """Helper to instantiate a CandidateChunk with derived attributes."""
        pages_in_chunk = [b.get("page_number", 1) for b in blocks]
        page_start = min(pages_in_chunk) if pages_in_chunk else 1
        page_end = max(pages_in_chunk) if pages_in_chunk else 1

        contains_table = any(b.get("block_type") == "TABLE" for b in blocks)
        contains_ocr = any(b.get("extraction_method") == "PADDLEOCR" for b in blocks)

        if token_count is None:
            text = ChunkFormatter.format_chunk_text(
                section_type=section_type,
                section_path=section_path,
                page_start=page_start,
                page_end=page_end,
                blocks=blocks,
            )
            token_count = estimate_tokens(text)

        return CandidateChunk(
            section_type=section_type,
            section_path=section_path,
            chunk_title=chunk_title,
            blocks=blocks,
            page_start=page_start,
            page_end=page_end,
            token_count=token_count,
            contains_table=contains_table,
            contains_ocr=contains_ocr,
            overlap_from_previous=overlap_from_previous,
        )

    def _split_oversized_group(
        self,
        section_type: str,
        section_path: List[str],
        chunk_title: str,
        blocks: List[Dict[str, Any]],
    ) -> List[CandidateChunk]:
        """
        Split an oversized section at natural boundaries with controlled overlap.
        Respects proviso bonding and table unity.
        """
        sub_chunks: List[CandidateChunk] = []
        current_sub_blocks: List[Dict[str, Any]] = []
        current_tokens = 0
        part_idx = 1
        overlap_blocks: List[Dict[str, Any]] = []

        for idx, blk in enumerate(blocks):
            blk_text = blk.get("text", "")
            blk_tokens = estimate_tokens(blk_text)

            # Check if adding this block exceeds target tokens
            # BUT do not split if this block is a proviso/exception
            is_proviso = self.is_proviso_or_exception(blk)

            if (current_tokens + blk_tokens) > self.target_tokens and current_sub_blocks and not is_proviso:
                # Seal current sub-chunk
                sub_title = f"{chunk_title} (Part {part_idx})"
                c = self._create_candidate_chunk(
                    section_type=section_type,
                    section_path=section_path,
                    chunk_title=sub_title,
                    blocks=list(current_sub_blocks),
                    overlap_from_previous=(part_idx > 1),
                )
                sub_chunks.append(c)
                part_idx += 1

                # Calculate overlap blocks for context continuity
                overlap_blocks = []
                overlap_toks = 0
                for prev_b in reversed(current_sub_blocks):
                    prev_t = estimate_tokens(prev_b.get("text", ""))
                    if (overlap_toks + prev_t) <= self.overlap_tokens:
                        overlap_blocks.insert(0, prev_b)
                        overlap_toks += prev_t
                    else:
                        break

                current_sub_blocks = list(overlap_blocks)
                current_tokens = sum(estimate_tokens(b.get("text", "")) for b in current_sub_blocks)

            current_sub_blocks.append(blk)
            current_tokens += blk_tokens

        # Seal final remaining sub-chunk
        if current_sub_blocks:
            sub_title = f"{chunk_title} (Part {part_idx})" if part_idx > 1 else chunk_title
            c = self._create_candidate_chunk(
                section_type=section_type,
                section_path=section_path,
                chunk_title=sub_title,
                blocks=list(current_sub_blocks),
                overlap_from_previous=(part_idx > 1),
            )
            sub_chunks.append(c)

        return sub_chunks

    def _merge_tiny_orphans(self, chunks: List[CandidateChunk]) -> List[CandidateChunk]:
        """
        Merge tiny trailing orphan chunks (< min_tokens) into the nearest same-section chunk
        without exceeding max_tokens or crossing distinct section boundaries.
        """
        if len(chunks) <= 1:
            return chunks

        merged: List[CandidateChunk] = []
        skip_indices = set()

        for i in range(len(chunks)):
            if i in skip_indices:
                continue

            current = chunks[i]

            # If current chunk is tiny and next chunk has the same section type
            if current.token_count < self.min_tokens and (i + 1) < len(chunks):
                nxt = chunks[i + 1]
                if nxt.section_type == current.section_type and (current.token_count + nxt.token_count) <= self.max_tokens:
                    # Merge current into next
                    combined_blocks = current.blocks + [b for b in nxt.blocks if b["block_id"] not in {x["block_id"] for x in current.blocks}]
                    merged_chunk = self._create_candidate_chunk(
                        section_type=nxt.section_type,
                        section_path=nxt.section_path,
                        chunk_title=nxt.chunk_title,
                        blocks=combined_blocks,
                    )
                    merged.append(merged_chunk)
                    skip_indices.add(i + 1)
                    continue

            # If current chunk is tiny and previous chunk has the same section type
            if current.token_count < self.min_tokens and merged:
                prev = merged[-1]
                if prev.section_type == current.section_type and (prev.token_count + current.token_count) <= self.max_tokens:
                    combined_blocks = prev.blocks + [b for b in current.blocks if b["block_id"] not in {x["block_id"] for x in prev.blocks}]
                    merged[-1] = self._create_candidate_chunk(
                        section_type=prev.section_type,
                        section_path=prev.section_path,
                        chunk_title=prev.chunk_title,
                        blocks=combined_blocks,
                    )
                    continue

            merged.append(current)

        return merged
