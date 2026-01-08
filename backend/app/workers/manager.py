"""Worker manager for orchestrating background workers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Type

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import ImportSource, ImportSourceStatus, Job, JobStatus, JobType
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService
from app.workers.base import BaseWorker

logger = get_logger(__name__)


class WorkerManager:
    """Orchestrates background workers for job processing.

    Manages the lifecycle of workers, including:
    - Starting workers in their own tasks
    - Graceful shutdown of all workers
    - Health monitoring and statistics
    - Stale job recovery
    """

    def __init__(
        self,
        *,
        stale_job_check_interval: int = 300,  # 5 minutes
        stale_job_threshold_minutes: int = 30,
    ):
        """Initialize the worker manager.

        Args:
            stale_job_check_interval: Seconds between stale job checks.
            stale_job_threshold_minutes: Jobs running longer than this
                are considered stale.
        """
        self.stale_job_check_interval = stale_job_check_interval
        self.stale_job_threshold_minutes = stale_job_threshold_minutes

        self._workers: list[BaseWorker] = []
        self._worker_tasks: list[asyncio.Task] = []
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._maintenance_task: asyncio.Task | None = None
        self._started_at: datetime | None = None

    def register_worker(
        self,
        worker_class: Type[BaseWorker],
        *,
        count: int = 1,
        **kwargs: Any,
    ) -> None:
        """Register a worker class to be managed.

        Args:
            worker_class: The worker class to instantiate.
            count: Number of worker instances to create.
            **kwargs: Arguments to pass to worker constructor.
        """
        for i in range(count):
            worker_id = f"{worker_class.__name__}-{i+1}"
            worker = worker_class(worker_id=worker_id, **kwargs)
            self._workers.append(worker)
            logger.info(
                "worker_registered",
                worker_id=worker_id,
                job_types=[jt.value for jt in worker.job_types],
            )

    async def start(self) -> None:
        """Start all registered workers.

        This method runs until shutdown is requested.
        """
        if self._running:
            logger.warning("worker_manager_already_running")
            return

        self._running = True
        self._started_at = datetime.now(timezone.utc)

        logger.info(
            "worker_manager_starting",
            worker_count=len(self._workers),
        )

        # Start all workers as tasks
        for worker in self._workers:
            task = asyncio.create_task(
                worker.run(),
                name=f"worker-{worker.worker_id}",
            )
            self._worker_tasks.append(task)

        # Start maintenance task (stale job recovery)
        self._maintenance_task = asyncio.create_task(
            self._maintenance_loop(),
            name="worker-maintenance",
        )

        logger.info(
            "worker_manager_started",
            worker_count=len(self._workers),
        )

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Shutdown workers
        await self._shutdown_workers()

    async def stop(self) -> None:
        """Request graceful shutdown of all workers."""
        if not self._running:
            return

        logger.info("worker_manager_stopping")
        self._running = False
        self._shutdown_event.set()

    async def _shutdown_workers(self) -> None:
        """Gracefully shut down all workers."""
        logger.info("worker_manager_shutting_down_workers")

        # Request shutdown from all workers
        for worker in self._workers:
            worker.request_shutdown()

        # Cancel maintenance task
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass

        # Wait for worker tasks to complete (with timeout)
        if self._worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._worker_tasks, return_exceptions=True),
                    timeout=30.0,  # 30 second timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "worker_shutdown_timeout",
                    pending_workers=len([t for t in self._worker_tasks if not t.done()]),
                )
                # Cancel remaining tasks
                for task in self._worker_tasks:
                    if not task.done():
                        task.cancel()

        logger.info("worker_manager_shutdown_complete")

    async def _maintenance_loop(self) -> None:
        """Background loop for maintenance tasks."""
        while self._running:
            try:
                await asyncio.sleep(self.stale_job_check_interval)

                if not self._running:
                    break

                # Check for stale jobs
                await self._requeue_stale_jobs()

                # Schedule import source syncs that are due
                await self._schedule_due_import_syncs()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "maintenance_loop_error",
                    error=str(e),
                    exc_info=True,
                )

    async def _requeue_stale_jobs(self) -> None:
        """Check for and requeue stale jobs."""
        async with async_session_maker() as db:
            queue = JobQueueService(db)
            count = await queue.requeue_stale_jobs(
                stale_minutes=self.stale_job_threshold_minutes,
            )
            await db.commit()

            if count > 0:
                logger.info(
                    "stale_jobs_recovered",
                    count=count,
                )

    async def _schedule_due_import_syncs(self) -> None:
        """Schedule sync jobs for import sources that are due.

        Checks for sources where:
        - sync_enabled is True
        - status is ACTIVE
        - last_sync_at is NULL OR last_sync_at + sync_interval_hours < now
        - No pending/running sync job exists for this source
        """
        async with async_session_maker() as db:
            now = datetime.now(timezone.utc)

            # Find sources that might be due for sync
            # We check the actual due time in Python since SQL interval math varies by DB
            result = await db.execute(
                select(ImportSource).where(
                    and_(
                        ImportSource.sync_enabled == True,
                        ImportSource.status == ImportSourceStatus.ACTIVE,
                    )
                )
            )
            sources = result.scalars().all()

            queued_count = 0
            for source in sources:
                # Check if sync is actually due
                if source.last_sync_at is not None:
                    next_sync_at = source.last_sync_at + timedelta(hours=source.sync_interval_hours)
                    if next_sync_at > now:
                        continue  # Not due yet

                # Check if there's already a pending/running sync job for this source
                existing_job = await db.execute(
                    select(Job).where(
                        and_(
                            Job.job_type == JobType.SYNC_IMPORT_SOURCE,
                            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
                            Job.payload_json.like(f'%{source.id}%'),
                        )
                    )
                )
                if existing_job.scalar_one_or_none():
                    continue  # Already has a pending sync

                # Queue a sync job
                queue = JobQueueService(db)
                await queue.enqueue(
                    job_type=JobType.SYNC_IMPORT_SOURCE,
                    payload={
                        "source_id": source.id,
                        "auto_import": False,  # Just detect, don't auto-import
                    },
                    priority=0,  # Normal priority
                    display_name=f"Scheduled sync: {source.name}",
                )
                queued_count += 1

                logger.info(
                    "import_sync_scheduled",
                    source_id=source.id,
                    source_name=source.name,
                    last_sync_at=source.last_sync_at.isoformat() if source.last_sync_at else None,
                    interval_hours=source.sync_interval_hours,
                )

            await db.commit()

            if queued_count > 0:
                logger.info(
                    "import_syncs_scheduled",
                    count=queued_count,
                )

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics about the worker manager and all workers.

        Returns:
            Dictionary with manager and worker stats.
        """
        # Get queue stats
        async with async_session_maker() as db:
            queue = JobQueueService(db)
            queue_stats = await queue.get_queue_stats()

        return {
            "manager": {
                "running": self._running,
                "worker_count": len(self._workers),
                "uptime_seconds": self._uptime_seconds(),
            },
            "queue": queue_stats,
            "workers": [w.stats for w in self._workers],
        }

    def _uptime_seconds(self) -> int:
        """Calculate manager uptime in seconds."""
        if self._started_at:
            return int((datetime.now(timezone.utc) - self._started_at).total_seconds())
        return 0

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running

    @property
    def worker_count(self) -> int:
        """Get number of registered workers."""
        return len(self._workers)


# Global worker manager instance
_manager: WorkerManager | None = None


def get_worker_manager() -> WorkerManager:
    """Get the global worker manager instance.

    Creates a new instance if one doesn't exist.

    Returns:
        The WorkerManager instance.
    """
    global _manager
    if _manager is None:
        _manager = WorkerManager()
    return _manager


async def start_workers() -> None:
    """Start the global worker manager.

    This is intended to be called from the application startup.
    """
    manager = get_worker_manager()

    # Import and register all worker types here
    # These imports are deferred to avoid circular imports
    # and to allow workers to be added incrementally

    from app.workers.ai import AiWorker
    from app.workers.download import DownloadWorker
    from app.workers.download_import_record import DownloadImportRecordWorker
    from app.workers.extract import ExtractArchiveWorker
    from app.workers.image import ImageWorker
    from app.workers.import_sync import SyncImportSourceWorker
    from app.workers.library_import import ImportToLibraryWorker
    from app.workers.render import RenderWorker

    # Register download workers
    # NOTE: SQLite doesn't handle concurrent writes well, so we limit to 1 worker
    # for SQLite databases. For PostgreSQL, we could use max_concurrent_downloads.
    download_worker_count = 1  # Forced to 1 for SQLite compatibility
    manager.register_worker(DownloadWorker, count=download_worker_count)

    # Register image workers (v0.7: preview image downloads)
    manager.register_worker(ImageWorker, count=1)

    # Register extract workers (single worker is sufficient for CPU-bound extraction)
    manager.register_worker(ExtractArchiveWorker, count=1)

    # Register import workers (single worker to avoid race conditions)
    manager.register_worker(ImportToLibraryWorker, count=1)

    # Register render workers (CPU-bound, single worker is sufficient)
    manager.register_worker(RenderWorker, count=1)

    # Register import sync workers (v0.8: async import source syncing)
    manager.register_worker(SyncImportSourceWorker, count=1)

    # Register per-design download workers (DEC-040)
    manager.register_worker(DownloadImportRecordWorker, count=1)

    # Register AI analysis workers (v1.0 - DEC-043)
    # Only useful if AI is enabled, but worker handles this gracefully
    manager.register_worker(AiWorker, count=1)

    logger.info("starting_workers", worker_count=manager.worker_count)
    await manager.start()


async def stop_workers() -> None:
    """Stop the global worker manager.

    This is intended to be called from the application shutdown.
    """
    global _manager
    if _manager is not None:
        await _manager.stop()
        _manager = None
