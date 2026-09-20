from typing import List, Tuple

from app.eligibility.evaluator import RuleEvaluator
from app.eligibility.fields import get_field_definition
from app.eligibility.models import ExclusionNode
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import (
    ConditionEvaluationResult,
    MissingFieldInfo,
    ReasonCode,
)
from app.eligibility.truth import TruthState


class ExclusionEvaluator:
    """
    Evaluates negative disqualifications (exclusions) against citizen profiles.
    Follows strict exclusion priority:
    - If positive eligibility already failed -> exclusions are short-circuited (NOT_ELIGIBLE stands).
    - If positive eligibility passed:
        - Any exclusion == TRUE -> NOT_ELIGIBLE (exclusion triggered).
        - Any exclusion == UNKNOWN -> MORE_INFORMATION_REQUIRED (cannot confirm eligibility).
        - All exclusions == FALSE -> ELIGIBLE.
    """

    @classmethod
    def evaluate_exclusions(
        cls,
        exclusions: List[ExclusionNode],
        profile: CitizenProfile,
        positive_state: TruthState,
    ) -> Tuple[TruthState, List[ConditionEvaluationResult], List[MissingFieldInfo]]:
        """
        Evaluates exclusions list.
        Returns:
            (exclusion_truth_state, triggered_exclusions, missing_fields)
            - TruthState.TRUE: at least one exclusion was triggered (citizen disqualified)
            - TruthState.UNKNOWN: at least one exclusion is unknown and none triggered
            - TruthState.FALSE: all exclusions definitely do not apply
        """
        if not exclusions:
            return TruthState.FALSE, [], []

        # If citizen already definitively failed positive mandatory conditions,
        # short-circuit: do not evaluate exclusions or demand missing exclusion fields.
        if positive_state == TruthState.FALSE:
            return TruthState.FALSE, [], []

        triggered: List[ConditionEvaluationResult] = []
        missing: List[MissingFieldInfo] = []
        has_unknown = False

        for excl in exclusions:
            evaluator = RuleEvaluator(profile)
            state, _ = evaluator.evaluate(excl.rule)

            if state == TruthState.TRUE:
                # Disqualification triggered!
                res = ConditionEvaluationResult(
                    condition_id=excl.exclusion_id,
                    field=getattr(excl.rule, "field", "exclusion"),
                    result=TruthState.TRUE,
                    operator=getattr(excl.rule, "operator", "EQ"),
                    required_value=getattr(excl.rule, "value", True),
                    citizen_value=profile.get_value(getattr(excl.rule, "field", "exclusion")),
                    reason_code=ReasonCode.EXCLUSION_TRIGGERED,
                    evidence_refs=excl.evidence_refs,
                    message=f"Disqualification triggered: {excl.raw_text or excl.exclusion_id}",
                )
                triggered.append(res)
                # An exclusion being TRUE is a definitive disqualification; we can short-circuit
                return TruthState.TRUE, triggered, []

            elif state == TruthState.UNKNOWN:
                if excl.mandatory_check:
                    has_unknown = True
                    field_name = getattr(excl.rule, "field", "exclusion")
                    f_def = get_field_definition(field_name)
                    missing.append(
                        MissingFieldInfo(
                            field=field_name,
                            reason="REQUIRED_FOR_EXCLUSION_CHECK",
                            condition_id=excl.exclusion_id,
                            display_name_en=f_def.display_name_en if f_def else field_name.replace("_", " ").title(),
                            display_name_hi=f_def.display_name_hi if f_def else None,
                        )
                    )

        if has_unknown:
            return TruthState.UNKNOWN, [], missing

        return TruthState.FALSE, [], []
