from datetime import date
from typing import Optional

from app.eligibility.models import CompiledScheme
from app.eligibility.result import SchemeAvailability


def check_scheme_availability(
    scheme: CompiledScheme,
    evaluation_date: Optional[date] = None,
) -> SchemeAvailability:
    """
    Deterministically verifies if a scheme is currently active as of evaluation_date.
    Does not mark a citizen ineligible for a scheme that is simply not active.
    """
    if evaluation_date is None:
        evaluation_date = date.today()

    if scheme.valid_from and evaluation_date < scheme.valid_from:
        return SchemeAvailability.NOT_YET_ACTIVE

    if scheme.valid_until and evaluation_date > scheme.valid_until:
        return SchemeAvailability.EXPIRED

    return SchemeAvailability.ACTIVE
