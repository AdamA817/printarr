"""Stats API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import Channel
from app.schemas.stats import StatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Get dashboard statistics.

    Returns counts for channels, designs, and active downloads.
    Designs and downloads are placeholders until those features are implemented.
    """
    # Count channels
    result = await db.execute(select(func.count()).select_from(Channel))
    channels_count = result.scalar() or 0

    return StatsResponse(
        channels_count=channels_count,
        designs_count=0,  # TODO: Implement when designs feature is added
        downloads_active=0,  # TODO: Implement when downloads feature is added
    )
