import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.review.schemas import ConflictResolutionChoice

logger = logging.getLogger("jansetu.review.conflict_service")


class ConflictResolutionService:
    """
    Handles structured human resolution of extraction contradictions and version conflicts.
    Supports selecting candidate value, retaining both conditionally, or rejecting.
    """

    @staticmethod
    def resolve_conflict_in_canonical_data(
        raw_canonical_data: Dict[str, Any],
        conflict_id: str,
        choice: ConflictResolutionChoice,
        selected_value: Optional[Any] = None,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Applies human conflict decision to canonical draft dictionary.
        Returns: (updated_canonical_data, resolved_conflict_record)
        """
        conflicts = raw_canonical_data.get("conflicts", [])
        target_conflict = None

        for c in conflicts:
            if c.get("conflict_id") == conflict_id:
                target_conflict = c
                break

        if not target_conflict:
            raise ValueError(f"Conflict with ID '{conflict_id}' not found in canonical draft.")

        field = target_conflict.get("field")

        if choice == ConflictResolutionChoice.SELECT_VALUE:
            target_conflict["status"] = "RESOLVED"
            target_conflict["resolution"] = "SELECTED_CANDIDATE"
            target_conflict["chosen_value"] = selected_value

        elif choice == ConflictResolutionChoice.KEEP_CONDITIONAL:
            target_conflict["status"] = "RESOLVED"
            target_conflict["resolution"] = "PRESERVED_AS_CONDITIONAL"

        elif choice == ConflictResolutionChoice.REJECT_FIELD:
            target_conflict["status"] = "RESOLVED"
            target_conflict["resolution"] = "REJECTED"

        elif choice == ConflictResolutionChoice.UNRESOLVED:
            target_conflict["status"] = "UNRESOLVED"

        return raw_canonical_data, target_conflict
