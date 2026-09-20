import logging
import re
import unicodedata
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.database.models.department import Department
from app.extraction.schemas import EvidenceItem, SchemeRawExtraction
from app.normalization.schemas import (
    CanonicalIdentity,
    CanonicalScope,
    EvidenceRegistryItem,
    SchemeNameDetail,
    SchemeOriginEnum,
)

logger = logging.getLogger("yojansetu.normalization.aggregator")


def clean_normalized_name(name: str) -> str:
    """Normalize scheme name for deduplication and candidate matching."""
    if not name:
        return ""
    # Unicode NFKC normalization
    nfkc = unicodedata.normalize("NFKC", name)
    # Lowercase, replace multiple whitespace and punctuation
    cleaned = re.sub(r'[\s_]+', ' ', nfkc).strip().lower()
    return cleaned


class DocumentSchemeAggregator:
    """
    Aggregates chunk-level raw extractions for a document into discrete scheme candidate bundles,
    building an immutable, auditable evidence registry with complete provenance.
    """

    def __init__(self, departments: Optional[List[Department]] = None):
        self.departments = departments or []

    def match_department(self, dept_text: Optional[str]) -> Tuple[Optional[str], Optional[uuid.UUID]]:
        """Attempt high-confidence deterministic match against known department registry."""
        if not dept_text or not self.departments:
            return None, None

        cleaned_query = clean_normalized_name(dept_text)
        for dept in self.departments:
            if dept.code and dept.code.lower() in cleaned_query:
                return dept.name_en, dept.id
            if dept.name_en and clean_normalized_name(dept.name_en) in cleaned_query:
                return dept.name_en, dept.id
            if dept.name_hi and clean_normalized_name(dept.name_hi) in cleaned_query:
                return dept.name_en, dept.id

        return None, None

    def group_schemes_from_chunks(
        self,
        document_id: str,
        doc_code: str,
        chunk_extractions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Scan all chunk extraction payloads for a document.
        Group extracted facts by distinct scheme candidate.
        If document has 0 schemes, returns empty list ([]).
        """
        # Collect all raw scheme blocks with their source chunk context
        candidates_by_name: Dict[str, Dict[str, Any]] = {}
        unassociated_chunks: List[Dict[str, Any]] = []

        for chunk_payload in chunk_extractions:
            c_id = chunk_payload.get("chunk_id", "")
            schemes_in_chunk = chunk_payload.get("schemes", [])

            if not schemes_in_chunk:
                continue

            for raw_scheme in schemes_in_chunk:
                s_name = raw_scheme.get("scheme_name")
                if not s_name:
                    unassociated_chunks.append({
                        "chunk_id": c_id,
                        "raw_scheme": raw_scheme,
                    })
                    continue

                norm_key = clean_normalized_name(s_name)
                if norm_key not in candidates_by_name:
                    candidates_by_name[norm_key] = {
                        "primary_name": s_name,
                        "raw_schemes": [],
                        "chunks_seen": set(),
                        "departments_seen": set(),
                    }

                candidates_by_name[norm_key]["raw_schemes"].append(raw_scheme)
                candidates_by_name[norm_key]["chunks_seen"].add(c_id)
                dept = raw_scheme.get("department")
                if dept:
                    candidates_by_name[norm_key]["departments_seen"].add(dept)

        # Handle unassociated facts if single scheme exists in doc
        if len(candidates_by_name) == 1 and unassociated_chunks:
            single_key = list(candidates_by_name.keys())[0]
            for unassoc in unassociated_chunks:
                candidates_by_name[single_key]["raw_schemes"].append(unassoc["raw_scheme"])
                candidates_by_name[single_key]["chunks_seen"].add(unassoc["chunk_id"])
        elif len(candidates_by_name) > 1 and unassociated_chunks:
            # Multi-scheme document with ambiguous unassociated chunks: mark review flag
            logger.warning(
                "Document %s has %d schemes and %d unassociated fact chunks",
                document_id,
                len(candidates_by_name),
                len(unassociated_chunks),
            )

        if not candidates_by_name:
            # Zero schemes detected
            return []

        # Package discrete scheme bundles
        scheme_bundles = []
        seq = 1
        for norm_key, cdata in candidates_by_name.items():
            primary_name = cdata["primary_name"]
            internal_code = f"RJ-DRAFT-{uuid.uuid4().hex[:8].upper()}"

            # Aggregate departments
            dept_text = list(cdata["departments_seen"])[0] if cdata["departments_seen"] else None
            matched_dept_name, matched_dept_id = self.match_department(dept_text)

            bundle = {
                "sequence": seq,
                "internal_scheme_code": internal_code,
                "primary_name": primary_name,
                "normalized_name": norm_key,
                "department_raw": dept_text,
                "matched_department_name": matched_dept_name,
                "matched_department_id": str(matched_dept_id) if matched_dept_id else None,
                "raw_schemes": cdata["raw_schemes"],
                "chunks_seen": list(cdata["chunks_seen"]),
                "requires_association_review": len(candidates_by_name) > 1 and bool(unassociated_chunks),
            }
            scheme_bundles.append(bundle)
            seq += 1

        return scheme_bundles

    def build_evidence_registry_for_bundle(
        self,
        document_id: str,
        bundle: Dict[str, Any],
    ) -> Tuple[Dict[str, EvidenceRegistryItem], Dict[str, str]]:
        """
        Build the immutable Evidence Registry for a scheme draft.
        Returns:
            (evidence_registry, snippet_to_id_map)
        """
        registry: Dict[str, EvidenceRegistryItem] = {}
        snippet_to_id: Dict[str, str] = {}
        evid_counter = 1

        for raw_s in bundle.get("raw_schemes", []):
            # Gather all evidence items across all sub-fields
            evidence_items: List[Dict[str, Any]] = []

            for p in raw_s.get("purpose", []):
                evidence_items.append(p)
            for tb in raw_s.get("target_beneficiaries", []):
                evidence_items.append(tb)
            for cond in raw_s.get("eligibility_conditions", []):
                if isinstance(cond, dict) and "evidence" in cond:
                    evidence_items.append(cond["evidence"])
            for excl in raw_s.get("exclusions", []):
                if isinstance(excl, dict) and "evidence" in excl:
                    evidence_items.append(excl["evidence"])
            for ben in raw_s.get("benefits", []):
                if isinstance(ben, dict) and "evidence" in ben:
                    evidence_items.append(ben["evidence"])
            for doc in raw_s.get("required_documents", []):
                if isinstance(doc, dict) and "evidence" in doc:
                    evidence_items.append(doc["evidence"])
            for step in raw_s.get("application_process", []):
                if isinstance(step, dict) and "evidence" in step:
                    evidence_items.append(step["evidence"])
            for d in raw_s.get("important_dates", []):
                if isinstance(d, dict) and "evidence" in d:
                    evidence_items.append(d["evidence"])
            for fr in raw_s.get("financial_values", []):
                if isinstance(fr, dict) and "evidence" in fr:
                    evidence_items.append(fr["evidence"])
            for cont in raw_s.get("contacts", []):
                if isinstance(cont, dict) and "evidence" in cont:
                    evidence_items.append(cont["evidence"])

            for item in evidence_items:
                if not isinstance(item, dict):
                    continue
                ev_text = item.get("evidence_text", "").strip()
                if not ev_text:
                    continue

                if ev_text not in snippet_to_id:
                    ev_id = f"EVID-{evid_counter:03d}"
                    evid_counter += 1
                    snippet_to_id[ev_text] = ev_id

                    registry[ev_id] = EvidenceRegistryItem(
                        evidence_id=ev_id,
                        document_id=document_id,
                        chunk_id=item.get("chunk_id"),
                        page_numbers=item.get("page_numbers", []),
                        source_block_ids=item.get("source_block_ids", []),
                        text=ev_text,
                        raw_value=item.get("value"),
                        extraction_method=item.get("extraction_method", "LLM"),
                    )

        return registry, snippet_to_id
