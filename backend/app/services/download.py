"""Download service for fetching files from Telegram.

NOTE: This service uses the "session-per-operation" pattern to avoid
holding database locks during long I/O operations. See DEC-019.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    Attachment,
    AttachmentDownloadStatus,
    Design,
    DesignFile,
    DesignSource,
    DesignStatus,
    FileKind,
    JobType,
    TelegramMessage,
)
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService
from app.telegram.exceptions import TelegramRateLimitError
from app.utils import compute_file_hash
from app.telegram.service import TelegramService

if TYPE_CHECKING:
    from telethon.types import Message

logger = get_logger(__name__)

# File extensions that indicate archives needing extraction
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar.gz", ".tgz"}

# File extensions for 3D model files
MODEL_EXTENSIONS = {".stl", ".3mf", ".obj", ".step", ".stp", ".iges", ".igs", ".blend", ".gcode"}


class DownloadError(Exception):
    """Error during download process."""

    pass


@dataclass
class AttachmentDownloadInfo:
    """Data needed for downloading an attachment (no ORM objects)."""

    id: str
    filename: str
    ext: str | None
    message_id: str
    channel_peer_id: str
    telegram_message_id: int


class DownloadService:
    """Service for downloading design files from Telegram.

    This service uses the "session-per-operation" pattern:
    - Database sessions are only held during brief read/write operations
    - Long I/O operations (file downloads) happen outside any session
    - This prevents SQLite locking issues during large file downloads
    """

    def __init__(self, db: AsyncSession | None = None):
        """Initialize the download service.

        Args:
            db: Optional session for queue_download/queue_extraction methods.
                For download_design, sessions are managed internally.
        """
        self.db = db
        self._telegram: TelegramService | None = None

    @property
    def telegram(self) -> TelegramService:
        if self._telegram is None:
            self._telegram = TelegramService.get_instance()
        return self._telegram

    async def download_design(
        self,
        design_id: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Download all attachments for a design.

        Uses session-per-operation pattern to avoid holding locks during downloads.
        """
        # PHASE 1: Read design and attachments, update status (brief session)
        async with async_session_maker() as db:
            design = await self._get_design_with_attachments(db, design_id)
            if not design:
                raise DownloadError(f"Design not found: {design_id}")

            design.status = DesignStatus.DOWNLOADING
            await db.commit()

            # Gather attachment info (plain data, not ORM objects)
            attachments_info = await self._collect_attachment_info(db, design)

        if not attachments_info:
            raise DownloadError("No attachments found for design")

        staging_dir = self._get_staging_dir(design_id)
        staging_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "staging_dir_created",
            design_id=design_id,
            staging_dir=str(staging_dir),
            exists=staging_dir.exists(),
        )

        # PHASE 2: Download files (NO database session held)
        downloaded_count = 0
        total_bytes = 0
        has_archives = False
        download_paths: list[str] = []
        downloaded_files: list[dict[str, Any]] = []  # Track file info for DesignFile creation
        total_attachments = len(attachments_info)

        for i, att_info in enumerate(attachments_info):
            # Each attachment download manages its own session
            result = await self._download_attachment(
                att_info, staging_dir, progress_callback
            )
            downloaded_count += 1
            total_bytes += result["size"]
            download_paths.append(result["path"])

            # Track file info for DesignFile creation
            downloaded_files.append({
                "attachment_id": att_info.id,
                "path": result["path"],
                "size": result["size"],
                "sha256": result["sha256"],
                "ext": att_info.ext,
                "filename": Path(result["path"]).name,
            })

            if att_info.ext and att_info.ext.lower() in ARCHIVE_EXTENSIONS:
                has_archives = True

            if progress_callback:
                progress_callback(i + 1, total_attachments)

        # PHASE 3: Update design status and create DesignFile records (brief session)
        async with async_session_maker() as db:
            design = await db.get(Design, design_id)
            if design:
                design.status = DesignStatus.DOWNLOADED

            # For non-archive designs, create DesignFile records now
            # (archive designs get DesignFile records during extraction)
            if not has_archives:
                for file_info in downloaded_files:
                    ext = file_info["ext"] or ""
                    ext_lower = ext.lower()

                    # Determine FileKind
                    if ext_lower in MODEL_EXTENSIONS:
                        file_kind = FileKind.MODEL
                    else:
                        file_kind = FileKind.OTHER

                    # Create DesignFile record
                    design_file = DesignFile(
                        design_id=design_id,
                        source_attachment_id=file_info["attachment_id"],
                        relative_path=file_info["filename"],  # Just the filename in staging
                        filename=file_info["filename"],
                        ext=ext,
                        size_bytes=file_info["size"],
                        sha256=file_info["sha256"],
                        file_kind=file_kind,
                        is_from_archive=False,
                    )
                    db.add(design_file)

            await db.commit()

        return {
            "design_id": design_id,
            "files_downloaded": downloaded_count,
            "total_bytes": total_bytes,
            "has_archives": has_archives,
            "download_paths": download_paths,
        }

    async def queue_download(self, design_id: str, priority: int = 0) -> str:
        """Queue a download job for a design."""
        if self.db is None:
            raise DownloadError("Database session required for queue_download")

        design = await self.db.get(Design, design_id)
        if not design:
            raise DownloadError(f"Design not found: {design_id}")

        design.status = DesignStatus.WANTED
        await self.db.flush()

        queue = JobQueueService(self.db)
        job = await queue.enqueue(JobType.DOWNLOAD_DESIGN, design_id=design_id, priority=priority)
        return job.id

    async def queue_extraction(self, design_id: str) -> str | None:
        """Queue an extraction job if design has archives."""
        if self.db is None:
            raise DownloadError("Database session required for queue_extraction")

        attachments = await self._get_downloaded_attachments(self.db, design_id)
        has_archives = any(a.ext and a.ext.lower() in ARCHIVE_EXTENSIONS for a in attachments)

        if not has_archives:
            return None

        queue = JobQueueService(self.db)
        job = await queue.enqueue(JobType.EXTRACT_ARCHIVE, design_id=design_id, priority=5)
        return job.id

    async def _get_design_with_attachments(
        self, db: AsyncSession, design_id: str
    ) -> Design | None:
        result = await db.execute(
            select(Design)
            .options(
                selectinload(Design.sources)
                .selectinload(DesignSource.message)
                .selectinload(TelegramMessage.attachments)
            )
            .where(Design.id == design_id)
        )
        return result.scalar_one_or_none()

    async def _collect_attachment_info(
        self, db: AsyncSession, design: Design
    ) -> list[AttachmentDownloadInfo]:
        """Collect attachment info as plain data (not ORM objects).

        This allows us to close the session and still have all the info
        needed for downloading.
        """
        attachments_info = []

        for source in design.sources:
            if not source.message:
                continue

            # Load channel info for this message
            message = await db.execute(
                select(TelegramMessage)
                .options(selectinload(TelegramMessage.channel))
                .where(TelegramMessage.id == source.message.id)
            )
            msg = message.scalar_one_or_none()
            if not msg or not msg.channel:
                continue

            for attachment in source.message.attachments:
                if attachment.is_candidate_design_file:
                    attachments_info.append(
                        AttachmentDownloadInfo(
                            id=attachment.id,
                            filename=attachment.filename or f"file_{attachment.id}",
                            ext=attachment.ext,
                            message_id=msg.id,
                            channel_peer_id=msg.channel.telegram_peer_id,
                            telegram_message_id=msg.telegram_message_id,
                        )
                    )

        return attachments_info

    async def _get_downloaded_attachments(
        self, db: AsyncSession, design_id: str
    ) -> list[Attachment]:
        result = await db.execute(
            select(Attachment)
            .join(TelegramMessage)
            .join(DesignSource, DesignSource.message_id == TelegramMessage.id)
            .where(
                DesignSource.design_id == design_id,
                Attachment.download_status == AttachmentDownloadStatus.DOWNLOADED,
            )
        )
        return list(result.scalars().all())

    async def _download_attachment(
        self,
        att_info: AttachmentDownloadInfo,
        staging_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Download a single attachment using session-per-operation pattern."""
        # PHASE 1: Update status to DOWNLOADING (brief session)
        async with async_session_maker() as db:
            attachment = await db.get(Attachment, att_info.id)
            if attachment:
                attachment.download_status = AttachmentDownloadStatus.DOWNLOADING
                await db.commit()

        # Determine file path
        file_path = staging_dir / att_info.filename
        if file_path.exists():
            base = file_path.stem
            ext = file_path.suffix
            counter = 1
            while file_path.exists():
                file_path = staging_dir / f"{base}_{counter}{ext}"
                counter += 1

        # PHASE 2: Download from Telegram (NO database session held)
        try:
            tg_message = await self._fetch_telegram_message(
                att_info.channel_peer_id,
                att_info.telegram_message_id,
            )

            if not tg_message or not tg_message.media:
                raise DownloadError("Message has no media to download")

            downloaded_path = await self._download_media(
                tg_message, file_path, progress_callback
            )

            if not downloaded_path:
                raise DownloadError("Download returned no path")

            downloaded_path_obj = Path(downloaded_path)

            # Verify file exists
            if not downloaded_path_obj.exists():
                raise DownloadError(f"Downloaded file not found: {downloaded_path}")

            # If Telethon saved to a different location, move to staging
            if downloaded_path_obj.parent.resolve() != staging_dir.resolve():
                logger.warning(
                    "download_path_mismatch",
                    expected_dir=str(staging_dir),
                    actual_path=str(downloaded_path),
                )
                import shutil
                correct_path = staging_dir / downloaded_path_obj.name
                # Handle collision
                if correct_path.exists():
                    base = correct_path.stem
                    ext = correct_path.suffix
                    counter = 1
                    while correct_path.exists():
                        correct_path = staging_dir / f"{base}_{counter}{ext}"
                        counter += 1
                shutil.move(str(downloaded_path_obj), str(correct_path))
                downloaded_path = str(correct_path)
                downloaded_path_obj = correct_path
                logger.info(
                    "download_moved_to_staging",
                    new_path=str(correct_path),
                )

            sha256 = await self._compute_file_hash(downloaded_path_obj)
            file_size = downloaded_path_obj.stat().st_size

        except TelegramRateLimitError as e:
            # Update status to FAILED
            async with async_session_maker() as db:
                attachment = await db.get(Attachment, att_info.id)
                if attachment:
                    attachment.download_status = AttachmentDownloadStatus.FAILED
                    await db.commit()
            raise DownloadError(f"Rate limited, retry after {e.retry_after}s")

        except Exception as e:
            # PHASE 3a: Record failure (brief session)
            async with async_session_maker() as db:
                attachment = await db.get(Attachment, att_info.id)
                if attachment:
                    attachment.download_status = AttachmentDownloadStatus.FAILED
                    await db.commit()
            raise

        # PHASE 3b: Record success (brief session)
        async with async_session_maker() as db:
            attachment = await db.get(Attachment, att_info.id)
            if attachment:
                attachment.download_status = AttachmentDownloadStatus.DOWNLOADED
                attachment.download_path = str(downloaded_path)
                attachment.sha256 = sha256
                await db.commit()

        return {"path": str(downloaded_path), "size": file_size, "sha256": sha256}

    async def _fetch_telegram_message(
        self, channel_peer_id: str, telegram_message_id: int
    ) -> Message | None:
        """Fetch message from Telegram. No database access here."""
        if not self.telegram.is_connected():
            await self.telegram.connect()

        if not await self.telegram.is_authenticated():
            raise DownloadError("Telegram not authenticated")

        client = self.telegram.client
        entity = await client.get_entity(int(channel_peer_id))
        message = await client.get_messages(entity, ids=telegram_message_id)
        return message

    async def _download_media(
        self,
        message: Message,
        file_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        """Download media from Telegram message. No database access here.

        Uses asyncio.wait_for to enforce a timeout and prevent indefinite hangs
        when Telegram needs to transfer files across datacenters.
        """
        client = self.telegram.client

        def telethon_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback(current, total)

        try:
            result = await asyncio.wait_for(
                client.download_media(
                    message,
                    file=str(file_path),
                    progress_callback=telethon_progress if progress_callback else None,
                ),
                timeout=settings.download_timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            # Clean up partial file if it exists
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass
            raise DownloadError(
                f"Download timed out after {settings.download_timeout_seconds} seconds. "
                "This may happen when Telegram transfers files between datacenters."
            )

    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file. No database access here."""
        return await compute_file_hash(file_path)

    def _get_staging_dir(self, design_id: str) -> Path:
        return settings.staging_path / design_id
