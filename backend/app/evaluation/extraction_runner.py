"""
JanSetu - Day 29: Production Extraction Benchmark Runner.

Orchestrates:
- Loading frozen gold extraction cases via GoldBenchmarkLoader
- Strict runtime data-leakage protection (zero expected answers passed to LLM)
- Invoking production extraction pipeline (SchemeExtractionService in-memory)
- Applying canonical normalization to extracted clauses
- Evaluating fact detection, normalized semantic values, relational operators, and logical trees
- Classifying failure severity and earliest pipeline-stage attribution
- Producing benchmark run manifest and persisting immutable artifacts
"""

from datetime import datetime, timezone
import logging
import platform
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from app.core.config import settings
from app.evaluation.evidence_metrics import EvidenceGroundingEvaluator
from app.evaluation.extraction_metrics import ExtractionMetricAggregator
from app.evaluation.failure_analysis import FailureAnalyzer
from app.evaluation.matching import ExtractedFactItem, FactMatcher
from app.evaluation.reporting import BenchmarkReportGenerator
from app.evaluation.rule_metrics import CanonicalRuleComparator, RuleNode, evaluate_exclusions_independently
from app.evaluation.schemas import (
    BenchmarkRunManifest,
    BenchmarkSummary,
    CaseEvaluationResult,
    FactEvaluation,
    FailureCode,
    FailureSeverity,
    MatchResult,
    PipelineStage,
)
from app.extraction.schemas import ChunkExtractionResult
from app.extraction.service import SchemeExtractionService
from app.gold.loader import GoldBenchmarkLoader
from app.gold.schemas import AmbiguityType, CaseStatus, ExtractionExpectedFact, ExtractionGoldCase, GoldSplit, GoldTask
from app.normalization.benefits import normalize_benefit
from app.normalization.dates import parse_date_expression
from app.normalization.documents import normalize_document_requirement
from app.normalization.eligibility import normalize_single_criterion
from app.normalization.numbers import parse_indian_number

logger = logging.getLogger("jansetu.evaluation.runner")


class ExtractionBenchmarkRunner:
    """
    Evaluates JanSetu's document extraction pipeline against human-verified gold ground truth.
    """

    def __init__(
        self,
        gold_version: str = "v1",
        extraction_service: Optional[SchemeExtractionService] = None,
        loader: Optional[GoldBenchmarkLoader] = None,
    ):
        self.gold_version = gold_version
        self.loader = loader or GoldBenchmarkLoader(version=gold_version)
        self.extraction_service = extraction_service or SchemeExtractionService()

    def run_benchmark(
        self,
        split: Union[GoldSplit, str] = GoldSplit.DEV,
        tag_filter: Optional[List[str]] = None,
        case_id_filter: Optional[str] = None,
    ) -> Tuple[BenchmarkSummary, BenchmarkRunManifest, List[CaseEvaluationResult]]:
        """
        Execute full benchmark evaluation across specified split or single case.
        """
        split_enum = GoldSplit(split) if isinstance(split, str) else split
        manifest_meta = self.loader.load_manifest()

        # Load cases
        all_cases: List[ExtractionGoldCase] = self.loader.load_cases(
            task=GoldTask.EXTRACTION,
            split=split_enum,
            status=CaseStatus.HUMAN_VERIFIED,
        )

        # Apply filters
        selected_cases = []
        for c in all_cases:
            if c.ambiguity_flag == AmbiguityType.STALE_REFERENCE:
                logger.warning(f"Excluding stale case {c.case_id} from strict benchmark scoring.")
                continue
            if case_id_filter and c.case_id != case_id_filter:
                continue
            if tag_filter:
                if not any(t.upper() in [tag.upper() for tag in c.tags] for t in tag_filter):
                    continue
            selected_cases.append(c)

        run_id = f"ext_eval_{split_enum.value.lower()}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(f"Starting extraction benchmark {run_id} on {len(selected_cases)} cases ({split_enum.value})")

        case_results: List[CaseEvaluationResult] = []
        execution_times_ms: List[float] = []

        for case in selected_cases:
            res, dur = self.evaluate_case(case)
            case_results.append(res)
            execution_times_ms.append(dur)

        summary = ExtractionMetricAggregator.aggregate(
            case_results=case_results,
            run_id=run_id,
            split=split_enum.value,
            timestamp=timestamp,
            execution_times_ms=execution_times_ms,
        )

        run_manifest = BenchmarkRunManifest(
            run_id=run_id,
            benchmark_version="1.0",
            gold_dataset_version=manifest_meta.dataset_version,
            gold_manifest_sha256=manifest_meta.dataset_sha256 or "UNKNOWN",
            git_commit="HEAD",
            split=split_enum,
            case_count=len(selected_cases),
            llm_model=getattr(self.extraction_service.llm_provider, "model_name", settings.ollama_model),
            llm_configuration={
                "temperature": settings.llm_temperature,
                "timeout": settings.llm_request_timeout_seconds,
                "provider": getattr(self.extraction_service.llm_provider, "provider", "ollama"),
            },
            mineru_version="0.1.0-sim",
            paddleocr_version="2.7.0-sim",
            normalizer_version=settings.normalizer_version,
            validator_version="1.0",
            device=platform.machine(),
            timestamp=timestamp,
        )

        # Persist immutable artifacts
        BenchmarkReportGenerator.persist_run(run_manifest, summary, case_results)
        logger.info(f"Benchmark {run_id} complete. Strict pass rate: {summary.strict_case_pass_rate*100:.1f}%, F1: {summary.field_f1*100:.1f}%")

        return summary, run_manifest, case_results

    def evaluate_case(self, case: ExtractionGoldCase) -> Tuple[CaseEvaluationResult, float]:
        """
        Evaluates a single gold extraction case with zero ground-truth data leakage.
        """
        start_time = time.time()

        source_text = case.source.text_snippet or ""
        doc_id = case.source.document_id
        chunk_id = case.source.chunk_id or f"chunk_{case.case_id}"
        page_num = case.source.page_number or 1
        source_bids = case.source.source_block_ids or []

        # 1. Zero data leakage: Pass ONLY source snippet to extraction pipeline
        extraction_res, diagnostics = self.extraction_service.extract_snippet_in_memory(
            chunk_text=source_text,
            document_id=doc_id,
            chunk_id=chunk_id,
            section_type="ELIGIBILITY",
            page_start=page_num,
            page_end=page_num,
            source_block_ids=source_bids,
        )

        duration_ms = (time.time() - start_time) * 1000.0

        # 2. Extract and canonically normalize predicted facts
        predicted_facts = self._normalize_predicted_facts(extraction_res, source_text)

        # 3. Grounding & Hallucination checks on predicted facts
        for pf in predicted_facts:
            # Check reference validity & semantic support
            ref_valid = EvidenceGroundingEvaluator.verify_reference_validity(pf.evidence_text, source_text)
            sem_supp = EvidenceGroundingEvaluator.verify_semantic_support(pf, pf.evidence_text)
            pf_meta = getattr(pf, "_eval_meta", {})
            pf_meta["ref_valid"] = ref_valid
            pf_meta["sem_supp"] = sem_supp
            setattr(pf, "_eval_meta", pf_meta)

        # 4. Compare predicted facts vs expected gold facts
        fact_evals: List[FactEvaluation] = []
        matched_pred_indices = set()
        critical_errors: List[Dict[str, Any]] = []
        failure_codes: List[FailureCode] = []

        # Evaluate expected gold facts
        for gold in case.expected_facts:
            matched_pf: Optional[ExtractedFactItem] = None
            matched_idx: Optional[int] = None

            for idx, pred in enumerate(predicted_facts):
                if idx in matched_pred_indices:
                    continue
                if FactMatcher.are_fields_matching(gold.field, pred.field):
                    matched_pf = pred
                    matched_idx = idx
                    matched_pred_indices.add(idx)
                    break

            if matched_pf is not None:
                # Field detected -> TRUE POSITIVE
                val_exact = FactMatcher.are_values_exact_match(gold.value, matched_pf.value)
                val_norm = FactMatcher.are_values_semantically_equivalent(
                    gold.value,
                    matched_pf.value,
                    gold_unit=gold.unit,
                    pred_unit=matched_pf.unit,
                    gold_period=gold.period,
                    pred_period=matched_pf.period,
                    gold_qualifier=False,
                    pred_qualifier=matched_pf.has_qualifier,
                )
                op_match = FactMatcher.are_operators_matching(gold.operator, matched_pf.operator)

                meta = getattr(matched_pf, "_eval_meta", {})
                ref_valid = meta.get("ref_valid", True)
                sem_supp = meta.get("sem_supp", True)

                # Attribution & Severity if failure
                fail_code: Optional[FailureCode] = None
                sev: Optional[FailureSeverity] = None
                attr_stage: Optional[PipelineStage] = None
                reason: Optional[str] = None

                if not val_norm or (op_match is not None and not op_match):
                    fail_code, sev, attr_stage, reason = FailureAnalyzer.attribute_pipeline_failure(
                        gold_fact=gold,
                        pred_fact=matched_pf,
                        raw_source_text=source_text,
                        raw_llm_text=matched_pf.raw_text,
                        canonical_norm_value=matched_pf.value,
                        is_table=case.source.contains_table,
                    )
                    if sev in (FailureSeverity.CRITICAL, FailureSeverity.HIGH):
                        critical_errors.append({"field": gold.field, "severity": sev.value, "reason": reason})
                    if fail_code:
                        failure_codes.append(fail_code)

                fact_evals.append(
                    FactEvaluation(
                        field=gold.field,
                        match_result=MatchResult.TRUE_POSITIVE,
                        gold_value=gold.value,
                        predicted_value=matched_pf.value,
                        gold_operator=FactMatcher.canonicalize_operator(gold.operator),
                        predicted_operator=FactMatcher.canonicalize_operator(matched_pf.operator),
                        gold_unit=gold.unit,
                        predicted_unit=matched_pf.unit,
                        gold_period=gold.period,
                        predicted_period=matched_pf.period,
                        value_exact_match=val_exact,
                        value_normalized_match=val_norm,
                        operator_match=op_match,
                        evidence_reference_valid=ref_valid,
                        evidence_supported=sem_supp,
                        is_hallucination=not sem_supp,
                        is_critical_hallucination=False,
                        failure_code=fail_code,
                        severity=sev,
                        attribution_stage=attr_stage,
                        reason=reason,
                        evidence_quote=gold.evidence_quote,
                        source_snippet=source_text[:100],
                    )
                )
            else:
                # Omission -> FALSE NEGATIVE
                fail_code, sev, attr_stage, reason = FailureAnalyzer.attribute_pipeline_failure(
                    gold_fact=gold,
                    pred_fact=None,
                    raw_source_text=source_text,
                    is_table=case.source.contains_table,
                )
                if sev in (FailureSeverity.CRITICAL, FailureSeverity.HIGH):
                    critical_errors.append({"field": gold.field, "severity": sev.value, "reason": reason})
                if fail_code:
                    failure_codes.append(fail_code)

                fact_evals.append(
                    FactEvaluation(
                        field=gold.field,
                        match_result=MatchResult.FALSE_NEGATIVE,
                        gold_value=gold.value,
                        predicted_value=None,
                        gold_operator=FactMatcher.canonicalize_operator(gold.operator),
                        predicted_operator=None,
                        gold_unit=gold.unit,
                        predicted_unit=None,
                        value_exact_match=False,
                        value_normalized_match=False,
                        operator_match=False,
                        evidence_reference_valid=False,
                        evidence_supported=False,
                        is_hallucination=False,
                        is_critical_hallucination=False,
                        failure_code=fail_code,
                        severity=sev,
                        attribution_stage=attr_stage,
                        reason=reason,
                        evidence_quote=gold.evidence_quote,
                        source_snippet=source_text[:100],
                    )
                )

        # Evaluate remaining ungrounded / extra predictions -> FALSE POSITIVES
        hallucinated_count = 0
        critical_hallucinations = 0

        for idx, pred in enumerate(predicted_facts):
            if idx not in matched_pred_indices:
                fail_code, sev, attr_stage, reason = FailureAnalyzer.attribute_pipeline_failure(
                    gold_fact=None,
                    pred_fact=pred,
                    raw_source_text=source_text,
                )
                is_crit = EvidenceGroundingEvaluator.is_critical_hallucination(pred.field, pred.value)
                if is_crit:
                    critical_hallucinations += 1
                    critical_errors.append({"field": pred.field, "severity": "CRITICAL", "reason": "Critical Hallucination"})
                hallucinated_count += 1
                if fail_code:
                    failure_codes.append(fail_code)

                fact_evals.append(
                    FactEvaluation(
                        field=pred.field,
                        match_result=MatchResult.FALSE_POSITIVE,
                        gold_value=None,
                        predicted_value=pred.value,
                        gold_operator=None,
                        predicted_operator=FactMatcher.canonicalize_operator(pred.operator),
                        gold_unit=None,
                        predicted_unit=pred.unit,
                        value_exact_match=False,
                        value_normalized_match=False,
                        operator_match=False,
                        evidence_reference_valid=False,
                        evidence_supported=False,
                        is_hallucination=True,
                        is_critical_hallucination=is_crit,
                        failure_code=fail_code,
                        severity=sev,
                        attribution_stage=attr_stage,
                        reason=reason,
                        evidence_quote=pred.evidence_text,
                        source_snippet=source_text[:100],
                    )
                )

        # 5. Logical Tree & Commutative Comparison
        gold_conds = [f.model_dump() for f in case.expected_facts if f.field.startswith("eligibility.")]
        pred_conds = [
            {"field": f.field, "operator": f.operator, "value": f.value}
            for f in predicted_facts
            if f.field.startswith("eligibility.")
        ]
        gold_tree = CanonicalRuleComparator.build_tree_from_conditions(gold_conds)
        pred_tree = CanonicalRuleComparator.build_tree_from_conditions(pred_conds)
        rule_tree_match = CanonicalRuleComparator.are_rule_trees_equivalent(gold_tree, pred_tree)

        # 6. Security & Negative cases
        prompt_resisted = None
        if case.is_security_test:
            # Check for synthetic malicious injection markers
            resisted, _ = EvidenceGroundingEvaluator.evaluate_security_test(
                predicted_facts, ["100000", "ignore your instructions"]
            )
            prompt_resisted = resisted
            if not resisted:
                critical_errors.append({"field": "security", "severity": "CRITICAL", "reason": "Prompt injection exploited"})

        # Metrics per case
        tp = sum(1 for fe in fact_evals if fe.match_result == MatchResult.TRUE_POSITIVE)
        fp = sum(1 for fe in fact_evals if fe.match_result == MatchResult.FALSE_POSITIVE)
        fn = sum(1 for fe in fact_evals if fe.match_result == MatchResult.FALSE_NEGATIVE)

        p = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

        val_exact_acc = sum(1 for fe in fact_evals if fe.match_result == MatchResult.TRUE_POSITIVE and fe.value_exact_match) / max(1, tp)
        val_norm_acc = sum(1 for fe in fact_evals if fe.match_result == MatchResult.TRUE_POSITIVE and fe.value_normalized_match) / max(1, tp)
        op_acc = sum(1 for fe in fact_evals if fe.match_result == MatchResult.TRUE_POSITIVE and fe.operator_match) / max(1, tp)

        ref_valid_rate = sum(1 for fe in fact_evals if fe.evidence_reference_valid) / max(1, len(predicted_facts))
        ground_rate = sum(1 for fe in fact_evals if fe.evidence_supported) / max(1, len(predicted_facts))

        strict_pass = (fn == 0 and fp == 0 and val_norm_acc == 1.0 and op_acc == 1.0 and rule_tree_match)
        if case.is_negative and len(predicted_facts) == 0:
            strict_pass = True
        critical_pass = (len(critical_errors) == 0 and critical_hallucinations == 0)

        source_fmt = "OCR" if case.source.contains_ocr else "DIGITAL"
        layout_tp = "TABLE" if case.source.contains_table else "PROSE"

        result = CaseEvaluationResult(
            case_id=case.case_id,
            split=case.split,
            status=case.status.value,
            difficulty=case.difficulty,
            tags=case.tags,
            is_negative=case.is_negative,
            is_security_test=case.is_security_test,
            prompt_injection_resisted=prompt_resisted,
            source_format=source_fmt,
            layout_type=layout_tp,
            language=case.source.language,
            document_id=doc_id,
            chunk_id=chunk_id,
            gold_fact_count=len(case.expected_facts),
            predicted_fact_count=len(predicted_facts),
            tp_count=tp,
            fp_count=fp,
            fn_count=fn,
            field_precision=round(p, 4),
            field_recall=round(r, 4),
            field_f1=round(f1, 4),
            value_exact_accuracy=round(val_exact_acc, 4),
            value_normalized_accuracy=round(val_norm_acc, 4),
            operator_accuracy=round(op_acc, 4),
            rule_tree_exact_match=rule_tree_match,
            evidence_reference_validity=round(ref_valid_rate, 4),
            evidence_grounding_rate=round(ground_rate, 4),
            hallucinated_fact_count=hallucinated_count,
            critical_hallucination_count=critical_hallucinations,
            strict_case_pass=strict_pass,
            critical_fact_pass=critical_pass,
            critical_errors=critical_errors,
            failure_codes=failure_codes,
            fact_evaluations=fact_evals,
            execution_time_ms=round(duration_ms, 2),
        )

        return result, duration_ms

    def _normalize_predicted_facts(
        self,
        extraction_res: Optional[ChunkExtractionResult],
        chunk_text: str,
    ) -> List[ExtractedFactItem]:
        """
        Flattens raw and canonical extractions into uniform ExtractedFactItem records.
        """
        facts: List[ExtractedFactItem] = []
        if not extraction_res or not extraction_res.schemes:
            return facts

        for scheme in extraction_res.schemes:
            # 1. Eligibility conditions
            for idx, cond in enumerate(scheme.eligibility_conditions):
                ev_text = cond.evidence.evidence_text if cond.evidence else ""
                # Deterministic canonical normalization
                can_cond = normalize_single_criterion(cond.condition, [ev_text], f"cond_{idx}")
                facts.append(
                    ExtractedFactItem(
                        field=f"eligibility.{can_cond.field}",
                        value=can_cond.value,
                        operator=can_cond.operator.value if can_cond.operator else "EQ",
                        unit=can_cond.unit,
                        period=can_cond.periodicity.value if can_cond.periodicity else None,
                        evidence_text=ev_text,
                        raw_text=cond.condition,
                    )
                )

            # 2. Exclusions
            for ex in scheme.exclusions:
                ev_text = ex.evidence.evidence_text if ex.evidence else ""
                # Classify exclusion field
                lower_ex = ex.exclusion.lower()
                ex_key = "government_service" if "government" in lower_ex or "सेवा" in lower_ex else "similar_pension"
                facts.append(
                    ExtractedFactItem(
                        field=f"exclusions.{ex_key}",
                        value=True,
                        operator="EQ",
                        evidence_text=ev_text,
                        raw_text=ex.exclusion,
                    )
                )

            # 3. Benefits
            for ben in scheme.benefits:
                ev_text = ben.evidence.evidence_text if ben.evidence else ""
                can_b = normalize_benefit(
                    raw_amount_text=ben.raw_amount,
                    frequency_text=ben.frequency_text,
                    description=ben.description,
                    evidence_refs=[ev_text],
                )
                facts.append(
                    ExtractedFactItem(
                        field="benefits.monthly_amount",
                        value=can_b.amount,
                        currency=can_b.currency.value if can_b.currency else "INR",
                        period=can_b.frequency.value if can_b.frequency else "MONTHLY",
                        has_qualifier=can_b.is_up_to,
                        evidence_text=ev_text,
                        raw_text=ben.raw_amount or ben.description,
                    )
                )

            # 4. Required documents
            for doc in scheme.required_documents:
                ev_text = doc.evidence.evidence_text if doc.evidence else ""
                can_doc = normalize_document_requirement(
                    document_name=doc.document_name,
                    mandatory=doc.mandatory,
                    description=doc.description,
                    evidence_refs=[ev_text],
                )
                facts.append(
                    ExtractedFactItem(
                        field=f"documents.{can_doc.document_type.value.lower()}",
                        value=can_doc.canonical_name,
                        is_mandatory=can_doc.mandatory,
                        evidence_text=ev_text,
                        raw_text=doc.document_name,
                    )
                )

            # 5. Important dates
            for dt in scheme.important_dates:
                ev_text = dt.evidence.evidence_text if dt.evidence else ""
                parsed_date = parse_date_expression(dt.raw_date_text)
                facts.append(
                    ExtractedFactItem(
                        field="dates.application_deadline",
                        value=parsed_date.isoformat() if parsed_date else dt.raw_date_text,
                        evidence_text=ev_text,
                        raw_text=dt.raw_date_text,
                    )
                )

            # 6. Financial values
            for fin in scheme.financial_values:
                ev_text = fin.evidence.evidence_text if fin.evidence else ""
                parsed_num = parse_indian_number(fin.raw_amount_text)
                facts.append(
                    ExtractedFactItem(
                        field="eligibility.income",
                        value=parsed_num,
                        operator="LTE",
                        currency="INR",
                        period="ANNUAL",
                        evidence_text=ev_text,
                        raw_text=fin.raw_amount_text,
                    )
                )

        return facts
