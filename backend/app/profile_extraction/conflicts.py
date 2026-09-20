"""
Conflict and correction detector between candidate facts and active session state.
Never silently overwrites established profile facts without explicit confirmation.
"""

import re
from typing import Any, Dict, Optional
from app.profile_extraction.schemas import CandidateProfileUpdate, CandidateStatus

CORRECTION_CLUES = [
    r'पहले\s*गलत',
    r'गलती\s*से',
    r'सुधार\s*करो',
    r'सुधारो',
    r'बदलना\s*है',
    r'बदलो',
    r'नहीं\s*,\s*(?:मेरी|मेरा|में|मैं)',
    r'incorrect',
    r'correct\s*my',
    r'change\s*to',
]


class ProfileConflictDetector:
    """
    Detects contradictions and explicit corrections relative to existing session profile facts.
    """

    @classmethod
    def is_explicit_correction(cls, text: str) -> bool:
        """Determines if the utterance contains explicit intent to correct previously stated data."""
        clean = text.strip().lower()
        for clue in CORRECTION_CLUES:
            if re.search(clue, clean):
                return True
        return False

    @classmethod
    def evaluate_conflict(
        cls,
        candidate: CandidateProfileUpdate,
        existing_profile: Dict[str, Any],
        full_utterance: str,
    ) -> CandidateProfileUpdate:
        """
        Evaluates candidate against existing session profile.
        Marks status as CONFLICT_WITH_EXISTING_VALUE or CORRECTION if a discrepancy exists.
        """
        field_name = candidate.field
        if field_name not in existing_profile or existing_profile.get(field_name) is None:
            # No existing fact; no conflict
            return candidate

        old_val = existing_profile[field_name]
        new_val = candidate.value

        # Normalize comparison for numeric types (int vs Decimal vs float)
        try:
            if float(old_val) == float(new_val):
                # Same value; mark accepted
                candidate.old_value = old_val
                return candidate
        except (ValueError, TypeError):
            if str(old_val).strip().lower() == str(new_val).strip().lower():
                candidate.old_value = old_val
                return candidate

        # Discrepancy detected!
        candidate.old_value = old_val
        is_corr = cls.is_explicit_correction(full_utterance) or cls.is_explicit_correction(candidate.source_text)

        if is_corr:
            candidate.is_correction = True
            candidate.status = CandidateStatus.CONFIRMATION_REQUIRED
            candidate.requires_confirmation = True
            candidate.confirmation_reason = "CORRECTION_OF_EXISTING_VALUE"
        else:
            candidate.is_correction = False
            candidate.status = CandidateStatus.CONFLICT_WITH_EXISTING_VALUE
            candidate.requires_confirmation = True
            candidate.confirmation_reason = "CONFLICT_WITH_EXISTING_VALUE"

        return candidate
