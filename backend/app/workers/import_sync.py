"""Import source sync worker for v0.8 Manual Imports.

Handles async syncing of import sources (BULK_FOLDER and GOOGLE_DRIVE).
This worker processes SYNC_IMPORT_SOURCE jobs to:
1. Scan the source folders for designs
2. Create import records for detected designs
3. Optionally import pending designs (auto_import)

Per DEC-038, syncing now operates at the folder level. If folder_id is
provided in the payload, only that folder is synced. Otherwise, all
enabled folders in the source are synced.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

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
    ImportSourceFolder,
    ImportSourceStatus,
    ImportSourceType,
    Job,
    JobType,
    MetadataAuthority,
)
from app.db.session import async_session_maker
from app.services.auto_render import auto_queue_render_for_design
from app.services.bulk_import import BulkImportError, BulkImportPathError, BulkImportService
from app.services.duplicate import DuplicateService
from app.services.google_drive import GoogleDriveError, GoogleDriveService, GoogleRateLimitError
from app.services.import_profile import ImportProfileService
from app.services.job_queue import JobQueueService
from app.services.phpbb import PhpbbAuthError, PhpbbError, PhpbbService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

# Auto-merge threshold for cross-source duplicate detection (DEC-041 / #216)
AUTO_MERGE_THRESHOLD = 0.9

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

        Scans import source folders and creates/updates import records.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict with:
                - source_id: Import source ID (required)
                - folder_id: Optional folder ID to sync just one folder
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

        folder_id = payload.get("folder_id")  # Optional: sync single folder
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
            folder_id=folder_id,
            auto_import=auto_import,
        )

        designs_detected = 0
        designs_imported = 0
        errors: list[str] = []

        async with async_session_maker() as db:
            # Load the import source with folders eagerly loaded
            result = await db.execute(
                select(ImportSource)
                .options(selectinload(ImportSource.folders))
                .where(ImportSource.id == source_id)
            )
            source = result.scalar_one_or_none()
            if not source:
                raise NonRetryableError(f"Import source {source_id} not found")

            # Update status to show sync is in progress
            source.status = ImportSourceStatus.ACTIVE
            await db.commit()  # Commit early to release lock before long operations

            try:
                # Determine which folders to sync
                if folder_id:
                    # Sync single folder
                    folder = await db.get(ImportSourceFolder, folder_id)
                    if not folder:
                        raise NonRetryableError(f"Folder {folder_id} not found")
                    if folder.import_source_id != source_id:
                        raise NonRetryableError(
                            f"Folder {folder_id} does not belong to source {source_id}"
                        )
                    folders_to_sync = [folder]
                else:
                    # Sync all enabled folders
                    folders_to_sync = [f for f in source.folders if f.enabled]

                if not folders_to_sync:
                    # Backward compatibility: use deprecated source fields
                    result = await self._sync_legacy_source(
                        db, source, auto_import, conflict_resolution
                    )
                else:
                    # Sync each folder
                    result = await self._sync_folders(
                        db, source, folders_to_sync, auto_import, conflict_resolution
                    )

                designs_detected = result["detected"]
                designs_imported = result["imported"]
                errors = result.get("errors", [])

                # Update source status
                source.status = ImportSourceStatus.ACTIVE
                source.last_sync_at = datetime.now(timezone.utc)
                source.last_sync_error = None

                logger.info(
                    "sync_job_complete",
                    job_id=job.id,
                    source_id=source_id,
                    folder_id=folder_id,
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

            except GoogleRateLimitError as e:
                # Set specific status for rate limiting so UI can show it
                source.status = ImportSourceStatus.RATE_LIMITED
                source.last_sync_error = f"Google API rate limited. Will retry automatically. {e}"
                await db.commit()
                logger.warning(
                    "sync_rate_limited",
                    source_id=source_id,
                    error=str(e),
                )
                raise RetryableError(str(e))

            except GoogleDriveError as e:
                source.status = ImportSourceStatus.ERROR
                source.last_sync_error = str(e)
                await db.commit()
                raise RetryableError(str(e))

            await db.commit()

        return {
            "source_id": source_id,
            "folder_id": folder_id,
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

        # Update progress: complete (force to bypass throttle)
        await self.update_progress(100, 100, force=True)

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

        # Get credentials if OAuth is configured
        gdrive_service = GoogleDriveService(db)
        credentials = None
        if source.google_credentials_id:
            credentials = await gdrive_service.get_credentials(source.google_credentials_id)

        # Scan Google Drive folder for designs with caching and batching
        detected_designs = await gdrive_service.scan_for_designs(
            source.google_drive_folder_id,
            credentials=credentials,
            config=config,
            use_cache=True,
            use_batch=True,
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
                detected_at=datetime.now(timezone.utc),
                google_folder_id=design.folder_id,  # Store Google Drive folder ID for download
            )
            db.add(record)

        # Commit records to release locks before potentially long import operations
        await db.commit()

        imported = 0
        errors: list[str] = []

        if auto_import:
            # Update progress: importing
            await self.update_progress(50, 100)

            # Import all pending records
            imported, errors = await self._import_google_drive_pending(
                db, source, conflict_resolution
            )

        # Update progress: complete (force to bypass throttle)
        await self.update_progress(100, 100, force=True)

        return {
            "detected": detected,
            "imported": imported,
            "errors": errors,
        }

    async def _sync_phpbb_forum(
        self,
        db,
        source: ImportSource,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync a phpBB forum import source (issue #239).

        Args:
            db: Database session.
            source: The import source.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        if not source.phpbb_forum_url:
            raise NonRetryableError("phpBB Forum source missing forum URL")

        if not source.phpbb_credentials_id:
            raise NonRetryableError("phpBB Forum source missing credentials")

        # Update progress: scanning
        await self.update_progress(0, 100)

        # Get phpBB credentials
        phpbb_service = PhpbbService(db)
        credentials = await phpbb_service.get_credentials(source.phpbb_credentials_id)
        if not credentials:
            raise NonRetryableError(f"phpBB credentials {source.phpbb_credentials_id} not found")

        try:
            # Get session cookies (login if needed)
            cookies = await phpbb_service.get_session_cookies(credentials)

            # Scan forum for designs (topics with ZIP attachments)
            detected_designs = await phpbb_service.scan_forum_for_designs(
                credentials.base_url,
                source.phpbb_forum_url,
                cookies,
            )
            detected = len(detected_designs)

            # Update progress: creating records
            await self.update_progress(30, 100)

            # Create import records for detected designs
            import json
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

                # Store attachment info in payload
                attachments_data = [
                    {
                        "file_id": a.file_id,
                        "filename": a.filename,
                        "size_bytes": a.size_bytes,
                        "download_url": a.download_url,
                    }
                    for a in design.attachments
                ]

                # Store image URLs for preview extraction
                images_data = [img.url for img in design.images]

                record = ImportRecord(
                    import_source_id=source.id,
                    source_path=design.relative_path,
                    file_size=design.total_size,
                    status=ImportRecordStatus.PENDING,
                    detected_title=design.title,
                    detected_designer=design.author or source.default_designer,
                    model_file_count=len(design.attachments),  # Each attachment is a ZIP
                    preview_file_count=len(design.images),
                    detected_at=datetime.now(timezone.utc),
                    # Store extra data in payload_json for download worker
                    payload_json=json.dumps({
                        "topic_id": design.topic_id,
                        "forum_id": design.forum_id,
                        "topic_title": design.topic_title,
                        "title": design.title,
                        "author": design.author,
                        "attachments": attachments_data,
                        "images": images_data,
                    }),
                )
                db.add(record)

            # Commit records to release locks before potentially long import operations
            await db.commit()

            imported = 0
            errors: list[str] = []

            if auto_import:
                # Update progress: importing
                await self.update_progress(50, 100)

                # Queue download jobs for pending records
                imported, errors = await self._queue_phpbb_pending_downloads(
                    db, source, conflict_resolution
                )

            # Update progress: complete (force to bypass throttle)
            await self.update_progress(100, 100, force=True)

            # Update source stats (phpBB doesn't use folders, so we count records directly)
            detected_count = await db.execute(
                select(func.count()).where(
                    ImportRecord.import_source_id == source.id,
                )
            )
            imported_count = await db.execute(
                select(func.count()).where(
                    ImportRecord.import_source_id == source.id,
                    ImportRecord.status == ImportRecordStatus.IMPORTED,
                    ImportRecord.design_id.isnot(None),
                )
            )
            source.items_detected = detected_count.scalar() or 0
            source.items_imported = imported_count.scalar() or 0
            await db.commit()

            return {
                "detected": detected,
                "imported": imported,
                "errors": errors,
            }

        except PhpbbAuthError as e:
            source.status = ImportSourceStatus.ERROR
            source.last_sync_error = f"phpBB authentication failed: {e}"
            await db.commit()
            raise NonRetryableError(str(e))

        except PhpbbError as e:
            source.status = ImportSourceStatus.ERROR
            source.last_sync_error = str(e)
            await db.commit()
            raise RetryableError(str(e))

    async def _queue_phpbb_pending_downloads(
        self,
        db,
        source: ImportSource,
        conflict_resolution: ConflictResolution,
    ) -> tuple[int, list[str]]:
        """Queue download jobs for pending phpBB designs.

        Args:
            db: Database session.
            source: The import source.
            conflict_resolution: How to handle conflicts.

        Returns:
            Tuple of (queued_count, errors).
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
            "phpbb_auto_import_queueing",
            source_id=source.id,
            pending_count=len(records),
        )

        queued = 0
        errors: list[str] = []
        queue = JobQueueService(db)

        # Track titles already queued in this batch for intra-batch deduplication
        queued_titles: set[str] = set()

        for i, record in enumerate(records):
            try:
                # Check for conflicts before queuing
                if conflict_resolution == ConflictResolution.SKIP:
                    # Intra-batch deduplication: skip if same title already queued
                    if record.detected_title and record.detected_title in queued_titles:
                        record.status = ImportRecordStatus.SKIPPED
                        logger.info(
                            "phpbb_import_skipped_intra_batch_duplicate",
                            record_id=record.id,
                            detected_title=record.detected_title,
                        )
                        continue

                    # Cross-source deduplication: check against existing designs
                    existing = await self._find_existing_design(db, record, source)
                    if existing:
                        record.status = ImportRecordStatus.SKIPPED
                        record.design_id = existing.id
                        logger.info(
                            "phpbb_import_skipped_duplicate",
                            record_id=record.id,
                            existing_design_id=existing.id,
                        )
                        continue

                # Check for existing queued/running job for this record
                existing_job = await queue.get_pending_job_for_import_record(record.id)
                if existing_job:
                    logger.debug(
                        "phpbb_import_job_already_queued",
                        record_id=record.id,
                        job_id=existing_job.id,
                    )
                    continue

                # Queue DOWNLOAD_IMPORT_RECORD job with display name
                display_name = f"Download: {record.detected_title or record.source_path.split('/')[-1]} from {source.name}"
                await queue.enqueue(
                    JobType.DOWNLOAD_IMPORT_RECORD,
                    payload={
                        "import_record_id": record.id,
                    },
                    priority=5,
                    display_name=display_name,
                )
                queued += 1

                # Track title for intra-batch deduplication
                if record.detected_title:
                    queued_titles.add(record.detected_title)

                # Update progress
                progress = 50 + int((i + 1) / len(records) * 45)  # 50-95% for queueing
                await self.update_progress(progress, 100)

            except Exception as e:
                error_msg = f"Failed to queue {record.source_path}: {e}"
                errors.append(error_msg)
                logger.error(
                    "phpbb_queue_failed",
                    record_id=record.id,
                    source_path=record.source_path,
                    error=str(e),
                )

        # Commit all queued jobs
        await db.commit()

        logger.info(
            "phpbb_auto_import_queued",
            source_id=source.id,
            queued=queued,
            errors=len(errors),
        )

        return queued, errors

    async def _import_google_drive_pending(
        self,
        db,
        source: ImportSource,
        conflict_resolution: ConflictResolution,
    ) -> tuple[int, list[str]]:
        """Queue download jobs for pending Google Drive designs (DEC-040).

        Instead of downloading inline, this method queues individual
        DOWNLOAD_IMPORT_RECORD jobs for each pending design. This enables
        per-design progress tracking in the Activity UI.

        Args:
            db: Database session.
            source: The import source.
            conflict_resolution: How to handle conflicts.

        Returns:
            Tuple of (queued_count, errors).
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
            "gdrive_auto_import_queueing",
            source_id=source.id,
            pending_count=len(records),
        )

        queued = 0
        errors: list[str] = []
        queue = JobQueueService(db)

        # Track titles already queued in this batch for intra-batch deduplication
        queued_titles: set[str] = set()

        for i, record in enumerate(records):
            try:
                # Check for conflicts before queuing
                if conflict_resolution == ConflictResolution.SKIP:
                    # Intra-batch deduplication: skip if same title already queued
                    if record.detected_title and record.detected_title in queued_titles:
                        record.status = ImportRecordStatus.SKIPPED
                        logger.info(
                            "gdrive_import_skipped_intra_batch_duplicate",
                            record_id=record.id,
                            detected_title=record.detected_title,
                        )
                        continue

                    # Cross-source deduplication: check against existing designs
                    existing = await self._find_existing_design(db, record, source)
                    if existing:
                        record.status = ImportRecordStatus.SKIPPED
                        record.design_id = existing.id
                        logger.info(
                            "gdrive_import_skipped_duplicate",
                            record_id=record.id,
                            existing_design_id=existing.id,
                        )
                        continue

                # Check for existing queued/running job for this record (#237)
                existing_job = await queue.get_pending_job_for_import_record(record.id)
                if existing_job:
                    logger.debug(
                        "gdrive_import_job_already_queued",
                        record_id=record.id,
                        job_id=existing_job.id,
                    )
                    continue

                # Queue DOWNLOAD_IMPORT_RECORD job with display name
                display_name = f"Download: {record.detected_title or record.source_path.split('/')[-1]} from {source.name}"
                await queue.enqueue(
                    JobType.DOWNLOAD_IMPORT_RECORD,
                    payload={
                        "import_record_id": record.id,
                    },
                    priority=5,
                    display_name=display_name,
                )
                queued += 1

                # Track title for intra-batch deduplication
                if record.detected_title:
                    queued_titles.add(record.detected_title)

                # Update progress
                progress = 50 + int((i + 1) / len(records) * 45)  # 50-95% for queueing
                await self.update_progress(progress, 100)

            except Exception as e:
                error_msg = f"Failed to queue {record.source_path}: {e}"
                errors.append(error_msg)
                logger.error(
                    "gdrive_queue_failed",
                    record_id=record.id,
                    source_path=record.source_path,
                    error=str(e),
                )

        # Commit all queued jobs
        await db.commit()

        logger.info(
            "gdrive_auto_import_queued",
            source_id=source.id,
            queued=queued,
            errors=len(errors),
        )

        return queued, errors

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

            # Get credentials if source has OAuth configured
            credentials = None
            if source.google_credentials_id:
                credentials = await gdrive_service.get_credentials(source.google_credentials_id)

            # Progress callback to report current file being downloaded (#188)
            async def download_progress(
                files_done: int, total_files: int, filename: str, file_size: int
            ) -> None:
                await self.update_progress(
                    files_done,
                    total_files,
                    current_file=filename,
                    current_file_total=file_size,
                )

            downloaded_files = await gdrive_service.download_folder(
                record.google_folder_id,
                staging_dir,
                credentials=credentials,
                progress_callback=download_progress,
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
                    file_kind = FileKind.IMAGE
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

            # Rename staging directory from gdrive_{record.id} to {design.id}
            # so IMPORT_TO_LIBRARY worker can find it
            new_staging_dir = settings.staging_path / design.id
            if staging_dir != new_staging_dir:
                staging_dir.rename(new_staging_dir)
                logger.debug(
                    "staging_dir_renamed",
                    old=str(staging_dir),
                    new=str(new_staging_dir),
                )

            # Queue IMPORT_TO_LIBRARY job to move files from staging to library
            # This also creates Preview records from image files
            queue = JobQueueService(db)
            await queue.enqueue(
                JobType.IMPORT_TO_LIBRARY,
                design_id=design.id,
                priority=5,
            )

            # Update import record
            record.status = ImportRecordStatus.IMPORTED
            record.design_id = design.id
            record.imported_at = datetime.now(timezone.utc)

            # Update source stats
            source.items_imported = (source.items_imported or 0) + 1
            source.last_sync_at = datetime.now(timezone.utc)

            return design

        except Exception as e:
            # Clean up staging directory on failure (may be original or renamed)
            import shutil
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            # Also clean up renamed path if it exists
            design_staging = settings.staging_path / design.id if 'design' in dir() else None
            if design_staging and design_staging.exists():
                shutil.rmtree(design_staging, ignore_errors=True)
            raise

    async def _find_existing_design(
        self, db, record: ImportRecord, source: ImportSource
    ) -> Design | None:
        """Find an existing design that matches the record.

        Checks for duplicates using multiple strategies (#189, #216):
        1. Exact match on google_folder_id (same GDrive folder across any source)
        2. Same source_path within the same import source
        3. Same detected_title from the same import source (fallback)
        4. Cross-source duplicate via DuplicateService (matches Telegram designs too)
        """
        # Strategy 1: Check by google_folder_id across ALL sources
        # This catches the case where the same GDrive folder is added to multiple sources
        if record.google_folder_id:
            result = await db.execute(
                select(ImportRecord).where(
                    ImportRecord.google_folder_id == record.google_folder_id,
                    ImportRecord.status == ImportRecordStatus.IMPORTED,
                    ImportRecord.id != record.id,
                )
            )
            existing_record = result.scalar_one_or_none()
            if existing_record and existing_record.design_id:
                design_result = await db.execute(
                    select(Design).where(Design.id == existing_record.design_id)
                )
                design = design_result.scalar_one_or_none()
                if design:
                    logger.debug(
                        "duplicate_found_by_google_folder_id",
                        record_id=record.id,
                        google_folder_id=record.google_folder_id,
                        design_id=design.id,
                    )
                    return design

        # Strategy 2: Check by source_path within same source
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
            design = design_result.scalar_one_or_none()
            if design:
                logger.debug(
                    "duplicate_found_by_source_path",
                    record_id=record.id,
                    source_path=record.source_path,
                    design_id=design.id,
                )
                return design

        # Strategy 3: Check by detected_title within same source (fuzzy match)
        # This catches renamed folders that point to the same content
        if record.detected_title:
            result = await db.execute(
                select(ImportRecord).where(
                    ImportRecord.import_source_id == source.id,
                    ImportRecord.detected_title == record.detected_title,
                    ImportRecord.status == ImportRecordStatus.IMPORTED,
                    ImportRecord.id != record.id,
                )
            )
            existing_record = result.scalar_one_or_none()
            if existing_record and existing_record.design_id:
                design_result = await db.execute(
                    select(Design).where(Design.id == existing_record.design_id)
                )
                design = design_result.scalar_one_or_none()
                if design:
                    logger.debug(
                        "duplicate_found_by_title",
                        record_id=record.id,
                        detected_title=record.detected_title,
                        design_id=design.id,
                    )
                    return design

        # Strategy 4: Cross-source duplicate detection via DuplicateService (#216)
        # This checks against ALL designs including Telegram-sourced ones
        if record.detected_title:
            dup_service = DuplicateService(db)
            match, match_type, confidence = await dup_service.check_pre_download(
                title=record.detected_title,
                designer=record.detected_designer or source.default_designer or "",
                files=[],  # No file info available before download
            )

            if match and confidence >= AUTO_MERGE_THRESHOLD:
                logger.info(
                    "duplicate_found_cross_source",
                    record_id=record.id,
                    detected_title=record.detected_title,
                    match_design_id=match.id,
                    match_type=match_type.value if match_type else None,
                    confidence=confidence,
                )
                return match

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

    # ============================================================
    # DEC-038: Folder-based sync methods
    # ============================================================

    async def _sync_folders(
        self,
        db,
        source: ImportSource,
        folders: list[ImportSourceFolder],
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync multiple folders.

        Args:
            db: Database session.
            source: The import source.
            folders: List of folders to sync.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with total detected and imported counts.
        """
        total_detected = 0
        total_imported = 0
        all_errors: list[str] = []

        for i, folder in enumerate(folders):
            logger.info(
                "sync_folder_starting",
                source_id=source.id,
                folder_id=folder.id,
                folder_name=folder.display_name,
                index=i + 1,
                total=len(folders),
            )

            try:
                if source.source_type == ImportSourceType.BULK_FOLDER:
                    result = await self._sync_folder_bulk(
                        db, source, folder, auto_import, conflict_resolution
                    )
                elif source.source_type == ImportSourceType.GOOGLE_DRIVE:
                    result = await self._sync_folder_google_drive(
                        db, source, folder, auto_import, conflict_resolution
                    )
                elif source.source_type == ImportSourceType.PHPBB_FORUM:
                    result = await self._sync_folder_phpbb(
                        db, source, folder, auto_import, conflict_resolution
                    )
                else:
                    logger.warning(
                        "unsupported_source_type_for_folder",
                        source_type=source.source_type,
                        folder_id=folder.id,
                    )
                    continue

                total_detected += result["detected"]
                total_imported += result["imported"]
                all_errors.extend(result.get("errors", []))

                # Update folder stats - compute actual counts from database
                # to avoid inflated counts from multiple syncs/retries
                detected_count = await db.execute(
                    select(func.count()).where(
                        ImportRecord.import_source_folder_id == folder.id
                    )
                )
                imported_count = await db.execute(
                    select(func.count()).where(
                        ImportRecord.import_source_folder_id == folder.id,
                        ImportRecord.status == ImportRecordStatus.IMPORTED,
                        ImportRecord.design_id.isnot(None),
                    )
                )
                folder.items_detected = detected_count.scalar() or 0
                folder.items_imported = imported_count.scalar() or 0
                folder.last_synced_at = datetime.now(timezone.utc)
                folder.last_sync_error = None

                # Commit after each folder to release locks and allow reads
                await db.commit()

            except Exception as e:
                error_msg = f"Failed to sync folder {folder.display_name}: {e}"
                all_errors.append(error_msg)
                folder.last_sync_error = str(e)
                logger.error(
                    "sync_folder_failed",
                    folder_id=folder.id,
                    error=str(e),
                )

        # Also process orphaned records (records without folder assignment)
        # These are records from the root source folder before sub-folders were added
        if auto_import:
            orphaned_queued, orphaned_errors = await self._queue_orphaned_pending_downloads(
                db, source, conflict_resolution
            )
            total_imported += orphaned_queued
            all_errors.extend(orphaned_errors)

        # Update aggregate source stats
        source.items_imported = sum(f.items_imported or 0 for f in source.folders)

        return {
            "detected": total_detected,
            "imported": total_imported,
            "errors": all_errors,
        }

    async def _sync_legacy_source(
        self,
        db,
        source: ImportSource,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync using deprecated source-level fields (backward compatibility).

        Args:
            db: Database session.
            source: The import source.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        logger.info(
            "sync_legacy_source",
            source_id=source.id,
            source_type=source.source_type,
        )

        if source.source_type == ImportSourceType.BULK_FOLDER:
            return await self._sync_bulk_folder(
                db, source, auto_import, conflict_resolution
            )
        elif source.source_type == ImportSourceType.GOOGLE_DRIVE:
            return await self._sync_google_drive(
                db, source, auto_import, conflict_resolution
            )
        elif source.source_type == ImportSourceType.PHPBB_FORUM:
            return await self._sync_phpbb_forum(
                db, source, auto_import, conflict_resolution
            )
        else:
            raise NonRetryableError(f"Unsupported source type: {source.source_type}")

    async def _sync_folder_bulk(
        self,
        db,
        source: ImportSource,
        folder: ImportSourceFolder,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync a single bulk folder.

        Args:
            db: Database session.
            source: The import source.
            folder: The folder to sync.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        if not folder.folder_path:
            raise NonRetryableError(f"Folder {folder.id} missing folder_path")

        service = BulkImportService(db)

        # Scan folder using folder's path
        designs = await service.scan_folder_path(folder.folder_path)
        detected = len(designs)

        # Get effective settings (folder override or source default)
        effective_designer = folder.default_designer or source.default_designer
        effective_profile_id = folder.import_profile_id or source.import_profile_id

        # Create import records
        for design_info in designs:
            # Check if record already exists
            existing = await db.execute(
                select(ImportRecord).where(
                    ImportRecord.import_source_folder_id == folder.id,
                    ImportRecord.source_path == design_info.relative_path,
                )
            )
            if existing.scalar_one_or_none():
                continue

            record = ImportRecord(
                import_source_folder_id=folder.id,
                import_source_id=source.id,  # Keep for backward compatibility
                source_path=design_info.relative_path,
                file_size=design_info.total_size,
                status=ImportRecordStatus.PENDING,
                detected_title=design_info.title,
                detected_designer=effective_designer,
                model_file_count=len(design_info.model_files),
                preview_file_count=len(design_info.preview_files),
                detected_at=datetime.now(timezone.utc),
            )
            db.add(record)

        # Commit records to release locks before potentially long import operations
        await db.commit()

        imported = 0
        errors: list[str] = []

        if auto_import:
            imported, errors = await self._import_folder_pending(
                db, source, folder, conflict_resolution
            )

        return {
            "detected": detected,
            "imported": imported,
            "errors": errors,
        }

    async def _sync_folder_google_drive(
        self,
        db,
        source: ImportSource,
        folder: ImportSourceFolder,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync a single Google Drive folder.

        Uses optimized sync strategy:
        - First sync: Full scan with caching and batching
        - Subsequent syncs: Incremental sync using change tokens (if available)
        - Stores sync_cursor for next incremental sync

        Args:
            db: Database session.
            source: The import source.
            folder: The folder to sync.
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        if not folder.google_folder_id:
            raise NonRetryableError(f"Folder {folder.id} missing google_folder_id")

        # Get effective settings (folder override or source default)
        effective_profile_id = folder.import_profile_id or source.import_profile_id
        effective_designer = folder.default_designer or source.default_designer

        # Get import profile config
        profile_service = ImportProfileService(db)
        config = await profile_service.get_profile_config(effective_profile_id)

        # Get credentials if OAuth is configured
        gdrive_service = GoogleDriveService(db)
        credentials = None
        if source.google_credentials_id:
            credentials = await gdrive_service.get_credentials(source.google_credentials_id)

        # Scan Google Drive folder with caching and batching
        # Note: Incremental sync via change tokens is available but requires
        # tracking file state which adds complexity. For now we use the
        # optimized full scan with caching.
        detected_designs = await gdrive_service.scan_for_designs(
            folder.google_folder_id,
            credentials=credentials,
            config=config,
            use_cache=True,
            use_batch=True,
        )

        # Store/update sync cursor for future incremental sync
        # Get a new page token so future syncs can detect changes
        if not folder.sync_cursor:
            try:
                new_token = await gdrive_service.get_start_page_token(credentials)
                folder.sync_cursor = new_token
                logger.debug(
                    "sync_cursor_set",
                    folder_id=folder.id,
                    token_preview=new_token[:20] + "..." if new_token else None,
                )
            except Exception as e:
                # Non-fatal - we can still sync without change tracking
                logger.warning("failed_to_get_page_token", error=str(e))
        detected = len(detected_designs)

        # Create import records
        for design in detected_designs:
            # Check if record already exists
            existing = await db.execute(
                select(ImportRecord).where(
                    ImportRecord.import_source_folder_id == folder.id,
                    ImportRecord.source_path == design.relative_path,
                )
            )
            if existing.scalar_one_or_none():
                continue

            record = ImportRecord(
                import_source_folder_id=folder.id,
                import_source_id=source.id,  # Keep for backward compatibility
                source_path=design.relative_path,
                file_size=design.total_size,
                status=ImportRecordStatus.PENDING,
                detected_title=design.title,
                detected_designer=effective_designer,
                model_file_count=len(design.model_files),
                preview_file_count=len(design.preview_files),
                detected_at=datetime.now(timezone.utc),
                google_folder_id=design.folder_id,  # Store for download
            )
            db.add(record)

        # Commit records to release locks before potentially long import operations
        await db.commit()

        imported = 0
        errors: list[str] = []

        if auto_import:
            imported, errors = await self._import_folder_pending(
                db, source, folder, conflict_resolution
            )

        return {
            "detected": detected,
            "imported": imported,
            "errors": errors,
        }

    async def _sync_folder_phpbb(
        self,
        db,
        source: ImportSource,
        folder: ImportSourceFolder,
        auto_import: bool,
        conflict_resolution: ConflictResolution,
    ) -> dict[str, Any]:
        """Sync a single phpBB forum folder (issue #242).

        Args:
            db: Database session.
            source: The import source.
            folder: The folder to sync (contains phpbb_forum_url).
            auto_import: Whether to auto-import detected designs.
            conflict_resolution: How to handle conflicts.

        Returns:
            Dict with detected and imported counts.
        """
        if not folder.phpbb_forum_url:
            raise NonRetryableError(f"Folder {folder.id} missing phpbb_forum_url")

        if not source.phpbb_credentials_id:
            raise NonRetryableError(f"Source {source.id} missing phpbb_credentials_id")

        # Get effective settings (folder override or source default)
        effective_designer = folder.default_designer or source.default_designer

        # Get phpBB credentials and session
        phpbb_service = PhpbbService(db)
        credentials = await phpbb_service.get_credentials(source.phpbb_credentials_id)
        if not credentials:
            raise NonRetryableError(f"phpBB credentials {source.phpbb_credentials_id} not found")

        try:
            # Get session cookies (login if needed)
            cookies = await phpbb_service.get_session_cookies(credentials)

            # Scan forum for designs (topics with ZIP attachments)
            detected_designs = await phpbb_service.scan_forum_for_designs(
                credentials.base_url,
                folder.phpbb_forum_url,
                cookies,
            )
            detected = len(detected_designs)

            # Create import records for detected designs
            import json as json_module
            for design in detected_designs:
                # Check if record already exists
                existing = await db.execute(
                    select(ImportRecord).where(
                        ImportRecord.import_source_folder_id == folder.id,
                        ImportRecord.source_path == design.relative_path,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Store attachment info in payload
                attachments_data = [
                    {
                        "file_id": a.file_id,
                        "filename": a.filename,
                        "size_bytes": a.size_bytes,
                        "download_url": a.download_url,
                    }
                    for a in design.attachments
                ]

                # Store image URLs for preview extraction
                images_data = [img.url for img in design.images]

                record = ImportRecord(
                    import_source_folder_id=folder.id,
                    import_source_id=source.id,  # Keep for backward compatibility
                    source_path=design.relative_path,
                    file_size=design.total_size,
                    status=ImportRecordStatus.PENDING,
                    detected_title=design.title,
                    detected_designer=design.author or effective_designer,
                    model_file_count=len(design.attachments),  # Each attachment is a ZIP
                    preview_file_count=len(design.images),
                    detected_at=datetime.now(timezone.utc),
                    payload_json=json_module.dumps({
                        "topic_id": design.topic_id,
                        "forum_id": design.forum_id,
                        "topic_title": design.topic_title,
                        "title": design.title,
                        "author": design.author,
                        "attachments": attachments_data,
                        "images": images_data,
                    }),
                )
                db.add(record)

            # Commit records to release locks before potentially long import operations
            await db.commit()

            imported = 0
            errors: list[str] = []

            if auto_import:
                imported, errors = await self._import_folder_pending(
                    db, source, folder, conflict_resolution
                )

            return {
                "detected": detected,
                "imported": imported,
                "errors": errors,
            }

        except PhpbbAuthError as e:
            folder.last_sync_error = f"phpBB authentication failed: {e}"
            await db.commit()
            raise NonRetryableError(str(e))

        except PhpbbError as e:
            folder.last_sync_error = str(e)
            await db.commit()
            raise RetryableError(str(e))

    async def _import_folder_pending(
        self,
        db,
        source: ImportSource,
        folder: ImportSourceFolder,
        conflict_resolution: ConflictResolution,
    ) -> tuple[int, list[str]]:
        """Queue download jobs for pending records in a folder (DEC-040).

        Instead of downloading inline, this method queues individual
        DOWNLOAD_IMPORT_RECORD jobs for each pending design.

        Args:
            db: Database session.
            source: The import source.
            folder: The folder to import from.
            conflict_resolution: How to handle conflicts.

        Returns:
            Tuple of (queued_count, errors).
        """
        # Get pending records for this folder
        result = await db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_folder_id == folder.id,
                ImportRecord.status == ImportRecordStatus.PENDING,
            )
        )
        records = list(result.scalars().all())

        logger.info(
            "folder_auto_import_queueing",
            folder_id=folder.id,
            pending_count=len(records),
        )

        queued = 0
        errors: list[str] = []
        queue = JobQueueService(db)

        # Track titles already queued in this batch for intra-batch deduplication
        queued_titles: set[str] = set()

        for record in records:
            try:
                # Only Google Drive folders support per-design downloads for now
                if source.source_type != ImportSourceType.GOOGLE_DRIVE:
                    continue  # TODO: Implement folder-based bulk import

                # Check for conflicts before queuing
                if conflict_resolution == ConflictResolution.SKIP:
                    # Intra-batch deduplication: skip if same title already queued
                    if record.detected_title and record.detected_title in queued_titles:
                        record.status = ImportRecordStatus.SKIPPED
                        logger.info(
                            "folder_import_skipped_intra_batch_duplicate",
                            folder_id=folder.id,
                            record_id=record.id,
                            detected_title=record.detected_title,
                        )
                        continue

                    # Cross-source deduplication: check against existing designs
                    existing = await self._find_existing_design(db, record, source)
                    if existing:
                        record.status = ImportRecordStatus.SKIPPED
                        record.design_id = existing.id
                        logger.info(
                            "folder_import_skipped_duplicate",
                            folder_id=folder.id,
                            record_id=record.id,
                            existing_design_id=existing.id,
                        )
                        continue

                # Check for existing queued/running job for this record (#237)
                existing_job = await queue.get_pending_job_for_import_record(record.id)
                if existing_job:
                    logger.debug(
                        "folder_import_job_already_queued",
                        folder_id=folder.id,
                        record_id=record.id,
                        job_id=existing_job.id,
                    )
                    continue

                # Queue DOWNLOAD_IMPORT_RECORD job with display name
                display_name = f"Download: {record.detected_title or record.source_path.split('/')[-1]} from {folder.display_name}"
                await queue.enqueue(
                    JobType.DOWNLOAD_IMPORT_RECORD,
                    payload={
                        "import_record_id": record.id,
                    },
                    priority=5,
                    display_name=display_name,
                )
                queued += 1

                # Track title for intra-batch deduplication
                if record.detected_title:
                    queued_titles.add(record.detected_title)

                # Note: items_imported is updated when the download job completes,
                # not when queued (to avoid inflated counts from retries/requeues)

            except Exception as e:
                error_msg = f"Failed to queue {record.source_path}: {e}"
                errors.append(error_msg)
                logger.error(
                    "folder_queue_failed",
                    folder_id=folder.id,
                    record_id=record.id,
                    error=str(e),
                )

        # Commit all queued jobs
        await db.commit()

        logger.info(
            "folder_auto_import_queued",
            folder_id=folder.id,
            queued=queued,
            errors=len(errors),
        )

        return queued, errors

    async def _queue_orphaned_pending_downloads(
        self,
        db,
        source: ImportSource,
        conflict_resolution: ConflictResolution,
    ) -> tuple[int, list[str]]:
        """Queue downloads for orphaned PENDING records without folder assignment.

        These are records from the root source folder before sub-folders were added,
        or records that were reset due to bugs but lost their folder assignment.

        Args:
            db: Database session.
            source: The import source.
            conflict_resolution: How to handle conflicts.

        Returns:
            Tuple of (queued_count, errors).
        """
        # Get PENDING records without folder assignment for this source
        result = await db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_id == source.id,
                ImportRecord.import_source_folder_id.is_(None),
                ImportRecord.status == ImportRecordStatus.PENDING,
            )
        )
        records = list(result.scalars().all())

        if not records:
            return 0, []

        logger.info(
            "orphaned_auto_import_queueing",
            source_id=source.id,
            pending_count=len(records),
        )

        queued = 0
        errors: list[str] = []
        queue = JobQueueService(db)

        # Track titles already queued in this batch for intra-batch deduplication
        queued_titles: set[str] = set()

        for record in records:
            try:
                # Only Google Drive sources support per-design downloads
                if source.source_type != ImportSourceType.GOOGLE_DRIVE:
                    continue

                # Check for conflicts before queuing
                if conflict_resolution == ConflictResolution.SKIP:
                    # Intra-batch deduplication: skip if same title already queued
                    if record.detected_title and record.detected_title in queued_titles:
                        record.status = ImportRecordStatus.SKIPPED
                        logger.info(
                            "orphaned_import_skipped_intra_batch_duplicate",
                            source_id=source.id,
                            record_id=record.id,
                            detected_title=record.detected_title,
                        )
                        continue

                    # Cross-source deduplication: check against existing designs
                    existing = await self._find_existing_design(db, record, source)
                    if existing:
                        record.status = ImportRecordStatus.SKIPPED
                        record.design_id = existing.id
                        logger.info(
                            "orphaned_import_skipped_duplicate",
                            source_id=source.id,
                            record_id=record.id,
                            existing_design_id=existing.id,
                        )
                        continue

                # Check for existing queued/running job for this record
                existing_job = await queue.get_pending_job_for_import_record(record.id)
                if existing_job:
                    logger.debug(
                        "orphaned_import_job_already_queued",
                        source_id=source.id,
                        record_id=record.id,
                        job_id=existing_job.id,
                    )
                    continue

                # Queue DOWNLOAD_IMPORT_RECORD job with display name
                display_name = f"Download: {record.detected_title or record.source_path.split('/')[-1]} from {source.name}"
                await queue.enqueue(
                    JobType.DOWNLOAD_IMPORT_RECORD,
                    payload={
                        "import_record_id": record.id,
                    },
                    priority=5,
                    display_name=display_name,
                )
                queued += 1

                # Track title for intra-batch deduplication
                if record.detected_title:
                    queued_titles.add(record.detected_title)

            except Exception as e:
                error_msg = f"Failed to queue orphaned {record.source_path}: {e}"
                errors.append(error_msg)
                logger.error(
                    "orphaned_queue_failed",
                    source_id=source.id,
                    record_id=record.id,
                    error=str(e),
                )

        # Commit all queued jobs
        await db.commit()

        logger.info(
            "orphaned_auto_import_queued",
            source_id=source.id,
            queued=queued,
            errors=len(errors),
        )

        return queued, errors
