"""Health check endpoint."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check application health.

    Returns:
        Health status and application version.
    """
    return HealthResponse(
        status="ok",
        version=settings.version,
    )
