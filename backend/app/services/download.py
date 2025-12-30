"""Download service for fetching files from Telegram."""

from __future__ import annotations

import asyncio
import hashlib
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
    DesignSource,
    DesignStatus,
    JobType,
    TelegramMessage,
)
from app.services.job_queue import JobQueueService
from app.telegram.exceptions import TelegramRateLimitError
from app.telegram.service import TelegramService

if TYPE_CHECKING:
    from telethon.types import Message

logger = get_logger(__name__)

# File extensions that indicate archives needing extraction
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar.gz", ".tgz"}


class DownloadError(Exception):
    """Error during download process."""

    pass


class DownloadService:
    """Service for downloading design files from Telegram."""

    def __init__(self, db: AsyncSession):
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
        """Download all attachments for a design."""
        design = await self._get_design_with_attachments(design_id)
        if not design:
            raise DownloadError(f"Design not found: {design_id}")

        design.status = DesignStatus.DOWNLOADING
        await self.db.flush()

        staging_dir = self._get_staging_dir(design_id)
        staging_dir.mkdir(parents=True, exist_ok=True)

        attachments = await self._get_downloadable_attachments(design)
        total_attachments = len(attachments)

        if total_attachments == 0:
            raise DownloadError("No attachments found for design")

        downloaded_count = 0
        total_bytes = 0
        has_archives = False
        download_paths: list[str] = []

        for i, attachment in enumerate(attachments):
            result = await self._download_attachment(attachment, staging_dir, progress_callback)
            downloaded_count += 1
            total_bytes += result["size"]
            download_paths.append(result["path"])

            if attachment.ext and attachment.ext.lower() in ARCHIVE_EXTENSIONS:
                has_archives = True

            if progress_callback:
                progress_callback(i + 1, total_attachments)

        design.status = DesignStatus.DOWNLOADED
        await self.db.flush()

        return {
            "design_id": design_id,
            "files_downloaded": downloaded_count,
            "total_bytes": total_bytes,
            "has_archives": has_archives,
            "download_paths": download_paths,
        }

    async def queue_download(self, design_id: str, priority: int = 0) -> str:
        """Queue a download job for a design."""
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
        attachments = await self._get_downloaded_attachments(design_id)
        has_archives = any(a.ext and a.ext.lower() in ARCHIVE_EXTENSIONS for a in attachments)

        if not has_archives:
            return None

        queue = JobQueueService(self.db)
        job = await queue.enqueue(JobType.EXTRACT_ARCHIVE, design_id=design_id, priority=5)
        return job.id

    async def _get_design_with_attachments(self, design_id: str) -> Design | None:
        result = await self.db.execute(
            select(Design)
            .options(
                selectinload(Design.sources)
                .selectinload(DesignSource.message)
                .selectinload(TelegramMessage.attachments)
            )
            .where(Design.id == design_id)
        )
        return result.scalar_one_or_none()

    async def _get_downloadable_attachments(self, design: Design) -> list[Attachment]:
        attachments = []
        for source in design.sources:
            if source.message:
                for attachment in source.message.attachments:
                    if attachment.is_candidate_design_file:
                        attachments.append(attachment)
        return attachments

    async def _get_downloaded_attachments(self, design_id: str) -> list[Attachment]:
        result = await self.db.execute(
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
        attachment: Attachment,
        staging_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        attachment.download_status = AttachmentDownloadStatus.DOWNLOADING
        await self.db.flush()

        message = await self._get_telegram_message(attachment.message_id)
        if not message:
            raise DownloadError(f"Message not found for attachment: {attachment.id}")

        filename = attachment.filename or f"file_{attachment.id}"
        file_path = staging_dir / filename

        if file_path.exists():
            base = file_path.stem
            ext = file_path.suffix
            counter = 1
            while file_path.exists():
                file_path = staging_dir / f"{base}_{counter}{ext}"
                counter += 1

        try:
            tg_message = await self._fetch_telegram_message(
                message.channel.telegram_peer_id,
                message.telegram_message_id,
            )

            if not tg_message or not tg_message.media:
                raise DownloadError("Message has no media to download")

            downloaded_path = await self._download_media(tg_message, file_path, progress_callback)

            if not downloaded_path:
                raise DownloadError("Download returned no path")

            sha256 = await self._compute_file_hash(Path(downloaded_path))

            attachment.download_status = AttachmentDownloadStatus.DOWNLOADED
            attachment.download_path = str(downloaded_path)
            attachment.sha256 = sha256
            await self.db.flush()

            file_size = Path(downloaded_path).stat().st_size
            return {"path": str(downloaded_path), "size": file_size, "sha256": sha256}

        except TelegramRateLimitError as e:
            raise DownloadError(f"Rate limited, retry after {e.retry_after}s")
        except Exception:
            attachment.download_status = AttachmentDownloadStatus.FAILED
            await self.db.flush()
            raise

    async def _get_telegram_message(self, message_id: str) -> TelegramMessage | None:
        result = await self.db.execute(
            select(TelegramMessage)
            .options(selectinload(TelegramMessage.channel))
            .where(TelegramMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_telegram_message(self, channel_peer_id: str, telegram_message_id: int) -> Message | None:
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
        client = self.telegram.client

        def telethon_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback(current, total)

        result = await client.download_media(
            message,
            file=str(file_path),
            progress_callback=telethon_progress if progress_callback else None,
        )
        return result

    async def _compute_file_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()

        def _hash_file() -> str:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _hash_file)

    def _get_staging_dir(self, design_id: str) -> Path:
        return settings.staging_path / design_id
