"""Auto-queue render service for v0.8 Manual Imports.

Provides functionality to automatically queue GENERATE_RENDER jobs
after designs are imported, if they don't have existing preview images.

See Issue #144 for requirements.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Design, JobType, PreviewAsset
from app.services.job_queue import JobQueueService

logger = get_logger(__name__)


class AutoRenderService:
    """Service for automatically queueing preview render jobs.

    Checks if a design has existing preview images and queues a
    GENERATE_RENDER job if none exist (when auto-render is enabled).
    """

    def __init__(self, db: AsyncSession):
        """Initialize the auto-render service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db
        self._job_service = JobQueueService(db)

    async def check_and_queue_render(
        self,
        design_id: str,
        force: bool = False,
    ) -> str | None:
        """Check if a design needs preview rendering and queue job if needed.

        Args:
            design_id: The design ID to check.
            force: If True, queue render even if previews exist.

        Returns:
            The job ID if a render job was queued, None otherwise.

        Behavior:
        - Returns None if auto_queue_render_after_import is disabled (and not forced)
        - Returns None if design already has preview images (and not forced)
        - Queues GENERATE_RENDER job with configured priority if no previews
        """
        # Check if auto-render is enabled
        if not force and not settings.auto_queue_render_after_import:
            logger.debug(
                "auto_render_disabled",
                design_id=design_id,
            )
            return None

        # Check if design exists
        design = await self.db.get(Design, design_id)
        if not design:
            logger.warning(
                "auto_render_design_not_found",
                design_id=design_id,
            )
            return None

        # Check if design already has previews
        if not force:
            preview_count = await self._get_preview_count(design_id)
            if preview_count > 0:
                logger.debug(
                    "auto_render_skipped_has_previews",
                    design_id=design_id,
                    preview_count=preview_count,
                )
                return None

        # Check if there's already a pending/running render job
        existing_job = await self._has_pending_render_job(design_id)
        if existing_job:
            logger.debug(
                "auto_render_skipped_job_exists",
                design_id=design_id,
            )
            return None

        # Queue render job
        job = await self._job_service.enqueue(
            job_type=JobType.GENERATE_RENDER,
            design_id=design_id,
            priority=settings.auto_queue_render_priority,
            payload={"auto_queued": True, "design_id": design_id},
            max_attempts=2,  # Limit retries for auto-queued renders
        )

        logger.info(
            "auto_render_job_queued",
            design_id=design_id,
            job_id=job.id,
            priority=settings.auto_queue_render_priority,
        )

        return job.id

    async def queue_renders_for_designs(
        self,
        design_ids: list[str],
        force: bool = False,
    ) -> dict[str, str | None]:
        """Queue render jobs for multiple designs.

        Args:
            design_ids: List of design IDs to check.
            force: If True, queue renders even if previews exist.

        Returns:
            Dict mapping design_id to job_id (or None if skipped).
        """
        results = {}
        for design_id in design_ids:
            job_id = await self.check_and_queue_render(design_id, force=force)
            results[design_id] = job_id

        queued = sum(1 for job_id in results.values() if job_id is not None)
        logger.info(
            "bulk_auto_render_complete",
            total=len(design_ids),
            queued=queued,
            skipped=len(design_ids) - queued,
        )

        return results

    async def _get_preview_count(self, design_id: str) -> int:
        """Get the count of preview assets for a design."""
        result = await self.db.execute(
            select(func.count(PreviewAsset.id)).where(
                PreviewAsset.design_id == design_id
            )
        )
        return result.scalar() or 0

    async def _has_pending_render_job(self, design_id: str) -> bool:
        """Check if there's already a pending/running render job for this design."""
        from app.db.models import Job, JobStatus

        result = await self.db.execute(
            select(func.count(Job.id)).where(
                Job.design_id == design_id,
                Job.type == JobType.GENERATE_RENDER,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
        )
        return (result.scalar() or 0) > 0


async def auto_queue_render_for_design(
    db: AsyncSession, design_id: str, force: bool = False
) -> str | None:
    """Convenience function to auto-queue render for a single design.

    Args:
        db: Database session.
        design_id: Design ID to queue render for.
        force: If True, queue render even if previews exist.

    Returns:
        Job ID if queued, None otherwise.
    """
    service = AutoRenderService(db)
    return await service.check_and_queue_render(design_id, force=force)
