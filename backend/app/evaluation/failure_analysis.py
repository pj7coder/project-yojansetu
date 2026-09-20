"""
JanSetu - Day 29: Failure Analysis, Criticality Classification & Pipeline-Stage Attribution.

Implements:
- Deterministic severity classification (CRITICAL, HIGH, MEDIUM, LOW)
- Stable failure taxonomy assignment (Phase 21)
- Pipeline-stage failure attribution across OCR, Chunking, LLM, Normalization, Evidence linking (Phase 22)
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.evaluation.matching import ExtractedFactItem, FactMatcher
from app.evaluation.schemas import FailureCode, FailureSeverity, PipelineStage
from app.gold.schemas import ExtractionExpectedFact


class FailureAnalyzer:
    """
    Deterministic failure classifier attributing errors to specific pipeline stages
    and assessing citizen safety criticality.
    """

    @classmethod
    def classify_severity(
        cls,
        field_name: str,
        gold_value: Any,
        pred_value: Any,
        is_operator_error: bool = False,
        is_connector_error: bool = False,
        is_missed_exclusion: bool = False,
        is_invented_exclusion: bool = False,
        is_lost_not: bool = False,
    ) -> FailureSeverity:
        """
        Determines failure severity based on impact on citizen eligibility or material benefit.
        """
        fn = field_name.lower()

        # 1. Critical Errors
        if is_operator_error:
            # Boundary shift in age/income is always critical
            if any(k in fn for k in ("age", "income", "percentage", "amount", "land")):
                return FailureSeverity.CRITICAL
            return FailureSeverity.HIGH

        if is_connector_error or is_lost_not or is_missed_exclusion or is_invented_exclusion:
            return FailureSeverity.CRITICAL

        if "age" in fn or "income" in fn or "pension" in fn or "benefit" in fn:
            # Check numeric delta
            if isinstance(gold_value, (int, float)) and isinstance(pred_value, (int, float)):
                if gold_value != pred_value:
                    return FailureSeverity.CRITICAL
            return FailureSeverity.CRITICAL

        if "exclusion" in fn:
            return FailureSeverity.CRITICAL

        # 2. High Severity
        if "document" in fn or "channel" in fn or "deadline" in fn or "effective_date" in fn:
            return FailureSeverity.HIGH

        # 3. Medium Severity
        if "contact" in fn or "office" in fn or "qualifier" in fn:
            return FailureSeverity.MEDIUM

        # 4. Low Severity default
        return FailureSeverity.LOW

    @classmethod
    def attribute_pipeline_failure(
        cls,
        gold_fact: Optional[ExtractionExpectedFact],
        pred_fact: Optional[ExtractedFactItem],
        raw_source_text: Optional[str] = None,
        ocr_text: Optional[str] = None,
        raw_llm_text: Optional[str] = None,
        canonical_norm_value: Optional[Any] = None,
        is_table: bool = False,
    ) -> Tuple[FailureCode, FailureSeverity, PipelineStage, str]:
        """
        Pinpoints the earliest failing stage in the document processing pipeline.

        Stages evaluated in order:
        1. Parsing / OCR (corrupted digits, table layout destruction)
        2. Chunking (clause split across chunks, boundary truncations)
        3. LLM Extraction (hallucination, omission, wrong operator, wrong value)
        4. Normalization (number parser error, unit conversion mistake)
        5. Evidence linking (ungrounded reference)
        """
        # Case A: False Negative (Omission)
        if gold_fact and not pred_fact:
            field = gold_fact.field
            sev = cls.classify_severity(field, gold_fact.value, None)

            # Check if text was present in source snippet
            if raw_source_text and gold_fact.evidence_quote:
                quote_in_source = gold_fact.evidence_quote.lower() in raw_source_text.lower()
                if not quote_in_source:
                    return (
                        FailureCode.CHUNK_BOUNDARY_ERROR,
                        sev,
                        PipelineStage.CHUNKING,
                        f"Evidence quote '{gold_fact.evidence_quote[:40]}...' missing from chunk text",
                    )

            if is_table:
                return (
                    FailureCode.OCR_TABLE_STRUCTURE_ERROR,
                    sev,
                    PipelineStage.PARSING_OCR,
                    f"Omission in tabular structure for field '{field}'",
                )

            return (
                FailureCode.LLM_FIELD_OMISSION,
                sev,
                PipelineStage.LLM_EXTRACTION,
                f"LLM omitted expected gold fact '{field}'",
            )

        # Case B: False Positive (Hallucination)
        if pred_fact and not gold_fact:
            field = pred_fact.field
            is_crit = FactMatcher.canonicalize_field_name(field) in (
                "eligibility.age", "eligibility.income", "benefits.monthly_amount", "exclusions.government_service"
            )
            sev = FailureSeverity.CRITICAL if is_crit else FailureSeverity.HIGH
            return (
                FailureCode.LLM_HALLUCINATION,
                sev,
                PipelineStage.LLM_EXTRACTION,
                f"LLM hallucinated unsupported fact '{field}' with value '{pred_fact.value}'",
            )

        # Case C: Both Present - Value or Operator Mismatch
        assert gold_fact is not None and pred_fact is not None
        field = gold_fact.field

        # 1. Operator Mismatch
        if gold_fact.operator and pred_fact.operator:
            if not FactMatcher.are_operators_matching(gold_fact.operator, pred_fact.operator):
                sev = cls.classify_severity(field, gold_fact.value, pred_fact.value, is_operator_error=True)
                return (
                    FailureCode.LLM_WRONG_OPERATOR,
                    sev,
                    PipelineStage.LLM_EXTRACTION,
                    f"Operator mismatch: expected {gold_fact.operator}, got {pred_fact.operator}",
                )

        # 2. Value Mismatch
        if not FactMatcher.are_values_semantically_equivalent(gold_fact.value, pred_fact.value):
            sev = cls.classify_severity(field, gold_fact.value, pred_fact.value)

            # Check if OCR corrupted the text first:
            # If official source text contains the gold value, but OCR text has a corrupted number
            if ocr_text and raw_source_text:
                from app.normalization.numbers import parse_indian_number
                src_num = parse_indian_number(raw_source_text)
                ocr_num = parse_indian_number(ocr_text)
                if (
                    (str(gold_fact.value) in raw_source_text or src_num == gold_fact.value)
                    and (str(gold_fact.value) not in ocr_text and ocr_num != gold_fact.value)
                ):
                    return (
                        FailureCode.OCR_NUMERIC_ERROR,
                        sev,
                        PipelineStage.PARSING_OCR,
                        f"OCR corrupted numeric text for {field}: '{gold_fact.value}' corrupted in OCR text '{ocr_text}'",
                    )

            # Check if LLM extracted the correct string, but canonical normalizer failed
            if raw_llm_text:
                from app.normalization.numbers import parse_indian_number
                llm_num = parse_indian_number(raw_llm_text)
                if str(gold_fact.value) in raw_llm_text or llm_num == gold_fact.value:
                    if canonical_norm_value is not None and canonical_norm_value != gold_fact.value:
                        return (
                            FailureCode.NUMBER_NORMALIZATION_ERROR,
                            sev,
                            PipelineStage.NORMALIZATION,
                            f"Canonical normalizer failed to parse correct raw LLM text: '{raw_llm_text}' -> '{canonical_norm_value}'",
                        )

            # Check if unit/frequency mismatched
            if gold_fact.period and pred_fact.period and gold_fact.period.upper() != pred_fact.period.upper():
                return (
                    FailureCode.UNIT_NORMALIZATION_ERROR,
                    sev,
                    PipelineStage.NORMALIZATION,
                    f"Period mismatch for {field}: expected {gold_fact.period}, got {pred_fact.period}",
                )

            return (
                FailureCode.LLM_WRONG_VALUE,
                sev,
                PipelineStage.LLM_EXTRACTION,
                f"LLM extracted incorrect value for {field}: expected {gold_fact.value}, got {pred_fact.value}",
            )

        # Case D: Evidence link error
        return (
            FailureCode.EVIDENCE_LINK_ERROR,
            FailureSeverity.LOW,
            PipelineStage.EVIDENCE_VERIFICATION,
            "Evidence citation unverified or weakly linked",
        )
