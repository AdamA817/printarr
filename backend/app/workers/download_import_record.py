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
    PhpbbCredentials,
)
from app.db.session import async_session_maker
from app.services.auto_render import auto_queue_render_for_design
from app.services.duplicate import DuplicateService
from app.services.google_drive import GoogleDriveError, GoogleDriveService, GoogleRateLimitError
from app.services.phpbb import PhpbbError, PhpbbService
from app.services.job_queue import JobQueueService
from app.utils import compute_file_hash
from app.workers.base import BaseWorker, CancellationError, NonRetryableError, RetryableError

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
                elif source.source_type == ImportSourceType.PHPBB_FORUM:
                    design = await self._download_phpbb_record(db, record, source)
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

            except CancellationError:
                # Job was cancelled (bug #235) - abort cleanly without error
                record.status = ImportRecordStatus.PENDING  # Reset to pending for potential retry
                await db.commit()

                # Clean up any partial downloads in staging
                import shutil
                staging_dir = settings.staging_path / f"gdrive_{record.id}"
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)

                logger.info(
                    "import_record_download_cancelled",
                    record_id=import_record_id,
                )
                return {
                    "record_id": import_record_id,
                    "status": "cancelled",
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

            except PhpbbError as e:
                # phpBB errors (auth, access denied, etc.)
                record.status = ImportRecordStatus.ERROR
                record.error_message = str(e)
                await db.commit()
                raise NonRetryableError(f"phpBB error: {e}")

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

            # NOTE: We do NOT update source.items_imported here because:
            # 1. It creates a write lock on ImportSource during long downloads
            # 2. This blocks delete operations (bug #235)
            # 3. The sync job handles source-level stats appropriately
            # Items imported can be calculated from ImportRecord counts instead.

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

    async def _download_phpbb_record(
        self,
        db,
        record: ImportRecord,
        source: ImportSource,
    ) -> Design | None:
        """Download and import a single phpBB forum topic.

        Args:
            db: Database session.
            record: The ImportRecord to import.
            source: The ImportSource.

        Returns:
            The created Design, or None if skipped.
        """
        import json
        import shutil

        # Get payload with attachment info
        if not record.payload_json:
            raise NonRetryableError(
                f"Import record {record.id} missing payload_json with attachment info"
            )

        try:
            payload = json.loads(record.payload_json)
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"Invalid payload_json: {e}")

        attachments = payload.get("attachments", [])
        if not attachments:
            raise NonRetryableError(f"Import record {record.id} has no attachments")

        images = payload.get("images", [])  # Preview images from post

        # Get phpBB credentials
        if not source.phpbb_credentials_id:
            raise NonRetryableError(
                f"Import source {source.id} has no phpBB credentials"
            )

        credentials = await db.get(PhpbbCredentials, source.phpbb_credentials_id)
        if not credentials:
            raise NonRetryableError(
                f"phpBB credentials {source.phpbb_credentials_id} not found"
            )

        # Update record status
        record.status = ImportRecordStatus.IMPORTING

        # Create staging directory for this design
        staging_dir = settings.staging_path / f"phpbb_{record.id}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Initialize phpBB service
            phpbb_service = PhpbbService(db)

            # Get session cookies
            cookies = await phpbb_service.get_session_cookies(credentials)

            # Download attachments
            downloaded_files: list[tuple[Path, int]] = []
            total_attachments = len(attachments)

            for idx, attachment in enumerate(attachments):
                download_url = attachment.get("download_url")
                filename = attachment.get("filename", f"attachment_{idx}")

                if not download_url:
                    continue

                # Check for cancellation
                await self.check_cancellation()

                # Report progress
                await self.update_progress(
                    idx,
                    total_attachments,
                    current_file=filename,
                )

                # Download the file
                dest_path = staging_dir / filename
                await phpbb_service.download_file(
                    download_url,
                    dest_path,
                    cookies,
                )

                if dest_path.exists():
                    file_size = dest_path.stat().st_size
                    downloaded_files.append((dest_path, file_size))

            if not downloaded_files:
                raise NonRetryableError(
                    f"No files downloaded from phpBB topic for record {record.id}"
                )

            # Extract archives to get model files
            extracted_files = await self._extract_archives(staging_dir, downloaded_files)

            # Download preview images from the post
            preview_files: list[tuple[Path, int]] = []
            if images:
                previews_dir = staging_dir / "previews"
                previews_dir.mkdir(exist_ok=True)

                for idx, image_url in enumerate(images[:5]):  # Limit to 5 preview images
                    try:
                        # Use a simple filename
                        ext = Path(image_url).suffix.lower()
                        if ext not in PREVIEW_EXTENSIONS:
                            ext = ".jpg"
                        img_filename = f"preview_{idx}{ext}"
                        img_path = previews_dir / img_filename

                        await phpbb_service.download_file(
                            image_url,
                            img_path,
                            cookies,
                        )

                        if img_path.exists():
                            preview_files.append((img_path, img_path.stat().st_size))
                    except Exception as e:
                        logger.warning(
                            "phpbb_preview_download_failed",
                            record_id=record.id,
                            image_url=image_url,
                            error=str(e),
                        )

            # Combine all files (extracted + previews)
            all_files = extracted_files + preview_files

            # Create Design record
            design = Design(
                canonical_title=record.detected_title or payload.get("title", "Unknown"),
                canonical_designer=record.detected_designer or source.default_designer or payload.get("author", "Unknown"),
                status=DesignStatus.DOWNLOADED,
                metadata_authority=MetadataAuthority.USER,
                import_source_id=source.id,
                total_size_bytes=sum(size for _, size in all_files),
            )
            db.add(design)
            await db.flush()

            # Create DesignFile records for each file
            has_previews = len(preview_files) > 0
            for file_path, file_size in all_files:
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

            # Rename staging directory to {design.id}
            new_staging_dir = settings.staging_path / design.id
            if staging_dir != new_staging_dir:
                staging_dir.rename(new_staging_dir)
                logger.debug(
                    "staging_dir_renamed",
                    old=str(staging_dir),
                    new=str(new_staging_dir),
                )

            # Queue IMPORT_TO_LIBRARY job
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

            logger.info(
                "phpbb_record_downloaded",
                record_id=record.id,
                design_id=design.id,
                title=design.canonical_title,
                files=len(all_files),
                archives=len(downloaded_files),
                previews=len(preview_files),
            )

            return design

        except Exception as e:
            # Clean up staging directory on failure
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    async def _extract_archives(
        self,
        staging_dir: Path,
        downloaded_files: list[tuple[Path, int]],
    ) -> list[tuple[Path, int]]:
        """Extract archives and return list of extracted model/image files.

        Args:
            staging_dir: Directory containing downloaded files.
            downloaded_files: List of (path, size) tuples of downloaded archives.

        Returns:
            List of (path, size) tuples for extracted files.
        """
        import shutil
        import zipfile

        extracted_files: list[tuple[Path, int]] = []
        archive_extensions = {".zip", ".rar", ".7z"}

        for file_path, _ in downloaded_files:
            ext = file_path.suffix.lower()

            if ext == ".zip":
                # Extract ZIP files
                extract_dir = staging_dir / file_path.stem
                extract_dir.mkdir(exist_ok=True)

                try:
                    with zipfile.ZipFile(file_path, "r") as zf:
                        zf.extractall(extract_dir)

                    # Walk extracted files
                    for root, _, files in extract_dir.iterdir() if extract_dir.is_dir() else []:
                        pass

                    # Use os.walk for recursive directory traversal
                    import os
                    for root, _, files in os.walk(extract_dir):
                        for filename in files:
                            extracted_path = Path(root) / filename
                            if extracted_path.suffix.lower() in MODEL_EXTENSIONS | PREVIEW_EXTENSIONS:
                                extracted_files.append((extracted_path, extracted_path.stat().st_size))

                    # Remove the original archive
                    file_path.unlink()

                except zipfile.BadZipFile:
                    logger.warning("phpbb_bad_zip", file=str(file_path))
                    # Keep the file as-is, might be useful

            elif ext == ".rar":
                # RAR extraction requires rarfile library
                try:
                    import rarfile

                    extract_dir = staging_dir / file_path.stem
                    extract_dir.mkdir(exist_ok=True)

                    with rarfile.RarFile(file_path, "r") as rf:
                        rf.extractall(extract_dir)

                    import os
                    for root, _, files in os.walk(extract_dir):
                        for filename in files:
                            extracted_path = Path(root) / filename
                            if extracted_path.suffix.lower() in MODEL_EXTENSIONS | PREVIEW_EXTENSIONS:
                                extracted_files.append((extracted_path, extracted_path.stat().st_size))

                    file_path.unlink()

                except ImportError:
                    logger.warning("phpbb_rarfile_not_installed", file=str(file_path))
                    # Keep RAR file as-is
                except Exception as e:
                    logger.warning("phpbb_rar_extraction_failed", file=str(file_path), error=str(e))

            elif ext == ".7z":
                # 7z extraction requires py7zr library
                try:
                    import py7zr

                    extract_dir = staging_dir / file_path.stem
                    extract_dir.mkdir(exist_ok=True)

                    with py7zr.SevenZipFile(file_path, "r") as sz:
                        sz.extractall(extract_dir)

                    import os
                    for root, _, files in os.walk(extract_dir):
                        for filename in files:
                            extracted_path = Path(root) / filename
                            if extracted_path.suffix.lower() in MODEL_EXTENSIONS | PREVIEW_EXTENSIONS:
                                extracted_files.append((extracted_path, extracted_path.stat().st_size))

                    file_path.unlink()

                except ImportError:
                    logger.warning("phpbb_py7zr_not_installed", file=str(file_path))
                except Exception as e:
                    logger.warning("phpbb_7z_extraction_failed", file=str(file_path), error=str(e))

            elif ext not in archive_extensions:
                # Non-archive file - add directly if it's a model or image
                if ext in MODEL_EXTENSIONS | PREVIEW_EXTENSIONS:
                    extracted_files.append((file_path, file_path.stat().st_size))

        return extracted_files
