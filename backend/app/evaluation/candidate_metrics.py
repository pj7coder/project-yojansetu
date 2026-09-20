"""
YojanSetu - Day 31: Candidate Filter Metrics & High-Recall Safety Evaluator.

Evaluates Stage B (SQL Candidate Filtering):
- Candidate Recall: Fraction of gold-relevant schemes preserved in candidate pool
- Candidate Precision: Efficiency of candidate pool
- Unknown-Field Candidate Recall: High-recall safety on UNKNOWN citizen attributes
- Unknown Profile Filter False Negatives: Safety violation counter (must be 0)
- Known Disqualifying Filter Accuracy: Proper exclusion of impossible schemes
"""

from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class CandidateMetrics(BaseModel):
    """Aggregated metrics for Stage B SQL Candidate Filtering."""
    total_cases_evaluated: int = 0
    total_gold_relevant_schemes: int = 0
    candidate_surviving_relevant_schemes: int = 0
    candidate_recall: float = 0.0
    candidate_precision: float = 0.0
    avg_candidates_per_case: float = 0.0

    # Unknown-field high-recall safety invariants
    cases_with_unknown_fields: int = 0
    unknown_field_relevant_schemes: int = 0
    unknown_field_surviving_schemes: int = 0
    unknown_field_candidate_recall: float = 0.0
    unknown_profile_filter_false_negatives: int = 0

    # Known disqualifying filters
    cases_with_known_disqualifications: int = 0
    known_disqualifying_accuracy: float = 0.0


class CandidateMetricsCalculator:
    """Computes CandidateMetrics across evaluated discovery search cases."""

    @classmethod
    def calculate(cls, case_evaluations: List[Dict[str, Any]]) -> CandidateMetrics:
        """
        Calculates Stage B candidate filtering metrics.

        Each item in case_evaluations should contain:
        - sql_candidates: List[str]
        - gold_relevant_scheme_ids: List[str]
        - profile: Optional[Dict[str, Any]]
        - is_known_disqualification: bool
        - disqualification_respected: bool
        """
        metrics = CandidateMetrics()
        metrics.total_cases_evaluated = len(case_evaluations)
        if not case_evaluations:
            return metrics

        total_candidates_count = 0
        total_relevant = 0
        surviving_relevant = 0
        total_relevant_in_candidates = 0

        unknown_cases_count = 0
        unknown_total_rel = 0
        unknown_surviving_rel = 0
        unknown_false_negatives = 0

        disqual_cases = 0
        disqual_correct = 0

        for case in case_evaluations:
            candidates: Set[str] = set(case.get("sql_candidates", []))
            gold_relevant: Set[str] = set(case.get("gold_relevant_scheme_ids", []))
            profile: Dict[str, Any] = case.get("profile") or {}

            total_candidates_count += len(candidates)
            total_relevant += len(gold_relevant)

            # Relevant schemes that survived SQL filtering
            surviving = gold_relevant.intersection(candidates)
            surviving_relevant += len(surviving)

            # Precision: how many candidates are relevant
            total_relevant_in_candidates += len(surviving)

            # Check unknown-field safety
            # If profile has UNKNOWN or None for critical fields
            has_unknown_fields = any(
                profile.get(field) in (None, "UNKNOWN", "")
                for field in ("district", "family_income", "occupation", "bpl_status")
            ) or not profile

            if has_unknown_fields and gold_relevant:
                unknown_cases_count += 1
                unknown_total_rel += len(gold_relevant)
                unknown_surv = len(gold_relevant.intersection(candidates))
                unknown_surviving_rel += unknown_surv

                missed = gold_relevant - candidates
                if missed:
                    unknown_false_negatives += len(missed)

            # Known disqualification check
            if case.get("is_known_disqualification"):
                disqual_cases += 1
                if case.get("disqualification_respected"):
                    disqual_correct += 1

        metrics.total_gold_relevant_schemes = total_relevant
        metrics.candidate_surviving_relevant_schemes = surviving_relevant
        metrics.candidate_recall = (
            round(surviving_relevant / total_relevant, 4) if total_relevant > 0 else 1.0
        )
        metrics.candidate_precision = (
            round(total_relevant_in_candidates / total_candidates_count, 4)
            if total_candidates_count > 0 else 0.0
        )
        metrics.avg_candidates_per_case = (
            round(total_candidates_count / len(case_evaluations), 2)
            if case_evaluations else 0.0
        )

        # Unknown field metrics
        metrics.cases_with_unknown_fields = unknown_cases_count
        metrics.unknown_field_relevant_schemes = unknown_total_rel
        metrics.unknown_field_surviving_schemes = unknown_surviving_rel
        metrics.unknown_field_candidate_recall = (
            round(unknown_surviving_rel / unknown_total_rel, 4)
            if unknown_total_rel > 0 else 1.0
        )
        metrics.unknown_profile_filter_false_negatives = unknown_false_negatives

        # Disqualification metrics
        metrics.cases_with_known_disqualifications = disqual_cases
        metrics.known_disqualifying_accuracy = (
            round(disqual_correct / disqual_cases, 4) if disqual_cases > 0 else 1.0
        )

        return metrics
