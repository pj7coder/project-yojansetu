from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Set

from app.chunking.formatter import ChunkFormatter

logger = logging.getLogger("jansetu.chunking.validator")


class ChunkValidationError(Exception):
    """Raised when chunk validation fails quality or coverage invariants."""
    pass


@dataclass
class ValidationReport:
    """Detailed summary of chunk validation and quality metrics."""
    is_valid: bool
    total_blocks: int
    included_blocks: int
    excluded_boilerplate_blocks: int
    unassigned_blocks: int
    unassigned_block_ids: List[str] = field(default_factory=list)
    number_of_chunks: int = 0
    average_tokens: int = 0
    max_tokens: int = 0
    min_tokens: int = 0
    chunks_with_tables: int = 0
    chunks_with_ocr: int = 0
    unknown_section_chunks: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_diagnostics_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_blocks": self.total_blocks,
            "included_blocks": self.included_blocks,
            "excluded_boilerplate_blocks": self.excluded_boilerplate_blocks,
            "unassigned_blocks": self.unassigned_blocks,
            "number_of_chunks": self.number_of_chunks,
            "average_tokens": self.average_tokens,
            "max_tokens": self.max_tokens,
            "min_tokens": self.min_tokens,
            "chunks_with_tables": self.chunks_with_tables,
            "chunks_with_ocr": self.chunks_with_ocr,
            "unknown_section_chunks": self.unknown_section_chunks,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ChunkValidator:
    """
    Enforces coverage, continuity, token limit, and quality invariants
    on generated document chunks.
    """

    @classmethod
    def validate(
        cls,
        all_blocks: List[Dict[str, Any]],
        candidate_chunks: List[Any],
        hard_max_tokens: int = 8000,
    ) -> ValidationReport:
        """
        Validate all candidate chunks against input blocks.

        Args:
            all_blocks: All raw blocks from the input document pages
            candidate_chunks: List of CandidateChunk objects produced by SemanticSplitter
            hard_max_tokens: Configured hard ceiling for chunk tokens

        Returns:
            ValidationReport with full coverage statistics and quality diagnostics
        """
        errors: List[str] = []
        warnings: List[str] = []

        all_block_map = {b["block_id"]: b for b in all_blocks if "block_id" in b}
        total_blocks = len(all_block_map)

        # 1. Identify boilerplate blocks
        boilerplate_ids: Set[str] = {
            bid for bid, b in all_block_map.items() if ChunkFormatter.is_boilerplate(b)
        }

        # 2. Gather included block IDs and duplicate checks
        chunk_block_ids: Set[str] = set()
        seen_in_non_overlap: Set[str] = set()

        for idx, chunk in enumerate(candidate_chunks):
            # Check empty chunk
            if not chunk.blocks:
                errors.append(f"Chunk at index {idx} has no blocks.")
            
            chunk_bids = [b["block_id"] for b in chunk.blocks if "block_id" in b]
            if not chunk_bids and chunk.blocks:
                errors.append(f"Chunk at index {idx} contains blocks without block_id.")

            # Duplicate block validation across non-overlapping chunks
            if not chunk.overlap_from_previous:
                duplicates = seen_in_non_overlap.intersection(chunk_bids)
                if duplicates:
                    warnings.append(
                        f"Chunk {idx} contains {len(duplicates)} blocks already present in earlier non-overlap chunks: {list(duplicates)[:3]}"
                    )
                seen_in_non_overlap.update(chunk_bids)

            chunk_block_ids.update(chunk_bids)

            # 3. Page continuity validation
            if chunk.page_start > chunk.page_end:
                errors.append(
                    f"Chunk {idx} page range invalid: page_start ({chunk.page_start}) > page_end ({chunk.page_end})"
                )

            for blk in chunk.blocks:
                p_num = blk.get("page_number", chunk.page_start)
                if p_num < chunk.page_start or p_num > chunk.page_end:
                    errors.append(
                        f"Chunk {idx} block {blk.get('block_id')} page {p_num} outside chunk range [{chunk.page_start}, {chunk.page_end}]"
                    )

            # 4. Token limit validation
            if chunk.token_count > hard_max_tokens:
                warnings.append(
                    f"Chunk {idx} token count ({chunk.token_count}) exceeds hard max ({hard_max_tokens}). CHUNK_REVIEW_REQUIRED flagged."
                )

        # 5. Coverage calculation
        included_blocks = len(chunk_block_ids)
        excluded_boilerplate_blocks = len(boilerplate_ids - chunk_block_ids)
        unassigned_ids = list(set(all_block_map.keys()) - chunk_block_ids - boilerplate_ids)
        unassigned_blocks = len(unassigned_ids)

        if unassigned_blocks > 0:
            errors.append(
                f"Coverage failure: {unassigned_blocks} non-boilerplate blocks were not assigned to any chunk: {unassigned_ids[:5]}"
            )

        # 6. Quality metrics
        num_chunks = len(candidate_chunks)
        token_counts = [c.token_count for c in candidate_chunks]
        avg_tokens = int(sum(token_counts) / num_chunks) if num_chunks > 0 else 0
        max_tokens = max(token_counts) if token_counts else 0
        min_tokens = min(token_counts) if token_counts else 0

        chunks_with_tables = sum(1 for c in candidate_chunks if c.contains_table)
        chunks_with_ocr = sum(1 for c in candidate_chunks if c.contains_ocr)
        unknown_sections = sum(1 for c in candidate_chunks if c.section_type == "UNKNOWN")

        is_valid = (len(errors) == 0)

        report = ValidationReport(
            is_valid=is_valid,
            total_blocks=total_blocks,
            included_blocks=included_blocks,
            excluded_boilerplate_blocks=excluded_boilerplate_blocks,
            unassigned_blocks=unassigned_blocks,
            unassigned_block_ids=unassigned_ids,
            number_of_chunks=num_chunks,
            average_tokens=avg_tokens,
            max_tokens=max_tokens,
            min_tokens=min_tokens,
            chunks_with_tables=chunks_with_tables,
            chunks_with_ocr=chunks_with_ocr,
            unknown_section_chunks=unknown_sections,
            errors=errors,
            warnings=warnings,
        )

        if not is_valid:
            logger.error("Chunk validation failed with %d errors: %s", len(errors), errors)
        else:
            logger.info(
                "Chunk validation passed. %d chunks generated, 0 unassigned blocks. Avg tokens: %d",
                num_chunks,
                avg_tokens,
            )

        return report
