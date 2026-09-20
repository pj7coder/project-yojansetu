from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid
from sqlalchemy.orm import Session

from app.normalization.numbers import parse_indian_number
from app.normalization.schemas import EvidenceRegistryItem
from app.verification.schemas import VerifiableFact


@dataclass
class ResolvedEvidenceItem:
    evidence_id: str
    text: str
    page_number: Optional[int] = None
    block_id: Optional[str] = None
    ocr_risk: bool = False
    table_context: Optional[str] = None


@dataclass
class EvidenceResolutionResult:
    formatted_source_text: str
    raw_texts: List[str] = field(default_factory=list)
    resolved_item_ids: List[str] = field(default_factory=list)
    missing_refs: List[str] = field(default_factory=list)
    ocr_risk: bool = False
    is_missing: bool = False
    is_broken: bool = False
    has_source_conflict: bool = False
    conflict_detail: Optional[str] = None


class EvidenceResolver:
    """
    Resolves evidence references against the draft evidence registry,
    constructs sandboxed context with page/block tags, propagates OCR risk,
    and detects intra-source contradictions across multiple citations.
    """

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def resolve_evidence_refs(
        self,
        evidence_refs: List[str],
        evidence_registry: Dict[str, Any],
        document_id: Optional[uuid.UUID] = None,
        low_confidence_blocks: Optional[Set[str]] = None,
    ) -> Tuple[List[ResolvedEvidenceItem], List[str]]:
        """
        Resolves a list of evidence IDs into structured ResolvedEvidenceItem objects.
        Returns: (resolved_items, broken_refs)
        """
        low_blocks = low_confidence_blocks or set()
        resolved_items: List[ResolvedEvidenceItem] = []
        broken_refs: List[str] = []

        for ref in evidence_refs:
            if ref in evidence_registry:
                entry = evidence_registry[ref]
                if isinstance(entry, dict):
                    text = entry.get("text") or entry.get("raw_text") or ""
                    page = entry.get("page_number")
                    if page is None and entry.get("page_numbers"):
                        page = entry.get("page_numbers")[0]
                    block_id = entry.get("block_id")
                    if block_id is None and entry.get("source_block_ids"):
                        block_id = entry.get("source_block_ids")[0]
                    extraction_method = entry.get("extraction_method") or ""
                    table_context = entry.get("table_context")
                elif isinstance(entry, EvidenceRegistryItem):
                    text = entry.text
                    page = entry.page_numbers[0] if entry.page_numbers else None
                    block_id = entry.source_block_ids[0] if entry.source_block_ids else None
                    extraction_method = entry.extraction_method or ""
                    table_context = None
                else:
                    text = str(entry)
                    page = None
                    block_id = None
                    extraction_method = ""
                    table_context = None

                ocr_risk = False
                if extraction_method and "OCR" in extraction_method.upper():
                    ocr_risk = True
                if block_id and block_id in low_blocks:
                    ocr_risk = True

                resolved_items.append(
                    ResolvedEvidenceItem(
                        evidence_id=ref,
                        text=text,
                        page_number=page,
                        block_id=block_id,
                        ocr_risk=ocr_risk,
                        table_context=table_context,
                    )
                )
            else:
                broken_refs.append(ref)

        return resolved_items, broken_refs

    def detect_source_evidence_conflict(
        self,
        evidence_items: List[ResolvedEvidenceItem],
        fact: Optional[VerifiableFact] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Detects if multiple cited evidence records have contradictory values."""
        if len(evidence_items) < 2:
            return False, None

        extracted_numbers: List[float] = []
        for item in evidence_items:
            num = parse_indian_number(item.text)
            if num is not None:
                extracted_numbers.append(num)

        if len(set(extracted_numbers)) > 1:
            return (
                True,
                f"Contradictory numeric values detected across cited evidence records: {extracted_numbers}",
            )

        return False, None

    @classmethod
    def format_sandboxed_evidence(
        cls,
        evidence_items: List[ResolvedEvidenceItem],
        fact: Optional[VerifiableFact] = None,
    ) -> str:
        """Constructs safe sandboxed source text with explicit page and block boundaries."""
        snippets: List[str] = []
        for item in evidence_items:
            p_str = f"PAGE {item.page_number}" if item.page_number else "PAGE UNKNOWN"
            b_str = f"BLOCK {item.block_id}" if item.block_id else "BLOCK UNKNOWN"
            snippet = f"[{p_str}][{b_str}] {item.text.strip()}"
            if item.table_context:
                snippet += f"\n[TABLE CONTEXT] {item.table_context}"
            snippets.append(snippet)

        body = "\n\n".join(snippets)
        return (
            "BEGIN_UNTRUSTED_GOVERNMENT_SOURCE\n"
            f"{body}\n"
            "END_UNTRUSTED_GOVERNMENT_SOURCE"
        )

    @classmethod
    def resolve(
        cls,
        evidence_refs: List[str],
        evidence_registry: Dict[str, Any],
        low_confidence_blocks: Optional[Set[str]] = None,
    ) -> EvidenceResolutionResult:
        """Classmethod helper for backwards compatibility."""
        resolver = cls()
        items, broken = resolver.resolve_evidence_refs(
            evidence_refs, evidence_registry, low_confidence_blocks=low_confidence_blocks
        )
        if not evidence_refs:
            return EvidenceResolutionResult(formatted_source_text="", is_missing=True)
        if broken:
            return EvidenceResolutionResult(
                formatted_source_text="", missing_refs=broken, is_broken=True
            )

        has_conf, conf_detail = resolver.detect_source_evidence_conflict(items)
        sandboxed = resolver.format_sandboxed_evidence(items)
        return EvidenceResolutionResult(
            formatted_source_text=sandboxed,
            raw_texts=[i.text for i in items],
            resolved_item_ids=[i.evidence_id for i in items],
            ocr_risk=any(i.ocr_risk for i in items),
            has_source_conflict=has_conf,
            conflict_detail=conf_detail,
        )
