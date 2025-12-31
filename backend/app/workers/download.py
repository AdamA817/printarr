"""Download worker for processing design file downloads from Telegram."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.db.models import Job, JobType
from app.db.session import async_session_maker
from app.services.download import DownloadError, DownloadService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

logger = get_logger(__name__)


class DownloadWorker(BaseWorker):
    """Worker for downloading design files from Telegram.

    Processes DOWNLOAD_DESIGN jobs by:
    1. Fetching design attachments from Telegram
    2. Saving files to staging directory
    3. Computing SHA256 hashes for integrity
    4. Queuing extraction if archives are present

    Uses the DownloadService for actual download logic.
    The DownloadService uses session-per-operation pattern to avoid
    holding database locks during long file downloads.
    """

    job_types = [JobType.DOWNLOAD_DESIGN]

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        worker_id: str | None = None,
    ):
        """Initialize the download worker.

        Args:
            poll_interval: Seconds between polling for jobs.
            worker_id: Optional identifier for this worker instance.
        """
        super().__init__(poll_interval=poll_interval, worker_id=worker_id)

    async def process(self, job: Job, payload: dict[str, Any] | None) -> None:
        """Process a download job.

        Downloads all attachments for a design from Telegram,
        saves them to the staging directory, and queues extraction
        if archives are present.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict (expects design_id).

        Raises:
            NonRetryableError: If design not found or no attachments.
            RetryableError: For transient errors like rate limits.
        """
        design_id = job.design_id
        if not design_id:
            raise NonRetryableError("Job missing design_id")

        logger.info(
            "download_job_starting",
            job_id=job.id,
            design_id=design_id,
        )

        try:
            # DownloadService manages its own sessions for download_design
            # This prevents holding locks during long Telegram downloads
            service = DownloadService()
            result = await service.download_design(
                design_id,
                progress_callback=self._make_progress_callback(),
            )

            logger.info(
                "download_job_complete",
                job_id=job.id,
                design_id=design_id,
                files_downloaded=result["files_downloaded"],
                total_bytes=result["total_bytes"],
                has_archives=result["has_archives"],
            )

            # Queue extraction if archives were downloaded
            # This needs a session, so we open one briefly
            if result["has_archives"]:
                async with async_session_maker() as db:
                    service_with_db = DownloadService(db)
                    extraction_job_id = await service_with_db.queue_extraction(design_id)
                    await db.commit()

                    if extraction_job_id:
                        logger.info(
                            "extraction_job_queued",
                            design_id=design_id,
                            extraction_job_id=extraction_job_id,
                        )

        except DownloadError as e:
            error_msg = str(e)
            logger.error(
                "download_job_error",
                job_id=job.id,
                design_id=design_id,
                error=error_msg,
            )

            # Check if this is a retryable error
            if "Rate limited" in error_msg:
                raise RetryableError(error_msg)
            elif "not found" in error_msg.lower():
                raise NonRetryableError(error_msg)
            else:
                # Default to retryable for other download errors
                raise RetryableError(error_msg)

    def _make_progress_callback(self):
        """Create a progress callback that updates job progress.

        Returns:
            A callback function for tracking download progress.
        """
        async def update_progress(current: int, total: int) -> None:
            await self.update_progress(current, total)

        # Since Telethon's progress callback is synchronous,
        # we need a sync wrapper. For now, just log progress.
        def sync_progress(current: int, total: int) -> None:
            # Log significant progress milestones
            if total > 0:
                percent = int((current / total) * 100)
                if percent % 25 == 0:  # Log at 0%, 25%, 50%, 75%, 100%
                    logger.debug(
                        "download_progress",
                        current=current,
                        total=total,
                        percent=percent,
                    )

        return sync_progress
