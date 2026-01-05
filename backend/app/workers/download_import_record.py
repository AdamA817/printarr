"""Download Import Record worker for per-design downloads (DEC-040).

This worker processes DOWNLOAD_IMPORT_RECORD jobs to:
1. Download files for a single import record
2. Create the Design and DesignFile records
3. Queue the IMPORT_TO_LIBRARY job

This enables per-design progress tracking in the Activity UI with
meaningful job names like "Download: Dragon Bust from Wicked STL".
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    Design,
    DesignFile,
    DesignStatus,
    FileKind,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceType,
    JobType,
    MetadataAuthority,
)
from app.db.session import async_session_maker
from app.services.auto_render import auto_queue_render_for_design
from app.services.duplicate import DuplicateService
from app.services.google_drive import GoogleDriveError, GoogleDriveService, GoogleRateLimitError
from app.services.job_queue import JobQueueService
from app.utils import compute_file_hash
from app.workers.base import BaseWorker, NonRetryableError, RetryableError

# Auto-merge threshold for pre-download duplicate check (DEC-041 / #216)
AUTO_MERGE_THRESHOLD = 0.9

# File extensions for 3D model files
MODEL_EXTENSIONS = {".stl", ".3mf", ".obj", ".step", ".stp", ".iges", ".igs", ".blend", ".gcode"}

# File extensions for preview/image files
PREVIEW_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

logger = get_logger(__name__)


class DownloadImportRecordWorker(BaseWorker):
    """Worker for downloading a single import record.

    Processes DOWNLOAD_IMPORT_RECORD jobs queued by the sync worker.
    Each job downloads files for one design, enabling per-design progress
    tracking in the Activity UI.
    """

    job_types = [JobType.DOWNLOAD_IMPORT_RECORD]

    async def process(self, job, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        """Process a DOWNLOAD_IMPORT_RECORD job.

        Args:
            job: The job to process.
            payload: Job payload with import_record_id.

        Returns:
            Result dict with import status.
        """
        if not payload:
            return {"error": "No payload provided"}

        import_record_id = payload.get("import_record_id")
        if not import_record_id:
            return {"error": "No import_record_id in payload"}

        async with async_session_maker() as db:
            # Get the import record with source
            result = await db.execute(
                select(ImportRecord)
                .options(selectinload(ImportRecord.import_source))
                .where(ImportRecord.id == import_record_id)
            )
            record = result.scalar_one_or_none()

            if not record:
                raise NonRetryableError(f"Import record {import_record_id} not found")

            source = record.import_source
            if not source:
                raise NonRetryableError(f"Import record {import_record_id} has no import source")

            # Check if already imported
            if record.status == ImportRecordStatus.IMPORTED:
                logger.info(
                    "import_record_already_imported",
                    record_id=import_record_id,
                    design_id=record.design_id,
                )
                return {
                    "record_id": import_record_id,
                    "status": "already_imported",
                    "design_id": record.design_id,
                }

            # Check for duplicates before downloading (DEC-041 / #216)
            existing_design = await self._check_pre_download_duplicate(
                db, record, source
            )
            if existing_design:
                # High confidence duplicate found - skip download and link record
                record.status = ImportRecordStatus.SKIPPED
                record.design_id = existing_design.id
                await db.commit()

                logger.info(
                    "download_skipped_duplicate_found",
                    record_id=import_record_id,
                    match_design_id=existing_design.id,
                )
                return {
                    "record_id": import_record_id,
                    "status": "skipped_duplicate",
                    "design_id": existing_design.id,
                }

            try:
                if source.source_type == ImportSourceType.GOOGLE_DRIVE:
                    design = await self._download_google_drive_record(db, record, source)
                else:
                    raise NonRetryableError(
                        f"Unsupported source type: {source.source_type}"
                    )

                await db.commit()

                if design:
                    return {
                        "record_id": import_record_id,
                        "status": "imported",
                        "design_id": design.id,
                        "title": design.canonical_title,
                    }
                else:
                    return {
                        "record_id": import_record_id,
                        "status": "skipped",
                    }

            except GoogleRateLimitError as e:
                # Rate limited - should retry
                record.status = ImportRecordStatus.ERROR
                record.error_message = str(e)
                await db.commit()
                raise RetryableError(f"Google rate limited: {e}")

            except GoogleDriveError as e:
                # Other Google errors
                record.status = ImportRecordStatus.ERROR
                record.error_message = str(e)
                await db.commit()
                raise NonRetryableError(f"Google Drive error: {e}")

            except Exception as e:
                record.status = ImportRecordStatus.ERROR
                record.error_message = str(e)
                await db.commit()
                raise

    async def _download_google_drive_record(
        self,
        db,
        record: ImportRecord,
        source: ImportSource,
    ) -> Design | None:
        """Download and import a single Google Drive folder.

        Args:
            db: Database session.
            record: The ImportRecord to import.
            source: The ImportSource.

        Returns:
            The created Design, or None if skipped.
        """
        if not record.google_folder_id:
            raise NonRetryableError(
                f"Import record {record.id} missing google_folder_id"
            )

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

            # Progress callback to report current file being downloaded
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

            logger.info(
                "import_record_downloaded",
                record_id=record.id,
                design_id=design.id,
                title=design.canonical_title,
                files=len(downloaded_files),
            )

            return design

        except Exception as e:
            # Clean up staging directory on failure
            import shutil
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            # Also clean up renamed path if it exists
            design_staging = settings.staging_path / design.id if 'design' in dir() else None
            if design_staging and design_staging.exists():
                shutil.rmtree(design_staging, ignore_errors=True)
            raise

    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        return await compute_file_hash(file_path)

    async def _check_pre_download_duplicate(
        self,
        db,
        record: ImportRecord,
        source: ImportSource,
    ) -> Design | None:
        """Check for duplicates before downloading (DEC-041 / #216).

        Uses DuplicateService to find cross-source duplicates including
        Telegram designs.

        Args:
            db: Database session.
            record: The import record to check.
            source: The import source.

        Returns:
            The matched Design if high-confidence duplicate found, None otherwise.
        """
        if not record.detected_title:
            return None

        dup_service = DuplicateService(db)
        match, match_type, confidence = await dup_service.check_pre_download(
            title=record.detected_title,
            designer=record.detected_designer or source.default_designer or "",
            files=[],  # File info not yet available before download
        )

        if match and confidence >= AUTO_MERGE_THRESHOLD:
            logger.info(
                "pre_download_duplicate_found",
                record_id=record.id,
                match_design_id=match.id,
                match_type=match_type.value if match_type else None,
                confidence=confidence,
            )
            return match

        elif match and confidence > 0:
            # Lower confidence - log but proceed with download
            logger.info(
                "pre_download_potential_duplicate",
                record_id=record.id,
                match_design_id=match.id,
                match_type=match_type.value if match_type else None,
                confidence=confidence,
            )

        return None
