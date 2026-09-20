from collections import defaultdict
from typing import Dict, List, Tuple

from app.normalization.schemas import (
    ConflictRecord,
    ConflictValue,
    EligibilityCondition,
    NormalizationStatus,
)


def merge_identical_conditions(
    conditions: List[EligibilityCondition],
) -> List[EligibilityCondition]:
    """
    Merge identical extracted conditions that state the exact same fact across chunks.
    Combines evidence references into a single de-duplicated list without creating duplicates.
    """
    merged: Dict[Tuple, EligibilityCondition] = {}

    for cond in conditions:
        # Create unique structural key
        key = (
            cond.field,
            cond.operator.value,
            str(cond.value),
            str(cond.unit),
            str(cond.periodicity.value if cond.periodicity else None),
            str(cond.context_qualifier),
        )

        if key in merged:
            existing = merged[key]
            # Merge evidence refs preserving order and uniqueness
            combined_refs = list(dict.fromkeys(existing.evidence_refs + cond.evidence_refs))
            existing.evidence_refs = combined_refs
        else:
            merged[key] = cond.model_copy(deep=True)

    return list(merged.values())


def detect_conflicts(
    conditions: List[EligibilityCondition],
) -> Tuple[List[EligibilityCondition], List[ConflictRecord]]:
    """
    Analyze conditions to detect contradictory facts versus contextual conditional branches.

    Rules:
    1. If two conditions address the SAME field in the SAME context but assert different values,
       flag as a CONFLICT with both values and their respective evidence references.
    2. If conditions apply to DIFFERENT contexts (e.g. General category vs SC/ST category),
       retain them as distinct conditional branches rather than a conflict.
    """
    # Group conditions by (field, context_qualifier)
    grouped: Dict[Tuple[str, str], List[EligibilityCondition]] = defaultdict(list)
    for c in conditions:
        ctx = c.context_qualifier or "DEFAULT"
        grouped[(c.field, ctx)].append(c)

    conflicts: List[ConflictRecord] = []
    conflict_counter = 1
    processed_conditions: List[EligibilityCondition] = []

    for (field, ctx), cond_list in grouped.items():
        # First merge exact duplicates within the group
        unique_in_group = merge_identical_conditions(cond_list)

        # Fields where multiple different values in same context are contradictory
        # (e.g. annual_income, family_income, min_age, max_age)
        single_value_fields = {"annual_income", "family_income", "age", "residency"}

        if field in single_value_fields and len(unique_in_group) > 1:
            # Check if values actually differ
            distinct_values = {str(c.value) for c in unique_in_group}
            if len(distinct_values) > 1:
                # Contradiction detected!
                conflict_vals = [
                    ConflictValue(
                        value=c.value,
                        raw_text=c.raw_text,
                        context=ctx if ctx != "DEFAULT" else None,
                        evidence_refs=c.evidence_refs,
                    )
                    for c in unique_in_group
                ]

                conf_rec = ConflictRecord(
                    conflict_id=f"CONF-{conflict_counter:03d}",
                    field=field,
                    values=conflict_vals,
                    status="REVIEW_REQUIRED",
                    explanation=f"Contradictory values extracted for '{field}' under the same context '{ctx}'.",
                )
                conflicts.append(conf_rec)
                conflict_counter += 1

                for c in unique_in_group:
                    c.normalization_status = NormalizationStatus.CONFLICT
                    processed_conditions.append(c)
                continue

        processed_conditions.extend(unique_in_group)

    return processed_conditions, conflicts
