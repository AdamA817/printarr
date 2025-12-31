"""Extract worker for processing archive extraction jobs."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.logging import get_logger
from app.db.models import Job, JobType
from app.db.session import async_session_maker
from app.services.archive import (
    ArchiveError,
    ArchiveExtractor,
    CorruptedArchiveError,
    MissingPartError,
    PasswordProtectedError,
)
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

logger = get_logger(__name__)

# Throttle progress updates to avoid database spam
PROGRESS_UPDATE_INTERVAL_SECONDS = 1.0


class ExtractArchiveWorker(BaseWorker):
    """Worker for extracting archive files.

    Processes EXTRACT_ARCHIVE jobs by:
    1. Finding archives in the design's staging directory
    2. Extracting supported formats (zip, rar, 7z, tar)
    3. Creating DesignFile records for extracted files
    4. Handling nested archives (one level deep)
    5. Deleting original archives after extraction
    6. Queuing IMPORT_TO_LIBRARY job when complete

    Uses the ArchiveExtractor service for actual extraction.
    The ArchiveExtractor uses session-per-operation pattern to avoid
    holding database locks during long extraction operations.
    """

    job_types = [JobType.EXTRACT_ARCHIVE]

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        worker_id: str | None = None,
    ):
        """Initialize the extract worker.

        Args:
            poll_interval: Seconds between polling for jobs.
            worker_id: Optional identifier for this worker instance.
        """
        super().__init__(poll_interval=poll_interval, worker_id=worker_id)

    async def process(
        self, job: Job, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Process an extraction job.

        Extracts all archives in the design's staging directory,
        creates DesignFile records, and queues import job.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict (expects design_id).

        Returns:
            Result dict with archives_extracted and files_created.

        Raises:
            NonRetryableError: For password protection, corruption, missing parts.
            RetryableError: For transient errors.
        """
        design_id = job.design_id
        if not design_id:
            raise NonRetryableError("Job missing design_id")

        logger.info(
            "extract_job_starting",
            job_id=job.id,
            design_id=design_id,
        )

        try:
            # ArchiveExtractor manages its own sessions for extract_design_archives
            # This prevents holding locks during long extraction operations
            extractor = ArchiveExtractor()
            result = await extractor.extract_design_archives(
                design_id,
                progress_callback=self._make_progress_callback(),
            )

            logger.info(
                "extract_job_complete",
                job_id=job.id,
                design_id=design_id,
                archives_extracted=result["archives_extracted"],
                files_created=result["files_created"],
                nested_archives=result["nested_archives"],
            )

            # Queue import job if files were extracted
            # This needs a session, so we open one briefly
            if result["files_created"] > 0:
                async with async_session_maker() as db:
                    extractor_with_db = ArchiveExtractor(db)
                    import_job_id = await extractor_with_db.queue_import(design_id)
                    await db.commit()

                    logger.info(
                        "import_job_queued",
                        design_id=design_id,
                        import_job_id=import_job_id,
                    )

            # Return result for storage in job
            return {
                "archives_extracted": result["archives_extracted"],
                "files_created": result["files_created"],
                "nested_archives": result["nested_archives"],
            }

        except PasswordProtectedError as e:
            logger.error(
                "extract_password_protected",
                job_id=job.id,
                design_id=design_id,
                error=str(e),
            )
            raise NonRetryableError(str(e))

        except CorruptedArchiveError as e:
            logger.error(
                "extract_corrupted_archive",
                job_id=job.id,
                design_id=design_id,
                error=str(e),
            )
            raise NonRetryableError(str(e))

        except MissingPartError as e:
            logger.error(
                "extract_missing_part",
                job_id=job.id,
                design_id=design_id,
                error=str(e),
            )
            raise NonRetryableError(str(e))

        except ArchiveError as e:
            error_msg = str(e)
            logger.error(
                "extract_job_error",
                job_id=job.id,
                design_id=design_id,
                error=error_msg,
            )
            # Default to retryable for generic archive errors
            raise RetryableError(error_msg)

    def _make_progress_callback(self):
        """Create a progress callback for tracking extraction progress.

        Returns:
            A callback function for tracking extraction progress.

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
                    "extract_progress",
                    current=current,
                    total=total,
                    percent=percent,
                )

        return sync_progress
