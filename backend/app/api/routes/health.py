"""Health check endpoints."""

import shutil
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Job, JobStatus
from app.schemas.health import (
    DatabaseStatus,
    DetailedHealthResponse,
    HealthResponse,
    RateLimiterStatus,
    RecentError,
    StorageStatus,
    Subsystems,
    TelegramStatus,
    WorkersStatus,
)

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

# Cache for detailed health check (5 second TTL)
_health_cache: dict = {"data": None, "expires": None}


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


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DetailedHealthResponse:
    """Detailed health check with subsystem status (DEC-042).

    Returns status for all subsystems:
    - database: connectivity and latency
    - telegram: connection and auth status
    - workers: job queue status
    - storage: disk usage
    - rate_limiter: request throttling status

    Results are cached for 5 seconds to avoid expensive checks.
    """
    global _health_cache

    # Check cache
    now = datetime.now(timezone.utc)
    if _health_cache["data"] and _health_cache["expires"] and _health_cache["expires"] > now:
        return _health_cache["data"]

    # Check all subsystems
    db_status = await _check_database(db)
    telegram_status = await _check_telegram()
    workers_status = await _check_workers(db)
    storage_status = _check_storage()
    rate_limiter_status = await _check_rate_limiter()

    # Get recent errors
    errors = await _get_recent_errors(db)

    # Determine overall status
    overall = _compute_overall_status(
        db_status, telegram_status, workers_status, storage_status, rate_limiter_status
    )

    result = DetailedHealthResponse(
        overall=overall,
        version=settings.version,
        subsystems=Subsystems(
            database=db_status,
            telegram=telegram_status,
            workers=workers_status,
            storage=storage_status,
            rate_limiter=rate_limiter_status,
        ),
        errors=errors,
    )

    # Cache result
    _health_cache["data"] = result
    _health_cache["expires"] = now + timedelta(seconds=5)

    # Set HTTP status
    if overall == "unhealthy":
        response.status_code = 503
    elif overall == "degraded":
        response.status_code = 200  # Still return 200 for degraded

    return result


async def _check_database(db: AsyncSession) -> DatabaseStatus:
    """Check database connectivity and latency."""
    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency_ms = (time.monotonic() - start) * 1000

        return DatabaseStatus(
            status="healthy",
            latency_ms=round(latency_ms, 2),
        )
    except Exception as e:
        logger.warning("database_health_check_failed", error=str(e))
        return DatabaseStatus(status="unhealthy", latency_ms=None)


async def _check_telegram() -> TelegramStatus:
    """Check Telegram connection status."""
    try:
        from app.telegram.service import TelegramService

        telegram = TelegramService.get_instance()
        connected = telegram.is_connected()
        authenticated = await telegram.is_authenticated() if connected else False

        if connected and authenticated:
            status = "healthy"
        elif connected:
            status = "degraded"
        else:
            status = "degraded"  # Telegram not connected is degraded, not unhealthy

        return TelegramStatus(
            status=status,
            connected=connected,
            authenticated=authenticated,
        )
    except Exception as e:
        logger.warning("telegram_health_check_failed", error=str(e))
        return TelegramStatus(status="degraded", connected=False, authenticated=False)


async def _check_workers(db: AsyncSession) -> WorkersStatus:
    """Check worker/job queue status."""
    try:
        # Count jobs by status
        result = await db.execute(
            select(Job.status, func.count(Job.id)).group_by(Job.status)
        )
        counts = {row[0]: row[1] for row in result}

        queued = counts.get(JobStatus.QUEUED, 0)
        running = counts.get(JobStatus.RUNNING, 0)

        # Count failed jobs in last 24 hours
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        failed_result = await db.execute(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.FAILED,
                Job.finished_at >= yesterday,
            )
        )
        failed_24h = failed_result.scalar() or 0

        # Workers are healthy if not too many failed jobs
        if failed_24h > 50:
            status = "degraded"
        else:
            status = "healthy"

        return WorkersStatus(
            status=status,
            jobs_queued=queued,
            jobs_running=running,
            jobs_failed_24h=failed_24h,
        )
    except Exception as e:
        logger.warning("workers_health_check_failed", error=str(e))
        return WorkersStatus(status="unhealthy")


def _check_storage() -> StorageStatus:
    """Check storage disk usage."""
    try:
        # Check library storage
        library_usage = shutil.disk_usage(settings.library_path)
        library_gb = library_usage.used / (1024**3)
        library_free_gb = library_usage.free / (1024**3)

        # Check staging storage
        staging_gb = 0.0
        if settings.staging_path.exists():
            staging_usage = shutil.disk_usage(settings.staging_path)
            staging_gb = staging_usage.used / (1024**3)

        # Check cache storage
        cache_gb = 0.0
        if settings.cache_path.exists():
            cache_usage = shutil.disk_usage(settings.cache_path)
            cache_gb = cache_usage.used / (1024**3)

        # Storage is degraded if free space < 10GB
        if library_free_gb < 10:
            status = "degraded"
        else:
            status = "healthy"

        return StorageStatus(
            status=status,
            library_gb=round(library_gb, 2),
            staging_gb=round(staging_gb, 2),
            cache_gb=round(cache_gb, 2),
            library_free_gb=round(library_free_gb, 2),
        )
    except Exception as e:
        logger.warning("storage_health_check_failed", error=str(e))
        return StorageStatus(status="unhealthy")


async def _check_rate_limiter() -> RateLimiterStatus:
    """Check Telegram rate limiter status."""
    try:
        from app.telegram.rate_limiter import TelegramRateLimiter

        rate_limiter = await TelegramRateLimiter.get_instance()
        stats = rate_limiter.get_stats()

        # Rate limiter is degraded if many channels are in backoff
        if stats["channels_in_backoff"] > 5:
            status = "degraded"
        else:
            status = "healthy"

        return RateLimiterStatus(
            status=status,
            requests_total=stats["requests_total"],
            throttled_count=stats["throttled_count"],
            channels_in_backoff=stats["channels_in_backoff"],
        )
    except Exception as e:
        logger.warning("rate_limiter_health_check_failed", error=str(e))
        return RateLimiterStatus(status="healthy")  # Default to healthy if not initialized


async def _get_recent_errors(db: AsyncSession, limit: int = 5) -> list[RecentError]:
    """Get recent job failures."""
    try:
        result = await db.execute(
            select(Job)
            .where(Job.status == JobStatus.FAILED, Job.last_error.isnot(None))
            .order_by(Job.finished_at.desc())
            .limit(limit)
        )
        jobs = result.scalars().all()

        return [
            RecentError(
                job_id=job.id,
                job_type=job.type.value,
                error=job.last_error[:200] if job.last_error else "Unknown error",
                timestamp=job.finished_at.isoformat() if job.finished_at else "",
            )
            for job in jobs
        ]
    except Exception:
        return []


def _compute_overall_status(
    db: DatabaseStatus,
    telegram: TelegramStatus,
    workers: WorkersStatus,
    storage: StorageStatus,
    rate_limiter: RateLimiterStatus,
) -> str:
    """Compute overall system status from subsystem statuses."""
    # Critical systems: database and workers
    critical = [db.status, workers.status]

    # Non-critical systems
    non_critical = [telegram.status, storage.status, rate_limiter.status]

    # Unhealthy if any critical system is unhealthy
    if any(s == "unhealthy" for s in critical):
        return "unhealthy"

    # Degraded if any critical system degraded or any non-critical unhealthy
    if any(s == "degraded" for s in critical) or any(s == "unhealthy" for s in non_critical):
        return "degraded"

    # Degraded if any non-critical degraded
    if any(s == "degraded" for s in non_critical):
        return "degraded"

    return "healthy"
