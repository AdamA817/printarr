"""Job queue service for managing background tasks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Design, DesignStatus, Job, JobStatus, JobType

logger = get_logger(__name__)

# Job types that are related to designs and affect design status
DESIGN_JOB_TYPES = {
    JobType.DOWNLOAD_DESIGN,
    JobType.EXTRACT_ARCHIVE,
    JobType.IMPORT_TO_LIBRARY,
}


class JobQueueService:
    """Service for managing the job queue.

    Provides methods to enqueue, dequeue, complete, and cancel jobs.
    Uses database-backed queue with atomic job claiming to prevent
    double-processing.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the job queue service.

        Args:
            db: Async database session.
        """
        self.db = db

    async def enqueue(
        self,
        job_type: JobType,
        *,
        design_id: str | None = None,
        channel_id: str | None = None,
        payload: dict[str, Any] | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        display_name: str | None = None,
    ) -> Job:
        """Add a new job to the queue.

        Args:
            job_type: Type of job to create.
            design_id: Optional design ID this job relates to.
            channel_id: Optional channel ID this job relates to.
            payload: Optional JSON payload with job-specific data.
            priority: Job priority (higher = more urgent). Default 0.
            max_attempts: Maximum retry attempts. Default 3.
            display_name: Optional custom name for Activity UI (DEC-040).

        Returns:
            The created Job instance.
        """
        job = Job(
            type=job_type,
            status=JobStatus.QUEUED,
            priority=priority,
            design_id=design_id,
            channel_id=channel_id,
            payload_json=json.dumps(payload) if payload else None,
            max_attempts=max_attempts,
            display_name=display_name,
        )
        self.db.add(job)
        await self.db.flush()

        logger.info(
            "job_enqueued",
            job_id=job.id,
            job_type=job_type.value,
            priority=priority,
            design_id=design_id,
            channel_id=channel_id,
            display_name=display_name,
        )

        return job

    async def dequeue(
        self,
        job_types: list[JobType] | None = None,
    ) -> Job | None:
        """Atomically claim the next available job.

        Uses SELECT ... FOR UPDATE to prevent race conditions when
        multiple workers try to claim the same job.

        Args:
            job_types: Optional list of job types to consider.
                      If None, considers all types.

        Returns:
            The claimed Job instance, or None if no jobs available.
        """
        # Build base query
        conditions = [Job.status == JobStatus.QUEUED]

        if job_types:
            conditions.append(Job.type.in_(job_types))

        # Select next job by priority (desc) then created_at (asc)
        # Use FOR UPDATE to lock the row
        query = (
            select(Job)
            .where(and_(*conditions))
            .order_by(Job.priority.desc(), Job.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        result = await self.db.execute(query)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        # Claim the job
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1

        await self.db.flush()

        logger.info(
            "job_claimed",
            job_id=job.id,
            job_type=job.type.value,
            attempt=job.attempts,
        )

        return job

    async def complete(
        self,
        job_id: str,
        *,
        success: bool,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> Job | None:
        """Mark a job as completed (success or failure).

        Args:
            job_id: ID of the job to complete.
            success: Whether the job succeeded.
            error: Error message if job failed.
            result: Optional result data to store (bytes, files, etc.).

        Returns:
            The updated Job instance, or None if not found.
        """
        db_result = await self.db.execute(
            select(Job).where(Job.id == job_id)
        )
        job = db_result.scalar_one_or_none()

        if job is None:
            logger.warning("job_not_found", job_id=job_id)
            return None

        job.finished_at = datetime.now(timezone.utc)

        if success:
            job.status = JobStatus.SUCCESS
            job.last_error = None
            if result:
                job.result_json = json.dumps(result)
            logger.info(
                "job_completed_success",
                job_id=job_id,
                job_type=job.type.value,
                duration_ms=self._duration_ms(job),
            )
        else:
            job.last_error = error

            # Check if we should retry
            if job.attempts < job.max_attempts:
                job.status = JobStatus.QUEUED  # Re-queue for retry
                job.started_at = None
                job.finished_at = None
                logger.info(
                    "job_failed_will_retry",
                    job_id=job_id,
                    job_type=job.type.value,
                    attempt=job.attempts,
                    max_attempts=job.max_attempts,
                    error=error,
                )
            else:
                job.status = JobStatus.FAILED
                logger.error(
                    "job_failed_max_attempts",
                    job_id=job_id,
                    job_type=job.type.value,
                    attempts=job.attempts,
                    error=error,
                )

                # Update design status to FAILED if this is a design-related job
                if job.design_id and job.type in DESIGN_JOB_TYPES:
                    await self._update_design_status(job.design_id, DesignStatus.FAILED)

        await self.db.flush()
        return job

    async def cancel(self, job_id: str) -> Job | None:
        """Cancel a job (only if QUEUED or RUNNING).

        Args:
            job_id: ID of the job to cancel.

        Returns:
            The updated Job instance, or None if not found.
        """
        result = await self.db.execute(
            select(Job).where(
                Job.id == job_id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
        )
        job = result.scalar_one_or_none()

        if job is None:
            logger.warning(
                "job_cancel_failed",
                job_id=job_id,
                reason="not_found_or_not_cancellable",
            )
            return None

        job.status = JobStatus.CANCELED
        job.finished_at = datetime.now(timezone.utc)

        # Reset design status to DISCOVERED if this is a design-related job
        if job.design_id and job.type in DESIGN_JOB_TYPES:
            await self._update_design_status(job.design_id, DesignStatus.DISCOVERED)

        await self.db.flush()

        logger.info(
            "job_canceled",
            job_id=job_id,
            job_type=job.type.value,
        )

        return job

    async def update_progress(
        self,
        job_id: str,
        current: int,
        total: int | None = None,
        *,
        current_file: str | None = None,
        current_file_bytes: int | None = None,
        current_file_total: int | None = None,
    ) -> None:
        """Update job progress tracking with optional file-level details (#161).

        Args:
            job_id: ID of the job.
            current: Current progress value (e.g., files completed).
            total: Total expected value (e.g., total files).
            current_file: Name of file currently being processed.
            current_file_bytes: Bytes downloaded for current file.
            current_file_total: Total size of current file.
        """
        update_values: dict[str, Any] = {"progress_current": current}
        if total is not None:
            update_values["progress_total"] = total

        # Store extended progress info in payload_json
        if current_file or current_file_bytes is not None or current_file_total is not None:
            # Get current job to merge with existing payload
            result = await self.db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                existing_payload = {}
                if job.payload_json:
                    try:
                        existing_payload = json.loads(job.payload_json)
                    except json.JSONDecodeError:
                        pass

                # Update progress fields
                progress_info = existing_payload.get("progress", {})
                if current_file:
                    progress_info["current_file"] = current_file
                if current_file_bytes is not None:
                    progress_info["current_file_bytes"] = current_file_bytes
                if current_file_total is not None:
                    progress_info["current_file_total"] = current_file_total

                existing_payload["progress"] = progress_info
                update_values["payload_json"] = json.dumps(existing_payload)

        await self.db.execute(
            update(Job).where(Job.id == job_id).values(**update_values)
        )
        await self.db.flush()

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get statistics about the job queue.

        Returns:
            Dictionary with counts by status and type:
            {
                "by_status": {"QUEUED": 5, "RUNNING": 2, ...},
                "by_type": {"DOWNLOAD_DESIGN": 3, ...},
                "total": 10,
            }
        """
        # Count by status
        status_result = await self.db.execute(
            select(Job.status, func.count(Job.id))
            .group_by(Job.status)
        )
        by_status = {row[0].value: row[1] for row in status_result.all()}

        # Count by type (only active jobs: QUEUED or RUNNING)
        type_result = await self.db.execute(
            select(Job.type, func.count(Job.id))
            .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
            .group_by(Job.type)
        )
        by_type = {row[0].value: row[1] for row in type_result.all()}

        total = sum(by_status.values())

        return {
            "by_status": by_status,
            "by_type": by_type,
            "total": total,
        }

    async def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID.

        Args:
            job_id: The job ID.

        Returns:
            The Job instance or None if not found.
        """
        result = await self.db.execute(
            select(Job).where(Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_jobs_for_design(
        self,
        design_id: str,
        status: JobStatus | None = None,
    ) -> list[Job]:
        """Get all jobs for a specific design.

        Args:
            design_id: The design ID.
            status: Optional status filter.

        Returns:
            List of Job instances.
        """
        conditions = [Job.design_id == design_id]
        if status:
            conditions.append(Job.status == status)

        result = await self.db.execute(
            select(Job)
            .where(and_(*conditions))
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_pending_job_for_design(
        self,
        design_id: str,
        job_type: JobType,
    ) -> Job | None:
        """Get a pending (QUEUED or RUNNING) job for a design.

        Args:
            design_id: The design ID.
            job_type: The job type to look for.

        Returns:
            The Job instance if found, None otherwise.
        """
        result = await self.db.execute(
            select(Job).where(
                Job.design_id == design_id,
                Job.type == job_type,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
        )
        return result.scalar_one_or_none()

    async def cancel_jobs_for_design(
        self,
        design_id: str,
    ) -> int:
        """Cancel all pending/running jobs for a design.

        Args:
            design_id: The design ID.

        Returns:
            Number of jobs canceled.
        """
        result = await self.db.execute(
            update(Job)
            .where(
                Job.design_id == design_id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            .values(
                status=JobStatus.CANCELED,
                finished_at=datetime.now(timezone.utc),
            )
        )
        await self.db.flush()

        count = result.rowcount
        if count > 0:
            logger.info(
                "jobs_canceled_for_design",
                design_id=design_id,
                count=count,
            )
            # Reset design status to DISCOVERED
            await self._update_design_status(design_id, DesignStatus.DISCOVERED)

        return count

    async def cancel_jobs_for_import_source(
        self,
        source_id: str,
        import_record_ids: list[str] | None = None,
    ) -> int:
        """Cancel all pending/running jobs for an import source (#191).

        Cancels:
        - SYNC_IMPORT_SOURCE jobs that have this source_id in their payload
        - DOWNLOAD_IMPORT_RECORD jobs for the given import record IDs

        This should be called when deleting an import source.

        Args:
            source_id: The import source ID.
            import_record_ids: Optional list of import record IDs to cancel jobs for.

        Returns:
            Number of jobs canceled.
        """
        job_ids_to_cancel = []

        # Cancel SYNC_IMPORT_SOURCE jobs
        result = await self.db.execute(
            select(Job).where(
                Job.type == JobType.SYNC_IMPORT_SOURCE,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
        )
        sync_jobs = result.scalars().all()

        for job in sync_jobs:
            if job.payload_json:
                try:
                    payload = json.loads(job.payload_json)
                    if payload.get("source_id") == source_id:
                        job_ids_to_cancel.append(job.id)
                except json.JSONDecodeError:
                    pass

        # Cancel DOWNLOAD_IMPORT_RECORD jobs for the import records
        if import_record_ids:
            result = await self.db.execute(
                select(Job).where(
                    Job.type == JobType.DOWNLOAD_IMPORT_RECORD,
                    Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
                )
            )
            download_jobs = result.scalars().all()

            for job in download_jobs:
                if job.payload_json:
                    try:
                        payload = json.loads(job.payload_json)
                        if payload.get("import_record_id") in import_record_ids:
                            job_ids_to_cancel.append(job.id)
                    except json.JSONDecodeError:
                        pass

        if not job_ids_to_cancel:
            return 0

        # Cancel the matching jobs
        await self.db.execute(
            update(Job)
            .where(Job.id.in_(job_ids_to_cancel))
            .values(
                status=JobStatus.CANCELED,
                finished_at=datetime.now(timezone.utc),
            )
        )
        await self.db.flush()

        logger.info(
            "jobs_canceled_for_import_source",
            source_id=source_id,
            count=len(job_ids_to_cancel),
        )

        return len(job_ids_to_cancel)

    async def recover_orphaned_jobs(self) -> int:
        """Recover jobs that were running when the container stopped.

        On application startup, any job in RUNNING status was interrupted
        by a restart. This resets them to QUEUED for retry.

        Returns:
            Number of jobs recovered.
        """
        result = await self.db.execute(
            update(Job)
            .where(Job.status == JobStatus.RUNNING)
            .values(
                status=JobStatus.QUEUED,
                started_at=None,
                last_error="Job interrupted by container restart - auto-recovered",
            )
            .returning(Job.id, Job.type)
        )
        recovered = result.all()

        if recovered:
            for job_id, job_type in recovered:
                logger.info(
                    "orphaned_job_recovered",
                    job_id=job_id,
                    job_type=job_type.value if hasattr(job_type, 'value') else job_type,
                )

            logger.warning(
                "orphaned_jobs_recovered_on_startup",
                count=len(recovered),
            )

        await self.db.flush()
        return len(recovered)

    async def requeue_stale_jobs(
        self,
        stale_minutes: int = 30,
    ) -> int:
        """Re-queue jobs that have been running too long.

        This handles jobs that were claimed but never completed
        (e.g., worker crashed).

        Args:
            stale_minutes: How long a job can be running before
                          it's considered stale.

        Returns:
            Number of jobs requeued.
        """
        stale_threshold = datetime.now(timezone.utc)
        # Calculate stale threshold manually to avoid timedelta import in query
        from datetime import timedelta
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)

        result = await self.db.execute(
            update(Job)
            .where(
                Job.status == JobStatus.RUNNING,
                Job.started_at < stale_threshold,
            )
            .values(
                status=JobStatus.QUEUED,
                started_at=None,
            )
        )
        await self.db.flush()

        count = result.rowcount
        if count > 0:
            logger.warning(
                "stale_jobs_requeued",
                count=count,
                stale_minutes=stale_minutes,
            )
        return count

    def _duration_ms(self, job: Job) -> int | None:
        """Calculate job duration in milliseconds."""
        if job.started_at and job.finished_at:
            delta = job.finished_at - job.started_at
            return int(delta.total_seconds() * 1000)
        return None

    def get_payload(self, job: Job) -> dict[str, Any] | None:
        """Parse and return the job's payload.

        Args:
            job: The Job instance.

        Returns:
            Parsed payload dict, or None if no payload.
        """
        if not job.payload_json:
            return None
        return json.loads(job.payload_json)

    def get_result(self, job: Job) -> dict[str, Any] | None:
        """Parse and return the job's result.

        Args:
            job: The Job instance.

        Returns:
            Parsed result dict, or None if no result.
        """
        if not job.result_json:
            return None
        return json.loads(job.result_json)

    async def _update_design_status(
        self,
        design_id: str,
        new_status: DesignStatus,
    ) -> None:
        """Update a design's status.

        Args:
            design_id: The design ID.
            new_status: The new status to set.
        """
        design = await self.db.get(Design, design_id)
        if design:
            old_status = design.status
            design.status = new_status
            logger.info(
                "design_status_updated",
                design_id=design_id,
                old_status=old_status.value if old_status else None,
                new_status=new_status.value,
            )
