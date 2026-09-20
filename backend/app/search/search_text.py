import hashlib
from typing import Any, Dict, List


def compute_search_text_hash(text: str) -> str:
    """Computes SHA-256 hash of normalized search text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class SchemeSearchTextBuilder:
    """
    Constructs a concise, rich, bilingual searchable document for a verified scheme.
    Used for generating semantic dense vector embeddings.
    Combines verified English and Hindi identity, scope, eligibility themes, and benefits.
    """

    @classmethod
    def build_search_text(cls, canonical_scheme: Dict[str, Any]) -> str:
        # Unwrap if wrapped inside verified artifact
        scheme = canonical_scheme.get("canonical_scheme") or canonical_scheme.get("scheme") or canonical_scheme

        parts: List[str] = []

        # 1. Scheme Identity & Official Names
        identity = scheme.get("scheme_identity") or scheme.get("identity") or {}
        name_obj = identity.get("name") or identity.get("official_name") or {}
        if isinstance(name_obj, dict):
            name_en = name_obj.get("en") or name_obj.get("english")
            name_hi = name_obj.get("hi") or name_obj.get("hindi")
            name_raw = name_obj.get("raw")
        else:
            name_en = str(name_obj)
            name_hi = identity.get("official_name_hi")
            name_raw = identity.get("official_name_raw")

        titles = [t for t in [name_en, name_hi, name_raw] if t]
        if titles:
            parts.append(f"Scheme: {' / '.join(dict.fromkeys(titles))}")

        short_name = identity.get("short_name")
        if short_name:
            parts.append(f"Abbreviation: {short_name}")

        category = identity.get("category")
        if category:
            parts.append(f"Category: {category}")

        dept = identity.get("department")
        if isinstance(dept, dict):
            dept_name = dept.get("department_name") or dept.get("raw_text")
            if dept_name:
                parts.append(f"Department: {dept_name}")
        elif dept:
            parts.append(f"Department: {dept}")

        desc = identity.get("description")
        if desc:
            parts.append(f"Purpose: {desc}")

        # 2. Scope & Target Beneficiaries
        scope = scheme.get("scope", {})
        target_bens = identity.get("target_beneficiaries", []) or scope.get("target_beneficiaries", []) or scope.get("beneficiary_group", [])
        if target_bens:
            parts.append(f"Target Beneficiaries: {', '.join(target_bens)}")

        state = scope.get("state") or identity.get("jurisdiction")
        if isinstance(state, list):
            state = ", ".join(state)
        if state:
            parts.append(f"State: {state}")

        districts = scope.get("districts", [])
        if districts:
            parts.append(f"Districts: {', '.join(districts)}")

        rural_urban = scope.get("rural_urban")
        if rural_urban and rural_urban not in ("BOTH", "UNKNOWN"):
            parts.append(f"Applicable to: {rural_urban} areas")

        # 3. Eligibility Themes
        eligibility = scheme.get("eligibility", {})
        root_rule = eligibility.get("root_rule", {})
        cond_summaries = cls._extract_condition_summaries(root_rule)
        if cond_summaries:
            parts.append(f"Key Eligibility Requirements: {'; '.join(cond_summaries)}")

        # 4. Exclusions
        exclusions = scheme.get("exclusions", [])
        excl_texts = [e.get("raw_text") for e in exclusions if e.get("raw_text")]
        if excl_texts:
            parts.append(f"Disqualifications: {'; '.join(excl_texts[:3])}")

        # 5. Benefits Summary
        benefits = scheme.get("benefits", [])
        benefit_texts = []
        for b in benefits:
            b_desc = b.get("description") or b.get("raw_text")
            b_type = b.get("type", "")
            b_amt = b.get("amount")
            if b_amt:
                curr = b.get("currency", "INR")
                freq = b.get("frequency") or b.get("periodicity", "")
                benefit_texts.append(f"{b_type}: {curr} {b_amt} {freq}".strip())
            elif b_desc:
                benefit_texts.append(b_desc)

        if benefit_texts:
            parts.append(f"Benefits Entitlements: {'; '.join(benefit_texts)}")

        return "\n".join(parts)

    @classmethod
    def _extract_condition_summaries(cls, node: Dict[str, Any]) -> List[str]:
        if not node:
            return []
        summaries: List[str] = []
        node_type = str(node.get("group_type") or node.get("type", "")).upper()

        if node_type in ("AND", "OR", "NOT"):
            for child in node.get("children", []):
                summaries.extend(cls._extract_condition_summaries(child))
        else:
            field = node.get("field")
            op = node.get("operator")
            val = node.get("value")
            raw = node.get("raw_text")
            if raw:
                summaries.append(raw)
            elif field and op:
                summaries.append(f"{field} {op} {val}")

        return summaries[:6]
