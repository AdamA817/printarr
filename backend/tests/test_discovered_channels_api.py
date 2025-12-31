"""Tests for discovered channels API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import Channel, DiscoveredChannel, DiscoverySourceType, DownloadMode


class TestDiscoveredChannelsListAPI:
    """Tests for GET /api/v1/discovered-channels/."""

    def test_list_empty(self, client: TestClient):
        """Test listing when no discovered channels exist."""
        response = client.get("/api/v1/discovered-channels/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_channels(self, client: TestClient, test_session):
        """Test listing discovered channels."""
        # Create some discovered channels
        dc1 = DiscoveredChannel(
            username="channel1",
            reference_count=5,
            source_types=[DiscoverySourceType.MENTION.value],
        )
        dc2 = DiscoveredChannel(
            username="channel2",
            reference_count=10,
            source_types=[DiscoverySourceType.CAPTION_LINK.value],
        )
        test_session.add_all([dc1, dc2])
        await test_session.commit()

        response = client.get("/api/v1/discovered-channels/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

        # Default sort is by reference_count desc
        usernames = [item["username"] for item in data["items"]]
        assert "channel2" in usernames
        assert "channel1" in usernames

    @pytest.mark.asyncio
    async def test_list_pagination(self, client: TestClient, test_session):
        """Test pagination of discovered channels."""
        # Create 5 channels
        for i in range(5):
            dc = DiscoveredChannel(
                username=f"pagtest{i}",
                reference_count=i + 1,
                source_types=[],
            )
            test_session.add(dc)
        await test_session.commit()

        # Get first page with 2 items
        response = client.get("/api/v1/discovered-channels/?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1

    @pytest.mark.asyncio
    async def test_list_sorting(self, client: TestClient, test_session):
        """Test sorting of discovered channels."""
        now = datetime.utcnow()
        dc1 = DiscoveredChannel(
            username="sorttest1",
            reference_count=1,
            first_seen_at=now - timedelta(days=1),
            source_types=[],
        )
        dc2 = DiscoveredChannel(
            username="sorttest2",
            reference_count=10,
            first_seen_at=now,
            source_types=[],
        )
        test_session.add_all([dc1, dc2])
        await test_session.commit()

        # Sort by first_seen_at asc
        response = client.get(
            "/api/v1/discovered-channels/?sort_by=first_seen_at&sort_order=asc"
        )
        assert response.status_code == 200
        data = response.json()

        # Filter to our test channels
        our_items = [i for i in data["items"] if i["username"].startswith("sorttest")]
        if len(our_items) >= 2:
            # First should be older
            assert our_items[0]["username"] == "sorttest1"

    @pytest.mark.asyncio
    async def test_list_excludes_monitored(self, client: TestClient, test_session):
        """Test that monitored channels are excluded."""
        # Create a monitored channel
        monitored = Channel(
            telegram_peer_id="123456",
            title="Monitored",
            username="monitoreduser",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(monitored)

        # Create discovered channels
        dc1 = DiscoveredChannel(
            username="monitoreduser",  # Same as monitored
            reference_count=5,
            source_types=[],
        )
        dc2 = DiscoveredChannel(
            username="notmonitored",
            reference_count=5,
            source_types=[],
        )
        test_session.add_all([dc1, dc2])
        await test_session.commit()

        # Default excludes monitored
        response = client.get("/api/v1/discovered-channels/")
        assert response.status_code == 200
        data = response.json()

        usernames = [item["username"] for item in data["items"]]
        assert "monitoreduser" not in usernames
        assert "notmonitored" in usernames


class TestDiscoveredChannelGetAPI:
    """Tests for GET /api/v1/discovered-channels/{id}."""

    @pytest.mark.asyncio
    async def test_get_channel(self, client: TestClient, test_session):
        """Test getting a single discovered channel."""
        dc = DiscoveredChannel(
            username="gettestchannel",
            reference_count=5,
            source_types=[DiscoverySourceType.MENTION.value],
        )
        test_session.add(dc)
        await test_session.commit()

        response = client.get(f"/api/v1/discovered-channels/{dc.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "gettestchannel"
        assert data["reference_count"] == 5

    def test_get_nonexistent(self, client: TestClient):
        """Test getting a non-existent channel returns 404."""
        response = client.get("/api/v1/discovered-channels/nonexistent-id")
        assert response.status_code == 404


class TestDiscoveredChannelDeleteAPI:
    """Tests for DELETE /api/v1/discovered-channels/{id}."""

    @pytest.mark.asyncio
    async def test_delete_channel(self, client: TestClient, test_session):
        """Test deleting a discovered channel."""
        dc = DiscoveredChannel(
            username="deletetestchannel",
            source_types=[],
        )
        test_session.add(dc)
        await test_session.commit()

        dc_id = dc.id

        response = client.delete(f"/api/v1/discovered-channels/{dc_id}")
        assert response.status_code == 204

        # Verify it's deleted
        response = client.get(f"/api/v1/discovered-channels/{dc_id}")
        assert response.status_code == 404

    def test_delete_nonexistent(self, client: TestClient):
        """Test deleting a non-existent channel returns 404."""
        response = client.delete("/api/v1/discovered-channels/nonexistent-id")
        assert response.status_code == 404


class TestDiscoveredChannelStatsAPI:
    """Tests for GET /api/v1/discovered-channels/stats."""

    def test_stats_empty(self, client: TestClient):
        """Test stats with no discovered channels."""
        response = client.get("/api/v1/discovered-channels/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "new_this_week" in data
        assert "most_referenced" in data

    @pytest.mark.asyncio
    async def test_stats_with_channels(self, client: TestClient, test_session):
        """Test stats with discovered channels."""
        now = datetime.utcnow()

        # Create channels with different ages
        dc1 = DiscoveredChannel(
            username="statstestold",
            reference_count=10,
            first_seen_at=now - timedelta(days=30),
            source_types=[],
        )
        dc2 = DiscoveredChannel(
            username="statstestnew",
            reference_count=5,
            first_seen_at=now - timedelta(days=1),
            source_types=[],
        )
        test_session.add_all([dc1, dc2])
        await test_session.commit()

        response = client.get("/api/v1/discovered-channels/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert data["new_this_week"] >= 1


class TestDiscoveredChannelAddAPI:
    """Tests for POST /api/v1/discovered-channels/{id}/add."""

    @pytest.mark.asyncio
    async def test_add_already_monitored(self, client: TestClient, test_session):
        """Test adding a channel that's already monitored."""
        # Create monitored channel
        monitored = Channel(
            telegram_peer_id="999999",
            title="Already Monitored",
            username="alreadymonitored",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(monitored)

        # Create discovered with same username
        dc = DiscoveredChannel(
            username="alreadymonitored",
            source_types=[],
        )
        test_session.add(dc)
        await test_session.commit()

        response = client.post(f"/api/v1/discovered-channels/{dc.id}/add")
        assert response.status_code == 200
        data = response.json()
        assert data["was_existing"] is True
        assert data["channel_id"] == monitored.id

    @pytest.mark.asyncio
    async def test_add_new_channel_telegram_not_connected(
        self, client: TestClient, test_session
    ):
        """Test adding when Telegram is not connected."""
        dc = DiscoveredChannel(
            username="newchanneltest",
            source_types=[],
        )
        test_session.add(dc)
        await test_session.commit()

        # Mock TelegramService
        with patch("app.api.routes.discovered_channels.TelegramService") as mock_ts:
            mock_instance = mock_ts.get_instance.return_value
            mock_instance.is_connected.return_value = False

            response = client.post(f"/api/v1/discovered-channels/{dc.id}/add")
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_add_no_identifier(self, client: TestClient, test_session):
        """Test adding a channel with no username or invite hash."""
        import uuid
        unique_id = str(uuid.uuid4())[:12]

        dc = DiscoveredChannel(
            telegram_peer_id=f"noident_{unique_id}",
            title="No Identifier",
            username=None,  # Explicitly no username
            invite_hash=None,  # Explicitly no invite hash
            source_types=[],
        )
        test_session.add(dc)
        await test_session.commit()

        # Mock TelegramService
        with patch("app.api.routes.discovered_channels.TelegramService") as mock_ts:
            mock_instance = mock_ts.get_instance.return_value
            mock_instance.is_connected.return_value = True
            mock_instance.is_authenticated = AsyncMock(return_value=True)

            response = client.post(f"/api/v1/discovered-channels/{dc.id}/add")
            assert response.status_code == 400
            assert "no username or invite hash" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_successful(self, client: TestClient, test_session):
        """Test successfully adding a new channel."""
        dc = DiscoveredChannel(
            username="successaddtest",
            source_types=[DiscoverySourceType.MENTION.value],
        )
        test_session.add(dc)
        await test_session.commit()

        # Mock TelegramService
        with patch("app.api.routes.discovered_channels.TelegramService") as mock_ts:
            mock_instance = mock_ts.get_instance.return_value
            mock_instance.is_connected.return_value = True
            mock_instance.is_authenticated = AsyncMock(return_value=True)
            mock_instance.resolve_channel = AsyncMock(
                return_value={
                    "id": 987654321,
                    "title": "Success Add Test",
                    "username": "successaddtest",
                    "type": "channel",
                }
            )

            response = client.post(
                f"/api/v1/discovered-channels/{dc.id}/add",
                json={"download_mode": "MANUAL", "is_enabled": True},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["was_existing"] is False
            assert data["title"] == "Success Add Test"
            assert "channel_id" in data

    def test_add_nonexistent(self, client: TestClient):
        """Test adding a non-existent discovered channel."""
        response = client.post("/api/v1/discovered-channels/nonexistent-id/add")
        assert response.status_code == 404
