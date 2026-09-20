import logging
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.database.session import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter()
logger = logging.getLogger("jansetu.health")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns operational status and runtime metadata for the backend service.",
    tags=["System"],
)
async def check_health(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Health check endpoint confirming backend availability."""
    logger.info("Health endpoint called")
    return HealthResponse(
        status="ok",
        service="jansetu-backend",
        environment=settings.app_env,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/health/database",
    summary="Database Health Check",
    description="Probes PostgreSQL database connectivity.",
    tags=["System"],
)
async def check_database_health() -> Dict[str, str]:
    """Database connectivity health check."""
    logger.info("Database health probe called")
    is_connected = check_database_connection()
    if not is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "disconnected"},
        )
    return {
        "status": "ok",
        "database": "connected",
    }
