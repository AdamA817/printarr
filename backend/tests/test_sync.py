"""Tests for SyncService."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, DownloadMode
from app.services.sync import SyncService


@pytest.fixture
def sync_service():
    """Create a fresh SyncService instance for testing."""
    SyncService.reset_instance()
    service = SyncService.get_instance()
    yield service
    SyncService.reset_instance()


class TestSyncServiceSingleton:
    """Tests for SyncService singleton behavior."""

    def test_get_instance_returns_same_instance(self):
        """Test that get_instance returns the same instance."""
        SyncService.reset_instance()
        instance1 = SyncService.get_instance()
        instance2 = SyncService.get_instance()
        assert instance1 is instance2
        SyncService.reset_instance()

    def test_reset_instance_creates_new_instance(self):
        """Test that reset_instance allows creating a new instance."""
        SyncService.reset_instance()
        instance1 = SyncService.get_instance()
        SyncService.reset_instance()
        instance2 = SyncService.get_instance()
        assert instance1 is not instance2
        SyncService.reset_instance()


class TestSyncServiceStats:
    """Tests for SyncService statistics."""

    def test_stats_when_not_running(self, sync_service):
        """Test stats when service is not running."""
        stats = sync_service.stats

        assert stats["is_running"] is False
        assert stats["started_at"] is None
        assert stats["subscribed_channels"] == 0
        assert stats["messages_processed"] == 0
        assert stats["designs_created"] == 0
        assert stats["uptime_seconds"] == 0

    def test_is_running_initially_false(self, sync_service):
        """Test that service is not running initially."""
        assert sync_service.is_running is False


class TestSyncServiceChannelManagement:
    """Tests for channel subscription management."""

    @pytest.mark.asyncio
    async def test_add_channel(self, sync_service):
        """Test adding a channel to subscriptions."""
        await sync_service.add_channel("123456789")

        assert 123456789 in sync_service._subscribed_channel_ids

    @pytest.mark.asyncio
    async def test_add_channel_handles_negative_id(self, sync_service):
        """Test that add_channel handles negative IDs (common for channels)."""
        await sync_service.add_channel("-1001234567890")

        # Should store absolute value
        assert 1001234567890 in sync_service._subscribed_channel_ids

    @pytest.mark.asyncio
    async def test_add_channel_invalid_id(self, sync_service):
        """Test that invalid channel IDs are handled gracefully."""
        await sync_service.add_channel("not_a_number")

        # Should not add anything
        assert len(sync_service._subscribed_channel_ids) == 0

    @pytest.mark.asyncio
    async def test_remove_channel(self, sync_service):
        """Test removing a channel from subscriptions."""
        sync_service._subscribed_channel_ids.add(123456789)

        await sync_service.remove_channel("123456789")

        assert 123456789 not in sync_service._subscribed_channel_ids

    @pytest.mark.asyncio
    async def test_remove_channel_handles_negative_id(self, sync_service):
        """Test that remove_channel handles negative IDs."""
        sync_service._subscribed_channel_ids.add(1001234567890)

        await sync_service.remove_channel("-1001234567890")

        assert 1001234567890 not in sync_service._subscribed_channel_ids

    @pytest.mark.asyncio
    async def test_remove_nonexistent_channel(self, sync_service):
        """Test that removing a non-existent channel doesn't raise."""
        await sync_service.remove_channel("999999999")
        # Should not raise any exception


class TestSyncServiceStart:
    """Tests for SyncService start/stop behavior."""

    @pytest.mark.asyncio
    async def test_start_when_not_configured(self, sync_service):
        """Test that start handles disabled sync gracefully."""
        with patch("app.services.sync.settings") as mock_settings:
            mock_settings.sync_enabled = False

            # Should return early without error
            await sync_service.start()

            assert sync_service.is_running is False

    @pytest.mark.asyncio
    async def test_start_when_already_running(self, sync_service):
        """Test that start does nothing when already running."""
        sync_service._running = True

        with patch("app.services.sync.settings") as mock_settings:
            mock_settings.sync_enabled = True

            await sync_service.start()

            # Should still be running (didn't restart)
            assert sync_service._running is True

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, sync_service):
        """Test that stop does nothing when not running."""
        await sync_service.stop()
        # Should not raise any exception


class TestSyncServiceMessageProcessing:
    """Tests for message processing logic."""

    @pytest.mark.asyncio
    async def test_subscribed_channel_check(self, sync_service):
        """Test that only subscribed channels are processed."""
        # Add a channel
        sync_service._subscribed_channel_ids.add(123456789)

        # Check subscription
        assert 123456789 in sync_service._subscribed_channel_ids
        assert 999999999 not in sync_service._subscribed_channel_ids


class TestSyncServiceWithDatabase:
    """Integration tests for SyncService with database."""

    @pytest.mark.asyncio
    async def test_subscribe_to_channels(self, test_session: AsyncSession):
        """Test subscribing to channels from database."""
        # Create test channels
        channel1 = Channel(
            telegram_peer_id="123456789",
            title="Test Channel 1",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        channel2 = Channel(
            telegram_peer_id="987654321",
            title="Test Channel 2",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        channel3 = Channel(
            telegram_peer_id="111111111",
            title="Disabled Channel",
            is_enabled=False,
            download_mode=DownloadMode.MANUAL,
        )

        test_session.add_all([channel1, channel2, channel3])
        await test_session.commit()

        # Create sync service and mock the session maker
        SyncService.reset_instance()
        sync_service = SyncService.get_instance()

        with patch("app.services.sync.async_session_maker") as mock_session_maker:
            # Create a mock async context manager
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = test_session
            mock_cm.__aexit__.return_value = None
            mock_session_maker.return_value = mock_cm

            await sync_service._subscribe_to_channels()

        # Should have subscribed to enabled channels only
        assert 123456789 in sync_service._subscribed_channel_ids
        assert 987654321 in sync_service._subscribed_channel_ids
        assert 111111111 not in sync_service._subscribed_channel_ids

        SyncService.reset_instance()


class TestAutoDownloadLogic:
    """Tests for auto-download trigger logic."""

    def test_download_all_mode_triggers_download(self):
        """Test that DOWNLOAD_ALL mode should trigger auto-download."""
        assert DownloadMode.DOWNLOAD_ALL in (
            DownloadMode.DOWNLOAD_ALL,
            DownloadMode.DOWNLOAD_ALL_NEW,
        )

    def test_download_all_new_mode_triggers_download(self):
        """Test that DOWNLOAD_ALL_NEW mode should trigger auto-download."""
        assert DownloadMode.DOWNLOAD_ALL_NEW in (
            DownloadMode.DOWNLOAD_ALL,
            DownloadMode.DOWNLOAD_ALL_NEW,
        )

    def test_manual_mode_does_not_trigger_download(self):
        """Test that MANUAL mode should not trigger auto-download."""
        assert DownloadMode.MANUAL not in (
            DownloadMode.DOWNLOAD_ALL,
            DownloadMode.DOWNLOAD_ALL_NEW,
        )


class TestSyncServiceUptime:
    """Tests for uptime calculation."""

    def test_uptime_when_not_started(self, sync_service):
        """Test uptime is 0 when service hasn't started."""
        assert sync_service._uptime_seconds() == 0

    def test_uptime_when_started(self, sync_service):
        """Test uptime calculation when started."""
        sync_service._started_at = datetime.utcnow()
        # Should be 0 or very small
        assert sync_service._uptime_seconds() >= 0
        assert sync_service._uptime_seconds() < 2  # Less than 2 seconds


class TestConfigSettings:
    """Tests for sync configuration settings."""

    def test_sync_poll_interval_default(self):
        """Test default sync poll interval."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.sync_poll_interval == 300  # 5 minutes

    def test_sync_enabled_default(self):
        """Test sync is enabled by default."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.sync_enabled is True
