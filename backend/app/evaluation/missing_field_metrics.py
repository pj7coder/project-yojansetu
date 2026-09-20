"""
JanSetu - Day 30: Missing Field Metrics & Minimal Information Requirement.

Evaluates whether the engine asks the exact minimal questions needed
to resolve citizen eligibility, measuring Precision, Recall, F1,
and tracking unnecessary question requests.
"""

from typing import List, Set, Union
from app.eligibility.result import MissingFieldInfo
from app.evaluation.eligibility_schemas import MissingFieldEvaluation


class MissingFieldEvaluator:
    """
    Evaluates missing fields discovered by the deterministic engine
    against human-verified gold requirements.
    """

    @classmethod
    def evaluate_missing_fields(
        cls,
        actual_missing: Union[List[str], List[MissingFieldInfo]],
        gold_missing: List[str],
    ) -> MissingFieldEvaluation:
        """
        Calculates precision, recall, F1, and unnecessary question count.
        """
        # 1. Normalize actual field names
        actual_names: Set[str] = set()
        for item in actual_missing:
            if isinstance(item, MissingFieldInfo):
                actual_names.add(item.field.strip().lower())
            elif isinstance(item, str):
                actual_names.add(item.strip().lower())

        gold_names: Set[str] = {g.strip().lower() for g in gold_missing if g}

        matched = sorted(actual_names.intersection(gold_names))
        fp = sorted(actual_names - gold_names)
        fn = sorted(gold_names - actual_names)

        # 2. Precision, Recall, F1
        if not actual_names and not gold_names:
            precision = 1.0
            recall = 1.0
            f1 = 1.0
        elif not actual_names and gold_names:
            precision = 0.0
            recall = 0.0
            f1 = 0.0
        elif actual_names and not gold_names:
            precision = 0.0
            recall = 1.0
            f1 = 0.0
        else:
            precision = len(matched) / len(actual_names)
            recall = len(matched) / len(gold_names)
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return MissingFieldEvaluation(
            gold_missing=sorted(gold_names),
            actual_missing=sorted(actual_names),
            matched_missing=matched,
            false_positive_missing=fp,
            false_negative_missing=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            unnecessary_question_count=len(fp),
        )
