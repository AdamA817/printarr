"""Download worker for processing design file downloads from Telegram."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import Attachment, Design, DesignSource, Job, JobType
from app.db.session import async_session_maker
from app.services.download import DownloadError, DownloadService
from app.services.duplicate import DuplicateService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

logger = get_logger(__name__)

# Auto-merge threshold for pre-download duplicate check
AUTO_MERGE_THRESHOLD = 0.9

# Throttle progress updates to avoid database spam
PROGRESS_UPDATE_INTERVAL_SECONDS = 1.0
PROGRESS_UPDATE_MIN_PERCENT_CHANGE = 2


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

    async def process(
        self, job: Job, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Process a download job.

        Downloads all attachments for a design from Telegram,
        saves them to the staging directory, and queues extraction
        if archives are present.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict (expects design_id).

        Returns:
            Result dict with files_downloaded and total_bytes.

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

        # Check for duplicates before downloading (DEC-041 / #216)
        merged_design = await self._check_pre_download_duplicate(design_id)
        if merged_design:
            logger.info(
                "download_skipped_duplicate_merged",
                job_id=job.id,
                design_id=design_id,
                merged_into_design_id=merged_design.id,
            )
            return {
                "status": "skipped_duplicate",
                "merged_into": merged_design.id,
                "files_downloaded": 0,
                "total_bytes": 0,
            }

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

            # Queue next step based on whether archives exist
            # This needs a session, so we open one briefly
            if result["has_archives"]:
                # Archives present - queue extraction first
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
            else:
                # No archives - queue import directly
                async with async_session_maker() as db:
                    from app.services.job_queue import JobQueueService
                    queue = JobQueueService(db)
                    import_job = await queue.enqueue(
                        JobType.IMPORT_TO_LIBRARY,
                        design_id=design_id,
                        priority=5,
                    )
                    await db.commit()

                    logger.info(
                        "import_job_queued",
                        design_id=design_id,
                        import_job_id=import_job.id,
                    )

            # Return result for storage in job
            return {
                "files_downloaded": result["files_downloaded"],
                "total_bytes": result["total_bytes"],
                "has_archives": result["has_archives"],
            }

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

        Note:
            Telethon's progress callback is synchronous, but we need to
            update the database asynchronously. We use asyncio.create_task()
            to schedule updates from within the sync callback, throttled
            to avoid database spam.
        """
        # Track state for throttling
        last_update_time = 0.0
        last_update_percent = -PROGRESS_UPDATE_MIN_PERCENT_CHANGE  # Force first update

        def sync_progress(current: int, total: int) -> None:
            nonlocal last_update_time, last_update_percent

            if total <= 0:
                return

            percent = int((current / total) * 100)
            now = time.time()

            # Check if we should throttle this update
            time_since_update = now - last_update_time
            percent_change = abs(percent - last_update_percent)

            should_update = (
                time_since_update >= PROGRESS_UPDATE_INTERVAL_SECONDS
                and percent_change >= PROGRESS_UPDATE_MIN_PERCENT_CHANGE
            ) or percent >= 100  # Always update on completion

            if should_update:
                last_update_time = now
                last_update_percent = percent

                # Schedule async database update
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.update_progress(current, total))
                except RuntimeError:
                    # No running loop - just log
                    pass

                # Log progress at significant milestones
                if percent % 25 == 0 or percent >= 100:
                    logger.debug(
                        "download_progress",
                        current=current,
                        total=total,
                        percent=percent,
                    )

        return sync_progress

    async def _check_pre_download_duplicate(self, design_id: str) -> Design | None:
        """Check for duplicates before downloading (DEC-041 / #216).

        If a high-confidence duplicate is found, merge sources instead of downloading.

        Args:
            design_id: The design ID to check.

        Returns:
            The merged design if duplicate was found and merged, None otherwise.
        """
        async with async_session_maker() as db:
            # Load design with sources and attachments
            result = await db.execute(
                select(Design)
                .options(
                    selectinload(Design.sources).selectinload(DesignSource.message)
                )
                .where(Design.id == design_id)
            )
            design = result.scalar_one_or_none()

            if not design:
                return None

            # Build file info from attachments
            files: list[dict] = []
            for source in design.sources:
                if source.message:
                    # Get attachments for this message
                    attach_result = await db.execute(
                        select(Attachment).where(Attachment.message_id == source.message.id)
                    )
                    attachments = attach_result.scalars().all()

                    for att in attachments:
                        if att.filename and att.size_bytes:
                            files.append({
                                "filename": att.filename,
                                "size": att.size_bytes,
                            })

            # Check for duplicates
            dup_service = DuplicateService(db)
            match, match_type, confidence = await dup_service.check_pre_download(
                title=design.canonical_title or "",
                designer=design.canonical_designer or "",
                files=files,
            )

            if match and confidence >= AUTO_MERGE_THRESHOLD:
                # High confidence match - merge sources instead of downloading
                logger.info(
                    "pre_download_duplicate_found",
                    design_id=design_id,
                    match_design_id=match.id,
                    match_type=match_type.value if match_type else None,
                    confidence=confidence,
                )

                # Move sources from this design to the matched design
                for source in design.sources:
                    source.design_id = match.id
                    source.is_preferred = False  # Don't override existing preferred

                # Delete the duplicate design (it has no files yet)
                await db.delete(design)
                await db.commit()

                return match

            elif match and confidence > 0:
                # Lower confidence - log for review but still download
                logger.info(
                    "pre_download_potential_duplicate",
                    design_id=design_id,
                    match_design_id=match.id,
                    match_type=match_type.value if match_type else None,
                    confidence=confidence,
                )

            return None
