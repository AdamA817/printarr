"""Tests for Telegram channel resolution API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.telegram import TelegramInvalidLinkError, TelegramService


@pytest.fixture(autouse=True)
def reset_telegram_service():
    """Reset the TelegramService singleton before and after each test."""
    TelegramService.reset_instance()
    yield
    TelegramService.reset_instance()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


class TestChannelResolveParsing:
    """Tests for channel link parsing logic."""

    def test_parse_username_with_at(self):
        """Should parse @username format."""
        link_type, identifier = TelegramService._parse_channel_link("@channelname")
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_plain_username(self):
        """Should parse plain username."""
        link_type, identifier = TelegramService._parse_channel_link("channelname")
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_t_me_link(self):
        """Should parse t.me/username format."""
        link_type, identifier = TelegramService._parse_channel_link("t.me/channelname")
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_https_t_me_link(self):
        """Should parse https://t.me/username format."""
        link_type, identifier = TelegramService._parse_channel_link(
            "https://t.me/channelname"
        )
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_http_t_me_link(self):
        """Should parse http://t.me/username format."""
        link_type, identifier = TelegramService._parse_channel_link(
            "http://t.me/channelname"
        )
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_t_me_with_message_id(self):
        """Should parse t.me/username/123 format (ignore message ID)."""
        link_type, identifier = TelegramService._parse_channel_link(
            "https://t.me/channelname/123"
        )
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_private_invite_link(self):
        """Should parse t.me/+hash format."""
        link_type, identifier = TelegramService._parse_channel_link(
            "https://t.me/+abcdef123"
        )
        assert link_type == "invite"
        assert identifier == "abcdef123"

    def test_parse_old_joinchat_format(self):
        """Should parse t.me/joinchat/hash format."""
        link_type, identifier = TelegramService._parse_channel_link(
            "https://t.me/joinchat/abcdef123"
        )
        assert link_type == "joinchat"
        assert identifier == "abcdef123"

    def test_parse_strips_whitespace(self):
        """Should strip whitespace from link."""
        link_type, identifier = TelegramService._parse_channel_link(
            "  @channelname  "
        )
        assert link_type == "username"
        assert identifier == "channelname"

    def test_parse_invalid_link_raises_error(self):
        """Should raise TelegramInvalidLinkError for unrecognized formats."""
        with pytest.raises(TelegramInvalidLinkError):
            TelegramService._parse_channel_link("not-a-valid-link!")

        with pytest.raises(TelegramInvalidLinkError):
            TelegramService._parse_channel_link("https://example.com/channel")


class TestChannelResolveEndpoint:
    """Tests for POST /api/v1/telegram/channels/resolve endpoint."""

    def test_resolve_not_connected(self, client: TestClient):
        """Should return 503 when not connected to Telegram."""
        response = client.post(
            "/api/v1/telegram/channels/resolve",
            json={"link": "https://t.me/testchannel"},
        )
        assert response.status_code == 503

    def test_resolve_missing_link(self, client: TestClient):
        """Should require link field."""
        response = client.post(
            "/api/v1/telegram/channels/resolve",
            json={},
        )
        assert response.status_code == 422

    def test_resolve_empty_link(self, client: TestClient):
        """Should reject empty link."""
        response = client.post(
            "/api/v1/telegram/channels/resolve",
            json={"link": ""},
        )
        assert response.status_code == 422

    def test_resolve_link_too_long(self, client: TestClient):
        """Should reject link that's too long."""
        response = client.post(
            "/api/v1/telegram/channels/resolve",
            json={"link": "x" * 600},  # Max is 512
        )
        assert response.status_code == 422


class TestEndpointPaths:
    """Tests to verify endpoint paths exist."""

    def test_resolve_endpoint_exists(self, client: TestClient):
        """Resolve endpoint should exist."""
        response = client.post(
            "/api/v1/telegram/channels/resolve",
            json={"link": "@testchannel"},
        )
        # Should be 503 (not connected), not 404
        assert response.status_code != 404
