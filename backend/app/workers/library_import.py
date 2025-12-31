"""Library import worker for organizing design files."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.db.models import Job, JobType
from app.services.library import LibraryError, LibraryImportService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

logger = get_logger(__name__)


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

    async def process(self, job: Job, payload: dict[str, Any] | None) -> None:
        """Process an import job.

        Moves design files from staging to the organized library
        folder structure based on template configuration.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict (expects design_id).

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

    def _make_progress_callback(self):
        """Create a progress callback for tracking import progress.

        Returns:
            A callback function for tracking import progress.
        """
        def sync_progress(current: int, total: int) -> None:
            # Log progress
            if total > 0:
                percent = int((current / total) * 100)
                logger.debug(
                    "import_progress",
                    current=current,
                    total=total,
                    percent=percent,
                )

        return sync_progress
