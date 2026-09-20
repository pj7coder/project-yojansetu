import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

from app.extraction.schemas import ChunkExtractionResult, EvidenceItem

logger = logging.getLogger("yojansetu.extraction.evidence_validator")


class EvidenceValidator:
    """
    Deterministically validates evidence snippets extracted by the LLM against the source chunk text,
    page boundaries, and block IDs.
    """

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Light normalization for reliable substring comparison."""
        if not text:
            return ""
        # 1. Unicode NFC normalization
        normalized = unicodedata.normalize("NFC", text)
        # 2. Lowercase and collapse consecutive whitespace
        normalized = re.sub(r"\s+", " ", normalized.lower()).strip()
        return normalized

    @classmethod
    def validate_evidence_item(
        cls,
        evidence: EvidenceItem,
        normalized_chunk_text: str,
        page_start: int,
        page_end: int,
        valid_block_ids: Set[str],
        chunk_id: str,
    ) -> Tuple[str, Optional[str]]:
        """
        Validate a single evidence item.

        Returns:
            Tuple of (status_string, error_detail_or_none)
        """
        evidence.chunk_id = chunk_id

        # 1. Check evidence text presence
        snippet = evidence.evidence_text.strip()
        if not snippet:
            evidence.validation_status = "EVIDENCE_MATCH_FAILED"
            return "EVIDENCE_MATCH_FAILED", "Empty evidence text snippet"

        normalized_snippet = cls.normalize_text(snippet)
        if normalized_snippet not in normalized_chunk_text:
            evidence.validation_status = "EVIDENCE_MATCH_FAILED"
            return "EVIDENCE_MATCH_FAILED", f"Evidence snippet '{snippet[:60]}...' not found in chunk text"

        # 2. Check page range continuity
        if evidence.page_numbers:
            invalid_pages = [p for p in evidence.page_numbers if p < page_start or p > page_end]
            if invalid_pages:
                evidence.validation_status = "PAGE_MISMATCH"
                return "PAGE_MISMATCH", f"Evidence pages {invalid_pages} outside chunk bounds [{page_start}, {page_end}]"
        else:
            # Default to chunk page bounds if omitted by model
            evidence.page_numbers = list(range(page_start, page_end + 1))

        # 3. Check source block IDs if returned
        if evidence.source_block_ids:
            invalid_blocks = [bid for bid in evidence.source_block_ids if bid not in valid_block_ids]
            if invalid_blocks:
                evidence.validation_status = "BLOCK_MISMATCH"
                return "BLOCK_MISMATCH", f"Evidence block IDs {invalid_blocks} not found in chunk"

        evidence.validation_status = "MATCHED"
        return "MATCHED", None

    @classmethod
    def validate_chunk_result(
        cls,
        extraction_result: ChunkExtractionResult,
        chunk_text: str,
        page_start: int,
        page_end: int,
        valid_block_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Scan all domain extractions in the result and validate every evidence item.

        Returns:
            Diagnostics summary dict with match statistics and violation details.
        """
        normalized_chunk_text = cls.normalize_text(chunk_text)
        block_id_set = set(valid_block_ids)

        total_facts = 0
        valid_facts = 0
        failed_facts = 0
        violations: List[Dict[str, Any]] = []

        for scheme in extraction_result.schemes:
            # Gather all evidence items across all domain fields
            evidence_items: List[Tuple[str, EvidenceItem]] = []

            for p in scheme.purpose:
                evidence_items.append(("purpose", p))
            for b in scheme.target_beneficiaries:
                evidence_items.append(("target_beneficiaries", b))
            for cond in scheme.eligibility_conditions:
                evidence_items.append(("eligibility_conditions", cond.evidence))
            for excl in scheme.exclusions:
                evidence_items.append(("exclusions", excl.evidence))
            for ben in scheme.benefits:
                evidence_items.append(("benefits", ben.evidence))
            for doc in scheme.required_documents:
                evidence_items.append(("required_documents", doc.evidence))
            for step in scheme.application_process:
                evidence_items.append(("application_process", step.evidence))
            for dt in scheme.important_dates:
                evidence_items.append(("important_dates", dt.evidence))
            for fin in scheme.financial_values:
                evidence_items.append(("financial_values", fin.evidence))
            for con in scheme.contacts:
                evidence_items.append(("contacts", con.evidence))
            for ref in scheme.references:
                evidence_items.append(("references", ref.evidence))
            for amd in scheme.amendments:
                evidence_items.append(("amendments", amd.evidence))

            for field_name, item in evidence_items:
                total_facts += 1
                status, err = cls.validate_evidence_item(
                    evidence=item,
                    normalized_chunk_text=normalized_chunk_text,
                    page_start=page_start,
                    page_end=page_end,
                    valid_block_ids=block_id_set,
                    chunk_id=extraction_result.chunk_id,
                )
                if status == "MATCHED":
                    valid_facts += 1
                else:
                    failed_facts += 1
                    violations.append({
                        "field": field_name,
                        "status": status,
                        "snippet": item.evidence_text[:80],
                        "error": err,
                    })

        all_passed = (failed_facts == 0)

        diagnostics = {
            "all_passed": all_passed,
            "facts_extracted": total_facts,
            "facts_with_valid_evidence": valid_facts,
            "facts_evidence_failed": failed_facts,
            "violations": violations,
        }

        if not all_passed:
            logger.warning(
                "Chunk %s extraction has %d evidence verification violations: %s",
                extraction_result.chunk_id,
                failed_facts,
                [v["error"] for v in violations[:3]],
            )

        return diagnostics
