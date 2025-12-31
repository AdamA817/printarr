"""Image worker for downloading Telegram preview images.

Per DEC-030, Telegram images are downloaded via background jobs to keep
ingestion fast. When a design is created from a message with photos,
we queue a DOWNLOAD_TELEGRAM_IMAGES job to download them separately.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any

from app.core.logging import get_logger
from app.db.models import Attachment, Design, Job, JobType, MediaType, PreviewAsset
from app.db.models.enums import PreviewKind, PreviewSource
from app.db.session import async_session_maker
from app.services.preview import PreviewService
from app.telegram import TelegramService
from app.workers.base import BaseWorker, NonRetryableError, RetryableError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)

# Maximum images to download per message (Telegram limit)
MAX_IMAGES_PER_MESSAGE = 10


class ImageWorker(BaseWorker):
    """Worker for downloading preview images from Telegram.

    Processes DOWNLOAD_TELEGRAM_IMAGES jobs by:
    1. Fetching the Telegram message
    2. Downloading photo attachments
    3. Saving to /cache/previews/telegram/{design_id}/
    4. Creating PreviewAsset records
    5. Auto-selecting primary preview

    Uses session-per-operation pattern to avoid holding database
    locks during Telegram downloads.
    """

    job_types = [JobType.DOWNLOAD_TELEGRAM_IMAGES]

    def __init__(
        self,
        *,
        poll_interval: float = 2.0,
        worker_id: str | None = None,
    ):
        """Initialize the image worker.

        Args:
            poll_interval: Seconds between polling for jobs.
            worker_id: Optional identifier for this worker instance.
        """
        super().__init__(poll_interval=poll_interval, worker_id=worker_id)
        self.telegram = TelegramService.get_instance()
        self.preview_service = PreviewService()

    async def process(
        self, job: Job, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Process an image download job.

        Downloads all photos from the Telegram message and creates
        PreviewAsset records.

        Args:
            job: The Job instance to process.
            payload: Parsed payload dict with design_id, message_id, channel_peer_id.

        Returns:
            Result dict with images_downloaded count.

        Raises:
            NonRetryableError: If design/message not found.
            RetryableError: For transient errors like rate limits.
        """
        if not payload:
            raise NonRetryableError("Job missing payload")

        design_id = payload.get("design_id") or job.design_id
        message_id = payload.get("message_id")
        channel_peer_id = payload.get("channel_peer_id")

        if not all([design_id, message_id, channel_peer_id]):
            raise NonRetryableError(
                f"Missing required payload fields: design_id={design_id}, "
                f"message_id={message_id}, channel_peer_id={channel_peer_id}"
            )

        logger.info(
            "image_download_starting",
            job_id=job.id,
            design_id=design_id,
            message_id=message_id,
        )

        # Verify design exists and get photo attachments
        async with async_session_maker() as db:
            design = await db.get(Design, design_id)
            if not design:
                raise NonRetryableError(f"Design not found: {design_id}")

            # Get photo attachments for this design's message
            result = await db.execute(
                select(Attachment)
                .join(Attachment.message)
                .where(
                    Attachment.message.has(telegram_message_id=message_id),
                    Attachment.media_type == MediaType.PHOTO,
                )
            )
            photo_attachments = list(result.scalars().all())

            # Check which photos we already have (by telegram_file_id)
            existing_result = await db.execute(
                select(PreviewAsset.telegram_file_id)
                .where(
                    PreviewAsset.design_id == design_id,
                    PreviewAsset.telegram_file_id.isnot(None),
                )
            )
            existing_file_ids = {r for r in existing_result.scalars().all()}

        # Filter out already downloaded photos
        attachments_to_download = [
            att for att in photo_attachments
            if att.telegram_file_id not in existing_file_ids
        ]

        if not attachments_to_download:
            logger.info(
                "image_download_skipped_all_exist",
                design_id=design_id,
                existing_count=len(existing_file_ids),
            )
            return {"images_downloaded": 0, "images_skipped": len(photo_attachments)}

        # Ensure Telegram is connected and authenticated
        try:
            await self._ensure_telegram()
        except Exception as e:
            raise RetryableError(f"Telegram not available: {e}")

        # Download images (NO database session held during downloads)
        downloaded = []
        try:
            for i, attachment in enumerate(attachments_to_download[:MAX_IMAGES_PER_MESSAGE]):
                try:
                    image_data = await self._download_photo(
                        channel_peer_id=channel_peer_id,
                        message_id=message_id,
                        attachment=attachment,
                    )

                    if image_data:
                        downloaded.append({
                            "attachment_id": attachment.id,
                            "telegram_file_id": attachment.telegram_file_id,
                            "filename": attachment.filename,
                            "data": image_data,
                        })

                    # Update progress
                    await self.update_progress(i + 1, len(attachments_to_download))

                except Exception as e:
                    logger.warning(
                        "image_download_failed",
                        design_id=design_id,
                        attachment_id=attachment.id,
                        error=str(e),
                    )
                    continue

        except Exception as e:
            error_msg = str(e)
            if "FloodWait" in error_msg or "rate limit" in error_msg.lower():
                raise RetryableError(f"Rate limited: {error_msg}")
            raise

        # Save previews and create records (brief session)
        images_saved = 0
        async with async_session_maker() as db:
            preview_service = PreviewService(db)

            for item in downloaded:
                try:
                    preview = await preview_service.save_preview(
                        design_id=design_id,
                        source=PreviewSource.TELEGRAM,
                        image_data=item["data"],
                        filename=item["filename"],
                        kind=PreviewKind.THUMBNAIL,
                        telegram_file_id=item["telegram_file_id"],
                        source_attachment_id=item["attachment_id"],
                    )
                    images_saved += 1

                except Exception as e:
                    logger.warning(
                        "preview_save_failed",
                        design_id=design_id,
                        error=str(e),
                    )
                    continue

            # Auto-select primary preview
            if images_saved > 0:
                await preview_service.auto_select_primary(design_id)

            await db.commit()

        logger.info(
            "image_download_complete",
            job_id=job.id,
            design_id=design_id,
            images_downloaded=images_saved,
        )

        return {
            "images_downloaded": images_saved,
            "images_attempted": len(attachments_to_download),
        }

    async def _ensure_telegram(self) -> None:
        """Ensure Telegram is connected and authenticated."""
        if not self.telegram.is_connected():
            await self.telegram.connect()

        if not await self.telegram.is_authenticated():
            raise Exception("Telegram not authenticated")

    async def _download_photo(
        self,
        channel_peer_id: str,
        message_id: int,
        attachment: Attachment,
    ) -> bytes | None:
        """Download a photo from Telegram.

        Args:
            channel_peer_id: The channel's peer ID
            message_id: The Telegram message ID
            attachment: The Attachment record with file info

        Returns:
            Image bytes if successful, None otherwise
        """
        client = self.telegram.client

        # Get the message
        entity = await client.get_entity(int(channel_peer_id))
        message = await client.get_messages(entity, ids=message_id)

        if not message:
            logger.warning(
                "message_not_found",
                channel_peer_id=channel_peer_id,
                message_id=message_id,
            )
            return None

        # Download to bytes buffer
        buffer = BytesIO()

        # For photo messages, download the photo
        if message.photo:
            await client.download_media(message.photo, file=buffer)
        elif message.media and hasattr(message.media, "photo"):
            await client.download_media(message.media.photo, file=buffer)
        else:
            logger.warning(
                "no_photo_in_message",
                message_id=message_id,
            )
            return None

        buffer.seek(0)
        return buffer.read()
