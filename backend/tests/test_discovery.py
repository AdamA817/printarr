"""Tests for DiscoveryService."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, DiscoveredChannel, DiscoverySourceType, DownloadMode
from app.services.discovery import (
    DiscoveredChannelInfo,
    DiscoveryService,
    MENTION_PATTERN,
    TME_LINK_PATTERN,
)


class TestTmeLinkPattern:
    """Tests for t.me link regex pattern."""

    def test_matches_simple_username(self):
        """Test matching simple t.me/username."""
        match = TME_LINK_PATTERN.search("Check out t.me/testchannel")
        assert match is not None
        assert match.group(1) == "testchannel"

    def test_matches_https_url(self):
        """Test matching https://t.me/username."""
        match = TME_LINK_PATTERN.search("Link: https://t.me/mychannel here")
        assert match is not None
        assert match.group(1) == "mychannel"

    def test_matches_http_url(self):
        """Test matching http://t.me/username."""
        match = TME_LINK_PATTERN.search("Link: http://t.me/oldchannel")
        assert match is not None
        assert match.group(1) == "oldchannel"

    def test_matches_private_invite(self):
        """Test matching private invite link t.me/+hash."""
        match = TME_LINK_PATTERN.search("Join: t.me/+abc123xyz")
        assert match is not None
        assert match.group(1) == "+abc123xyz"

    def test_matches_joinchat_invite(self):
        """Test matching old joinchat link t.me/joinchat/hash."""
        match = TME_LINK_PATTERN.search("Join: t.me/joinchat/XYZ789abc")
        assert match is not None
        assert match.group(1) == "joinchat/XYZ789abc"

    def test_matches_multiple_links(self):
        """Test matching multiple links in text."""
        text = "Check t.me/first and t.me/second channels"
        matches = TME_LINK_PATTERN.findall(text)
        assert len(matches) == 2
        assert "first" in matches
        assert "second" in matches

    def test_no_match_for_short_username(self):
        """Test that very short usernames (< 5 chars) don't match."""
        # Telegram usernames must be 5-32 characters
        match = TME_LINK_PATTERN.search("t.me/abc")
        assert match is None

    def test_matches_username_with_underscores(self):
        """Test matching username with underscores."""
        match = TME_LINK_PATTERN.search("t.me/my_cool_channel")
        assert match is not None
        assert match.group(1) == "my_cool_channel"


class TestMentionPattern:
    """Tests for @mention regex pattern."""

    def test_matches_simple_mention(self):
        """Test matching simple @mention."""
        match = MENTION_PATTERN.search("Follow @testuser for updates")
        assert match is not None
        assert match.group(1) == "testuser"

    def test_matches_mention_with_underscores(self):
        """Test matching @mention with underscores."""
        match = MENTION_PATTERN.search("Credit: @cool_designer_123")
        assert match is not None
        assert match.group(1) == "cool_designer_123"

    def test_matches_multiple_mentions(self):
        """Test matching multiple mentions."""
        text = "Thanks to @user1 and @user2 for this!"
        matches = MENTION_PATTERN.findall(text)
        assert len(matches) == 2
        assert "user1" in matches
        assert "user2" in matches

    def test_no_match_for_short_username(self):
        """Test that short usernames (< 5 chars) don't match."""
        match = MENTION_PATTERN.search("Hi @abc there")
        assert match is None

    def test_no_match_for_number_start(self):
        """Test that usernames starting with number don't match."""
        match = MENTION_PATTERN.search("User @123user is here")
        assert match is None


class TestDiscoveryServiceDetection:
    """Tests for DiscoveryService detection methods."""

    @pytest.fixture
    def discovery_service(self, test_session: AsyncSession):
        """Create a DiscoveryService instance."""
        return DiscoveryService(test_session)

    def test_detect_from_caption_links_public(self, discovery_service):
        """Test detecting public channel links from caption."""
        caption = "Check out this channel: https://t.me/awesome_channel"
        results = discovery_service.detect_from_caption_links(caption)

        assert len(results) == 1
        assert results[0].username == "awesome_channel"
        assert results[0].is_private is False
        assert results[0].source_type == DiscoverySourceType.CAPTION_LINK

    def test_detect_from_caption_links_private(self, discovery_service):
        """Test detecting private channel invite links from caption."""
        caption = "Join our group: t.me/+secrethash123"
        results = discovery_service.detect_from_caption_links(caption)

        assert len(results) == 1
        assert results[0].invite_hash == "secrethash123"
        assert results[0].is_private is True
        assert results[0].source_type == DiscoverySourceType.CAPTION_LINK

    def test_detect_from_caption_links_joinchat(self, discovery_service):
        """Test detecting old-style joinchat links."""
        caption = "Join: t.me/joinchat/abcdef123456"
        results = discovery_service.detect_from_caption_links(caption)

        assert len(results) == 1
        assert results[0].invite_hash == "abcdef123456"
        assert results[0].is_private is True

    def test_detect_from_caption_links_multiple(self, discovery_service):
        """Test detecting multiple links."""
        caption = "Check t.me/channel1 and https://t.me/channel2"
        results = discovery_service.detect_from_caption_links(caption)

        assert len(results) == 2
        usernames = [r.username for r in results]
        assert "channel1" in usernames
        assert "channel2" in usernames

    def test_detect_from_caption_links_deduplicates(self, discovery_service):
        """Test that duplicate links are deduplicated."""
        caption = "Visit t.me/mychannel - really, go to t.me/mychannel!"
        results = discovery_service.detect_from_caption_links(caption)

        assert len(results) == 1
        assert results[0].username == "mychannel"

    def test_detect_from_caption_links_skips_bots(self, discovery_service):
        """Test that bot usernames are skipped."""
        caption = "Use @myhelperbot or visit t.me/coolbot"
        results = discovery_service.detect_from_caption_links(caption)

        # Should not include the bot
        assert len(results) == 0 or all("bot" not in r.username.lower() for r in results if r.username)

    def test_detect_from_mentions(self, discovery_service):
        """Test detecting @mentions."""
        text = "Thanks to @amazing_designer for this model!"
        results = discovery_service.detect_from_mentions(text)

        assert len(results) == 1
        assert results[0].username == "amazing_designer"
        assert results[0].source_type == DiscoverySourceType.MENTION

    def test_detect_from_mentions_deduplicates(self, discovery_service):
        """Test that duplicate mentions are deduplicated."""
        text = "Credit: @designer - thanks @designer!"
        results = discovery_service.detect_from_mentions(text)

        assert len(results) == 1

    def test_detect_from_mentions_skips_bots(self, discovery_service):
        """Test that bot mentions are skipped."""
        text = "Ask @helperbot for help"
        results = discovery_service.detect_from_mentions(text)

        assert len(results) == 0

    def test_detect_from_text_links(self, discovery_service):
        """Test detecting links from message text."""
        text = "More designs at t.me/designchannel"
        results = discovery_service.detect_from_text_links(text)

        assert len(results) == 1
        assert results[0].username == "designchannel"
        assert results[0].source_type == DiscoverySourceType.TEXT_LINK

    def test_detect_from_forward_no_data(self, discovery_service):
        """Test forward detection with no forward data."""
        message_data = {"text": "Hello"}
        result = discovery_service.detect_from_forward(message_data)

        assert result is None

    def test_detect_from_forward_with_raw_data(self, discovery_service):
        """Test forward detection with raw forward data."""
        message_data = {
            "text": "Forwarded content",
            "_raw_forward": {
                "channel_id": 123456789,
                "channel_title": "Original Channel",
                "channel_username": "originalchannel",
            },
        }
        result = discovery_service.detect_from_forward(message_data)

        assert result is not None
        assert result.telegram_peer_id == "123456789"
        assert result.title == "Original Channel"
        assert result.username == "originalchannel"
        assert result.source_type == DiscoverySourceType.FORWARD

    def test_detect_empty_caption(self, discovery_service):
        """Test detection with empty caption."""
        assert discovery_service.detect_from_caption_links(None) == []
        assert discovery_service.detect_from_caption_links("") == []
        assert discovery_service.detect_from_mentions(None) == []
        assert discovery_service.detect_from_mentions("") == []


class TestDiscoveryServiceDatabase:
    """Integration tests for DiscoveryService with database."""

    @pytest.fixture
    async def discovery_service(self, test_session: AsyncSession):
        """Create a DiscoveryService instance with test session."""
        return DiscoveryService(test_session)

    @pytest.mark.asyncio
    async def test_track_discovered_channel_creates_new(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test creating a new discovered channel."""
        info = DiscoveredChannelInfo(
            username="newchannel",
            source_type=DiscoverySourceType.MENTION,
        )

        result = await discovery_service.track_discovered_channel(info)
        await test_session.commit()

        assert result is not None
        assert result.username == "newchannel"
        assert result.reference_count == 1
        assert DiscoverySourceType.MENTION.value in result.source_types

    @pytest.mark.asyncio
    async def test_track_discovered_channel_updates_existing(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test updating an existing discovered channel."""
        # Create initial record
        info1 = DiscoveredChannelInfo(
            username="existingchannel",
            source_type=DiscoverySourceType.MENTION,
        )
        result1 = await discovery_service.track_discovered_channel(info1)
        await test_session.commit()

        initial_count = result1.reference_count

        # Track again with different source
        info2 = DiscoveredChannelInfo(
            username="existingchannel",
            source_type=DiscoverySourceType.CAPTION_LINK,
        )
        result2 = await discovery_service.track_discovered_channel(info2)
        await test_session.commit()

        assert result2.reference_count == initial_count + 1
        assert DiscoverySourceType.MENTION.value in result2.source_types
        assert DiscoverySourceType.CAPTION_LINK.value in result2.source_types

    @pytest.mark.asyncio
    async def test_track_private_channel(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test tracking a private channel with invite hash."""
        info = DiscoveredChannelInfo(
            invite_hash="secrethash123",
            is_private=True,
            source_type=DiscoverySourceType.CAPTION_LINK,
        )

        result = await discovery_service.track_discovered_channel(info)
        await test_session.commit()

        assert result is not None
        assert result.invite_hash == "secrethash123"
        assert result.is_private is True

    @pytest.mark.asyncio
    async def test_process_message_skips_monitored(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test that monitored channels are skipped."""
        # Create a monitored channel
        monitored = Channel(
            telegram_peer_id="123456789",
            title="Monitored Channel",
            username="monitoredchannel",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(monitored)
        await test_session.commit()

        # Try to discover the same channel
        message_data = {
            "text": "Check out t.me/monitoredchannel for more!",
        }

        results = await discovery_service.process_message(message_data)

        # Should not discover the monitored channel
        assert all(r.username != "monitoredchannel" for r in results)

    @pytest.mark.asyncio
    async def test_process_message_full_flow(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test full message processing with multiple discovery sources."""
        message_data = {
            "text": "Check @designer1 at t.me/designchannel for more models! Also see t.me/+privatehash",
        }

        results = await discovery_service.process_message(message_data)
        await test_session.commit()

        # Should find multiple channels
        assert len(results) >= 2

        # Verify they were saved
        db_result = await test_session.execute(select(DiscoveredChannel))
        saved = db_result.scalars().all()
        assert len(saved) >= 2

    @pytest.mark.asyncio
    async def test_get_discovered_channels(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test getting discovered channels with filters."""
        # Create some discovered channels with unique prefixes
        prefix = "gettest_"
        for i, username in enumerate([f"{prefix}channel1", f"{prefix}channel2", f"{prefix}channel3"]):
            dc = DiscoveredChannel(
                username=username,
                reference_count=i + 1,
                source_types=[DiscoverySourceType.MENTION.value],
            )
            test_session.add(dc)
        await test_session.commit()

        # Get all
        results = await discovery_service.get_discovered_channels()
        # Filter to only our test channels
        our_results = [r for r in results if r.username and r.username.startswith(prefix)]
        assert len(our_results) == 3

        # Get with min references (2 out of 3 have ref count >= 2)
        results = await discovery_service.get_discovered_channels(min_references=2)
        our_results = [r for r in results if r.username and r.username.startswith(prefix)]
        assert len(our_results) == 2

    @pytest.mark.asyncio
    async def test_find_existing_by_username(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test finding existing channel by username."""
        dc = DiscoveredChannel(
            username="existinguser",
            reference_count=1,
            source_types=[],
        )
        test_session.add(dc)
        await test_session.commit()

        info = DiscoveredChannelInfo(
            username="existinguser",
            telegram_peer_id="999",  # New info to add
        )

        result = await discovery_service._find_existing(info)

        assert result is not None
        assert result.username == "existinguser"
        # Should have updated with new peer_id
        assert result.telegram_peer_id == "999"

    @pytest.mark.asyncio
    async def test_find_existing_by_invite_hash(
        self, test_session: AsyncSession, discovery_service
    ):
        """Test finding existing channel by invite hash."""
        dc = DiscoveredChannel(
            invite_hash="uniquehash123",
            is_private=True,
            reference_count=1,
            source_types=[],
        )
        test_session.add(dc)
        await test_session.commit()

        info = DiscoveredChannelInfo(
            invite_hash="uniquehash123",
            is_private=True,
        )

        result = await discovery_service._find_existing(info)

        assert result is not None
        assert result.invite_hash == "uniquehash123"
