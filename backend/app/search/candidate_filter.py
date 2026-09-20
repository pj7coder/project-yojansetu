from datetime import date
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models.scheme_search_metadata import SchemeSearchMetadata
from app.eligibility.profile import CitizenProfile

logger = logging.getLogger("jansetu.search.candidate_filter")


class CandidateFilterService:
    """
    High-recall SQL candidate filtering over verified scheme search metadata.
    Reduces the candidate set from thousands of schemes to a small, relevant candidate set.
    Strict Invariant: Never filter on unknown profile attributes!
    """

    @classmethod
    def filter_candidates(
        cls,
        session: Session,
        profile: CitizenProfile,
        evaluation_date: Optional[date] = None,
        category: Optional[str] = None,
        max_candidates: Optional[int] = None,
    ) -> Tuple[List[str], int]:
        """
        Executes safe candidate filtering query.
        Returns:
            (candidate_scheme_ids, total_verified_active_count)
        """
        settings = get_settings()
        eval_date = evaluation_date or date.today()
        limit = max_candidates or settings.max_sql_candidates

        # 1. Base query for verified active schemes
        conditions = [
            SchemeSearchMetadata.is_verified == True,
            SchemeSearchMetadata.is_active == True,
            # Temporal boundaries
            or_(
                SchemeSearchMetadata.valid_from == None,
                SchemeSearchMetadata.valid_from <= eval_date,
            ),
            or_(
                SchemeSearchMetadata.valid_until == None,
                SchemeSearchMetadata.valid_until >= eval_date,
            ),
        ]

        # 2. Scheme Origin Policy
        if not settings.include_central_schemes:
            # Only include Rajasthan state schemes and centrally sponsored schemes with state participation
            conditions.append(
                SchemeSearchMetadata.scheme_origin.in_([
                    "RAJASTHAN_STATE",
                    "CENTRALLY_SPONSORED",
                    "RAJASTHAN_MODIFIED_CSS",
                    "UNKNOWN",
                ])
            )

        # 3. State Jurisdiction Filtering
        if profile.state:
            # Citizen state is explicitly known
            if profile.state.lower() == "rajasthan":
                conditions.append(
                    or_(
                        SchemeSearchMetadata.state == None,
                        func.lower(SchemeSearchMetadata.state) == "rajasthan",
                        func.lower(SchemeSearchMetadata.state) == "all_india",
                    )
                )
            else:
                # Citizen is from another state (e.g. Gujarat); exclude Rajasthan-only schemes
                conditions.append(
                    func.lower(SchemeSearchMetadata.state) == profile.state.lower()
                )
        # If profile.state is unknown: DO NOT filter by state!

        # 4. District Filtering (High Recall!)
        if profile.district:
            # If district is explicitly known, match schemes that are statewide (empty districts list)
            # OR explicitly list this district.
            dist_str = f'"{profile.district}"'
            conditions.append(
                or_(
                    SchemeSearchMetadata.districts == None,
                    func.jsonb_array_length(SchemeSearchMetadata.districts) == 0,
                    SchemeSearchMetadata.districts.contains([profile.district]),
                    SchemeSearchMetadata.districts.contains([profile.district.lower()]),
                )
            )
        # If profile.district is unknown: DO NOT filter by district!

        # 5. Rural / Urban Filtering
        if profile.rural_urban:
            ru = profile.rural_urban.upper()
            if ru in ("RURAL", "URBAN"):
                conditions.append(
                    SchemeSearchMetadata.rural_urban.in_([ru, "BOTH", "ALL"])
                )
        # If profile.rural_urban is unknown: DO NOT filter by rural/urban!

        # 6. Optional Category Filter
        if category:
            conditions.append(
                func.lower(SchemeSearchMetadata.category) == category.lower().strip()
            )

        # Execute total verified count query for diagnostics
        total_stmt = select(func.count()).select_from(SchemeSearchMetadata).where(
            SchemeSearchMetadata.is_verified == True,
            SchemeSearchMetadata.is_active == True,
        )
        total_verified = session.execute(total_stmt).scalar() or 0

        # Execute candidate selection query
        candidate_stmt = (
            select(SchemeSearchMetadata.scheme_id)
            .where(and_(*conditions))
            .order_by(SchemeSearchMetadata.scheme_id.asc())
            .limit(limit)
        )

        candidate_ids = list(session.execute(candidate_stmt).scalars().all())

        logger.debug(
            f"Candidate filtering: {len(candidate_ids)} candidates matched out of {total_verified} verified schemes"
        )
        return candidate_ids, total_verified
