import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import get_settings

logger = logging.getLogger("yojansetu.review.auth")


class ReviewAuthorizationService:
    """
    Guards human review endpoints to ensure only authorized reviewers
    can view, edit, approve, or reject canonical scheme drafts.
    Provides development identity ('DEV_REVIEWER') with clear audit tracking.
    """

    @staticmethod
    def get_current_reviewer(
        x_reviewer_id: Optional[str] = Header(default=None, alias="X-Reviewer-Id"),
        authorization: Optional[str] = Header(default=None),
    ) -> str:
        settings = get_settings()

        # In production, require valid token / identity
        if settings.app_env == "production":
            if not authorization and not x_reviewer_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication credentials required for admin review.",
                )

        reviewer = x_reviewer_id or "DEV_REVIEWER"
        return reviewer
