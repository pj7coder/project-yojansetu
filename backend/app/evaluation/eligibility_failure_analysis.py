"""
JanSetu - Day 30: Eligibility Failure Analysis & Taxonomy Classification.

Implements deterministic failure categorization, safety criticality ranking,
and root-cause attribution distinguishing engine logic from rule data mismatches.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.evaluation.eligibility_schemas import (
    EligibilityFailureCode,
    EligibilitySeverity,
    FailureRootCause,
)
from app.gold.schemas import EligibilityStatus


class EligibilityFailureAnalyzer:
    """
    Deterministic failure classifier assessing safety severity and root cause
    for eligibility engine evaluation.
    """

    @classmethod
    def classify_status_failure(
        cls,
        gold_status: EligibilityStatus,
        actual_status: EligibilityStatus,
        tags: List[str],
        failure_details: Optional[str] = None,
    ) -> Tuple[EligibilityFailureCode, EligibilitySeverity, FailureRootCause]:
        """
        Classifies status disagreements with deterministic safety severities.
        """
        tag_str = " ".join(tags).upper()

        # 1. Critical Errors: Inverted Entitlement Decisions
        if gold_status == EligibilityStatus.NOT_ELIGIBLE and actual_status == EligibilityStatus.ELIGIBLE:
            # Citizen who is ineligible was declared eligible (dangerous entitlement grant)
            if "EXCLUSION" in tag_str:
                return (
                    EligibilityFailureCode.EXCLUSION_IGNORED,
                    EligibilitySeverity.CRITICAL,
                    FailureRootCause.ENGINE_LOGIC,
                )
            if "BOUNDARY" in tag_str or "OVER_INCOME" in tag_str or "UNDERAGE" in tag_str:
                return (
                    EligibilityFailureCode.BOUNDARY_ERROR,
                    EligibilitySeverity.CRITICAL,
                    FailureRootCause.ENGINE_LOGIC,
                )
            if "VERSION" in tag_str:
                return (
                    EligibilityFailureCode.FUTURE_VERSION_USED_EARLY,
                    EligibilitySeverity.CRITICAL,
                    FailureRootCause.VERSION_SELECTION,
                )
            return (
                EligibilityFailureCode.WRONG_FINAL_STATUS,
                EligibilitySeverity.CRITICAL,
                FailureRootCause.ENGINE_LOGIC,
            )

        if gold_status == EligibilityStatus.ELIGIBLE and actual_status == EligibilityStatus.NOT_ELIGIBLE:
            # Eligible citizen denied valid government benefit
            if "BOUNDARY" in tag_str:
                return (
                    EligibilityFailureCode.BOUNDARY_ERROR,
                    EligibilitySeverity.CRITICAL,
                    FailureRootCause.ENGINE_LOGIC,
                )
            if "EXCLUSION" in tag_str:
                return (
                    EligibilityFailureCode.EXCLUSION_FALSE_POSITIVE,
                    EligibilitySeverity.CRITICAL,
                    FailureRootCause.ENGINE_LOGIC,
                )
            if "VERSION" in tag_str:
                return (
                    EligibilityFailureCode.HISTORICAL_VERSION_ERROR,
                    EligibilitySeverity.CRITICAL,
                    FailureRootCause.VERSION_SELECTION,
                )
            return (
                EligibilityFailureCode.WRONG_FINAL_STATUS,
                EligibilitySeverity.CRITICAL,
                FailureRootCause.ENGINE_LOGIC,
            )

        # 2. High Severity: Premature Decision with Missing Information
        if gold_status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
            if actual_status in (EligibilityStatus.ELIGIBLE, EligibilityStatus.NOT_ELIGIBLE):
                return (
                    EligibilityFailureCode.TRISTATE_LOGIC_ERROR,
                    EligibilitySeverity.HIGH,
                    FailureRootCause.ENGINE_LOGIC,
                )

        # 3. Medium Severity: Information Requested Unnecessarily
        if actual_status == EligibilityStatus.MORE_INFORMATION_REQUIRED:
            if "SHORT_CIRCUIT" in tag_str or "BPL" in tag_str:
                return (
                    EligibilityFailureCode.OR_SHORT_CIRCUIT_ERROR,
                    EligibilitySeverity.MEDIUM,
                    FailureRootCause.ENGINE_LOGIC,
                )
            return (
                EligibilityFailureCode.MISSING_FIELD_FALSE_POSITIVE,
                EligibilitySeverity.MEDIUM,
                FailureRootCause.ENGINE_LOGIC,
            )

        # Fallback
        return (
            EligibilityFailureCode.WRONG_FINAL_STATUS,
            EligibilitySeverity.HIGH,
            FailureRootCause.UNKNOWN,
        )

    @classmethod
    def classify_trace_or_missing_field_failure(
        cls,
        has_missing_field_error: bool,
        has_trace_error: bool,
        is_rule_data_mismatch: bool = False,
    ) -> Tuple[EligibilityFailureCode, EligibilitySeverity, FailureRootCause]:
        """
        Classifies non-status failures (e.g. status was correct, but missing fields or trace reasoning was flawed).
        """
        if is_rule_data_mismatch:
            return (
                EligibilityFailureCode.RULE_DATA_MISMATCH,
                EligibilitySeverity.HIGH,
                FailureRootCause.RULE_DATA,
            )

        if has_missing_field_error:
            return (
                EligibilityFailureCode.MISSING_FIELD_FALSE_POSITIVE,
                EligibilitySeverity.MEDIUM,
                FailureRootCause.ENGINE_LOGIC,
            )

        if has_trace_error:
            return (
                EligibilityFailureCode.TRACE_ERROR,
                EligibilitySeverity.LOW,
                FailureRootCause.TRACE_ONLY,
            )

        return (
            EligibilityFailureCode.UNKNOWN_ROOT_CAUSE,
            EligibilitySeverity.LOW,
            FailureRootCause.UNKNOWN,
        )
