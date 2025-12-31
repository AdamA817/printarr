"""Stats API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Channel, Design, Job, JobStatus, JobType
from app.schemas.stats import StatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Get dashboard statistics.

    Returns counts for channels, designs, and active downloads.
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
