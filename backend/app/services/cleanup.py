"""Periodic cleanup service for data consistency.

This service runs periodically to clean up:
1. Orphaned jobs (no design_id linked)
2. Stuck jobs (RUNNING too long without progress)
3. Orphaned import records (design_id points to deleted design)
4. Orphaned staging directories (design deleted but files remain)

Issue #237 - Automated cleanup for data consistency
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update, delete

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    Design,
    DesignStatus,
    ImportRecord,
    ImportRecordStatus,
    Job,
    JobStatus,
    JobType,
)
from app.db.session import async_session_maker

logger = get_logger(__name__)

# Configuration
CLEANUP_INTERVAL_MINUTES = 10  # How often to run cleanup
STUCK_JOB_THRESHOLD_HOURS = 4  # Jobs running longer than this are considered stuck
ORPHAN_STAGING_AGE_HOURS = 24  # Staging dirs older than this without design are cleaned


class CleanupService:
    """Service for periodic data cleanup and consistency checks."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the cleanup service."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("cleanup_service_started", interval_minutes=CLEANUP_INTERVAL_MINUTES)

    async def stop(self) -> None:
        """Stop the cleanup service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("cleanup_service_stopped")

    async def _run_loop(self) -> None:
        """Main cleanup loop."""
        # Wait a bit before first run to let other services start
        await asyncio.sleep(60)

        while self._running:
            try:
                await self.run_cleanup()
            except Exception as e:
                logger.error("cleanup_error", error=str(e))

            # Wait for next interval
            await asyncio.sleep(CLEANUP_INTERVAL_MINUTES * 60)

    async def run_cleanup(self) -> dict:
        """Run all cleanup tasks.

        Returns:
            Dictionary with counts of cleaned items.
        """
        logger.info("cleanup_starting")

        results = {
            "orphaned_jobs_deleted": 0,
            "stuck_jobs_recovered": 0,
            "orphaned_import_records_reset": 0,
            "orphaned_staging_dirs_cleaned": 0,
            "failed_downloads_reset": 0,
        }

        try:
            results["orphaned_jobs_deleted"] = await self._cleanup_orphaned_jobs()
        except Exception as e:
            logger.error("cleanup_orphaned_jobs_error", error=str(e))

        try:
            results["stuck_jobs_recovered"] = await self._recover_stuck_jobs()
        except Exception as e:
            logger.error("cleanup_stuck_jobs_error", error=str(e))

        try:
            results["orphaned_import_records_reset"] = await self._reset_orphaned_import_records()
        except Exception as e:
            logger.error("cleanup_orphaned_import_records_error", error=str(e))

        try:
            results["orphaned_staging_dirs_cleaned"] = await self._cleanup_orphaned_staging()
        except Exception as e:
            logger.error("cleanup_orphaned_staging_error", error=str(e))

        try:
            results["failed_downloads_reset"] = await self._reset_failed_downloads()
        except Exception as e:
            logger.error("cleanup_failed_downloads_error", error=str(e))

        logger.info("cleanup_complete", **results)
        return results

    async def _cleanup_orphaned_jobs(self) -> int:
        """Delete jobs that have no design_id but should have one.

        These are jobs where the design was deleted but the job remained.
        """
        async with async_session_maker() as db:
            # Job types that require a design_id
            design_job_types = [
                JobType.DOWNLOAD_DESIGN,
                JobType.IMPORT_TO_LIBRARY,
                JobType.EXTRACT_ARCHIVE,
                JobType.GENERATE_RENDER,
            ]

            result = await db.execute(
                select(Job)
                .where(Job.type.in_(design_job_types))
                .where(Job.design_id.is_(None))
                .where(Job.status.in_([JobStatus.FAILED, JobStatus.QUEUED]))
            )
            jobs = result.scalars().all()

            for job in jobs:
                logger.info(
                    "cleanup_deleting_orphaned_job",
                    job_id=job.id,
                    job_type=job.type.value,
                )
                await db.delete(job)

            await db.commit()
            return len(jobs)

    async def _recover_stuck_jobs(self) -> int:
        """Recover jobs that have been RUNNING for too long.

        Uses a generous threshold to avoid interrupting large downloads.
        Only recovers jobs that haven't had progress updates recently.
        """
        async with async_session_maker() as db:
            threshold = datetime.now(timezone.utc) - timedelta(hours=STUCK_JOB_THRESHOLD_HOURS)

            result = await db.execute(
                select(Job)
                .where(Job.status == JobStatus.RUNNING)
                .where(Job.started_at < threshold)
            )
            jobs = result.scalars().all()

            recovered = 0
            for job in jobs:
                # Check if job has had recent progress (stored in payload)
                # If progress was updated recently, don't consider it stuck
                if job.updated_at and job.updated_at > threshold:
                    continue

                logger.info(
                    "cleanup_recovering_stuck_job",
                    job_id=job.id,
                    job_type=job.type.value,
                    started_at=job.started_at.isoformat() if job.started_at else None,
                )

                # Reset to QUEUED for retry
                job.status = JobStatus.QUEUED
                job.started_at = None
                job.last_error = f"Job stuck for >{STUCK_JOB_THRESHOLD_HOURS}h - auto-recovered"
                recovered += 1

            await db.commit()
            return recovered

    async def _reset_orphaned_import_records(self) -> int:
        """Reset import records that point to deleted designs.

        These records have a design_id that no longer exists in the database.
        """
        async with async_session_maker() as db:
            # Find import records with design_id that doesn't exist
            result = await db.execute(
                select(ImportRecord)
                .where(ImportRecord.design_id.isnot(None))
                .where(ImportRecord.status.in_([
                    ImportRecordStatus.IMPORTED,
                    ImportRecordStatus.IMPORTING,
                    ImportRecordStatus.ERROR,
                ]))
            )
            records = result.scalars().all()

            reset_count = 0
            for record in records:
                # Check if design exists
                design = await db.get(Design, record.design_id)
                if design is None:
                    logger.info(
                        "cleanup_resetting_orphaned_import_record",
                        record_id=record.id,
                        detected_title=record.detected_title,
                        old_design_id=record.design_id,
                    )
                    record.status = ImportRecordStatus.PENDING
                    record.design_id = None
                    record.error_message = "Design deleted - reset for re-import"
                    reset_count += 1

            await db.commit()
            return reset_count

    async def _cleanup_orphaned_staging(self) -> int:
        """Clean up staging directories for deleted designs.

        Only cleans dirs that are old enough to avoid race conditions.
        """
        staging_path = settings.staging_path
        if not staging_path.exists():
            return 0

        async with async_session_maker() as db:
            # Get all design IDs
            result = await db.execute(select(Design.id))
            valid_design_ids = {row[0] for row in result.fetchall()}

        cleaned = 0
        age_threshold = datetime.now(timezone.utc) - timedelta(hours=ORPHAN_STAGING_AGE_HOURS)

        for item in staging_path.iterdir():
            if not item.is_dir():
                continue

            # Check if this is a design staging dir
            dir_name = item.name
            if dir_name.startswith("gdrive_"):
                # Google Drive temp dir - different format
                continue

            # Check if design exists
            if dir_name in valid_design_ids:
                continue

            # Check age
            try:
                mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
                if mtime > age_threshold:
                    continue  # Too new, might be in-progress
            except OSError:
                continue

            # Safe to clean
            logger.info(
                "cleanup_removing_orphaned_staging",
                path=str(item),
            )
            try:
                shutil.rmtree(item)
                cleaned += 1
            except OSError as e:
                logger.warning(
                    "cleanup_staging_removal_failed",
                    path=str(item),
                    error=str(e),
                )

        return cleaned

    async def _reset_failed_downloads(self) -> int:
        """Reset failed download jobs that can be retried.

        Only resets jobs that:
        - Failed due to transient errors (timeout, rate limit)
        - Haven't exceeded max retry attempts
        - Have been in FAILED state for a while (backoff)
        """
        async with async_session_maker() as db:
            # Only reset jobs that have been failed for at least 30 minutes
            # This provides natural backoff
            failed_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)

            result = await db.execute(
                select(Job)
                .where(Job.type == JobType.DOWNLOAD_IMPORT_RECORD)
                .where(Job.status == JobStatus.FAILED)
                .where(Job.finished_at < failed_threshold)
                .where(Job.attempts < Job.max_attempts)
            )
            jobs = result.scalars().all()

            reset_count = 0
            for job in jobs:
                # Only reset jobs that failed due to transient errors
                error = job.last_error or ""
                transient_errors = [
                    "timed out",
                    "timeout",
                    "rate limit",
                    "temporarily unavailable",
                    "connection",
                    "network",
                ]

                if not any(e in error.lower() for e in transient_errors):
                    continue

                logger.info(
                    "cleanup_resetting_failed_download",
                    job_id=job.id,
                    attempts=job.attempts,
                    error=error[:100],
                )

                job.status = JobStatus.QUEUED
                job.last_error = f"Auto-retry after transient failure: {error[:100]}"
                reset_count += 1

            await db.commit()
            return reset_count


# Global instance
_cleanup_service: CleanupService | None = None


def get_cleanup_service() -> CleanupService:
    """Get or create the cleanup service instance."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = CleanupService()
    return _cleanup_service
