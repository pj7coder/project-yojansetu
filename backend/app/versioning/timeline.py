import logging
import uuid
from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.database.models.scheme import SchemeVersion

logger = logging.getLogger("yojansetu.versioning.timeline")


class SchemeTimelineService:
    """
    Temporal version query and validation service.
    Enforces reproducible evaluation at any past, present, or future date,
    and detects timeline gaps and overlaps.
    """

    def get_active_scheme_version(
        self,
        db: Session,
        scheme_id: uuid.UUID,
        evaluation_date: Optional[date] = None,
    ) -> Optional[SchemeVersion]:
        """
        Retrieve the legally active verified version of a scheme for a given evaluation date.
        If evaluation_date is not specified, defaults to today.
        """
        eval_dt = evaluation_date or date.today()

        stmt = (
            select(SchemeVersion)
            .where(
                SchemeVersion.scheme_id == scheme_id,
                SchemeVersion.status.in_(["ACTIVE", "HUMAN_VERIFIED"]),
                or_(
                    SchemeVersion.valid_from.is_(None),
                    SchemeVersion.valid_from <= eval_dt,
                ),
                or_(
                    SchemeVersion.valid_until.is_(None),
                    SchemeVersion.valid_until >= eval_dt,
                ),
            )
            .order_by(SchemeVersion.version_number.desc())
        )

        # Prioritize explicit ACTIVE version first, then HUMAN_VERIFIED
        versions = db.execute(stmt).scalars().all()
        for v in versions:
            if v.status == "ACTIVE":
                return v
        return versions[0] if versions else None

    def get_scheme_version_at_date(
        self,
        db: Session,
        scheme_id: uuid.UUID,
        target_date: date,
    ) -> Optional[SchemeVersion]:
        """
        Retrieve the authoritative historical scheme version valid at target_date.
        """
        return self.get_active_scheme_version(db, scheme_id, evaluation_date=target_date)

    def detect_timeline_anomalies(
        self,
        db: Session,
        scheme_id: uuid.UUID,
    ) -> List[str]:
        """
        Detect temporal anomalies (overlapping date intervals or unexpected gaps)
        across consecutive versions of a scheme.
        """
        stmt = (
            select(SchemeVersion)
            .where(SchemeVersion.scheme_id == scheme_id)
            .order_by(SchemeVersion.version_number.asc())
        )
        versions = list(db.execute(stmt).scalars().all())
        anomalies: List[str] = []

        for i in range(len(versions) - 1):
            curr_v = versions[i]
            next_v = versions[i + 1]

            curr_until = curr_v.valid_until
            next_from = next_v.valid_from

            if curr_until and next_from:
                if curr_until > next_from:
                    anomalies.append(
                        f"VERSION_DATE_OVERLAP: v{curr_v.version_number} ends {curr_until} after v{next_v.version_number} begins {next_from}"
                    )
                elif next_from - curr_until > timedelta(days=1):
                    anomalies.append(
                        f"VERSION_DATE_GAP: Gap between v{curr_v.version_number} (until {curr_until}) and v{next_v.version_number} (from {next_from})"
                    )

        return anomalies
