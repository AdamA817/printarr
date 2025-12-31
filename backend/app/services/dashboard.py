"""Dashboard statistics service.

Provides aggregated statistics for the dashboard with caching
for expensive operations like storage calculations.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.logging import get_logger
from app.db.models import (
    Channel,
    Design,
    DesignStatus,
    DiscoveredChannel,
    Job,
    JobStatus,
    JobType,
)
from app.schemas.stats import (
    CalendarDay,
    CalendarDesign,
    CalendarResponse,
    ChannelCounts,
    DashboardStatsResponse,
    DesignStatusCounts,
    DownloadStats,
    JobSummary,
    QueueResponse,
    StorageResponse,
)

logger = get_logger(__name__)

# Cache for storage calculations (expensive I/O operations)
_storage_cache: dict[str, tuple[Any, float]] = {}
STORAGE_CACHE_TTL = 300  # 5 minutes


class DashboardService:
    """Service for computing dashboard statistics."""

    def __init__(self, db: AsyncSession):
        """Initialize the dashboard service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.settings = app_settings

    async def get_stats(self) -> DashboardStatsResponse:
        """Get comprehensive dashboard statistics.

        Returns:
            DashboardStatsResponse with all statistics.
        """
        # Run all queries in parallel for performance
        (
            design_counts,
            channel_counts,
            discovered_count,
            download_stats,
            library_stats,
        ) = await asyncio.gather(
            self._get_design_status_counts(),
            self._get_channel_counts(),
            self._get_discovered_channels_count(),
            self._get_download_stats(),
            self._get_library_stats(),
        )

        return DashboardStatsResponse(
            designs=design_counts,
            channels=channel_counts,
            discovered_channels=discovered_count,
            downloads=download_stats,
            library_file_count=library_stats["file_count"],
            library_size_bytes=library_stats["size_bytes"],
        )

    async def get_calendar(self, days: int = 14) -> CalendarResponse:
        """Get calendar data for recent designs.

        Args:
            days: Number of days to include (default 14).

        Returns:
            CalendarResponse with design counts by date.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        start_datetime = datetime.combine(start_date, datetime.min.time())

        # Query designs grouped by date
        result = await self.db.execute(
            select(
                func.date(Design.created_at).label("date"),
                func.count(Design.id).label("count"),
            )
            .where(Design.created_at >= start_datetime)
            .group_by(func.date(Design.created_at))
            .order_by(func.date(Design.created_at).desc())
        )
        date_counts = {row.date: row.count for row in result.all()}

        # Get sample designs for each day (limit 5 per day)
        designs_by_date: dict[date, list[CalendarDesign]] = defaultdict(list)

        if date_counts:
            result = await self.db.execute(
                select(Design)
                .where(Design.created_at >= start_datetime)
                .order_by(Design.created_at.desc())
            )
            designs = result.scalars().all()

            for design in designs:
                design_date = design.created_at.date()
                if len(designs_by_date[design_date]) < 5:
                    designs_by_date[design_date].append(
                        CalendarDesign(
                            id=design.id,
                            title=design.canonical_title,
                            thumbnail_url=design.thumbnail_url,
                        )
                    )

        # Build calendar days (include all days even if empty)
        calendar_days = []
        current = end_date
        while current >= start_date:
            count = date_counts.get(current, 0)
            calendar_days.append(
                CalendarDay(
                    date=current,
                    count=count,
                    designs=designs_by_date.get(current, []),
                )
            )
            current -= timedelta(days=1)

        total_period = sum(date_counts.values())

        return CalendarResponse(
            days=calendar_days,
            total_period=total_period,
        )

    async def get_queue(self) -> QueueResponse:
        """Get queue summary.

        Returns:
            QueueResponse with job counts and recent completions/failures.
        """
        # Count running jobs
        result = await self.db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == JobStatus.RUNNING)
        )
        running = result.scalar() or 0

        # Count queued jobs
        result = await self.db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == JobStatus.QUEUED)
        )
        queued = result.scalar() or 0

        # Get recent completions (last 10)
        result = await self.db.execute(
            select(Job)
            .where(Job.status == JobStatus.SUCCESS)
            .order_by(Job.finished_at.desc())
            .limit(10)
        )
        recent_completions = [
            await self._job_to_summary(job) for job in result.scalars().all()
        ]

        # Get recent failures (last 5)
        result = await self.db.execute(
            select(Job)
            .where(Job.status == JobStatus.FAILED)
            .order_by(Job.finished_at.desc())
            .limit(5)
        )
        recent_failures = [
            await self._job_to_summary(job) for job in result.scalars().all()
        ]

        return QueueResponse(
            running=running,
            queued=queued,
            recent_completions=recent_completions,
            recent_failures=recent_failures,
        )

    async def get_storage(self) -> StorageResponse:
        """Get storage breakdown.

        Results are cached for 5 minutes to avoid expensive I/O.

        Returns:
            StorageResponse with directory sizes and disk space.
        """
        cache_key = "storage_stats"
        now = time.time()

        # Check cache
        if cache_key in _storage_cache:
            cached_value, cached_time = _storage_cache[cache_key]
            if now - cached_time < STORAGE_CACHE_TTL:
                logger.debug("storage_cache_hit")
                return cached_value

        # Calculate sizes (expensive I/O operations)
        library_size = await self._calculate_directory_size(
            self.settings.library_path
        )
        staging_size = await self._calculate_directory_size(
            self.settings.staging_path
        )
        cache_size = await self._calculate_directory_size(
            Path(self.settings.data_path) / "cache"
        )

        # Get disk space
        available, total = await self._get_disk_space(self.settings.library_path)

        result = StorageResponse(
            library_size_bytes=library_size,
            staging_size_bytes=staging_size,
            cache_size_bytes=cache_size,
            available_bytes=available,
            total_bytes=total,
        )

        # Update cache
        _storage_cache[cache_key] = (result, now)
        logger.debug("storage_cache_updated")

        return result

    # Private helper methods

    async def _get_design_status_counts(self) -> DesignStatusCounts:
        """Get design counts by status."""
        result = await self.db.execute(
            select(Design.status, func.count(Design.id))
            .group_by(Design.status)
        )
        counts_by_status = {row[0]: row[1] for row in result.all()}

        total = sum(counts_by_status.values())

        return DesignStatusCounts(
            discovered=counts_by_status.get(DesignStatus.DISCOVERED, 0),
            wanted=counts_by_status.get(DesignStatus.WANTED, 0),
            downloading=counts_by_status.get(DesignStatus.DOWNLOADING, 0),
            downloaded=counts_by_status.get(DesignStatus.DOWNLOADED, 0),
            imported=counts_by_status.get(DesignStatus.IMPORTED, 0),
            failed=counts_by_status.get(DesignStatus.FAILED, 0),
            total=total,
        )

    async def _get_channel_counts(self) -> ChannelCounts:
        """Get channel counts by enabled state."""
        result = await self.db.execute(
            select(Channel.is_enabled, func.count(Channel.id))
            .group_by(Channel.is_enabled)
        )
        counts_by_enabled = {row[0]: row[1] for row in result.all()}

        enabled = counts_by_enabled.get(True, 0)
        disabled = counts_by_enabled.get(False, 0)

        return ChannelCounts(
            enabled=enabled,
            disabled=disabled,
            total=enabled + disabled,
        )

    async def _get_discovered_channels_count(self) -> int:
        """Get count of discovered channels."""
        result = await self.db.execute(
            select(func.count()).select_from(DiscoveredChannel)
        )
        return result.scalar() or 0

    async def _get_download_stats(self) -> DownloadStats:
        """Get download statistics."""
        now = datetime.utcnow()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())

        # Downloads completed today
        result = await self.db.execute(
            select(func.count())
            .select_from(Job)
            .where(
                Job.type == JobType.DOWNLOAD_DESIGN,
                Job.status == JobStatus.SUCCESS,
                Job.finished_at >= today_start,
            )
        )
        today = result.scalar() or 0

        # Downloads completed this week
        result = await self.db.execute(
            select(func.count())
            .select_from(Job)
            .where(
                Job.type == JobType.DOWNLOAD_DESIGN,
                Job.status == JobStatus.SUCCESS,
                Job.finished_at >= week_start,
            )
        )
        this_week = result.scalar() or 0

        # Active downloads
        result = await self.db.execute(
            select(func.count())
            .select_from(Job)
            .where(
                Job.type == JobType.DOWNLOAD_DESIGN,
                Job.status == JobStatus.RUNNING,
            )
        )
        active = result.scalar() or 0

        # Queued downloads
        result = await self.db.execute(
            select(func.count())
            .select_from(Job)
            .where(
                Job.type == JobType.DOWNLOAD_DESIGN,
                Job.status == JobStatus.QUEUED,
            )
        )
        queued = result.scalar() or 0

        return DownloadStats(
            today=today,
            this_week=this_week,
            active=active,
            queued=queued,
        )

    async def _get_library_stats(self) -> dict[str, int]:
        """Get library file count and size."""
        library_path = Path(self.settings.library_path)

        if not library_path.exists():
            return {"file_count": 0, "size_bytes": 0}

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        file_count, size_bytes = await loop.run_in_executor(
            None, self._count_files_and_size, library_path
        )

        return {"file_count": file_count, "size_bytes": size_bytes}

    def _count_files_and_size(self, path: Path) -> tuple[int, int]:
        """Count files and total size in a directory (sync operation)."""
        file_count = 0
        size_bytes = 0

        try:
            for root, dirs, files in os.walk(path):
                for f in files:
                    file_path = Path(root) / f
                    try:
                        file_count += 1
                        size_bytes += file_path.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError) as e:
            logger.warning("library_scan_error", path=str(path), error=str(e))

        return file_count, size_bytes

    async def _job_to_summary(self, job: Job) -> JobSummary:
        """Convert a Job to a JobSummary."""
        design_title = None
        if job.design_id:
            result = await self.db.execute(
                select(Design.canonical_title).where(Design.id == job.design_id)
            )
            design_title = result.scalar()

        return JobSummary(
            id=job.id,
            type=job.type.value,
            status=job.status.value,
            design_title=design_title,
            created_at=job.created_at,
            finished_at=job.finished_at,
            error=job.last_error,
        )

    async def _calculate_directory_size(self, path: Path | str) -> int:
        """Calculate total size of a directory in bytes."""
        path = Path(path)

        if not path.exists():
            return 0

        loop = asyncio.get_event_loop()
        _, size_bytes = await loop.run_in_executor(
            None, self._count_files_and_size, path
        )
        return size_bytes

    async def _get_disk_space(self, path: Path | str) -> tuple[int, int]:
        """Get available and total disk space.

        Returns:
            Tuple of (available_bytes, total_bytes).
        """
        path = Path(path)

        # Find an existing parent path
        check_path = path
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent

        if not check_path.exists():
            return 0, 0

        try:
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(None, os.statvfs, str(check_path))
            available = stat.f_bavail * stat.f_frsize
            total = stat.f_blocks * stat.f_frsize
            return available, total
        except (OSError, AttributeError):
            # AttributeError: statvfs not available on Windows
            return 0, 0


def clear_storage_cache() -> None:
    """Clear the storage cache (for testing)."""
    _storage_cache.clear()
