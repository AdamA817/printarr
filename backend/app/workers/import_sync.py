"""Import source sync worker for v0.8 Manual Imports.

Handles async syncing of import sources (BULK_FOLDER and GOOGLE_DRIVE).
This worker processes SYNC_IMPORT_SOURCE jobs to:
1. Scan the source for designs
2. Create import records for detected designs
3. Optionally import pending designs (auto_import)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models import (
    ConflictResolution,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceStatus,
    ImportSourceType,
    Job,
    JobType,
)
from app.db.session import async_session_maker
from app.services.bulk_import import BulkImportError, BulkImportPathError, BulkImportService
from app.services.google_drive import GoogleDriveError, GoogleDriveService
from app.services.import_profile import ImportProfileService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

logger = get_logger(__name__)

# Throttle progress updates
PROGRESS_UPDATE_INTERVAL_SECONDS = 1.0


class SyncImportSourceWorker(BaseWorker):
    """Worker for syncing import sources.

    Processes SYNC_IMPORT_SOURCE jobs by:
    1. Loading the import source configuration
    2. Scanning the source for designs (folder or Google Drive)
    3. Creating import records for detected designs
    4. Optionally importing all pending designs
    5. Updating source status and sync timestamp
    """

    job_types = [JobType.SYNC_IMPORT_SOURCE]

    def __init__(
        self,
        *,
        poll_interval: float = 1.0,
        worker_id: str | None = None,
    ):
        """Initialize the sync worker.

        Args:
            poll_interval: Seconds between polling for jobs.
            worker_id: Optional identifier for this worker instance.
        """
        super().__init__(poll_interval=poll_interval, worker_id=worker_id)

    async def process(
        self, job: Job, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Process a sync job.

        Scans the import source and creates/updates import records.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict with:
                - source_id: Import source ID (required)
                - auto_import: Whether to auto-import detected designs
                - conflict_resolution: How to handle conflicts

        Returns:
            Result dict with designs_detected, designs_imported, errors.

        Raises:
            NonRetryableError: For missing source or invalid configuration.
            RetryableError: For transient errors that can be retried.
        """
        if not payload:
            raise NonRetryableError("Job missing payload")

        source_id = payload.get("source_id")
        if not source_id:
            raise NonRetryableError("Payload missing source_id")

        auto_import = payload.get("auto_import", False)
        conflict_resolution_str = payload.get("conflict_resolution", "SKIP")
        try:
            conflict_resolution = ConflictResolution(conflict_resolution_str)
        except ValueError:
            conflict_resolution = ConflictResolution.SKIP

        logger.info(
            "sync_job_starting",
            job_id=job.id,
            source_id=source_id,
            auto_import=auto_import,
        )

        designs_detected = 0
        designs_imported = 0
        errors: list[str] = []

        async with async_session_maker() as db:
            # Load the import source
            source = await db.get(ImportSource, source_id)
            if not source:
                raise NonRetryableError(f"Import source {source_id} not found")

            # Update status to show sync is in progress
            source.status = ImportSourceStatus.ACTIVE

            try:
                if source.source_type == ImportSourceType.BULK_FOLDER:
                    result = await self._sync_bulk_folder(
                        db, source, auto_import, conflict_resolution
                    )
                elif source.source_type == ImportSourceType.GOOGLE_DRIVE:
                    result = await self._sync_google_drive(
                        db, source, auto_import, conflict_resolution
                    )
                else:
                    raise NonRetryableError(
                        f"Unsupported source type: {source.source_type}"
                    )

                designs_detected = result["detected"]
                designs_imported = result["imported"]
                errors = result.get("errors", [])

                # Update source status
                source.status = ImportSourceStatus.ACTIVE
                source.last_sync_at = datetime.utcnow()
                source.last_sync_error = None

                logger.info(
                    "sync_job_complete",
                    job_id=job.id,
                    source_id=source_id,
                    designs_detected=designs_detected,
                    designs_imported=designs_imported,
                    errors=len(errors),
                )

            except BulkImportPathError as e:
                source.status = ImportSourceStatus.ERROR
                source.last_sync_error = str(e)
                await db.commit()
                raise NonRetryableError(str(e))

            except BulkImportError as e:
                source.status = ImportSourceStatus.ERROR
                source.last_sync_error = str(e)
                await db.commit()
                raise RetryableError(str(e))

            except GoogleDriveError as e:
                source.status = ImportSourceStatus.ERROR
                source.last_sync_error = str(e)
                await db.commit()
                raise RetryableError(str(e))

            await db.commit()

        return {
            "source_id": source_id,
            "designs_detected": designs_detected,
            "designs_imported": designs_imported,
            "errors": errors,
        }

    async def _sync_bulk_folder(
        self,
        db,
        source: ImportSource,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync a bulk folder import source.

        Args:
            db: Database session.
            source: The import source.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        service = BulkImportService(db)

        # Update progress: scanning
        await self.update_progress(0, 100)

        # Scan folder
        designs = await service.scan_folder(source)
        detected = len(designs)

        # Update progress: creating records
        await self.update_progress(30, 100)

        # Create import records
        await service.create_import_records(source, designs)

        imported = 0
        errors: list[str] = []

        if auto_import:
            # Update progress: importing
            await self.update_progress(50, 100)

            try:
                imported, skipped = await service.import_all_pending(
                    source, conflict_resolution
                )
            except Exception as e:
                errors.append(str(e))
                logger.error(
                    "auto_import_error",
                    source_id=source.id,
                    error=str(e),
                )

        # Update progress: complete
        await self.update_progress(100, 100)

        return {
            "detected": detected,
            "imported": imported,
            "errors": errors,
        }

    async def _sync_google_drive(
        self,
        db,
        source: ImportSource,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync a Google Drive import source.

        Args:
            db: Database session.
            source: The import source.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        if not source.google_drive_folder_id:
            raise NonRetryableError("Google Drive source missing folder ID")

        # Update progress: scanning
        await self.update_progress(0, 100)

        # Get import profile config
        profile_service = ImportProfileService(db)
        config = await profile_service.get_profile_config(source.import_profile_id)

        # Scan Google Drive folder for designs
        gdrive_service = GoogleDriveService(db)
        detected_designs = await gdrive_service.scan_for_designs(
            source.google_drive_folder_id,
            credentials=None,  # Public folder access via API key
            config=config,
        )
        detected = len(detected_designs)

        # Update progress: creating records
        await self.update_progress(50, 100)

        # Create import records for detected designs
        for design in detected_designs:
            # Check if record already exists
            existing = await db.execute(
                select(ImportRecord).where(
                    ImportRecord.import_source_id == source.id,
                    ImportRecord.source_path == design.relative_path,
                )
            )
            if existing.scalar_one_or_none():
                continue  # Skip existing records

            record = ImportRecord(
                import_source_id=source.id,
                source_path=design.relative_path,
                file_size=design.total_size,
                status=ImportRecordStatus.PENDING,
                detected_title=design.title,
                detected_designer=source.default_designer,
                model_file_count=len(design.model_files),
                preview_file_count=len(design.preview_files),
                detected_at=datetime.utcnow(),
            )
            db.add(record)

        imported = 0
        errors: list[str] = []

        # Note: auto_import for Google Drive would require downloading files
        # This is not yet implemented - just create records for now

        # Update progress: complete
        await self.update_progress(100, 100)

        return {
            "detected": detected,
            "imported": imported,
            "errors": errors,
        }
