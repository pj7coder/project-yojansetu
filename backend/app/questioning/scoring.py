from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.questioning.field_metadata import get_field_metadata
from app.questioning.schemas import CandidateSchemeMissingInfo

logger = logging.getLogger("yojansetu.questioning.scoring")


@dataclass
class FieldScoreBreakdown:
    """Detailed explainable breakdown of a candidate field's selection score."""
    field_name: str
    raw_utility: float
    affected_schemes_count: int
    has_one_field_away_scheme: bool
    repeat_penalty: float
    sensitivity_cost: float
    final_score: float


class QuestionScorer:
    """
    Deterministic information-gain scorer for candidate next questions.
    Combines:
    1. Scheme coverage frequency (how many unresolved schemes need this field)
    2. Candidate semantic relevance (weights schemes aligned with citizen's need)
    3. One-field-away immediate resolution bonus (prioritizes immediate eligibility decisions)
    4. Repeat question penalty (avoids badgering the citizen with repeatedly asked questions)
    5. Sensitivity cost (prefers less invasive questions on utility ties)
    """

    def __init__(
        self,
        relevance_weight: Optional[float] = None,
        resolution_bonus: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        sensitivity_penalty: Optional[float] = None,
    ):
        settings = get_settings()
        self.relevance_weight = relevance_weight if relevance_weight is not None else settings.question_relevance_weight
        self.resolution_bonus = resolution_bonus if resolution_bonus is not None else settings.question_resolution_bonus
        self.repeat_penalty_factor = repeat_penalty if repeat_penalty is not None else settings.question_repeat_penalty
        self.sensitivity_penalty_factor = sensitivity_penalty if sensitivity_penalty is not None else settings.question_sensitivity_penalty

    def calculate_field_score(
        self,
        field_name: str,
        schemes_needing_field: List[CandidateSchemeMissingInfo],
        ask_count: int = 0,
        profile_context: Optional[Dict[str, Any]] = None,
        need_text: Optional[str] = None,
    ) -> FieldScoreBreakdown:
        raw_utility = 0.0
        has_one_field_away = False
        profile = profile_context or {}
        need_lower = (need_text or "").lower()

        for scheme in schemes_needing_field:
            # Semantic relevance weight (default 1.0 if not ranked, or normalized 0.0-1.0)
            rel_score = scheme.semantic_score if scheme.semantic_score is not None else 1.0
            weighted_relevance = 1.0 + (self.relevance_weight * rel_score)

            # One-field-away resolution bonus
            one_away_bonus = 0.0
            if len(scheme.missing_fields) == 1:
                one_away_bonus = self.resolution_bonus
                has_one_field_away = True

            scheme_contribution = weighted_relevance + one_away_bonus
            raw_utility += scheme_contribution

        # Context-aware domain alignment boosts:
        # 1. Farmer context -> prioritize land holding
        if profile.get("occupation") == "FARMER" or any(w in need_lower for w in ["मैं किसान", "किसान हूँ", "खेती करता"]):
            if field_name in ("land_area_bigha", "land_holding"):
                raw_utility += 15.0
            elif field_name in ("annual_income", "family_income") and "land_area_bigha" not in profile:
                raw_utility -= 8.0

        # 2. Pension intent -> prioritize age over income
        if any(w in need_lower for w in ["पेंशन", "pension", "वृद्ध", "बुजुर्ग", "senior"]):
            if field_name == "age":
                raw_utility += 15.0
            elif field_name in ("annual_income", "family_income") and "age" not in profile:
                raw_utility -= 8.0

        # 3. Student / Coaching context -> prioritize student status / category
        if any(w in need_lower for w in ["छात्र", "विद्यार्थी", "student", "coaching", "कोचिंग", "neet", "reet", "upsc"]):
            if field_name in ("is_student", "caste_category"):
                raw_utility += 15.0

        # 4. Senior Citizen Age known (>= 55) -> prioritize annual income to confirm pension (unless farmer need)
        is_farmer_need = any(w in need_lower for w in ["किसान", "farmer", "खेती", "कृषि", "फसल"])
        if profile.get("age") and int(profile.get("age", 0)) >= 55 and not is_farmer_need:
            if field_name in ("annual_income", "family_income"):
                raw_utility += 12.0

        # 5. General Demographic Priority: Ask WHO the citizen is before means testing
        if not profile.get("age") and not profile.get("occupation"):
            if field_name in ("age", "occupation"):
                raw_utility += 5.0
            elif field_name in ("annual_income", "family_income"):
                raw_utility -= 3.0

        # Repetition penalty
        repeat_cost = ask_count * self.repeat_penalty_factor

        # Sensitivity cost based on metadata registry
        meta = get_field_metadata(field_name)
        sens_multiplier = 0.0
        if meta.sensitivity_level == "MEDIUM":
            sens_multiplier = 0.5
        elif meta.sensitivity_level == "HIGH":
            sens_multiplier = 1.0
        sensitivity_cost = sens_multiplier * self.sensitivity_penalty_factor

        final_score = raw_utility - repeat_cost - sensitivity_cost

        return FieldScoreBreakdown(
            field_name=field_name,
            raw_utility=round(raw_utility, 4),
            affected_schemes_count=len(schemes_needing_field),
            has_one_field_away_scheme=has_one_field_away,
            repeat_penalty=round(repeat_cost, 4),
            sensitivity_cost=round(sensitivity_cost, 4),
            final_score=round(final_score, 4),
        )
