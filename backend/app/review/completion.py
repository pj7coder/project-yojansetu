import logging
from typing import List, Tuple
from app.database.models.human_review_session import HumanReviewSession

logger = logging.getLogger("yojansetu.review.completion")


class ReviewCompletionGuard:
    """
    Strict backend completion guard enforcing that a scheme draft can only reach
    HUMAN_VERIFIED when all mandatory criteria are resolved.
    Frontend button states cannot bypass these checks.
    """

    @classmethod
    def check_completion_eligibility(
        cls,
        session: HumanReviewSession,
        current_canonical_sha256: str,
        has_unresolved_blockers: bool = False,
    ) -> Tuple[bool, List[str]]:
        reasons: List[str] = []

        # 1. Check for stale session / concurrent modification
        if session.canonical_artifact_sha256 != current_canonical_sha256:
            reasons.append(
                "Canonical scheme draft has been modified since review started. "
                "The review session is STALE and must be re-evaluated."
            )

        # 2. Check for pending review items
        pending_items = [item for item in session.items if item.decision == "PENDING"]
        if pending_items:
            reasons.append(
                f"{len(pending_items)} item(s) remain PENDING. All review items must be resolved."
            )

        # 3. Check for unresolved BLOCKER validation issues
        if has_unresolved_blockers:
            reasons.append(
                "Draft contains unresolved BLOCKER validation issues that must be fixed before verification."
            )

        # 4. Check for unaddressed CONTRADICTED items without override reason
        for item in session.items:
            if item.decision == "APPROVED" and item.verification_result == "CONTRADICTED":
                if not item.override_reason and not item.reviewer_comment:
                    reasons.append(
                        f"Field '{item.field_path}' is CONTRADICTED by evidence. "
                        "An explicit override reason is mandatory to approve this field."
                    )

        # 5. Check for NOT_ENOUGH_EVIDENCE items approved without explanation
        for item in session.items:
            if item.decision == "APPROVED" and item.verification_result == "NOT_ENOUGH_EVIDENCE":
                if not item.override_reason and not item.reviewer_comment:
                    reasons.append(
                        f"Field '{item.field_path}' has INSUFFICIENT EVIDENCE. "
                        "An explicit override reason is mandatory to approve this field."
                    )

        can_complete = len(reasons) == 0
        return can_complete, reasons
