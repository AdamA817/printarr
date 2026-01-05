"""Discovery service for detecting channels referenced in monitored content.

This service implements channel discovery per DEC-021:
- Detect channels from forwarded messages
- Parse t.me/ links in captions
- Parse @mentions in captions
- Parse t.me/ links in message text
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Channel, DiscoveredChannel, DiscoverySourceType

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Regex patterns for channel detection
# Matches: t.me/username, t.me/+invitehash, t.me/joinchat/hash
TME_LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/(\+[\w-]+|joinchat/[\w-]+|[\w_]{5,32})",
    re.IGNORECASE,
)

# Matches: @username (5-32 chars, starts with letter)
MENTION_PATTERN = re.compile(
    r"@([a-zA-Z][a-zA-Z0-9_]{4,31})",
)

# Common bot suffixes to skip
BOT_SUFFIXES = ("bot", "Bot", "BOT", "_bot", "_Bot")


@dataclass
class DiscoveredChannelInfo:
    """Information about a discovered channel reference."""

    username: str | None = None
    invite_hash: str | None = None
    telegram_peer_id: str | None = None
    title: str | None = None
    is_private: bool = False
    source_type: DiscoverySourceType = DiscoverySourceType.MENTION


class DiscoveryService:
    """Service for discovering channels from monitored content.

    This service detects channel references from:
    - Forwarded messages
    - t.me/ links in captions and text
    - @mentions in captions and text
    """

    def __init__(self, db: AsyncSession):
        """Initialize the discovery service.

        Args:
            db: Async database session.
        """
        self.db = db
        # Cache of monitored channel usernames for quick lookup
        self._monitored_usernames: set[str] | None = None
        self._monitored_peer_ids: set[str] | None = None

    async def _load_monitored_channels(self) -> None:
        """Load the set of monitored channel identifiers."""
        if self._monitored_usernames is not None:
            return

        result = await self.db.execute(
            select(Channel.username, Channel.telegram_peer_id)
        )
        rows = result.all()

        self._monitored_usernames = set()
        self._monitored_peer_ids = set()

        for username, peer_id in rows:
            if username:
                self._monitored_usernames.add(username.lower())
            if peer_id:
                self._monitored_peer_ids.add(str(peer_id))

    def _is_monitored(
        self,
        username: str | None = None,
        peer_id: str | None = None,
    ) -> bool:
        """Check if a channel is already monitored."""
        if self._monitored_usernames is None:
            return False

        if username and username.lower() in self._monitored_usernames:
            return True
        if peer_id and str(peer_id) in self._monitored_peer_ids:
            return True

        return False

    def detect_from_forward(
        self, message_data: dict[str, Any]
    ) -> DiscoveredChannelInfo | None:
        """Detect channel from forward metadata.

        Args:
            message_data: Parsed message data from TelegramService.

        Returns:
            DiscoveredChannelInfo if a channel was found, None otherwise.
        """
        # Check for forward_from in message data
        forward_from = message_data.get("forward_from")

        # Also check raw forward info if available
        raw_forward = message_data.get("_raw_forward")

        if not forward_from and not raw_forward:
            return None

        # Try to extract channel info
        if isinstance(forward_from, str) and forward_from:
            # Simple string title - might be from a channel
            # Without full Telegram data, we can't determine if it's a channel
            logger.debug(
                "forward_from_string_only",
                forward_from=forward_from,
            )
            return None

        # If we have raw forward data with channel info
        if raw_forward and isinstance(raw_forward, dict):
            channel_id = raw_forward.get("channel_id")
            channel_title = raw_forward.get("channel_title")
            channel_username = raw_forward.get("channel_username")

            if channel_id:
                return DiscoveredChannelInfo(
                    telegram_peer_id=str(channel_id),
                    username=channel_username,
                    title=channel_title,
                    is_private=channel_username is None,
                    source_type=DiscoverySourceType.FORWARD,
                )

        return None

    def detect_from_caption_links(self, caption: str | None) -> list[DiscoveredChannelInfo]:
        """Detect t.me/ links in caption text.

        Args:
            caption: Message caption text.

        Returns:
            List of discovered channel info.
        """
        if not caption:
            return []

        return self._extract_tme_links(caption, DiscoverySourceType.CAPTION_LINK)

    def detect_from_text_links(self, text: str | None) -> list[DiscoveredChannelInfo]:
        """Detect t.me/ links in message text.

        Args:
            text: Message body text.

        Returns:
            List of discovered channel info.
        """
        if not text:
            return []

        return self._extract_tme_links(text, DiscoverySourceType.TEXT_LINK)

    def _extract_tme_links(
        self, text: str, source_type: DiscoverySourceType
    ) -> list[DiscoveredChannelInfo]:
        """Extract t.me links from text.

        Args:
            text: Text to parse.
            source_type: Type of source (caption or text link).

        Returns:
            List of discovered channel info.
        """
        results = []
        seen = set()

        for match in TME_LINK_PATTERN.finditer(text):
            identifier = match.group(1)

            if identifier in seen:
                continue
            seen.add(identifier)

            # Skip bot usernames
            if any(identifier.endswith(suffix) for suffix in BOT_SUFFIXES):
                continue

            if identifier.startswith("+"):
                # Private invite link: t.me/+hash
                results.append(
                    DiscoveredChannelInfo(
                        invite_hash=identifier[1:],
                        is_private=True,
                        source_type=source_type,
                    )
                )
            elif identifier.startswith("joinchat/"):
                # Old-style invite link: t.me/joinchat/hash
                results.append(
                    DiscoveredChannelInfo(
                        invite_hash=identifier[9:],  # Remove "joinchat/"
                        is_private=True,
                        source_type=source_type,
                    )
                )
            else:
                # Public channel username
                results.append(
                    DiscoveredChannelInfo(
                        username=identifier,
                        is_private=False,
                        source_type=source_type,
                    )
                )

        return results

    def detect_from_mentions(self, text: str | None) -> list[DiscoveredChannelInfo]:
        """Detect @mentions in text.

        Args:
            text: Text to parse for mentions.

        Returns:
            List of discovered channel info.
        """
        if not text:
            return []

        results = []
        seen = set()

        for match in MENTION_PATTERN.finditer(text):
            username = match.group(1)

            if username.lower() in seen:
                continue
            seen.add(username.lower())

            # Skip bot usernames
            if any(username.endswith(suffix) for suffix in BOT_SUFFIXES):
                continue

            results.append(
                DiscoveredChannelInfo(
                    username=username,
                    is_private=False,
                    source_type=DiscoverySourceType.MENTION,
                )
            )

        return results

    async def process_message(self, message_data: dict[str, Any]) -> list[DiscoveredChannel]:
        """Process a message for channel discovery.

        This is the main entry point for discovery. It:
        1. Detects channels from all sources
        2. Filters out already-monitored channels
        3. Creates or updates DiscoveredChannel records

        Args:
            message_data: Parsed message data from TelegramService.

        Returns:
            List of DiscoveredChannel records that were created or updated.
        """
        await self._load_monitored_channels()

        discovered: list[DiscoveredChannelInfo] = []

        # Detect from forward
        forward_info = self.detect_from_forward(message_data)
        if forward_info:
            discovered.append(forward_info)

        # Get caption and text
        caption = message_data.get("text", "") or ""

        # Detect from caption links
        discovered.extend(self.detect_from_caption_links(caption))

        # Detect from text links
        discovered.extend(self.detect_from_text_links(caption))

        # Detect from mentions
        discovered.extend(self.detect_from_mentions(caption))

        # Track each discovered channel
        results = []
        for info in discovered:
            # Skip if already monitored
            if self._is_monitored(info.username, info.telegram_peer_id):
                continue

            record = await self.track_discovered_channel(info)
            if record:
                results.append(record)

        return results

    async def track_discovered_channel(
        self, info: DiscoveredChannelInfo
    ) -> DiscoveredChannel | None:
        """Track a discovered channel reference.

        Creates a new DiscoveredChannel record or updates an existing one.

        Args:
            info: Information about the discovered channel.

        Returns:
            The DiscoveredChannel record, or None if invalid.
        """
        if not info.username and not info.invite_hash and not info.telegram_peer_id:
            return None

        # Try to find existing record
        existing = await self._find_existing(info)

        if existing:
            # Update existing record
            existing.increment_reference(info.source_type.value)
            logger.debug(
                "discovered_channel_updated",
                id=existing.id,
                username=existing.username,
                reference_count=existing.reference_count,
            )
            return existing

        # Create new record
        now = datetime.now(timezone.utc)
        record = DiscoveredChannel(
            telegram_peer_id=info.telegram_peer_id,
            title=info.title,
            username=info.username,
            invite_hash=info.invite_hash,
            is_private=info.is_private,
            reference_count=1,
            first_seen_at=now,
            last_seen_at=now,
            source_types=[info.source_type.value],
        )

        self.db.add(record)
        await self.db.flush()

        logger.info(
            "discovered_channel_created",
            id=record.id,
            username=info.username,
            invite_hash=info.invite_hash[:10] + "..." if info.invite_hash else None,
            source_type=info.source_type.value,
        )

        return record

    async def _find_existing(
        self, info: DiscoveredChannelInfo
    ) -> DiscoveredChannel | None:
        """Find an existing DiscoveredChannel record.

        Matches by telegram_peer_id, username, or invite_hash.
        """
        # Try telegram_peer_id first (most specific)
        if info.telegram_peer_id:
            result = await self.db.execute(
                select(DiscoveredChannel).where(
                    DiscoveredChannel.telegram_peer_id == info.telegram_peer_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                # Update username if we have it and the existing doesn't
                if info.username and not existing.username:
                    existing.username = info.username
                if info.title and not existing.title:
                    existing.title = info.title
                return existing

        # Try username
        if info.username:
            result = await self.db.execute(
                select(DiscoveredChannel).where(
                    DiscoveredChannel.username == info.username
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                # Update telegram_peer_id if we have it
                if info.telegram_peer_id and not existing.telegram_peer_id:
                    existing.telegram_peer_id = info.telegram_peer_id
                if info.title and not existing.title:
                    existing.title = info.title
                return existing

        # Try invite_hash
        if info.invite_hash:
            result = await self.db.execute(
                select(DiscoveredChannel).where(
                    DiscoveredChannel.invite_hash == info.invite_hash
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing

        return None

    async def get_discovered_channels(
        self,
        *,
        exclude_monitored: bool = True,
        min_references: int = 1,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DiscoveredChannel]:
        """Get discovered channels with filtering.

        Args:
            exclude_monitored: If True, exclude channels that are now monitored.
            min_references: Minimum reference count to include.
            limit: Maximum number of results.
            offset: Offset for pagination.

        Returns:
            List of DiscoveredChannel records.
        """
        query = select(DiscoveredChannel).where(
            DiscoveredChannel.reference_count >= min_references
        )

        # Order by reference count (most referenced first), then recency
        query = query.order_by(
            DiscoveredChannel.reference_count.desc(),
            DiscoveredChannel.last_seen_at.desc(),
        )

        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        channels = result.scalars().all()

        if exclude_monitored:
            await self._load_monitored_channels()
            channels = [
                c
                for c in channels
                if not self._is_monitored(c.username, c.telegram_peer_id)
            ]

        return channels
