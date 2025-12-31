"""Stats API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Channel, Design, Job, JobStatus, JobType
from app.schemas.stats import (
    CalendarResponse,
    DashboardStatsResponse,
    QueueResponse,
    StatsResponse,
    StorageResponse,
)
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Get basic dashboard statistics (legacy endpoint).

    Returns counts for channels, designs, and active downloads.
    For more detailed statistics, use /dashboard/stats.
    """
    # Count channels
    result = await db.execute(select(func.count()).select_from(Channel))
    channels_count = result.scalar() or 0

    # Count designs
    result = await db.execute(select(func.count()).select_from(Design))
    designs_count = result.scalar() or 0

    # Count active downloads (RUNNING or QUEUED download jobs)
    result = await db.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.type == JobType.DOWNLOAD_DESIGN,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    downloads_active = result.scalar() or 0

    return StatsResponse(
        channels_count=channels_count,
        designs_count=designs_count,
        downloads_active=downloads_active,
    )


# Dashboard endpoints (Issue #103)


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    """Get comprehensive dashboard statistics.

    Returns design counts by status, channel counts, discovered channels,
    download statistics, and library info.
    """
    service = DashboardService(db)
    return await service.get_stats()


@router.get("/dashboard/calendar", response_model=CalendarResponse)
async def get_dashboard_calendar(
    days: int = Query(default=14, ge=1, le=90, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
) -> CalendarResponse:
    """Get calendar data for recent designs.

    Returns design counts by date for the dashboard calendar view.
    Includes up to 5 sample designs per day.
    """
    service = DashboardService(db)
    return await service.get_calendar(days=days)


@router.get("/dashboard/queue", response_model=QueueResponse)
async def get_dashboard_queue(
    db: AsyncSession = Depends(get_db),
) -> QueueResponse:
    """Get queue summary for dashboard.

    Returns active/queued job counts and recent completions/failures.
    """
    service = DashboardService(db)
    return await service.get_queue()


@router.get("/dashboard/storage", response_model=StorageResponse)
async def get_dashboard_storage(
    db: AsyncSession = Depends(get_db),
) -> StorageResponse:
    """Get storage breakdown for dashboard.

    Returns sizes for library, staging, and cache directories,
    plus available disk space. Results are cached for 5 minutes.
    """
    service = DashboardService(db)
    return await service.get_storage()
