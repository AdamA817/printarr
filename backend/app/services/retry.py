"""Retry service for job failure handling (DEC-042).

Provides automatic retry scheduling with exponential backoff and
error categorization to determine retry eligibility.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Job, JobStatus

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ErrorCategory(str, Enum):
    """Categories for error handling (DEC-042).

    Determines whether a job should be retried based on error type.
    """

    TRANSIENT = "TRANSIENT"  # Network errors, rate limits, temp failures → retry
    PERMANENT = "PERMANENT"  # Invalid data, missing resource, auth failure → no retry
    UNKNOWN = "UNKNOWN"  # Unexpected errors → retry once


# Retry delays per DEC-042: 1m, 5m, 15m, 60m
RETRY_DELAYS = [
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
]

# Keywords that indicate transient errors (should retry)
TRANSIENT_ERROR_KEYWORDS = [
    "timeout",
    "timed out",
    "connection",
    "network",
    "rate limit",
    "flood",
    "429",  # Too Many Requests
    "502",  # Bad Gateway
    "503",  # Service Unavailable
    "504",  # Gateway Timeout
    "temporary",
    "unavailable",
    "retry",
    "throttl",
    "busy",
    "overload",
]

# Keywords that indicate permanent errors (no retry)
PERMANENT_ERROR_KEYWORDS = [
    "not found",
    "404",
    "missing",
    "invalid",
    "unauthorized",
    "401",
    "forbidden",
    "403",
    "permission denied",
    "does not exist",
    "already exists",
    "duplicate",
    "malformed",
    "corrupt",
    "password protected",
    "authentication failed",
]


class RetryService:
    """Service for managing job retries with exponential backoff.

    Implements DEC-042 retry strategy:
    - Retry delays: 1m, 5m, 15m, 60m
    - Error categorization for smart retry decisions
    - Max 4 attempts (1 initial + 3 retries)
    """

    def __init__(self, db: AsyncSession):
        """Initialize the retry service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db

    async def schedule_retry(self, job: Job, error: str | None = None) -> bool:
        """Schedule a retry for a failed job.

        Args:
            job: The failed job to retry.
            error: The error message (used for categorization).

        Returns:
            True if retry was scheduled, False if max retries exceeded.
        """
        # Check if we've exceeded max attempts
        if job.attempts >= job.max_attempts:
            logger.info(
                "retry_max_attempts_exceeded",
                job_id=job.id,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
            )
            return False

        # Categorize the error
        category = self.categorize_error(error) if error else ErrorCategory.UNKNOWN

        # Don't retry permanent errors
        if category == ErrorCategory.PERMANENT:
            logger.info(
                "retry_skipped_permanent_error",
                job_id=job.id,
                error_category=category.value,
                error=error,
            )
            return False

        # For unknown errors, only retry once
        if category == ErrorCategory.UNKNOWN and job.attempts >= 2:
            logger.info(
                "retry_skipped_unknown_error_max",
                job_id=job.id,
                attempts=job.attempts,
            )
            return False

        # Calculate next retry time
        delay = self.get_retry_delay(job.attempts)
        next_retry = datetime.now(timezone.utc) + delay

        # Schedule the retry
        job.status = JobStatus.QUEUED
        job.next_retry_at = next_retry
        job.started_at = None
        job.finished_at = None
        job.last_error = error

        await self.db.flush()

        logger.info(
            "retry_scheduled",
            job_id=job.id,
            attempt=job.attempts,
            delay_minutes=delay.total_seconds() / 60,
            next_retry_at=next_retry.isoformat(),
            error_category=category.value,
        )

        return True

    def get_retry_delay(self, attempt: int) -> timedelta:
        """Get the retry delay for a given attempt number.

        Uses the delays defined in DEC-042: 1m, 5m, 15m, 60m.

        Args:
            attempt: The current attempt number (1-indexed).

        Returns:
            Timedelta for how long to wait before retrying.
        """
        # attempt 1 → delay[0], attempt 2 → delay[1], etc.
        index = min(attempt - 1, len(RETRY_DELAYS) - 1)
        index = max(0, index)  # Ensure non-negative
        return RETRY_DELAYS[index]

    def categorize_error(self, error: str | None) -> ErrorCategory:
        """Categorize an error to determine retry behavior.

        Args:
            error: The error message to categorize.

        Returns:
            ErrorCategory indicating how to handle the error.
        """
        if not error:
            return ErrorCategory.UNKNOWN

        error_lower = error.lower()

        # Check for permanent errors first (higher precedence)
        for keyword in PERMANENT_ERROR_KEYWORDS:
            if keyword in error_lower:
                return ErrorCategory.PERMANENT

        # Check for transient errors
        for keyword in TRANSIENT_ERROR_KEYWORDS:
            if keyword in error_lower:
                return ErrorCategory.TRANSIENT

        # Unknown error type
        return ErrorCategory.UNKNOWN

    async def manual_retry(self, job_id: str) -> Job | None:
        """Manually trigger a retry for a failed job.

        Resets the job to QUEUED status regardless of attempt count.

        Args:
            job_id: The job ID to retry.

        Returns:
            The updated job, or None if not found or not retryable.
        """
        job = await self.db.get(Job, job_id)

        if not job:
            logger.warning("manual_retry_job_not_found", job_id=job_id)
            return None

        # Only retry failed or canceled jobs
        if job.status not in (JobStatus.FAILED, JobStatus.CANCELED):
            logger.warning(
                "manual_retry_invalid_status",
                job_id=job_id,
                status=job.status.value,
            )
            return None

        # Reset job for retry
        job.status = JobStatus.QUEUED
        job.attempts = 0  # Reset attempt count for manual retry
        job.next_retry_at = None  # Execute immediately
        job.started_at = None
        job.finished_at = None
        job.last_error = None

        await self.db.flush()

        logger.info(
            "manual_retry_scheduled",
            job_id=job_id,
            job_type=job.type.value,
        )

        return job

    async def get_retry_stats(self) -> dict:
        """Get statistics about job retries.

        Returns:
            Dictionary with retry statistics.
        """
        from sqlalchemy import func, select

        # Count jobs pending retry
        pending_result = await self.db.execute(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.QUEUED,
                Job.next_retry_at.isnot(None),
            )
        )
        pending_retry = pending_result.scalar() or 0

        # Count jobs that have been retried
        retried_result = await self.db.execute(
            select(func.count(Job.id)).where(Job.attempts > 1)
        )
        total_retried = retried_result.scalar() or 0

        # Count jobs failed after max retries
        failed_result = await self.db.execute(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.FAILED,
                Job.attempts >= Job.max_attempts,
            )
        )
        failed_after_max = failed_result.scalar() or 0

        return {
            "pending_retry": pending_retry,
            "total_retried": total_retried,
            "failed_after_max_retries": failed_after_max,
        }
