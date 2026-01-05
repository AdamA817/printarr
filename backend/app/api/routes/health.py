"""Health check endpoint."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response, db: AsyncSession = Depends(get_db)
) -> HealthResponse:
    """Check application health including database connectivity.

    Returns 200 when healthy, 503 when database is unavailable.

    Returns:
        Health status, application version, and database status.
    """
    # Check database connection
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Set HTTP status based on health
    if db_status != "connected":
        response.status_code = 503

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version=settings.version,
        database=db_status,
    )
