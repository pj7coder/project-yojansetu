"""
YojanSetu - Day 29: Benchmark Metric Aggregation & Multi-Dimensional Breakdowns.

Aggregates:
- Field Precision, Recall, F1
- Value Exact and Normalized Accuracy
- Operator and Logical Tree Accuracy
- Grounding and Hallucination Rates
- Critical Safety Error Counts
- Category, Format, Layout, Language, and Difficulty Breakdowns
"""

from collections import defaultdict
from typing import Any, Dict, List

from app.evaluation.schemas import (
    BenchmarkSummary,
    CaseEvaluationResult,
    FailureCode,
    FailureSeverity,
    MatchResult,
)


class ExtractionMetricAggregator:
    """
    Aggregates per-case evaluation results into comprehensive multi-dimensional benchmark summaries.
    """

    @classmethod
    def aggregate(
        cls,
        case_results: List[CaseEvaluationResult],
        run_id: str,
        split: str,
        timestamp: str,
        execution_times_ms: List[float],
    ) -> BenchmarkSummary:
        total_cases = len(case_results)
        if total_cases == 0:
            return BenchmarkSummary(
                run_id=run_id,
                split=split,
                timestamp=timestamp,
                total_cases=0,
                strict_case_pass_count=0,
                strict_case_pass_rate=0.0,
                critical_fact_pass_count=0,
                critical_fact_pass_rate=0.0,
                total_gold_facts=0,
                total_predicted_facts=0,
                total_tp=0,
                total_fp=0,
                total_fn=0,
                field_precision=0.0,
                field_recall=0.0,
                field_f1=0.0,
                value_exact_accuracy=0.0,
                value_normalized_accuracy=0.0,
                operator_accuracy=0.0,
                logical_connector_accuracy=0.0,
                rule_tree_exact_match_rate=0.0,
                evidence_reference_validity=1.0,
                evidence_grounding_rate=1.0,
                hallucination_rate=0.0,
                critical_hallucination_count=0,
            )

        strict_passes = sum(1 for c in case_results if c.strict_case_pass)
        critical_passes = sum(1 for c in case_results if c.critical_fact_pass)

        total_gold = sum(c.gold_fact_count for c in case_results)
        total_pred = sum(c.predicted_fact_count for c in case_results)
        total_tp = sum(c.tp_count for c in case_results)
        total_fp = sum(c.fp_count for c in case_results)
        total_fn = sum(c.fn_count for c in case_results)

        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Fact-level aggregations
        exact_matches = 0
        norm_matches = 0
        op_comparisons = 0
        op_matches = 0
        ref_valid_count = 0
        grounded_count = 0
        total_hallucinations = 0
        total_critical_hallucinations = 0

        safety_error_counts = {
            "age_threshold_errors": 0,
            "income_threshold_errors": 0,
            "percentage_threshold_errors": 0,
            "and_or_connector_errors": 0,
            "lost_not_errors": 0,
            "missed_exclusions": 0,
            "invented_exclusions": 0,
            "benefit_amount_errors": 0,
            "wrong_application_channel": 0,
            "wrong_dates": 0,
        }

        failure_counts: Dict[str, int] = defaultdict(int)
        attribution_counts: Dict[str, int] = defaultdict(int)

        # Breakdowns
        cat_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"gold": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0, "norm_match": 0})
        format_stats: Dict[str, List[CaseEvaluationResult]] = defaultdict(list)
        layout_stats: Dict[str, List[CaseEvaluationResult]] = defaultdict(list)
        lang_stats: Dict[str, List[CaseEvaluationResult]] = defaultdict(list)
        diff_stats: Dict[str, List[CaseEvaluationResult]] = defaultdict(list)

        prompt_injection_total = 0
        prompt_injection_passed = 0

        for c in case_results:
            format_stats[c.source_format].append(c)
            layout_stats[c.layout_type].append(c)
            lang_stats[c.language].append(c)
            diff_stats[c.difficulty.value].append(c)

            if c.is_security_test:
                prompt_injection_total += 1
                if c.prompt_injection_resisted:
                    prompt_injection_passed += 1

            for fc in c.failure_codes:
                failure_counts[fc.value] += 1

            for fe in c.fact_evaluations:
                # Attribution
                if fe.attribution_stage:
                    attribution_counts[fe.attribution_stage.value] += 1

                # Value matches
                if fe.match_result == MatchResult.TRUE_POSITIVE:
                    if fe.value_exact_match:
                        exact_matches += 1
                    if fe.value_normalized_match:
                        norm_matches += 1
                    if fe.operator_match is not None:
                        op_comparisons += 1
                        if fe.operator_match:
                            op_matches += 1

                # Evidence & Grounding
                if fe.evidence_reference_valid:
                    ref_valid_count += 1
                if fe.evidence_supported:
                    grounded_count += 1

                if fe.is_hallucination:
                    total_hallucinations += 1
                if fe.is_critical_hallucination:
                    total_critical_hallucinations += 1

                # Safety errors tracking
                fn = fe.field.lower()
                if fe.severity == FailureSeverity.CRITICAL or not fe.value_normalized_match:
                    if "age" in fn:
                        safety_error_counts["age_threshold_errors"] += 1
                    elif "income" in fn:
                        safety_error_counts["income_threshold_errors"] += 1
                    elif "percent" in fn:
                        safety_error_counts["percentage_threshold_errors"] += 1
                    elif "exclusion" in fn:
                        if fe.match_result == MatchResult.FALSE_NEGATIVE:
                            safety_error_counts["missed_exclusions"] += 1
                        elif fe.match_result == MatchResult.FALSE_POSITIVE:
                            safety_error_counts["invented_exclusions"] += 1
                    elif "benefit" in fn or "pension" in fn or "amount" in fn:
                        safety_error_counts["benefit_amount_errors"] += 1
                    elif "channel" in fn or "sso" in fn or "emitra" in fn:
                        safety_error_counts["wrong_application_channel"] += 1
                    elif "date" in fn or "deadline" in fn:
                        safety_error_counts["wrong_dates"] += 1

                if fe.failure_code == FailureCode.LLM_WRONG_LOGICAL_CONNECTOR:
                    safety_error_counts["and_or_connector_errors"] += 1
                elif fe.failure_code == FailureCode.LLM_NEGATION_ERROR:
                    safety_error_counts["lost_not_errors"] += 1

                # Category breakdown mapping
                domain = fn.split('.')[0] if '.' in fn else "other"
                if "eligibility" in domain:
                    # sub-split eligibility
                    if "age" in fn:
                        cat_key = "eligibility_age"
                    elif "income" in fn:
                        cat_key = "eligibility_income"
                    elif "domicile" in fn or "residency" in fn:
                        cat_key = "eligibility_location"
                    elif "bpl" in fn:
                        cat_key = "eligibility_bpl"
                    elif "disability" in fn:
                        cat_key = "eligibility_disability"
                    elif "land" in fn:
                        cat_key = "eligibility_land"
                    elif "caste" in fn or "category" in fn:
                        cat_key = "eligibility_social_category"
                    elif "occupation" in fn:
                        cat_key = "eligibility_occupation"
                    else:
                        cat_key = "eligibility_other"
                elif "exclusion" in domain:
                    cat_key = "exclusions"
                elif "benefit" in domain:
                    cat_key = "benefits"
                elif "document" in domain:
                    cat_key = "documents"
                elif "application" in domain:
                    cat_key = "application"
                elif "date" in domain:
                    cat_key = "dates"
                elif "financial" in domain:
                    cat_key = "financial"
                elif "contact" in domain:
                    cat_key = "contacts"
                elif "amendment" in domain:
                    cat_key = "amendments"
                else:
                    cat_key = "scheme_identity"

                if fe.match_result == MatchResult.TRUE_POSITIVE:
                    cat_stats[cat_key]["gold"] += 1
                    cat_stats[cat_key]["pred"] += 1
                    cat_stats[cat_key]["tp"] += 1
                    if fe.value_normalized_match:
                        cat_stats[cat_key]["norm_match"] += 1
                elif fe.match_result == MatchResult.FALSE_NEGATIVE:
                    cat_stats[cat_key]["gold"] += 1
                    cat_stats[cat_key]["fn"] += 1
                elif fe.match_result == MatchResult.FALSE_POSITIVE:
                    cat_stats[cat_key]["pred"] += 1
                    cat_stats[cat_key]["fp"] += 1

        val_exact_acc = exact_matches / total_tp if total_tp > 0 else 1.0
        val_norm_acc = norm_matches / total_tp if total_tp > 0 else 1.0
        op_acc = op_matches / op_comparisons if op_comparisons > 0 else 1.0
        rule_tree_rate = sum(1 for c in case_results if c.rule_tree_exact_match) / total_cases

        ref_validity_rate = ref_valid_count / total_pred if total_pred > 0 else 1.0
        grounding_rate = grounded_count / total_pred if total_pred > 0 else 1.0
        hallucination_rate = total_hallucinations / total_pred if total_pred > 0 else 0.0

        # Sub-group metric helper
        def compute_group_metrics(group_cases: List[CaseEvaluationResult]) -> Dict[str, float]:
            if not group_cases:
                return {"count": 0, "f1": 0.0, "value_acc": 0.0, "strict_pass": 0.0}
            g_tp = sum(c.tp_count for c in group_cases)
            g_fp = sum(c.fp_count for c in group_cases)
            g_fn = sum(c.fn_count for c in group_cases)
            g_p = g_tp / (g_tp + g_fp) if (g_tp + g_fp) > 0 else 1.0
            g_r = g_tp / (g_tp + g_fn) if (g_tp + g_fn) > 0 else 1.0
            g_f1 = 2 * g_p * g_r / (g_p + g_r) if (g_p + g_r) > 0 else 0.0
            g_val = sum(c.value_normalized_accuracy for c in group_cases) / len(group_cases)
            g_pass = sum(1 for c in group_cases if c.strict_case_pass) / len(group_cases)
            return {
                "count": len(group_cases),
                "precision": round(g_p, 4),
                "recall": round(g_r, 4),
                "f1": round(g_f1, 4),
                "value_accuracy": round(g_val, 4),
                "strict_pass_rate": round(g_pass, 4),
            }

        cat_breakdown: Dict[str, Dict[str, float]] = {}
        for k, v in cat_stats.items():
            p = v["tp"] / (v["tp"] + v["fp"]) if (v["tp"] + v["fp"]) > 0 else 1.0
            r = v["tp"] / (v["tp"] + v["fn"]) if (v["tp"] + v["fn"]) > 0 else 1.0
            f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
            vm = v["norm_match"] / v["tp"] if v["tp"] > 0 else 1.0
            cat_breakdown[k] = {
                "gold_count": v["gold"],
                "pred_count": v["pred"],
                "precision": round(p, 4),
                "recall": round(r, 4),
                "f1": round(f, 4),
                "value_accuracy": round(vm, 4),
            }

        # Execution times
        sorted_times = sorted(execution_times_ms) if execution_times_ms else [0.0]
        p50 = sorted_times[len(sorted_times) // 2]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        avg_time = sum(sorted_times) / len(sorted_times) if sorted_times else 0.0

        return BenchmarkSummary(
            run_id=run_id,
            split=split,
            timestamp=timestamp,
            total_cases=total_cases,
            strict_case_pass_count=strict_passes,
            strict_case_pass_rate=round(strict_passes / total_cases, 4),
            critical_fact_pass_count=critical_passes,
            critical_fact_pass_rate=round(critical_passes / total_cases, 4),
            total_gold_facts=total_gold,
            total_predicted_facts=total_pred,
            total_tp=total_tp,
            total_fp=total_fp,
            total_fn=total_fn,
            field_precision=round(precision, 4),
            field_recall=round(recall, 4),
            field_f1=round(f1, 4),
            value_exact_accuracy=round(val_exact_acc, 4),
            value_normalized_accuracy=round(val_norm_acc, 4),
            operator_accuracy=round(op_acc, 4),
            logical_connector_accuracy=round(1.0 - (safety_error_counts["and_or_connector_errors"] / max(1, total_cases)), 4),
            rule_tree_exact_match_rate=round(rule_tree_rate, 4),
            evidence_reference_validity=round(ref_validity_rate, 4),
            evidence_grounding_rate=round(grounding_rate, 4),
            hallucination_rate=round(hallucination_rate, 4),
            critical_hallucination_count=total_critical_hallucinations,
            critical_safety_errors=safety_error_counts,
            failure_taxonomy_counts=dict(failure_counts),
            pipeline_attribution_counts=dict(attribution_counts),
            category_metrics=cat_breakdown,
            format_breakdown={k: compute_group_metrics(v) for k, v in format_stats.items()},
            layout_breakdown={k: compute_group_metrics(v) for k, v in layout_stats.items()},
            language_breakdown={k: compute_group_metrics(v) for k, v in lang_stats.items()},
            difficulty_breakdown={k: compute_group_metrics(v) for k, v in diff_stats.items()},
            prompt_injection_resistance={
                "total_security_cases": prompt_injection_total,
                "resisted_cases": prompt_injection_passed,
                "resistance_rate": round(prompt_injection_passed / prompt_injection_total, 4) if prompt_injection_total > 0 else 1.0,
            },
            performance={
                "avg_case_ms": round(avg_time, 2),
                "p50_case_ms": round(p50, 2),
                "p95_case_ms": round(p95, 2),
                "total_benchmark_seconds": round(sum(sorted_times) / 1000.0, 2),
            },
        )
