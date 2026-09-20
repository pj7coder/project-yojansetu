import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.normalization.numbers import devanagari_to_ascii, parse_indian_number
from app.normalization.operators import detect_operator_and_value
from app.normalization.schemas import OperatorEnum
from app.verification.evidence_resolver import (
    EvidenceResolutionResult,
    ResolvedEvidenceItem,
)
from app.verification.schemas import (
    FactType,
    VerifiableFact,
    VerificationReasonCode,
    VerificationResult,
)


class DeterministicVerifier:
    """
    Executes fast, deterministic validation of facts against resolved evidence text.
    Handles numeric equivalence, operator checks, periodicity, subject mismatch,
    and ensures deterministic contradictions immediately override LLM inference.
    """

    def verify_deterministic(
        self,
        fact: VerifiableFact,
        evidence_items: Union[List[ResolvedEvidenceItem], EvidenceResolutionResult, List[str]],
    ) -> Optional[Tuple[VerificationResult, VerificationReasonCode, str]]:
        """
        Attempt deterministic verification of a single atomic fact.
        Returns:
            (result, reason_code, explanation) if resolved deterministically, or None if LLM is needed.
        """
        # Extract raw texts
        if isinstance(evidence_items, EvidenceResolutionResult):
            raw_texts = evidence_items.raw_texts
        elif isinstance(evidence_items, list):
            raw_texts = [
                item.text if isinstance(item, ResolvedEvidenceItem) else str(item)
                for item in evidence_items
            ]
        else:
            raw_texts = [str(evidence_items)]

        if not raw_texts:
            return (
                VerificationResult.NOT_ENOUGH_EVIDENCE,
                VerificationReasonCode.EVIDENCE_MISSING,
                "No evidence text available for deterministic check.",
            )

        combined_raw_text = " ".join(raw_texts)
        norm_text = devanagari_to_ascii(combined_raw_text)
        text_lower = norm_text.lower()
        canon_val = fact.canonical_value or {}

        # 1. Table Context Check
        table_ctx = fact.table_context or (
            evidence_items[0].table_context
            if evidence_items and isinstance(evidence_items[0], ResolvedEvidenceItem)
            else None
        )
        if table_ctx and ("category" in canon_val or "income" in str(canon_val).lower()):
            for line in combined_raw_text.splitlines():
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2:
                        cat_name, limit_text = parts[0], parts[1]
                        fact_cat = canon_val.get("category", "")
                        if fact_cat and fact_cat.lower() in cat_name.lower():
                            row_num = parse_indian_number(limit_text)
                            claim_num = canon_val.get("value") or parse_indian_number(
                                fact.statement
                            )
                            if row_num is not None and claim_num is not None:
                                if abs(row_num - claim_num) < 0.001:
                                    return (
                                        VerificationResult.SUPPORTED,
                                        VerificationReasonCode.DIRECT_MATCH,
                                        f"Table row '{cat_name}' matches claimed limit {claim_num}.",
                                    )
                                else:
                                    return (
                                        VerificationResult.CONTRADICTED,
                                        VerificationReasonCode.VALUE_CONFLICT,
                                        f"Table row '{cat_name}' specifies limit {row_num}, contradicting claimed {claim_num}.",
                                    )

        # 2. Periodicity Check (Monthly vs Annual)
        is_source_monthly = any(
            w in text_lower for w in ["प्रति माह", "मासिक", "monthly", "per month"]
        )
        is_source_annual = any(
            w in text_lower
            for w in ["वार्षिक", "प्रति वर्ष", "annual", "per annum", "yearly"]
        )

        fact_period = (
            canon_val.get("periodicity")
            or canon_val.get("period")
            or canon_val.get("frequency")
        )
        if fact_period or "ANNUAL" in fact.statement.upper() or "MONTHLY" in fact.statement.upper():
            period_str = (
                str(fact_period).upper()
                if fact_period
                else ("ANNUAL" if "ANNUAL" in fact.statement.upper() else "MONTHLY")
            )
            if "ANNUAL" in period_str and is_source_monthly and not is_source_annual:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.PERIOD_CONFLICT,
                    "Evidence specifies monthly periodicity, but canonical fact asserts annual.",
                )
            if "MONTHLY" in period_str and is_source_annual and not is_source_monthly:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.PERIOD_CONFLICT,
                    "Evidence specifies annual periodicity, but canonical fact asserts monthly.",
                )

        # 3. Subject Mismatch Check (Family vs Applicant Personal Income)
        fact_field = canon_val.get("field", "").lower()
        if not fact_field:
            if "applicant_income" in fact.statement or "personal income" in fact.statement.lower():
                fact_field = "applicant_income"
            elif "family_income" in fact.statement or "family income" in fact.statement.lower():
                fact_field = "family_income"

        if "family_income" in fact_field:
            if "व्यक्तिगत आय" in text_lower or "applicant income" in text_lower:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.SUBJECT_MISMATCH,
                    "Evidence specifies applicant personal income, but canonical fact asserts family income.",
                )
        elif "applicant_income" in fact_field or "personal_income" in fact_field:
            if "पारिवारिक आय" in text_lower or "family income" in text_lower:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.SUBJECT_MISMATCH,
                    "Evidence specifies family income, but canonical fact asserts applicant personal income.",
                )

        # 4. Logical Connector Check (AND vs OR)
        if fact.fact_type == FactType.LOGICAL_CONNECTOR:
            claimed_connector = canon_val.get("group_type") or (
                "OR" if " OR" in fact.statement.upper() else "AND"
            )
            has_or_word = any(
                w in text_lower
                for w in [" या ", " अथवा ", " or ", "या ", "or "]
            )
            has_and_word = any(
                w in text_lower
                for w in [" तथा ", " एवं ", " और ", " and "]
            )

            if claimed_connector == "AND" and has_or_word and not has_and_word:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.LOGICAL_CONNECTOR_CONFLICT,
                    "Evidence specifies disjunctive (OR) relationship, but canonical tree asserts conjunctive (AND).",
                )
            if claimed_connector == "OR" and has_or_word:
                return (
                    VerificationResult.SUPPORTED,
                    VerificationReasonCode.NORMALIZED_EQUIVALENCE,
                    "Disjunctive (OR) logical connector is directly supported by evidence.",
                )
            if claimed_connector == "AND" and has_and_word:
                return (
                    VerificationResult.SUPPORTED,
                    VerificationReasonCode.NORMALIZED_EQUIVALENCE,
                    "Conjunctive (AND) logical connector is directly supported by evidence.",
                )

        # 5. Exclusion Negation Check
        if fact.fact_type == FactType.EXCLUSION:
            is_eligible_claimed = canon_val.get("eligible", False)
            if "eligible" in fact.statement.lower() and "not eligible" not in fact.statement.lower():
                is_eligible_claimed = True

            has_negation = any(
                w in text_lower
                for w in [
                    "नहीं",
                    "पात्र नहीं",
                    "shall not be eligible",
                    "not eligible",
                    "disqualified",
                    "वर्जित",
                ]
            )
            if is_eligible_claimed and has_negation:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.NEGATION_CONFLICT,
                    "Evidence specifies disqualification/non-eligibility, but fact asserts eligibility.",
                )

        # 6. Required Document Mandatory vs Optional Check
        if fact.fact_type == FactType.DOCUMENT or "mandatory" in str(canon_val).lower():
            is_mandatory_claimed = canon_val.get("is_mandatory") or canon_val.get("mandatory")
            if is_mandatory_claimed is None and "mandatory=true" in fact.statement.lower():
                is_mandatory_claimed = True

            has_optional_wording = any(
                w in text_lower
                for w in ["वैकल्पिक", "optional", "may submit", "may provide", "may be used"]
            )
            if is_mandatory_claimed is True and has_optional_wording:
                return (
                    VerificationResult.CONTRADICTED,
                    VerificationReasonCode.OPERATOR_CONFLICT,
                    "Evidence indicates document is optional or discretionary, but canonical fact asserts mandatory=True.",
                )

        # 7. Date Format Equivalence Check
        if fact.fact_type == FactType.DATE or "date" in str(canon_val).lower():
            date_claim = canon_val.get("date") or canon_val.get("normalized_date")
            m_date = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', combined_raw_text)
            if m_date and date_claim:
                d, m, y = m_date.groups()
                formatted_src_date = f"{y}-{int(m):02d}-{int(d):02d}"
                if formatted_src_date == str(date_claim):
                    return (
                        VerificationResult.SUPPORTED,
                        VerificationReasonCode.NORMALIZED_EQUIVALENCE,
                        f"Source date '{m_date.group(0)}' corresponds to canonical '{date_claim}'.",
                    )

        # 8. Numeric & Operator Check
        numeric_val = canon_val.get("value")
        if numeric_val is None:
            numeric_val = canon_val.get("amount")
        if numeric_val is None:
            # Try to parse from statement
            m_num = re.search(r'(?:<=|>=|<|>|==|=)\s*(?:₹)?([0-9,]+)', fact.statement)
            if m_num:
                numeric_val = parse_indian_number(m_num.group(1))

        if isinstance(numeric_val, (int, float)):
            evidence_num = parse_indian_number(combined_raw_text)
            if evidence_num is not None:
                # Direct Contradiction: numbers disagree
                if abs(evidence_num - numeric_val) > 0.001:
                    return (
                        VerificationResult.CONTRADICTED,
                        VerificationReasonCode.VALUE_CONFLICT,
                        f"Evidence specifies numeric value {evidence_num}, contradicting canonical fact value {numeric_val}.",
                    )

                # Numbers match! Now check operator consistency
                canon_op = canon_val.get("operator")
                if not canon_op:
                    if ">=" in fact.statement:
                        canon_op = "GTE"
                    elif "<=" in fact.statement:
                        canon_op = "LTE"
                    elif ">" in fact.statement:
                        canon_op = "GT"
                    elif "<" in fact.statement:
                        canon_op = "LT"
                    elif "==" in fact.statement or "=" in fact.statement:
                        canon_op = "EQ"

                detected_op, _, _ = detect_operator_and_value(combined_raw_text)

                # Check strict operator contradictions
                # e.g. evidence says "older than 60" (GT) but fact asserts ">= 60" (GTE)
                if (
                    "older than" in text_lower
                    or "above 60" in text_lower
                    or "strictly above" in text_lower
                ) and canon_op == "GTE":
                    return (
                        VerificationResult.CONTRADICTED,
                        VerificationReasonCode.OPERATOR_CONFLICT,
                        "Evidence specifies strict greater-than (>), contradicting greater-than-or-equal (>=).",
                    )

                # e.g. evidence says "up to" (LTE) but fact asserts "exactly" (EQ)
                if (
                    "up to" in text_lower
                    or "अधिकतम" in text_lower
                ) and canon_op == "EQ":
                    return (
                        VerificationResult.CONTRADICTED,
                        VerificationReasonCode.OPERATOR_CONFLICT,
                        "Evidence specifies 'up to' maximum ceiling, contradicting exact equality.",
                    )

                # Hindi negation "से अधिक नहीं" supports <= / LTE, contradicts > / GT
                if "से अधिक नहीं" in text_lower or "से ज्यादा नहीं" in text_lower or "not exceeding" in text_lower or "not more than" in text_lower:
                    if canon_op in ["GT", "GTE"] and canon_op != "LTE":
                        if canon_op == "GT":
                            return (
                                VerificationResult.CONTRADICTED,
                                VerificationReasonCode.OPERATOR_CONFLICT,
                                "Evidence specifies negation limit (<=), contradicting strict greater-than (>).",
                            )
                    elif canon_op == "LTE":
                        return (
                            VerificationResult.SUPPORTED,
                            VerificationReasonCode.NORMALIZED_EQUIVALENCE,
                            f"Negation limit (<= {numeric_val}) matches evidence directly.",
                        )

                # Hindi "वर्ष या अधिक" / "or older" / "or more" supports GTE
                if (
                    "या अधिक" in text_lower
                    or "or older" in text_lower
                    or "or more" in text_lower
                    or "न्यूनतम" in text_lower
                    or "at least" in text_lower
                ) and canon_op == "GTE":
                    return (
                        VerificationResult.SUPPORTED,
                        VerificationReasonCode.NORMALIZED_EQUIVALENCE,
                        f"Evidence directly supports greater-than-or-equal (>= {numeric_val}).",
                    )

                # If detected operator matches
                if detected_op and canon_op and detected_op.value == canon_op:
                    return (
                        VerificationResult.SUPPORTED,
                        VerificationReasonCode.NUMERIC_MATCH,
                        f"Numeric value ({numeric_val}) and operator ({canon_op}) match evidence.",
                    )

                return (
                    VerificationResult.SUPPORTED,
                    VerificationReasonCode.NORMALIZED_EQUIVALENCE,
                    f"Normalized numeric value {numeric_val} corresponds to evidence {evidence_num}.",
                )

        return None

    @classmethod
    def verify(
        cls,
        fact: VerifiableFact,
        resolution: EvidenceResolutionResult,
    ) -> Optional[Tuple[VerificationResult, VerificationReasonCode, str]]:
        """Class method compatibility wrapper."""
        verifier = cls()
        return verifier.verify_deterministic(fact, resolution)
