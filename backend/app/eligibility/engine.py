from datetime import date
import time
from typing import Any, Dict, List, Optional, Union

from app.eligibility.availability import check_scheme_availability
from app.eligibility.compiler import EligibilityRuleCompiler
from app.eligibility.evaluator import RuleEvaluator
from app.eligibility.exclusions import ExclusionEvaluator
from app.eligibility.models import CompiledScheme
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import (
    ConditionEvaluationResult,
    EligibilityResult,
    EligibilityStatus,
    MissingFieldInfo,
    SchemeAvailability,
)
from app.eligibility.truth import TruthState

ELIGIBILITY_ENGINE_VERSION = "1.0"


class EligibilityEngine:
    """
    YojanSetu Pure Python Deterministic Eligibility Engine.
    Evaluates human-verified government scheme rules against citizen profiles.
    Decisions strictly stem from verified rule trees; zero LLM reasoning.
    """

    @classmethod
    def compile_scheme(cls, raw_scheme: Dict[str, Any]) -> CompiledScheme:
        """Helper to compile a verified scheme JSON into an immutable AST."""
        return EligibilityRuleCompiler.compile_scheme(raw_scheme)

    @classmethod
    def evaluate_scheme(
        cls,
        scheme: Union[CompiledScheme, Dict[str, Any]],
        profile: Union[CitizenProfile, Dict[str, Any]],
        evaluation_date: Optional[date] = None,
    ) -> EligibilityResult:
        """
        Main pure evaluation interface.
        Independent of database, FastAPI, or network infrastructure.
        """
        start_time = time.perf_counter()

        # 1. Prepare Citizen Profile
        if isinstance(profile, dict):
            citizen_profile = CitizenProfile(**profile)
        else:
            citizen_profile = profile

        # 2. Prepare Compiled Scheme
        if isinstance(scheme, dict):
            compiled_scheme = EligibilityRuleCompiler.compile_scheme(scheme)
        else:
            compiled_scheme = scheme

        # 3. Check Temporal Scheme Availability
        availability = check_scheme_availability(compiled_scheme, evaluation_date)
        if availability != SchemeAvailability.ACTIVE:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return EligibilityResult(
                scheme_id=compiled_scheme.scheme_id,
                scheme_name=compiled_scheme.scheme_name,
                scheme_name_hi=compiled_scheme.scheme_name_hi,
                availability=availability,
                eligibility_status=EligibilityStatus.NOT_ELIGIBLE,
                missing_fields=[],
                failed_conditions=[],
                passed_conditions=[],
                exclusions_triggered=[],
                preferences_matched=[],
                evaluation_trace={
                    "availability": availability.value,
                    "reason": f"Scheme is currently {availability.value} as of {evaluation_date or date.today()}",
                },
                engine_version=ELIGIBILITY_ENGINE_VERSION,
                evaluation_duration_ms=round(duration_ms, 3),
            )

        # 4. Evaluate Positive Mandatory Eligibility
        evaluator = RuleEvaluator(citizen_profile)
        pos_state, pos_trace = evaluator.evaluate(compiled_scheme.root_rule)

        # 5. Evaluate Exclusions (with short-circuiting if positive eligibility failed)
        excl_state, triggered_exclusions, missing_exclusions = ExclusionEvaluator.evaluate_exclusions(
            compiled_scheme.exclusions,
            citizen_profile,
            pos_state,
        )

        # 6. Evaluate Preferences (non-blocking for ranking/matching metadata)
        preferences_matched: List[ConditionEvaluationResult] = []
        for pref in compiled_scheme.preferences:
            pref_eval = RuleEvaluator(citizen_profile)
            p_state, _ = pref_eval.evaluate(pref)
            if p_state == TruthState.TRUE and pref_eval.passed_conditions:
                preferences_matched.extend(pref_eval.passed_conditions)

        # 7. Determine Final Eligibility Decision
        final_status: EligibilityStatus
        if pos_state == TruthState.FALSE:
            final_status = EligibilityStatus.NOT_ELIGIBLE
        elif excl_state == TruthState.TRUE:
            final_status = EligibilityStatus.NOT_ELIGIBLE
        elif pos_state == TruthState.UNKNOWN:
            final_status = EligibilityStatus.MORE_INFORMATION_REQUIRED
        elif excl_state == TruthState.UNKNOWN:
            final_status = EligibilityStatus.MORE_INFORMATION_REQUIRED
        else:
            final_status = EligibilityStatus.ELIGIBLE

        # 8. Consolidate Missing Fields
        consolidated_missing: List[MissingFieldInfo] = list(evaluator.missing_fields)
        existing_names = {m.field for m in consolidated_missing}
        for mex in missing_exclusions:
            if mex.field not in existing_names:
                consolidated_missing.append(mex)
                existing_names.add(mex.field)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        trace_summary = {
            "root_rule": pos_trace,
            "positive_state": pos_state.value,
            "exclusion_state": excl_state.value,
            "conditions_evaluated": evaluator.conditions_evaluated_count,
            "conditions_short_circuited": evaluator.conditions_short_circuited_count,
            "evaluation_duration_ms": round(duration_ms, 3),
        }

        return EligibilityResult(
            scheme_id=compiled_scheme.scheme_id,
            scheme_name=compiled_scheme.scheme_name,
            scheme_name_hi=compiled_scheme.scheme_name_hi,
            availability=availability,
            eligibility_status=final_status,
            missing_fields=consolidated_missing,
            failed_conditions=evaluator.failed_conditions,
            passed_conditions=evaluator.passed_conditions,
            exclusions_triggered=triggered_exclusions,
            preferences_matched=preferences_matched,
            evaluation_trace=trace_summary,
            engine_version=ELIGIBILITY_ENGINE_VERSION,
            evaluation_duration_ms=round(duration_ms, 3),
        )
