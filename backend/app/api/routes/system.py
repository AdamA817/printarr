"""System API endpoints for status and activity monitoring."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Job, JobStatus, JobType

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


# =============================================================================
# Response Models
# =============================================================================


class SyncActivity(BaseModel):
    """Sync-related activity status."""

    channels_syncing: int = 0
    backfills_running: int = 0
    imports_syncing: int = 0


class DownloadActivity(BaseModel):
    """Download-related activity status."""

    active: int = 0
    queued: int = 0


class ImageActivity(BaseModel):
    """Image processing activity status."""

    telegram_downloading: int = 0
    previews_generating: int = 0


class AnalysisActivity(BaseModel):
    """Analysis-related activity status."""

    archives_extracting: int = 0
    importing_to_library: int = 0
    analyzing_3mf: int = 0


class ActivitySummary(BaseModel):
    """Summary of all activity."""

    total_active: int = 0
    total_queued: int = 0
    is_idle: bool = True


class SystemActivityResponse(BaseModel):
    """Response for system activity status endpoint."""

    sync: SyncActivity
    downloads: DownloadActivity
    images: ImageActivity
    analysis: AnalysisActivity
    summary: ActivitySummary


# =============================================================================
# Job Type to Category Mapping
# =============================================================================

# Maps JobType to (category, field, is_active_type)
# is_active_type: True if RUNNING state should count, False if QUEUED
JOB_CATEGORY_MAP: dict[JobType, tuple[str, str]] = {
    # Sync
    JobType.SYNC_CHANNEL_LIVE: ("sync", "channels_syncing"),
    JobType.BACKFILL_CHANNEL: ("sync", "backfills_running"),
    JobType.SYNC_IMPORT_SOURCE: ("sync", "imports_syncing"),
    # Downloads
    JobType.DOWNLOAD_DESIGN: ("downloads", "active"),
    JobType.DOWNLOAD_IMPORT_RECORD: ("downloads", "active"),  # DEC-040: Per-design downloads
    # Images
    JobType.DOWNLOAD_TELEGRAM_IMAGES: ("images", "telegram_downloading"),
    JobType.GENERATE_RENDER: ("images", "previews_generating"),
    # Analysis
    JobType.EXTRACT_ARCHIVE: ("analysis", "archives_extracting"),
    JobType.IMPORT_TO_LIBRARY: ("analysis", "importing_to_library"),
    JobType.ANALYZE_3MF: ("analysis", "analyzing_3mf"),
}


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/activity", response_model=SystemActivityResponse)
async def get_system_activity(
    db: AsyncSession = Depends(get_db),
) -> SystemActivityResponse:
    """Get current system activity status.

    Returns a summary of all running and queued background jobs,
    categorized by type (sync, downloads, images, analysis).

    This endpoint is designed to be polled frequently for the
    sidebar activity indicator.
    """
    # Single efficient query with GROUP BY
    query = select(
        Job.type,
        func.count(case((Job.status == JobStatus.RUNNING, 1))).label("running"),
        func.count(case((Job.status == JobStatus.QUEUED, 1))).label("queued"),
    ).where(
        Job.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
    ).group_by(Job.type)

    result = await db.execute(query)
    rows = result.all()

    # Initialize response structures
    sync = SyncActivity()
    downloads = DownloadActivity()
    images = ImageActivity()
    analysis = AnalysisActivity()

    total_active = 0
    total_queued = 0

    # Process results
    for row in rows:
        job_type = row.type
        running = row.running or 0
        queued = row.queued or 0

        total_active += running
        total_queued += queued

        # Map to category
        if job_type in JOB_CATEGORY_MAP:
            category, field = JOB_CATEGORY_MAP[job_type]

            if category == "sync":
                # Include both running and queued for sync stats (#186)
                # Users expect to see pending syncs immediately after triggering
                setattr(sync, field, running + queued)
            elif category == "downloads":
                if field == "active":
                    downloads.active = running
                    downloads.queued = queued
            elif category == "images":
                setattr(images, field, running)
            elif category == "analysis":
                setattr(analysis, field, running)

    summary = ActivitySummary(
        total_active=total_active,
        total_queued=total_queued,
        is_idle=total_active == 0 and total_queued == 0,
    )

    logger.debug(
        "system_activity_queried",
        total_active=total_active,
        total_queued=total_queued,
    )

    return SystemActivityResponse(
        sync=sync,
        downloads=downloads,
        images=images,
        analysis=analysis,
        summary=summary,
    )
