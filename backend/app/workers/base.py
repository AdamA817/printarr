"""Base worker class for processing background jobs."""

from __future__ import annotations

import asyncio
import signal
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.db.models import Job, JobStatus, JobType
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService

logger = get_logger(__name__)


def calculate_retry_delay(attempts: int) -> int:
    """Calculate retry delay with exponential backoff.

    Formula: min(30 * (2 ** attempts), 3600) seconds

    Args:
        attempts: Number of attempts so far.

    Returns:
        Delay in seconds before next retry.
    """
    return min(30 * (2 ** attempts), 3600)


class BaseWorker(ABC):
    """Abstract base class for background job workers.

    Subclasses must implement:
    - job_types: list of JobType values this worker handles
    - process(job): the actual job processing logic

    Features:
    - Configurable poll interval
    - Graceful shutdown handling
    - Automatic retry with exponential backoff
    - Error logging and job state updates
    - Progress tracking support
    """

    # Subclasses must set this to the job types they handle
    job_types: list[JobType] = []

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        batch_size: int = 1,
        worker_id: str | None = None,
    ):
        """Initialize the worker.

        Args:
            poll_interval: Seconds to wait between polling for jobs.
            batch_size: Number of jobs to claim per poll (for future use).
            worker_id: Optional identifier for this worker instance.
        """
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.worker_id = worker_id or self.__class__.__name__

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._current_job: Job | None = None
        self._jobs_processed = 0
        self._jobs_failed = 0
        self._started_at: datetime | None = None
        self._last_progress_update: datetime | None = None
        self._progress_update_interval = 1.0  # Minimum seconds between updates

    @abstractmethod
    async def process(
        self, job: Job, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Process a single job.

        Subclasses must implement this method. The job is already claimed
        (status=RUNNING) when this is called.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict from job.payload_json.

        Returns:
            Optional result dict with completion stats (bytes, files, etc.)
            that will be stored in the job's result_json field.

        Raises:
            Any exception will be caught and logged, and the job
            will be marked as failed (with potential retry).
        """
        pass

    async def run(self) -> None:
        """Main worker loop.

        Polls for jobs and processes them until shutdown is requested.
        """
        self._running = True
        self._started_at = datetime.now(timezone.utc)
        self._setup_signal_handlers()

        logger.info(
            "worker_started",
            worker_id=self.worker_id,
            job_types=[jt.value for jt in self.job_types],
            poll_interval=self.poll_interval,
        )

        try:
            while self._running and not self._shutdown_event.is_set():
                try:
                    await self._poll_and_process()
                except Exception as e:
                    logger.error(
                        "worker_poll_error",
                        worker_id=self.worker_id,
                        error=str(e),
                        exc_info=True,
                    )
                    # Wait before retrying after unexpected error
                    await asyncio.sleep(self.poll_interval * 2)
        finally:
            logger.info(
                "worker_stopped",
                worker_id=self.worker_id,
                jobs_processed=self._jobs_processed,
                jobs_failed=self._jobs_failed,
                uptime_seconds=self._uptime_seconds(),
            )

    async def _poll_and_process(self) -> None:
        """Poll for a job and process it if found."""
        async with async_session_maker() as db:
            queue = JobQueueService(db)

            # Try to claim a job
            job = await queue.dequeue(self.job_types or None)

            if job is None:
                # No job available, wait and retry
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval,
                    )
                except TimeoutError:
                    pass
                return

            # CRITICAL: Commit the job claim BEFORE processing to release
            # the database lock. This allows the process() method to use
            # its own session without deadlocking with this one.
            await db.commit()

            # Process the job
            self._current_job = job
            self._last_progress_update = None  # Reset throttle for new job
            payload = queue.get_payload(job)

            try:
                logger.info(
                    "job_processing_start",
                    worker_id=self.worker_id,
                    job_id=job.id,
                    job_type=job.type.value,
                )

                result = await self.process(job, payload)

                # Mark success with optional result
                await queue.complete(job.id, success=True, result=result)
                self._jobs_processed += 1

            except Exception as e:
                error_msg = str(e)
                logger.error(
                    "job_processing_error",
                    worker_id=self.worker_id,
                    job_id=job.id,
                    job_type=job.type.value,
                    error=error_msg,
                    exc_info=True,
                )

                # Mark failure (may trigger retry)
                await queue.complete(job.id, success=False, error=error_msg)
                self._jobs_failed += 1

                # If job will be retried, calculate delay
                # Re-fetch job to check updated status
                updated_job = await queue.get_job(job.id)
                if updated_job and updated_job.status == JobStatus.QUEUED:
                    delay = calculate_retry_delay(updated_job.attempts)
                    logger.info(
                        "job_retry_scheduled",
                        job_id=job.id,
                        attempt=updated_job.attempts,
                        delay_seconds=delay,
                    )

            finally:
                self._current_job = None
                # Commit the transaction
                await db.commit()

    async def update_progress(
        self,
        current: int,
        total: int | None = None,
        force: bool = False,
    ) -> None:
        """Update progress for the current job.

        This method is non-fatal - if the progress update fails due to
        database locking (common with SQLite during long-running operations),
        the error is logged but doesn't cause the job to fail.

        Progress updates are throttled to avoid excessive database writes.
        Use force=True to bypass throttling (e.g., for 100% completion).

        Args:
            current: Current progress value.
            total: Total expected value.
            force: Bypass throttling if True.
        """
        if self._current_job is None:
            return

        # Throttle progress updates to reduce DB contention
        now = datetime.now(timezone.utc)
        if not force and self._last_progress_update:
            elapsed = (now - self._last_progress_update).total_seconds()
            if elapsed < self._progress_update_interval:
                return  # Skip this update

        try:
            async with async_session_maker() as db:
                queue = JobQueueService(db)
                await queue.update_progress(self._current_job.id, current, total)
                await db.commit()
            self._last_progress_update = now
        except Exception as e:
            # Progress updates are non-fatal - log and continue
            # This prevents SQLite locking issues from causing job failures
            logger.debug(
                "progress_update_failed",
                job_id=self._current_job.id,
                current=current,
                total=total,
                error=str(e),
            )

    def request_shutdown(self) -> None:
        """Request graceful shutdown of the worker."""
        logger.info(
            "worker_shutdown_requested",
            worker_id=self.worker_id,
            current_job_id=self._current_job.id if self._current_job else None,
        )
        self._running = False
        self._shutdown_event.set()

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_running_loop()

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    self.request_shutdown,
                )
        except (NotImplementedError, RuntimeError):
            # Signal handlers not supported (e.g., Windows, or running in thread)
            pass

    def _uptime_seconds(self) -> int:
        """Calculate worker uptime in seconds."""
        if self._started_at:
            return int((datetime.now(timezone.utc) - self._started_at).total_seconds())
        return 0

    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self._running

    @property
    def is_processing(self) -> bool:
        """Check if worker is currently processing a job."""
        return self._current_job is not None

    @property
    def stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.worker_id,
            "job_types": [jt.value for jt in self.job_types],
            "is_running": self._running,
            "is_processing": self._current_job is not None,
            "current_job_id": self._current_job.id if self._current_job else None,
            "jobs_processed": self._jobs_processed,
            "jobs_failed": self._jobs_failed,
            "uptime_seconds": self._uptime_seconds(),
        }


class RetryableError(Exception):
    """Exception that indicates a job should be retried.

    Use this when you want the job to be retried but with a specific
    error message.
    """

    pass


class NonRetryableError(Exception):
    """Exception that indicates a job should not be retried.

    The job will be marked as failed immediately without using
    remaining retry attempts.
    """

    pass
