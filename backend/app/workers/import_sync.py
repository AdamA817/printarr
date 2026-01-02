"""Import source sync worker for v0.8 Manual Imports.

Handles async syncing of import sources (BULK_FOLDER and GOOGLE_DRIVE).
This worker processes SYNC_IMPORT_SOURCE jobs to:
1. Scan the source for designs
2. Create import records for detected designs
3. Optionally import pending designs (auto_import)
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    ConflictResolution,
    Design,
    DesignFile,
    DesignStatus,
    FileKind,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceStatus,
    ImportSourceType,
    Job,
    JobType,
    MetadataAuthority,
)
from app.db.session import async_session_maker
from app.services.auto_render import auto_queue_render_for_design
from app.services.bulk_import import BulkImportError, BulkImportPathError, BulkImportService
from app.services.google_drive import GoogleDriveError, GoogleDriveService
from app.services.import_profile import ImportProfileService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

# File extensions for 3D model files
MODEL_EXTENSIONS = {".stl", ".3mf", ".obj", ".step", ".stp", ".iges", ".igs", ".blend", ".gcode"}

# File extensions for preview/image files
PREVIEW_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

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
        await self.update_progress(30, 100)

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
                google_folder_id=design.folder_id,  # Store Google Drive folder ID for download
            )
            db.add(record)

        # Flush to ensure records are visible
        await db.flush()

        imported = 0
        errors: list[str] = []

        if auto_import:
            # Update progress: importing
            await self.update_progress(50, 100)

            # Import all pending records
            imported, errors = await self._import_google_drive_pending(
                db, source, conflict_resolution
            )

        # Update progress: complete
        await self.update_progress(100, 100)

        return {
            "detected": detected,
            "imported": imported,
            "errors": errors,
        }

    async def _import_google_drive_pending(
        self,
        db,
        source: ImportSource,
        conflict_resolution: ConflictResolution,
    ) -> tuple[int, list[str]]:
        """Import all pending Google Drive designs.

        Downloads files from Google Drive and creates Design/DesignFile records.

        Args:
            db: Database session.
            source: The import source.
            conflict_resolution: How to handle conflicts.

        Returns:
            Tuple of (imported_count, errors).
        """
        # Get pending records
        result = await db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_id == source.id,
                ImportRecord.status == ImportRecordStatus.PENDING,
            )
        )
        records = list(result.scalars().all())

        logger.info(
            "gdrive_auto_import_starting",
            source_id=source.id,
            pending_count=len(records),
        )

        imported = 0
        errors: list[str] = []

        for record in records:
            try:
                design = await self._import_google_drive_record(
                    db, source, record, conflict_resolution
                )
                if design:
                    imported += 1
                    logger.info(
                        "gdrive_design_imported",
                        record_id=record.id,
                        design_id=design.id,
                        title=design.canonical_title,
                    )
            except Exception as e:
                error_msg = f"Failed to import {record.source_path}: {e}"
                errors.append(error_msg)
                record.status = ImportRecordStatus.ERROR
                record.error_message = str(e)
                logger.error(
                    "gdrive_import_failed",
                    record_id=record.id,
                    source_path=record.source_path,
                    error=str(e),
                )

        logger.info(
            "gdrive_auto_import_complete",
            source_id=source.id,
            imported=imported,
            errors=len(errors),
        )

        return imported, errors

    async def _import_google_drive_record(
        self,
        db,
        source: ImportSource,
        record: ImportRecord,
        conflict_resolution: ConflictResolution,
    ) -> Design | None:
        """Import a single Google Drive design.

        Downloads files and creates Design/DesignFile records.

        Args:
            db: Database session.
            source: The import source.
            record: The import record to import.
            conflict_resolution: How to handle conflicts.

        Returns:
            The created Design, or None if skipped.
        """
        if not record.google_folder_id:
            raise NonRetryableError(
                f"Import record {record.id} missing google_folder_id"
            )

        # Check for conflicts
        if conflict_resolution == ConflictResolution.SKIP:
            existing = await self._find_existing_design(db, record, source)
            if existing:
                record.status = ImportRecordStatus.SKIPPED
                record.design_id = existing.id
                logger.info(
                    "gdrive_import_skipped_duplicate",
                    record_id=record.id,
                    existing_design_id=existing.id,
                )
                return None

        # Update record status
        record.status = ImportRecordStatus.IMPORTING

        # Create staging directory for this design
        staging_dir = settings.staging_path / f"gdrive_{record.id}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Download files from Google Drive
            gdrive_service = GoogleDriveService(db)
            downloaded_files = await gdrive_service.download_folder(
                record.google_folder_id,
                staging_dir,
                credentials=None,  # Public folder access
            )

            if not downloaded_files:
                raise NonRetryableError(
                    f"No files downloaded from Google Drive folder {record.google_folder_id}"
                )

            # Create Design record
            design = Design(
                canonical_title=record.detected_title or record.source_path.split("/")[-1],
                canonical_designer=record.detected_designer or source.default_designer or "Unknown",
                status=DesignStatus.DOWNLOADED,
                metadata_authority=MetadataAuthority.USER,
                import_source_id=source.id,
                total_size_bytes=sum(size for _, size in downloaded_files),
            )
            db.add(design)
            await db.flush()

            # Create DesignFile records for each downloaded file
            has_previews = False
            for file_path, file_size in downloaded_files:
                ext = file_path.suffix.lower()
                relative_path = str(file_path.relative_to(staging_dir))

                # Determine file kind
                if ext in MODEL_EXTENSIONS:
                    file_kind = FileKind.MODEL
                elif ext in PREVIEW_EXTENSIONS:
                    file_kind = FileKind.PREVIEW
                    has_previews = True
                else:
                    file_kind = FileKind.OTHER

                # Calculate file hash
                sha256 = await self._compute_file_hash(file_path)

                design_file = DesignFile(
                    design_id=design.id,
                    relative_path=relative_path,
                    filename=file_path.name,
                    ext=ext,
                    size_bytes=file_size,
                    sha256=sha256,
                    file_kind=file_kind,
                    is_from_archive=False,
                )
                db.add(design_file)

            # Auto-queue render if no previews were downloaded
            if not has_previews:
                await auto_queue_render_for_design(db, design.id)

            # Update import record
            record.status = ImportRecordStatus.IMPORTED
            record.design_id = design.id
            record.imported_at = datetime.utcnow()

            # Update source stats
            source.items_imported = (source.items_imported or 0) + 1
            source.last_sync_at = datetime.utcnow()

            return design

        except Exception as e:
            # Clean up staging directory on failure
            import shutil
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    async def _find_existing_design(
        self, db, record: ImportRecord, source: ImportSource
    ) -> Design | None:
        """Find an existing design that matches the record."""
        result = await db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_id == source.id,
                ImportRecord.source_path == record.source_path,
                ImportRecord.status == ImportRecordStatus.IMPORTED,
                ImportRecord.id != record.id,
            )
        )
        existing_record = result.scalar_one_or_none()
        if existing_record and existing_record.design_id:
            design_result = await db.execute(
                select(Design).where(Design.id == existing_record.design_id)
            )
            return design_result.scalar_one_or_none()
        return None

    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        import asyncio

        sha256 = hashlib.sha256()

        def _hash_file() -> str:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _hash_file)
