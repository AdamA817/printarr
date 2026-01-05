"""Health check schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str
    database: str  # "connected" or "disconnected"


# ==================== Detailed Health Check Schemas (DEC-042) ====================


class SubsystemStatus(BaseModel):
    """Base status for a subsystem."""

    status: Literal["healthy", "degraded", "unhealthy"]


class DatabaseStatus(SubsystemStatus):
    """Database subsystem status."""

    latency_ms: float | None = None


class TelegramStatus(SubsystemStatus):
    """Telegram subsystem status."""

    connected: bool = False
    authenticated: bool = False


class WorkersStatus(SubsystemStatus):
    """Workers subsystem status."""

    jobs_queued: int = 0
    jobs_running: int = 0
    jobs_failed_24h: int = 0


class StorageStatus(SubsystemStatus):
    """Storage subsystem status."""

    library_gb: float = 0.0
    staging_gb: float = 0.0
    cache_gb: float = 0.0
    library_free_gb: float = 0.0


class RateLimiterStatus(SubsystemStatus):
    """Rate limiter subsystem status."""

    requests_total: int = 0
    throttled_count: int = 0
    channels_in_backoff: int = 0


class Subsystems(BaseModel):
    """All subsystem statuses."""

    database: DatabaseStatus
    telegram: TelegramStatus
    workers: WorkersStatus
    storage: StorageStatus
    rate_limiter: RateLimiterStatus


class RecentError(BaseModel):
    """Recent error entry."""

    job_id: str
    job_type: str
    error: str
    timestamp: str


class DetailedHealthResponse(BaseModel):
    """Detailed health check response (DEC-042)."""

    overall: Literal["healthy", "degraded", "unhealthy"]
    version: str
    subsystems: Subsystems
    errors: list[RecentError] = []
