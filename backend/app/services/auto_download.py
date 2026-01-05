"""Auto-download service for automatic download triggering.

This service implements download mode behaviors per DEC-022:
- MANUAL: No automatic downloads
- DOWNLOAD_ALL_NEW: Auto-download designs detected AFTER mode enabled
- DOWNLOAD_ALL: One-time bulk queue + auto-download future designs
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    Channel,
    Design,
    DesignSource,
    DesignStatus,
    DownloadMode,
    JobType,
)
from app.services.job_queue import JobQueueService

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Default priority for auto-downloads (lower than manual downloads)
AUTO_DOWNLOAD_PRIORITY = 5


class AutoDownloadService:
    """Service for automatically triggering downloads based on channel settings.

    Implements the download mode behaviors:
    - MANUAL: No auto-downloads
    - DOWNLOAD_ALL_NEW: Auto-queue new designs only
    - DOWNLOAD_ALL: Bulk queue existing + auto-queue new
    """

    def __init__(self, db: AsyncSession):
        """Initialize the auto-download service.

        Args:
            db: Async database session.
        """
        self.db = db

    async def check_and_queue_design(
        self,
        design: Design,
        channel: Channel,
    ) -> bool:
        """Check if a design should be auto-downloaded and queue if so.

        This is called after a new design is created during ingestion.

        Args:
            design: The newly created Design.
            channel: The Channel the design was found in.

        Returns:
            True if a download was queued, False otherwise.
        """
        # Check if auto-download is enabled for this channel
        if channel.download_mode == DownloadMode.MANUAL:
            return False

        # Only auto-download designs in DISCOVERED status
        if design.status != DesignStatus.DISCOVERED:
            logger.debug(
                "auto_download_skipped_status",
                design_id=design.id,
                status=design.status.value,
            )
            return False

        # For DOWNLOAD_ALL_NEW, only download if the design was created after
        # the mode was enabled
        if channel.download_mode == DownloadMode.DOWNLOAD_ALL_NEW:
            if channel.download_mode_enabled_at:
                if design.created_at < channel.download_mode_enabled_at:
                    logger.debug(
                        "auto_download_skipped_before_enabled",
                        design_id=design.id,
                        design_created=design.created_at.isoformat(),
                        mode_enabled=channel.download_mode_enabled_at.isoformat(),
                    )
                    return False

        # Queue the download
        return await self._queue_download(design, channel)

    async def _queue_download(
        self,
        design: Design,
        channel: Channel,
    ) -> bool:
        """Queue a download job for a design.

        Args:
            design: The design to download.
            channel: The channel it belongs to.

        Returns:
            True if queued successfully.
        """
        try:
            queue = JobQueueService(self.db)

            # Check if already has a pending download job
            existing_job = await queue.get_pending_job_for_design(
                design.id, JobType.DOWNLOAD_DESIGN
            )
            if existing_job:
                logger.debug(
                    "auto_download_skipped_existing_job",
                    design_id=design.id,
                    job_id=existing_job.id,
                )
                return False

            # Queue the download
            job = await queue.enqueue(
                job_type=JobType.DOWNLOAD_DESIGN,
                design_id=design.id,
                channel_id=channel.id,
                payload={"design_id": design.id},
                priority=AUTO_DOWNLOAD_PRIORITY,
            )

            # Update design status to WANTED
            design.status = DesignStatus.WANTED
            await self.db.flush()

            logger.info(
                "auto_download_queued",
                design_id=design.id,
                channel_id=channel.id,
                job_id=job.id,
                download_mode=channel.download_mode.value,
            )

            return True

        except Exception as e:
            logger.error(
                "auto_download_queue_failed",
                design_id=design.id,
                error=str(e),
            )
            return False

    async def trigger_bulk_download(
        self,
        channel: Channel,
        *,
        dry_run: bool = False,
    ) -> dict:
        """Trigger bulk download for all eligible designs in a channel.

        This is used when DOWNLOAD_ALL mode is first enabled.

        Args:
            channel: The channel to bulk download.
            dry_run: If True, only count designs without queueing.

        Returns:
            Dict with 'count' and 'queued' (if not dry_run).
        """
        # Find all DISCOVERED designs for this channel
        result = await self.db.execute(
            select(Design)
            .join(DesignSource, Design.id == DesignSource.design_id)
            .where(
                and_(
                    DesignSource.channel_id == channel.id,
                    Design.status == DesignStatus.DISCOVERED,
                )
            )
        )
        designs = result.scalars().all()

        count = len(designs)

        if dry_run:
            return {"count": count, "queued": 0}

        queued = 0
        for design in designs:
            if await self._queue_download(design, channel):
                queued += 1

        logger.info(
            "bulk_download_triggered",
            channel_id=channel.id,
            total_designs=count,
            queued=queued,
        )

        return {"count": count, "queued": queued}

    async def update_download_mode(
        self,
        channel: Channel,
        new_mode: DownloadMode,
        *,
        trigger_bulk: bool = False,
    ) -> dict:
        """Update a channel's download mode with proper tracking.

        Args:
            channel: The channel to update.
            new_mode: The new download mode.
            trigger_bulk: If True and mode is DOWNLOAD_ALL, trigger bulk download.

        Returns:
            Dict with mode change info and optional bulk download results.
        """
        old_mode = channel.download_mode
        result = {
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
        }

        if old_mode == new_mode:
            result["changed"] = False
            return result

        # Update the mode
        channel.download_mode = new_mode

        # Track when mode was enabled (if moving away from MANUAL)
        if old_mode == DownloadMode.MANUAL and new_mode != DownloadMode.MANUAL:
            channel.download_mode_enabled_at = datetime.now(timezone.utc)

        # If switching back to MANUAL, clear the enabled_at
        if new_mode == DownloadMode.MANUAL:
            channel.download_mode_enabled_at = None

        await self.db.flush()

        result["changed"] = True
        result["enabled_at"] = (
            channel.download_mode_enabled_at.isoformat()
            if channel.download_mode_enabled_at
            else None
        )

        # If DOWNLOAD_ALL and trigger_bulk is True, queue all existing designs
        if new_mode == DownloadMode.DOWNLOAD_ALL and trigger_bulk:
            bulk_result = await self.trigger_bulk_download(channel)
            result["bulk_download"] = bulk_result

        logger.info(
            "download_mode_updated",
            channel_id=channel.id,
            old_mode=old_mode.value,
            new_mode=new_mode.value,
            enabled_at=result.get("enabled_at"),
        )

        return result

    async def get_bulk_download_preview(self, channel: Channel) -> dict:
        """Get a preview of how many designs would be queued for bulk download.

        Args:
            channel: The channel to check.

        Returns:
            Dict with 'count' of designs that would be queued.
        """
        return await self.trigger_bulk_download(channel, dry_run=True)
