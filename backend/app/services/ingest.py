"""Ingestion service for processing Telegram messages into Design catalog."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    Attachment,
    Design,
    DesignSource,
    DesignStatus,
    MediaType,
    MetadataAuthority,
    MulticolorStatus,
    TelegramMessage,
)
from app.services.thangs import ThangsAdapter

if TYPE_CHECKING:
    from app.db.models import Channel

logger = get_logger(__name__)

# File extensions that indicate a design file
DESIGN_EXTENSIONS = {
    # 3D model files
    ".stl",
    ".3mf",
    ".obj",
    ".step",
    ".stp",
    # Archives that likely contain models
    ".zip",
    ".rar",
    ".7z",
    ".tar.gz",
    ".tgz",
}


class IngestService:
    """Service for ingesting Telegram messages and creating Design records."""

    def __init__(self, db: AsyncSession):
        """Initialize the ingestion service.

        Args:
            db: Async database session.
        """
        self.db = db

    async def ingest_message(
        self,
        channel: Channel,
        message_data: dict[str, Any],
    ) -> tuple[TelegramMessage | None, bool]:
        """Ingest a single Telegram message.

        This method:
        1. Creates or updates TelegramMessage record
        2. Creates Attachment records for any media
        3. Detects if this is a design post
        4. If so, creates Design and DesignSource records

        Args:
            channel: The Channel model this message belongs to.
            message_data: Parsed message data from TelegramService.

        Returns:
            Tuple of (TelegramMessage or None if skipped, design_created flag).
        """
        telegram_message_id = message_data.get("id")
        if telegram_message_id is None:
            logger.warning("message_missing_id", message=message_data)
            return None, False

        # Check if message already exists (idempotent)
        existing = await self._get_existing_message(channel.id, telegram_message_id)
        if existing:
            logger.debug(
                "message_already_exists",
                channel_id=channel.id,
                telegram_message_id=telegram_message_id,
            )
            # TODO: Consider updating if needed
            return existing, False

        # Parse message date
        date_posted = self._parse_date(message_data.get("date"))
        if date_posted is None:
            date_posted = datetime.utcnow()

        # Extract caption text
        caption_text = message_data.get("text", "") or ""

        # Create TelegramMessage
        message = TelegramMessage(
            channel_id=channel.id,
            telegram_message_id=telegram_message_id,
            date_posted=date_posted,
            author_name=self._extract_author_name(message_data),
            caption_text=caption_text,
            caption_text_normalized=self._normalize_text(caption_text),
            has_media=message_data.get("has_media", False),
        )
        self.db.add(message)
        await self.db.flush()

        # Process attachments
        attachments = await self._process_attachments(message, message_data)

        # Check if this is a design post
        has_design_files = any(a.is_candidate_design_file for a in attachments)

        if has_design_files:
            await self._create_design(channel, message, caption_text)
            logger.info(
                "design_detected",
                channel_id=channel.id,
                message_id=message.id,
                telegram_message_id=telegram_message_id,
            )
            return message, True
        else:
            logger.debug(
                "message_ingested_no_design",
                channel_id=channel.id,
                telegram_message_id=telegram_message_id,
            )
            return message, False

    async def _get_existing_message(
        self, channel_id: str, telegram_message_id: int
    ) -> TelegramMessage | None:
        """Check if a message already exists in the database."""
        result = await self.db.execute(
            select(TelegramMessage).where(
                TelegramMessage.channel_id == channel_id,
                TelegramMessage.telegram_message_id == telegram_message_id,
            )
        )
        return result.scalar_one_or_none()

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse an ISO date string to datetime."""
        if not date_str:
            return None
        try:
            # Handle ISO format with or without timezone
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _extract_author_name(self, message_data: dict) -> str | None:
        """Extract author name from message data."""
        sender = message_data.get("sender")
        if sender:
            return sender.get("name")
        return None

    def _normalize_text(self, text: str) -> str:
        """Normalize text for search (lowercase, remove special chars)."""
        if not text:
            return ""
        # Normalize unicode
        text = unicodedata.normalize("NFKC", text)
        # Lowercase
        text = text.lower()
        # Remove URLs
        text = re.sub(r"https?://\S+", " ", text)
        # Keep only alphanumeric and whitespace
        text = re.sub(r"[^\w\s]", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _process_attachments(
        self,
        message: TelegramMessage,
        message_data: dict,
    ) -> list[Attachment]:
        """Process and store attachments from message data."""
        attachments = []
        raw_attachments = message_data.get("attachments", [])

        for raw_att in raw_attachments:
            attachment = self._create_attachment(message.id, raw_att)
            self.db.add(attachment)
            attachments.append(attachment)

        await self.db.flush()
        return attachments

    def _create_attachment(self, message_id: str, raw: dict) -> Attachment:
        """Create an Attachment model from raw attachment data."""
        # Determine media type
        att_type = raw.get("type", "other").upper()
        media_type = MediaType.DOCUMENT
        if att_type == "PHOTO":
            media_type = MediaType.PHOTO
        elif att_type == "VIDEO":
            media_type = MediaType.VIDEO
        elif att_type in ("DOCUMENT", "FILE"):
            media_type = MediaType.DOCUMENT
        else:
            media_type = MediaType.OTHER

        # Extract filename and extension
        filename = raw.get("filename")
        ext = None
        if filename:
            ext = self._extract_extension(filename)

        # Determine if this is a candidate design file
        is_candidate = self._is_candidate_design_file(ext, filename)

        return Attachment(
            message_id=message_id,
            media_type=media_type,
            filename=filename,
            mime_type=raw.get("mime_type"),
            size_bytes=raw.get("size"),
            ext=ext,
            is_candidate_design_file=is_candidate,
        )

    def _extract_extension(self, filename: str) -> str | None:
        """Extract file extension from filename (lowercase, with dot)."""
        if not filename:
            return None

        # Handle double extensions like .tar.gz
        lower_filename = filename.lower()
        if lower_filename.endswith(".tar.gz"):
            return ".tar.gz"
        if lower_filename.endswith(".tgz"):
            return ".tgz"

        # Regular extension
        dot_idx = filename.rfind(".")
        if dot_idx > 0:
            return filename[dot_idx:].lower()
        return None

    def _is_candidate_design_file(
        self, ext: str | None, filename: str | None
    ) -> bool:
        """Determine if a file is a candidate design file based on extension."""
        if not ext:
            return False
        return ext.lower() in DESIGN_EXTENSIONS

    async def _create_design(
        self,
        channel: Channel,
        message: TelegramMessage,
        caption_text: str,
    ) -> Design:
        """Create a Design record from a design post message."""
        # Extract title from caption or filename
        title = await self._extract_title(caption_text, message)

        # Get file types from attachments
        file_types = await self._get_file_types(message.id)

        # Create Design
        design = Design(
            canonical_title=title,
            canonical_designer="Unknown",  # Will be enriched later
            status=DesignStatus.DISCOVERED,
            multicolor=MulticolorStatus.UNKNOWN,
            primary_file_types=",".join(file_types) if file_types else None,
            metadata_authority=MetadataAuthority.TELEGRAM,
        )
        self.db.add(design)
        await self.db.flush()

        # Create DesignSource
        source = DesignSource(
            design_id=design.id,
            channel_id=channel.id,
            message_id=message.id,
            source_rank=1,
            is_preferred=True,
            caption_snapshot=caption_text[:2000] if caption_text else None,
        )
        self.db.add(source)
        await self.db.flush()

        logger.info(
            "design_created",
            design_id=design.id,
            title=title,
            file_types=file_types,
        )

        # Process external URLs (Thangs, Printables, Thingiverse)
        # This is non-blocking - errors are logged but don't fail ingestion
        await self._process_external_urls(design, caption_text)

        return design

    async def _process_external_urls(self, design: Design, caption: str) -> None:
        """Process caption for external platform URLs and create links.

        This is async but non-blocking - errors are logged but don't fail ingestion.

        NOTE: Metadata fetching is disabled during ingestion to avoid greenlet
        conflicts with aiosqlite. Metadata can be fetched in a separate pass.
        """
        if not caption:
            return

        try:
            adapter = ThangsAdapter(self.db)
            # Don't fetch metadata during ingestion - causes greenlet conflicts
            # with aiosqlite. Metadata can be refreshed separately.
            sources = await adapter.process_design_urls(
                design, caption, fetch_metadata=False
            )

            if sources:
                logger.info(
                    "external_urls_processed",
                    design_id=design.id,
                    count=len(sources),
                )

            await adapter.close()
        except Exception as e:
            # Log but don't fail - external URL processing is best-effort
            logger.warning(
                "external_url_processing_failed",
                design_id=design.id,
                error=str(e),
            )

    async def _extract_title(self, caption: str, message: TelegramMessage) -> str:
        """Extract a title from caption or fallback to filename."""
        if caption:
            # Use first non-empty line as title
            lines = caption.strip().split("\n")
            for line in lines:
                line = line.strip()
                # Skip URLs, hashtag-only lines, and very short lines
                if line and not line.startswith("http") and not line.startswith("#") and len(line) > 3:
                    # Skip if line is only hashtags
                    if all(word.startswith("#") for word in line.split()):
                        continue
                    # Truncate if too long
                    if len(line) > 200:
                        line = line[:197] + "..."
                    return line

        # Fallback: get first candidate attachment filename without extension
        filename = await self._get_first_attachment_filename(message.id)
        if filename:
            # Strip extension and return
            title = self._strip_extension(filename)
            if title and len(title) > 3:
                return title

        # Last fallback: generic date-based title
        return f"Design from {message.date_posted.strftime('%Y-%m-%d')}"

    async def _get_first_attachment_filename(self, message_id: str) -> str | None:
        """Get the filename of the first candidate design attachment."""
        result = await self.db.execute(
            select(Attachment.filename)
            .where(
                Attachment.message_id == message_id,
                Attachment.is_candidate_design_file == True,  # noqa: E712
                Attachment.filename.isnot(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _strip_extension(self, filename: str) -> str:
        """Strip file extension from filename for use as title."""
        if not filename:
            return ""
        # Handle double extensions like .tar.gz
        lower = filename.lower()
        if lower.endswith(".tar.gz"):
            return filename[:-7]
        if lower.endswith(".tgz"):
            return filename[:-4]
        # Regular extension
        dot_idx = filename.rfind(".")
        if dot_idx > 0:
            return filename[:dot_idx]
        return filename

    async def _get_file_types(self, message_id: str) -> list[str]:
        """Get distinct file extensions for a message's attachments."""
        result = await self.db.execute(
            select(Attachment.ext)
            .where(
                Attachment.message_id == message_id,
                Attachment.is_candidate_design_file == True,  # noqa: E712
                Attachment.ext.isnot(None),
            )
            .distinct()
        )
        extensions = result.scalars().all()
        # Convert to uppercase without dots for display
        return [ext.lstrip(".").upper() for ext in extensions if ext]
