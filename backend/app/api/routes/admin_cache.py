import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.cache.verified_rule_cache import get_rule_cache
from app.database.session import get_db

logger = logging.getLogger("jansetu.api.admin_cache")

router = APIRouter(prefix="/admin/cache", tags=["Admin System & Cache"])


@router.get(
    "/rules",
    summary="Get verified rule cache metrics",
)
def get_rule_cache_status() -> Dict[str, Any]:
    """
    Returns rule cache entries, hits, misses, loads, refreshes, and compile failures.
    Does not expose sensitive or citizen data.
    """
    cache = get_rule_cache()
    return cache.get_metrics_dict()


@router.post(
    "/rules/refresh",
    summary="Refresh cached verified rules",
)
def refresh_rule_cache(
    scheme_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Refreshes a specific scheme or all cached rules from PostgreSQL.
    """
    cache = get_rule_cache()
    if scheme_id:
        compiled = cache.refresh_scheme(scheme_id, session=db)
        return {
            "status": "refreshed",
            "scheme_id": scheme_id,
            "success": compiled is not None,
            "cache_metrics": cache.get_metrics_dict(),
        }
    else:
        count = cache.refresh_all(session=db)
        return {
            "status": "refreshed_all",
            "count": count,
            "cache_metrics": cache.get_metrics_dict(),
        }
