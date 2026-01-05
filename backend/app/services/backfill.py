"""Backfill service for fetching historical messages from Telegram channels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import BackfillMode, Channel
from app.services.ingest import IngestService
from app.services.thangs import ThangsAdapter
from app.telegram.service import TelegramService

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class BackfillService:
    """Service for backfilling historical messages from Telegram channels."""

    def __init__(self, db: AsyncSession):
        """Initialize the backfill service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.telegram = TelegramService.get_instance()
        self.ingest = IngestService(db)

    async def backfill_channel(
        self,
        channel: Channel,
        *,
        mode: BackfillMode | None = None,
        value: int | None = None,
    ) -> dict:
        """Backfill messages from a channel.

        Args:
            channel: The Channel to backfill.
            mode: Override backfill mode (defaults to channel setting).
            value: Override backfill value (defaults to channel setting).

        Returns:
            Dict with backfill results:
            - messages_processed: Total messages processed
            - designs_created: Number of designs detected
            - last_message_id: Last processed message ID
        """
        # Use channel settings if not overridden
        backfill_mode = mode or channel.backfill_mode
        backfill_value = value if value is not None else channel.backfill_value

        logger.info(
            "backfill_starting",
            channel_id=channel.id,
            telegram_peer_id=channel.telegram_peer_id,
            mode=backfill_mode.value,
            value=backfill_value,
        )

        # Get the Telegram peer ID
        try:
            peer_id = int(channel.telegram_peer_id)
        except ValueError:
            # It might be a username
            peer_id = channel.telegram_peer_id

        # Calculate message fetch parameters based on mode
        limit = None
        offset_date = None
        min_id = channel.last_backfill_checkpoint or 0

        if backfill_mode == BackfillMode.LAST_N_MESSAGES:
            limit = backfill_value
        elif backfill_mode == BackfillMode.LAST_N_DAYS:
            offset_date = datetime.now(timezone.utc) - timedelta(days=backfill_value)
        elif backfill_mode == BackfillMode.ALL_HISTORY:
            limit = None  # No limit, fetch all

        # Fetch and process messages
        messages_processed = 0
        designs_created = 0
        last_message_id = min_id
        batch_size = 100  # Process in batches

        try:
            client = self.telegram.client

            # Phase 1: Collect all messages from Telegram (no database operations)
            # This avoids greenlet conflicts between Telethon and aiosqlite
            collected_messages = []
            async for message in client.iter_messages(
                peer_id,
                limit=limit,
                offset_date=offset_date,
                min_id=min_id,
                reverse=True,  # Process oldest first for consistent checkpointing
            ):
                # Parse message using TelegramService's parser
                message_data = await self.telegram._parse_message(message)
                collected_messages.append((message.id, message_data))

            logger.info(
                "backfill_messages_collected",
                channel_id=channel.id,
                count=len(collected_messages),
            )

            # Phase 2: Process collected messages through ingestion (database only)
            for msg_id, message_data in collected_messages:
                message, design_created = await self.ingest.ingest_message(
                    channel, message_data
                )

                if message:
                    messages_processed += 1
                    last_message_id = max(last_message_id, msg_id)

                    if design_created:
                        designs_created += 1

                # Checkpoint periodically
                if messages_processed % batch_size == 0:
                    await self._update_checkpoint(channel.id, msg_id)
                    await self.db.commit()
                    logger.debug(
                        "backfill_checkpoint",
                        channel_id=channel.id,
                        messages_processed=messages_processed,
                        checkpoint=msg_id,
                    )

            # Final checkpoint
            await self._update_checkpoint(channel.id, last_message_id)
            await self._update_last_ingested(channel.id, last_message_id)
            await self.db.commit()

            logger.info(
                "backfill_completed",
                channel_id=channel.id,
                messages_processed=messages_processed,
                designs_created=designs_created,
                last_message_id=last_message_id,
            )

            # Post-backfill: Fetch metadata for any unfetched Thangs sources
            # This runs outside the ingestion transaction to avoid greenlet conflicts
            metadata_stats = await self._fetch_unfetched_metadata()

            return {
                "messages_processed": messages_processed,
                "designs_created": designs_created,
                "last_message_id": last_message_id,
                "metadata_fetched": metadata_stats.get("fetched", 0),
                "metadata_failed": metadata_stats.get("failed", 0),
            }

        except Exception as e:
            logger.error(
                "backfill_error",
                channel_id=channel.id,
                error=str(e),
                messages_processed=messages_processed,
            )
            # Save checkpoint on error so we can resume
            if last_message_id > min_id:
                await self._update_checkpoint(channel.id, last_message_id)
                await self.db.commit()
            raise

    async def _update_checkpoint(self, channel_id: str, message_id: int) -> None:
        """Update the backfill checkpoint for a channel."""
        await self.db.execute(
            update(Channel)
            .where(Channel.id == channel_id)
            .values(last_backfill_checkpoint=message_id)
        )

    async def _update_last_ingested(self, channel_id: str, message_id: int) -> None:
        """Update the last ingested message ID for a channel."""
        await self.db.execute(
            update(Channel)
            .where(Channel.id == channel_id)
            .values(
                last_ingested_message_id=message_id,
                last_sync_at=datetime.now(timezone.utc),
            )
        )

    async def get_backfill_status(self, channel: Channel) -> dict:
        """Get the current backfill status for a channel.

        Args:
            channel: The Channel to check.

        Returns:
            Dict with backfill status info.
        """
        return {
            "channel_id": channel.id,
            "last_backfill_checkpoint": channel.last_backfill_checkpoint,
            "last_ingested_message_id": channel.last_ingested_message_id,
            "last_sync_at": channel.last_sync_at.isoformat() if channel.last_sync_at else None,
            "backfill_mode": channel.backfill_mode.value,
            "backfill_value": channel.backfill_value,
        }

    async def _fetch_unfetched_metadata(self) -> dict:
        """Fetch metadata for any unfetched Thangs sources.

        This runs after backfill completes to enrich designs with
        metadata from Thangs API.

        Returns:
            Dict with 'fetched', 'failed' counts.
        """
        try:
            adapter = ThangsAdapter(self.db)
            result = await adapter.fetch_unfetched_metadata()
            await adapter.close()

            if result["fetched"] > 0 or result["failed"] > 0:
                logger.info(
                    "post_backfill_metadata_fetch",
                    fetched=result["fetched"],
                    failed=result["failed"],
                )

            return result
        except Exception as e:
            logger.warning(
                "post_backfill_metadata_error",
                error=str(e),
            )
            return {"fetched": 0, "failed": 0}
