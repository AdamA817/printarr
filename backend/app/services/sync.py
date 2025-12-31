"""Sync service for live monitoring of Telegram channels.

This service implements hybrid monitoring per DEC-020:
- Real-time: Telethon event handlers for instant new message detection
- Catch-up: Poll on reconnection to fetch messages missed during disconnects
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy import select
from telethon import events
from telethon.errors import FloodWaitError

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Channel, DownloadMode, JobType, TelegramMessage
from app.db.session import async_session_maker
from app.services.ingest import IngestService
from app.services.job_queue import JobQueueService
from app.telegram.service import TelegramService

if TYPE_CHECKING:
    from telethon import TelegramClient

logger = get_logger(__name__)


class SyncService:
    """Service for live monitoring of Telegram channels.

    This service:
    - Subscribes to real-time message updates from enabled channels
    - Handles catch-up sync when reconnecting after disconnection
    - Triggers auto-downloads based on channel settings
    - Tracks sync state (last_ingested_message_id) per channel
    """

    _instance: SyncService | None = None

    def __init__(self) -> None:
        """Initialize the sync service."""
        self._running = False
        self._started_at: datetime | None = None
        self._subscribed_channel_ids: set[int] = set()
        self._messages_processed = 0
        self._designs_created = 0
        self._last_sync_at: datetime | None = None
        self._event_handler: Callable | None = None
        self._shutdown_event = asyncio.Event()

    @classmethod
    def get_instance(cls) -> SyncService:
        """Get the singleton instance of SyncService."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    async def start(self) -> None:
        """Start the sync service.

        This will:
        1. Connect to Telegram if not connected
        2. Register event handlers for new messages
        3. Subscribe to all enabled channels
        4. Start the catch-up sync loop
        """
        if self._running:
            logger.warning("sync_service_already_running")
            return

        if not settings.sync_enabled:
            logger.info("sync_service_disabled")
            return

        self._running = True
        self._started_at = datetime.utcnow()
        self._shutdown_event.clear()

        logger.info(
            "sync_service_starting",
            poll_interval=settings.sync_poll_interval,
        )

        try:
            # Ensure Telegram is connected
            telegram = TelegramService.get_instance()
            if not telegram.is_connected():
                await telegram.connect()

            if not await telegram.is_authenticated():
                logger.warning("sync_service_not_authenticated")
                self._running = False
                return

            # Register event handler
            await self._register_event_handler(telegram.client)

            # Subscribe to all enabled channels
            await self._subscribe_to_channels()

            # Run the main sync loop
            await self._run_sync_loop()

        except Exception as e:
            logger.error("sync_service_error", error=str(e), exc_info=True)
            raise
        finally:
            await self._cleanup()

    async def stop(self) -> None:
        """Stop the sync service gracefully."""
        if not self._running:
            return

        logger.info("sync_service_stopping")
        self._running = False
        self._shutdown_event.set()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self._running = False

        # Remove event handler
        if self._event_handler:
            try:
                telegram = TelegramService.get_instance()
                if telegram.is_connected():
                    telegram.client.remove_event_handler(self._event_handler)
            except Exception as e:
                logger.warning("sync_cleanup_error", error=str(e))

        self._event_handler = None
        self._subscribed_channel_ids.clear()

        logger.info(
            "sync_service_stopped",
            messages_processed=self._messages_processed,
            designs_created=self._designs_created,
            uptime_seconds=self._uptime_seconds(),
        )

    async def _register_event_handler(self, client: TelegramClient) -> None:
        """Register Telethon event handler for new messages."""

        @client.on(events.NewMessage)
        async def handle_new_message(event: events.NewMessage.Event) -> None:
            """Handle new message events from subscribed channels."""
            try:
                await self._process_new_message(event)
            except Exception as e:
                logger.error(
                    "sync_message_handler_error",
                    error=str(e),
                    exc_info=True,
                )

        self._event_handler = handle_new_message
        logger.info("sync_event_handler_registered")

    async def _process_new_message(self, event: events.NewMessage.Event) -> None:
        """Process a new message event."""
        message = event.message

        # Get channel ID from the event
        chat_id = event.chat_id
        if chat_id is None:
            return

        # Check if this is a subscribed channel
        if abs(chat_id) not in self._subscribed_channel_ids:
            return

        logger.debug(
            "sync_new_message_received",
            chat_id=chat_id,
            message_id=message.id,
        )

        # Parse message using TelegramService patterns
        telegram = TelegramService.get_instance()
        message_data = await telegram._parse_message(message)

        # Get channel from database and ingest
        async with async_session_maker() as db:
            # Find channel by telegram_peer_id
            result = await db.execute(
                select(Channel).where(
                    Channel.telegram_peer_id == str(abs(chat_id)),
                    Channel.is_enabled == True,  # noqa: E712
                )
            )
            channel = result.scalar_one_or_none()

            if not channel:
                logger.debug(
                    "sync_channel_not_found",
                    chat_id=chat_id,
                )
                return

            # Ingest the message
            ingest = IngestService(db)
            telegram_message, design_created = await ingest.ingest_message(
                channel=channel,
                message_data=message_data,
            )

            if telegram_message:
                self._messages_processed += 1

                # Update last_ingested_message_id
                channel.last_ingested_message_id = message.id
                channel.last_sync_at = datetime.utcnow()

            if design_created:
                self._designs_created += 1

                # Check if auto-download is enabled
                if channel.download_mode in (
                    DownloadMode.DOWNLOAD_ALL,
                    DownloadMode.DOWNLOAD_ALL_NEW,
                ):
                    # Queue download job
                    await self._queue_download(db, telegram_message)
                    logger.info(
                        "sync_auto_download_queued",
                        channel_id=channel.id,
                        message_id=telegram_message.id if telegram_message else None,
                    )

            await db.commit()

            logger.info(
                "sync_message_processed",
                channel_id=channel.id,
                telegram_message_id=message.id,
                design_created=design_created,
            )

    async def _queue_download(self, db, telegram_message: TelegramMessage) -> None:
        """Queue a download job for a design from this message."""
        from sqlalchemy import select as sql_select

        from app.db.models import DesignSource

        # Find the design for this message
        result = await db.execute(
            sql_select(DesignSource.design_id).where(
                DesignSource.message_id == telegram_message.id
            )
        )
        design_id = result.scalar_one_or_none()

        if design_id:
            queue = JobQueueService(db)
            await queue.enqueue(
                job_type=JobType.DOWNLOAD_DESIGN,
                payload={"design_id": design_id},
                priority=5,  # Default priority for auto-downloads
            )

    async def _subscribe_to_channels(self) -> None:
        """Subscribe to all enabled channels."""
        async with async_session_maker() as db:
            result = await db.execute(
                select(Channel).where(Channel.is_enabled == True)  # noqa: E712
            )
            channels = result.scalars().all()

            for channel in channels:
                try:
                    channel_id = int(channel.telegram_peer_id)
                    self._subscribed_channel_ids.add(abs(channel_id))
                except (ValueError, TypeError):
                    logger.warning(
                        "sync_invalid_channel_id",
                        channel_id=channel.id,
                        telegram_peer_id=channel.telegram_peer_id,
                    )

            logger.info(
                "sync_channels_subscribed",
                count=len(self._subscribed_channel_ids),
            )

    async def add_channel(self, telegram_peer_id: str) -> None:
        """Add a channel to the subscription list.

        Called when a new channel is added or enabled.
        """
        try:
            channel_id = abs(int(telegram_peer_id))
            self._subscribed_channel_ids.add(channel_id)
            logger.info("sync_channel_added", telegram_peer_id=telegram_peer_id)
        except (ValueError, TypeError):
            logger.warning(
                "sync_add_channel_invalid_id",
                telegram_peer_id=telegram_peer_id,
            )

    async def remove_channel(self, telegram_peer_id: str) -> None:
        """Remove a channel from the subscription list.

        Called when a channel is disabled or deleted.
        """
        try:
            channel_id = abs(int(telegram_peer_id))
            self._subscribed_channel_ids.discard(channel_id)
            logger.info("sync_channel_removed", telegram_peer_id=telegram_peer_id)
        except (ValueError, TypeError):
            pass

    async def _run_sync_loop(self) -> None:
        """Main sync loop for catch-up polling."""
        while self._running and not self._shutdown_event.is_set():
            try:
                # Perform catch-up sync
                await self._catch_up_sync()
                self._last_sync_at = datetime.utcnow()

                # Wait for poll interval or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=settings.sync_poll_interval,
                    )
                except TimeoutError:
                    pass

            except FloodWaitError as e:
                logger.warning(
                    "sync_rate_limited",
                    wait_seconds=e.seconds,
                )
                # Wait the required time plus a buffer
                await asyncio.sleep(e.seconds + 5)

            except Exception as e:
                logger.error(
                    "sync_loop_error",
                    error=str(e),
                    exc_info=True,
                )
                # Wait before retrying after error
                await asyncio.sleep(30)

    async def _catch_up_sync(self) -> None:
        """Perform catch-up sync for all channels.

        This fetches messages since last_ingested_message_id for each channel
        to catch any messages missed during disconnection.
        """
        async with async_session_maker() as db:
            result = await db.execute(
                select(Channel).where(Channel.is_enabled == True)  # noqa: E712
            )
            channels = result.scalars().all()

        # Process each channel (release db session during Telegram calls)
        for channel in channels:
            if not self._running:
                break

            try:
                await self._catch_up_channel(channel)
            except FloodWaitError:
                raise  # Re-raise to be handled by caller
            except Exception as e:
                logger.warning(
                    "sync_catch_up_channel_error",
                    channel_id=channel.id,
                    error=str(e),
                )

    async def _catch_up_channel(self, channel: Channel) -> None:
        """Catch up a single channel by fetching messages since last sync."""
        telegram = TelegramService.get_instance()

        if not telegram.is_connected() or not await telegram.is_authenticated():
            return

        last_id = channel.last_ingested_message_id or 0

        # Fetch messages since last_id
        try:
            entity = await telegram.client.get_entity(int(channel.telegram_peer_id))
        except Exception as e:
            logger.warning(
                "sync_get_entity_error",
                channel_id=channel.id,
                error=str(e),
            )
            return

        messages_fetched = 0
        designs_created = 0

        # Fetch messages newer than last_id (min_id parameter)
        async for message in telegram.client.iter_messages(
            entity,
            min_id=last_id,
            limit=100,  # Batch size for catch-up
        ):
            if not self._running:
                break

            message_data = await telegram._parse_message(message)

            # Ingest in a fresh session (session-per-operation)
            async with async_session_maker() as db:
                # Re-fetch channel in this session
                result = await db.execute(
                    select(Channel).where(Channel.id == channel.id)
                )
                db_channel = result.scalar_one_or_none()
                if not db_channel:
                    break

                ingest = IngestService(db)
                telegram_msg, design_created = await ingest.ingest_message(
                    channel=db_channel,
                    message_data=message_data,
                )

                if telegram_msg:
                    messages_fetched += 1
                    self._messages_processed += 1

                    # Update last_ingested_message_id
                    if message.id > (db_channel.last_ingested_message_id or 0):
                        db_channel.last_ingested_message_id = message.id
                        db_channel.last_sync_at = datetime.utcnow()

                if design_created:
                    designs_created += 1
                    self._designs_created += 1

                    # Check if auto-download is enabled
                    if db_channel.download_mode in (
                        DownloadMode.DOWNLOAD_ALL,
                        DownloadMode.DOWNLOAD_ALL_NEW,
                    ):
                        await self._queue_download(db, telegram_msg)

                await db.commit()

        if messages_fetched > 0:
            logger.info(
                "sync_catch_up_complete",
                channel_id=channel.id,
                channel_title=channel.title,
                messages_fetched=messages_fetched,
                designs_created=designs_created,
            )

    def _uptime_seconds(self) -> int:
        """Calculate service uptime in seconds."""
        if self._started_at:
            return int((datetime.utcnow() - self._started_at).total_seconds())
        return 0

    @property
    def is_running(self) -> bool:
        """Check if the sync service is running."""
        return self._running

    @property
    def stats(self) -> dict[str, Any]:
        """Get sync service statistics."""
        return {
            "is_running": self._running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "subscribed_channels": len(self._subscribed_channel_ids),
            "messages_processed": self._messages_processed,
            "designs_created": self._designs_created,
            "last_sync_at": self._last_sync_at.isoformat() if self._last_sync_at else None,
            "uptime_seconds": self._uptime_seconds(),
            "poll_interval": settings.sync_poll_interval,
        }


# Convenience function for dependency injection
def get_sync_service() -> SyncService:
    """Get the SyncService singleton instance."""
    return SyncService.get_instance()
