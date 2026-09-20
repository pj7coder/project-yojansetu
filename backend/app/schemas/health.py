from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for API health status check."""

    status: str = Field(..., description="Operational status of the backend service", examples=["ok"])
    service: str = Field(..., description="Service identifier", examples=["yojansetu-backend"])
    environment: str = Field(..., description="Active runtime environment", examples=["development"])
    version: str = Field(..., description="Application semantic version", examples=["0.1.0"])
    timestamp: datetime = Field(..., description="UTC timestamp of the health check")
