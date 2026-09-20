from collections import defaultdict
import logging
from typing import Any, Dict, List, Optional, Set

from app.core.config import get_settings
from app.questioning.field_metadata import get_field_metadata
from app.questioning.schemas import (
    CandidateSchemeMissingInfo,
    NextQuestionResult,
    QuestionReasonCode,
)
from app.questioning.scoring import QuestionScorer
from app.sessions.models import FieldValueState

logger = logging.getLogger("jansetu.questioning.selector")


class NextQuestionSelector:
    """
    Deterministic question selection engine for multi-turn citizen discovery.
    Identifies the single highest-value profile attribute to request next,
    balancing scheme coverage, candidate relevance, immediate resolution power,
    and citizen interaction fatigue.
    """

    def __init__(
        self,
        scorer: Optional[QuestionScorer] = None,
        target_confirmed_schemes: Optional[int] = None,
    ):
        settings = get_settings()
        self.scorer = scorer or QuestionScorer()
        self.target_confirmed_schemes = (
            target_confirmed_schemes
            if target_confirmed_schemes is not None
            else settings.target_confirmed_schemes
        )

    def select_next_question(
        self,
        eligible_schemes_count: int,
        more_info_schemes: List[CandidateSchemeMissingInfo],
        known_profile_fields: Optional[Set[str]] = None,
        declined_fields: Optional[Set[str]] = None,
        field_ask_counts: Optional[Dict[str, int]] = None,
    ) -> NextQuestionResult:
        """
        Evaluates current discovery candidate state and selects the best next question.
        Returns NextQuestionResult with null field if stopping conditions are satisfied.
        """
        known_fields = known_profile_fields or set()
        declined = declined_fields or set()
        ask_counts = field_ask_counts or {}

        # 1. Stopping Rule: Target confirmed eligible schemes reached
        if eligible_schemes_count >= self.target_confirmed_schemes:
            logger.info(
                f"Stopping question selection: {eligible_schemes_count} eligible schemes confirmed "
                f"(target: {self.target_confirmed_schemes})"
            )
            return NextQuestionResult(
                field=None,
                reason_code=QuestionReasonCode.ENOUGH_CONFIRMED_RESULTS.value,
                affected_scheme_count=0,
            )

        # 2. Stopping Rule: No unresolved candidate schemes requiring more info
        if not more_info_schemes:
            logger.info("Stopping question selection: 0 candidate schemes require more information")
            return NextQuestionResult(
                field=None,
                reason_code=QuestionReasonCode.NO_RELEVANT_CANDIDATES.value,
                affected_scheme_count=0,
            )

        # 3. Aggregate missing fields across unresolved candidate schemes
        # Group schemes by the missing fields they need
        field_to_schemes: Dict[str, List[CandidateSchemeMissingInfo]] = defaultdict(list)
        all_unresolved_fields: Set[str] = set()

        for scheme in more_info_schemes:
            for f in scheme.missing_fields:
                if not f:
                    continue
                clean_f = f.strip()
                if not clean_f:
                    continue
                # Skip fields that are already known in the profile
                if clean_f in known_fields:
                    continue
                all_unresolved_fields.add(clean_f)
                field_to_schemes[clean_f].append(scheme)

        if not all_unresolved_fields:
            logger.info("No unknown fields remaining among candidate schemes")
            return NextQuestionResult(
                field=None,
                reason_code=QuestionReasonCode.CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION.value,
                affected_scheme_count=0,
            )

        # 4. Filter out declined fields
        candidate_fields = [f for f in all_unresolved_fields if f not in declined]
        if not candidate_fields:
            logger.info("All remaining candidate fields have been DECLINED by citizen")
            return NextQuestionResult(
                field=None,
                reason_code=QuestionReasonCode.CANNOT_RESOLVE_WITH_AVAILABLE_INFORMATION.value,
                affected_scheme_count=0,
            )

        # 5. Score every candidate field using QuestionScorer
        scored_fields = []
        for f in candidate_fields:
            schemes = field_to_schemes[f]
            ask_count = ask_counts.get(f, 0)
            breakdown = self.scorer.calculate_field_score(
                field_name=f,
                schemes_needing_field=schemes,
                ask_count=ask_count,
            )
            scored_fields.append(breakdown)

        # Sort primarily by final_score descending, secondarily by affected_schemes_count descending
        scored_fields.sort(
            key=lambda item: (item.final_score, item.affected_schemes_count),
            reverse=True,
        )

        top_field = scored_fields[0]
        meta = get_field_metadata(top_field.field_name)

        # Determine reason code based on resolution power
        reason_code = (
            QuestionReasonCode.IMMEDIATE_SCHEME_RESOLUTION.value
            if top_field.has_one_field_away_scheme
            else QuestionReasonCode.RESOLVES_MOST_RELEVANT_SCHEMES.value
        )

        logger.info(
            f"Selected next question field='{top_field.field_name}': "
            f"reason={reason_code}, "
            f"affected_schemes={top_field.affected_schemes_count}, "
            f"score={top_field.final_score}"
        )

        return NextQuestionResult(
            field=top_field.field_name,
            reason_code=reason_code,
            affected_scheme_count=top_field.affected_schemes_count,
            display_name_en=meta.display_name_en,
            display_name_hi=meta.display_name_hi,
            data_type=meta.data_type,
            sensitivity_level=meta.sensitivity_level,
            example_question_en=meta.example_question_en,
            example_question_hi=meta.example_question_hi,
        )
