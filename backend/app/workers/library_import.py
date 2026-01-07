"""Library import worker for organizing design files."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Job, JobType
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService
from app.services.library import LibraryError, LibraryImportService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

logger = get_logger(__name__)

# Throttle progress updates to avoid database spam
PROGRESS_UPDATE_INTERVAL_SECONDS = 1.0


class ImportToLibraryWorker(BaseWorker):
    """Worker for importing design files to the library.

    Processes IMPORT_TO_LIBRARY jobs by:
    1. Getting the design's files from staging
    2. Building library path from template
    3. Moving files to organized library folder
    4. Updating DesignFile records with new locations
    5. Cleaning up empty staging directories

    Uses the LibraryImportService for actual import logic.
    The LibraryImportService uses session-per-operation pattern to avoid
    holding database locks during file move operations.
    """

    job_types = [JobType.IMPORT_TO_LIBRARY]

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        worker_id: str | None = None,
    ):
        """Initialize the import worker.

        Args:
            poll_interval: Seconds between polling for jobs.
            worker_id: Optional identifier for this worker instance.
        """
        super().__init__(poll_interval=poll_interval, worker_id=worker_id)

    async def process(
        self, job: Job, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Process an import job.

        Moves design files from staging to the organized library
        folder structure based on template configuration.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict (expects design_id).

        Returns:
            Result dict with files_imported, total_bytes, and library_path.

        Raises:
            NonRetryableError: For missing design or staging directory.
            RetryableError: For transient file system errors.
        """
        design_id = job.design_id
        if not design_id:
            raise NonRetryableError("Job missing design_id")

        logger.info(
            "import_job_starting",
            job_id=job.id,
            design_id=design_id,
        )

        try:
            # LibraryImportService manages its own sessions for import_design
            # This prevents holding locks during file move operations
            service = LibraryImportService()
            result = await service.import_design(
                design_id,
                progress_callback=self._make_progress_callback(),
            )

            logger.info(
                "import_job_complete",
                job_id=job.id,
                design_id=design_id,
                files_imported=result["files_imported"],
                total_bytes=result["total_bytes"],
                library_path=result["library_path"],
            )

            # Queue AI analysis if enabled (DEC-043)
            if settings.ai_configured and settings.ai_auto_analyze_on_import:
                await self._queue_ai_analysis(design_id)

            # Return result for storage in job
            return {
                "files_imported": result["files_imported"],
                "total_bytes": result["total_bytes"],
                "library_path": result["library_path"],
            }

        except LibraryError as e:
            error_msg = str(e)
            logger.error(
                "import_job_error",
                job_id=job.id,
                design_id=design_id,
                error=error_msg,
            )

            # Check if this is a retryable error
            if "not found" in error_msg.lower():
                raise NonRetryableError(error_msg)
            else:
                # File system errors may be transient
                raise RetryableError(error_msg)

        except OSError as e:
            # File system errors
            error_msg = str(e)
            logger.error(
                "import_filesystem_error",
                job_id=job.id,
                design_id=design_id,
                error=error_msg,
            )
            # Retry file system errors (might be temporary disk issues)
            raise RetryableError(error_msg)

    async def _queue_ai_analysis(self, design_id: str) -> None:
        """Queue an AI analysis job for the design.

        Args:
            design_id: The design to analyze.
        """
        try:
            async with async_session_maker() as db:
                queue = JobQueueService(db)
                job = await queue.enqueue(
                    job_type=JobType.AI_ANALYZE_DESIGN,
                    design_id=design_id,
                    payload={"design_id": design_id},
                    priority=-1,  # Lower priority than user-triggered
                    display_name="AI Analysis (auto)",
                )
                await db.commit()

                logger.info(
                    "ai_analysis_auto_queued",
                    design_id=design_id,
                    job_id=job.id,
                )
        except Exception as e:
            # Don't fail the import if AI queueing fails
            logger.warning(
                "ai_analysis_queue_failed",
                design_id=design_id,
                error=str(e),
            )

    def _make_progress_callback(self):
        """Create a progress callback for tracking import progress.

        Returns:
            A callback function for tracking import progress.

        Note:
            Updates job progress in the database, throttled to avoid spam.
        """
        last_update_time = 0.0

        def sync_progress(current: int, total: int) -> None:
            nonlocal last_update_time

            if total <= 0:
                return

            percent = int((current / total) * 100)
            now = time.time()

            # Throttle updates
            should_update = (
                now - last_update_time >= PROGRESS_UPDATE_INTERVAL_SECONDS
                or current >= total  # Always update on completion
            )

            if should_update:
                last_update_time = now

                # Schedule async database update
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.update_progress(current, total))
                except RuntimeError:
                    pass

                logger.debug(
                    "import_progress",
                    current=current,
                    total=total,
                    percent=percent,
                )

        return sync_progress
