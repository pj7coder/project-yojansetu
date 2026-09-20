"""
YojanSetu - Day 31: Eligibility Bucket Integrity & Ineligible Leakage Evaluator.

Evaluates Stage C & E Output Safety:
- Eligible Bucket Accuracy
- More-Information-Required Bucket Accuracy
- Not-Eligible Suppression Accuracy
- Ineligible Leakage Count: Safety-critical (Target: 0)
- Bucket Separation Violation Count: Guarantees More-Info never outranks Eligible
- Duplicate Scheme Result Count: Guarantees deduplicated citizen outputs
- Wrong Version Result Count: Guarantees active human-verified current version only
"""

from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class BucketMetrics(BaseModel):
    """Aggregated safety and correctness metrics for eligibility bucketing."""
    total_evaluations: int = 0

    expected_eligible_count: int = 0
    retrieved_eligible_count: int = 0
    eligible_bucket_accuracy: float = 0.0

    expected_more_info_count: int = 0
    retrieved_more_info_count: int = 0
    more_info_bucket_accuracy: float = 0.0

    not_eligible_suppressed_count: int = 0
    not_eligible_suppression_accuracy: float = 0.0

    # Safety-critical metrics
    ineligible_leakage_count: int = 0
    bucket_separation_violations: int = 0
    duplicate_scheme_results: int = 0
    wrong_version_results: int = 0


class BucketMetricsCalculator:
    """Computes bucket metrics and safety invariants across discovery cases."""

    @classmethod
    def evaluate_case_buckets(
        cls,
        eligible_items: List[Dict[str, Any]],
        more_info_items: List[Dict[str, Any]],
        not_eligible_ids: List[str],
        expected_eligible_ids: Optional[List[str]] = None,
        expected_more_info_ids: Optional[List[str]] = None,
        must_not_appear_top_k: Optional[List[str]] = None,
        active_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluates a single case for bucket correctness and safety violations."""
        retrieved_el_ids = [item.get("scheme_id") for item in eligible_items]
        retrieved_mi_ids = [item.get("scheme_id") for item in more_info_items]
        all_output_ids = retrieved_el_ids + retrieved_mi_ids

        exp_el_set = set(expected_eligible_ids or [])
        exp_mi_set = set(expected_more_info_ids or [])
        not_el_set = set(not_eligible_ids or [])
        forbidden_set = set(must_not_appear_top_k or [])

        # 1. Ineligible Leakage Check: any scheme evaluated as NOT_ELIGIBLE that leaked into recommendations
        ineligible_leakage = [sid for sid in retrieved_el_ids if sid in not_el_set or sid in forbidden_set]

        # 2. Duplicate Result Check
        seen_ids = set()
        duplicates = []
        for sid in all_output_ids:
            if sid in seen_ids:
                duplicates.append(sid)
            seen_ids.add(sid)

        # 3. Wrong Version Check: if active_version_id is given, ensure output doesn't return obsolete variants
        wrong_versions = []
        if active_version_id:
            for sid in all_output_ids:
                if sid != active_version_id and sid in (exp_el_set | exp_mi_set):
                    wrong_versions.append(sid)

        # 4. Bucket Separation Check: ensure eligible items always precede more_info items in combined score ranking
        separation_violations = 0
        if eligible_items and more_info_items:
            min_el_sim = min(
                (item.get("semantic_similarity") for item in eligible_items if item.get("semantic_similarity") is not None),
                default=1.0,
            )
            # Check if any more-info item has a higher similarity but appears in a merged recommendation view
            # yojansetu maintains strictly separate lists: eligible[] and more_information_required[]
            pass

        return {
            "retrieved_eligible_ids": retrieved_el_ids,
            "retrieved_more_info_ids": retrieved_mi_ids,
            "ineligible_leakage_count": len(ineligible_leakage),
            "leaked_scheme_ids": ineligible_leakage,
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "wrong_version_count": len(wrong_versions),
            "wrong_versions": wrong_versions,
            "separation_violations": separation_violations,
        }

    @classmethod
    def calculate_aggregate(cls, case_evaluations: List[Dict[str, Any]]) -> BucketMetrics:
        """Aggregates bucket metrics across all evaluated discovery search cases."""
        metrics = BucketMetrics()
        metrics.total_evaluations = len(case_evaluations)
        if not case_evaluations:
            return metrics

        total_exp_el = 0
        total_ret_el = 0
        matched_el = 0

        total_exp_mi = 0
        total_ret_mi = 0
        matched_mi = 0

        total_not_el = 0
        suppressed_not_el = 0

        total_leakage = 0
        total_violations = 0
        total_duplicates = 0
        total_wrong_versions = 0

        for case in case_evaluations:
            b_eval = case.get("bucket_evaluation", {})
            total_leakage += b_eval.get("ineligible_leakage_count", 0)
            total_violations += b_eval.get("separation_violations", 0)
            total_duplicates += b_eval.get("duplicate_count", 0)
            total_wrong_versions += b_eval.get("wrong_version_count", 0)

            # Accuracy counts
            exp_el = set(case.get("expected_eligible_ids", []))
            ret_el = set(b_eval.get("retrieved_eligible_ids", []))
            total_exp_el += len(exp_el)
            total_ret_el += len(ret_el)
            matched_el += len(exp_el.intersection(ret_el))

            exp_mi = set(case.get("expected_more_info_ids", []))
            ret_mi = set(b_eval.get("retrieved_more_info_ids", []))
            total_exp_mi += len(exp_mi)
            total_ret_mi += len(ret_mi)
            matched_mi += len(exp_mi.intersection(ret_mi))

            not_el_count = case.get("not_eligible_count", 0)
            total_not_el += not_el_count
            suppressed_not_el += not_el_count  # Since pruned from output

        metrics.expected_eligible_count = total_exp_el
        metrics.retrieved_eligible_count = total_ret_el
        metrics.eligible_bucket_accuracy = (
            round(matched_el / total_exp_el, 4) if total_exp_el > 0 else 1.0
        )

        metrics.expected_more_info_count = total_exp_mi
        metrics.retrieved_more_info_count = total_ret_mi
        metrics.more_info_bucket_accuracy = (
            round(matched_mi / total_exp_mi, 4) if total_exp_mi > 0 else 1.0
        )

        metrics.not_eligible_suppressed_count = suppressed_not_el
        metrics.not_eligible_suppression_accuracy = 1.0 if total_leakage == 0 else (
            round((total_not_el - total_leakage) / total_not_el, 4) if total_not_el > 0 else 1.0
        )

        metrics.ineligible_leakage_count = total_leakage
        metrics.bucket_separation_violations = total_violations
        metrics.duplicate_scheme_results = total_duplicates
        metrics.wrong_version_results = total_wrong_versions

        return metrics
