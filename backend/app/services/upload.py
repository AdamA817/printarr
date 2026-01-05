"""File upload service for v0.8 Manual Imports.

Provides:
- File upload to staging directory
- Archive extraction
- Design detection and creation
- Upload cleanup
"""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

import aiofiles
import aiofiles.os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Design, ImportSource
from app.db.models.enums import DesignStatus, ImportSourceType, MetadataAuthority
from app.schemas.import_profile import ImportProfileConfig
from app.schemas.upload import (
    ProcessUploadResponse,
    UploadInfo,
    UploadResponse,
    UploadStatus,
)
from app.services.archive import ArchiveExtractor
from app.services.auto_render import auto_queue_render_for_design
from app.services.import_profile import ImportProfileService

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Metadata file for tracking upload state
UPLOAD_META_FILE = ".upload_meta.json"


class UploadError(Exception):
    """Base exception for upload errors."""

    pass


class UploadNotFoundError(UploadError):
    """Raised when an upload is not found."""

    pass


class UploadValidationError(UploadError):
    """Raised when file validation fails."""

    pass


class UploadProcessingError(UploadError):
    """Raised when processing fails."""

    pass


class UploadService:
    """Service for managing file uploads.

    Handles file upload, validation, extraction, and design creation.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the upload service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db
        self._staging_path = settings.upload_staging_path

    async def ensure_staging_dir(self) -> None:
        """Ensure the upload staging directory exists."""
        await aiofiles.os.makedirs(self._staging_path, exist_ok=True)

    # ========== Upload Operations ==========

    async def create_upload(
        self,
        filename: str,
        file_content: BinaryIO | bytes,
        content_type: str | None = None,
    ) -> UploadResponse:
        """Create a new upload from file content.

        Args:
            filename: Original filename.
            file_content: File content (file-like object or bytes).
            content_type: Optional MIME type.

        Returns:
            UploadResponse with upload details.

        Raises:
            UploadValidationError: If file is invalid.
        """
        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in settings.upload_allowed_extensions:
            raise UploadValidationError(
                f"File type '{ext}' not allowed. Allowed: {settings.upload_allowed_extensions}"
            )

        # Generate upload ID and paths
        upload_id = str(uuid.uuid4())
        upload_dir = self._staging_path / upload_id
        await aiofiles.os.makedirs(upload_dir, exist_ok=True)

        file_path = upload_dir / filename

        # Write file to staging
        if isinstance(file_content, bytes):
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)
        else:
            # File-like object (from FastAPI UploadFile)
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := file_content.read(1024 * 1024):  # 1MB chunks
                    await f.write(chunk)

        # Get file size
        stat = await aiofiles.os.stat(file_path)
        size = stat.st_size

        # Validate size
        max_size_bytes = settings.upload_max_size_mb * 1024 * 1024
        if size > max_size_bytes:
            # Cleanup and raise error
            await self._cleanup_upload(upload_id)
            raise UploadValidationError(
                f"File size ({size / 1024 / 1024:.1f}MB) exceeds maximum ({settings.upload_max_size_mb}MB)"
            )

        # Save metadata
        await self._save_meta(upload_id, {
            "filename": filename,
            "size": size,
            "mime_type": content_type,
            "status": UploadStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "upload_created",
            upload_id=upload_id,
            filename=filename,
            size=size,
        )

        return UploadResponse(
            upload_id=upload_id,
            filename=filename,
            size=size,
            status=UploadStatus.PENDING,
        )

    async def get_upload(self, upload_id: str) -> UploadInfo:
        """Get information about an upload.

        Args:
            upload_id: Upload ID.

        Returns:
            UploadInfo with details.

        Raises:
            UploadNotFoundError: If upload not found.
        """
        meta = await self._load_meta(upload_id)
        if not meta:
            raise UploadNotFoundError(f"Upload {upload_id} not found")

        return UploadInfo(
            id=upload_id,
            filename=meta["filename"],
            size=meta["size"],
            mime_type=meta.get("mime_type"),
            status=UploadStatus(meta["status"]),
            error_message=meta.get("error_message"),
            created_at=datetime.fromisoformat(meta["created_at"]),
            processed_at=datetime.fromisoformat(meta["processed_at"]) if meta.get("processed_at") else None,
            design_id=meta.get("design_id"),
        )

    async def list_uploads(self, include_expired: bool = False) -> list[UploadInfo]:
        """List all uploads in staging.

        Args:
            include_expired: Include expired uploads.

        Returns:
            List of UploadInfo.
        """
        uploads = []
        if not self._staging_path.exists():
            return uploads

        for upload_dir in self._staging_path.iterdir():
            if not upload_dir.is_dir():
                continue

            try:
                info = await self.get_upload(upload_dir.name)
                if not include_expired and info.status == UploadStatus.EXPIRED:
                    continue
                uploads.append(info)
            except UploadNotFoundError:
                continue

        return sorted(uploads, key=lambda u: u.created_at, reverse=True)

    async def delete_upload(self, upload_id: str) -> None:
        """Delete an upload and cleanup files.

        Args:
            upload_id: Upload ID.

        Raises:
            UploadNotFoundError: If upload not found.
        """
        meta = await self._load_meta(upload_id)
        if not meta:
            raise UploadNotFoundError(f"Upload {upload_id} not found")

        await self._cleanup_upload(upload_id)
        logger.info("upload_deleted", upload_id=upload_id)

    # ========== Processing ==========

    async def process_upload(
        self,
        upload_id: str,
        import_profile_id: str | None = None,
        designer: str | None = None,
        tags: list[str] | None = None,
        title: str | None = None,
    ) -> ProcessUploadResponse:
        """Process an uploaded file and create a design.

        Args:
            upload_id: Upload ID.
            import_profile_id: Optional import profile to use.
            designer: Optional designer name override.
            tags: Optional tags to apply.
            title: Optional title override.

        Returns:
            ProcessUploadResponse with results.

        Raises:
            UploadNotFoundError: If upload not found.
            UploadProcessingError: If processing fails.
        """
        meta = await self._load_meta(upload_id)
        if not meta:
            raise UploadNotFoundError(f"Upload {upload_id} not found")

        if meta["status"] != UploadStatus.PENDING.value:
            raise UploadProcessingError(
                f"Upload {upload_id} already processed (status: {meta['status']})"
            )

        # Update status
        meta["status"] = UploadStatus.PROCESSING.value
        await self._save_meta(upload_id, meta)

        upload_dir = self._staging_path / upload_id
        filename = meta["filename"]
        file_path = upload_dir / filename

        try:
            # Get import profile config
            profile_service = ImportProfileService(self.db)
            config = await profile_service.get_profile_config(import_profile_id)

            # Extract if archive
            extracted_dir = upload_dir / "extracted"
            files_extracted = 0
            model_files = 0
            preview_files = 0

            ext = Path(filename).suffix.lower()
            if ext in [".zip", ".rar", ".7z"]:
                # Extract archive
                extractor = ArchiveExtractor()
                extract_result = await extractor.extract(
                    file_path,
                    extracted_dir,
                )
                files_extracted = extract_result.files_extracted

                # Detect design from extracted folder
                detection = profile_service.is_design_folder(extracted_dir, config)
                model_files = len(detection.model_files)
                preview_files = len(detection.preview_files)
                detected_title = detection.title

            else:
                # Single model file
                await aiofiles.os.makedirs(extracted_dir, exist_ok=True)
                shutil.copy2(file_path, extracted_dir / filename)
                files_extracted = 1
                model_files = 1
                detected_title = Path(filename).stem

            # Determine title
            design_title = title or detected_title or Path(filename).stem

            # Create design record
            design = Design(
                canonical_title=design_title,
                canonical_designer=designer or "Unknown",
                status=DesignStatus.DOWNLOADED,
                metadata_authority=MetadataAuthority.USER,
            )
            self.db.add(design)
            await self.db.flush()

            # Auto-queue render if no previews detected
            render_job_id = None
            if preview_files == 0:
                render_job_id = await auto_queue_render_for_design(self.db, design.id)

            # Update metadata
            meta["status"] = UploadStatus.COMPLETED.value
            meta["processed_at"] = datetime.now(timezone.utc).isoformat()
            meta["design_id"] = design.id
            await self._save_meta(upload_id, meta)

            logger.info(
                "upload_processed",
                upload_id=upload_id,
                design_id=design.id,
                title=design_title,
                files_extracted=files_extracted,
            )

            return ProcessUploadResponse(
                upload_id=upload_id,
                status=UploadStatus.COMPLETED,
                design_id=design.id,
                design_title=design_title,
                files_extracted=files_extracted,
                model_files=model_files,
                preview_files=preview_files,
            )

        except Exception as e:
            meta["status"] = UploadStatus.FAILED.value
            meta["error_message"] = str(e)
            await self._save_meta(upload_id, meta)

            logger.error(
                "upload_processing_failed",
                upload_id=upload_id,
                error=str(e),
            )

            return ProcessUploadResponse(
                upload_id=upload_id,
                status=UploadStatus.FAILED,
                error_message=str(e),
            )

    # ========== Cleanup ==========

    async def cleanup_expired(self) -> int:
        """Clean up expired uploads.

        Removes uploads older than retention period.

        Returns:
            Number of uploads cleaned up.
        """
        if not self._staging_path.exists():
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.upload_retention_hours)
        cleaned = 0

        for upload_dir in self._staging_path.iterdir():
            if not upload_dir.is_dir():
                continue

            try:
                meta = await self._load_meta(upload_dir.name)
                if not meta:
                    continue

                created_at = datetime.fromisoformat(meta["created_at"])
                if created_at < cutoff and meta["status"] in [
                    UploadStatus.PENDING.value,
                    UploadStatus.FAILED.value,
                ]:
                    await self._cleanup_upload(upload_dir.name)
                    cleaned += 1

            except Exception as e:
                logger.warning(
                    "cleanup_failed",
                    upload_id=upload_dir.name,
                    error=str(e),
                )

        if cleaned > 0:
            logger.info("expired_uploads_cleaned", count=cleaned)

        return cleaned

    # ========== Private Helpers ==========

    async def _save_meta(self, upload_id: str, meta: dict) -> None:
        """Save upload metadata to file."""
        import json

        meta_path = self._staging_path / upload_id / UPLOAD_META_FILE
        async with aiofiles.open(meta_path, "w") as f:
            await f.write(json.dumps(meta, indent=2))

    async def _load_meta(self, upload_id: str) -> dict | None:
        """Load upload metadata from file."""
        import json

        meta_path = self._staging_path / upload_id / UPLOAD_META_FILE
        if not meta_path.exists():
            return None

        try:
            async with aiofiles.open(meta_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except Exception:
            return None

    async def _cleanup_upload(self, upload_id: str) -> None:
        """Remove upload directory and all files."""
        upload_dir = self._staging_path / upload_id
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
