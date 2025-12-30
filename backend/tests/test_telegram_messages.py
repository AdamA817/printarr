"""Tests for Telegram messages API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.telegram import TelegramService


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


class TestGetMessagesEndpoint:
    """Tests for GET /api/v1/telegram/channels/{channel_id}/messages endpoint."""

    def test_get_messages_not_connected(self, client: TestClient):
        """Should return 503 when not connected to Telegram."""
        response = client.get("/api/v1/telegram/channels/123456789/messages/")
        assert response.status_code == 503

    def test_get_messages_default_limit(self, client: TestClient):
        """Should accept request without limit parameter."""
        response = client.get("/api/v1/telegram/channels/123456789/messages/")
        # 503 because not connected, but request is valid
        assert response.status_code == 503

    def test_get_messages_custom_limit(self, client: TestClient):
        """Should accept limit query parameter."""
        response = client.get(
            "/api/v1/telegram/channels/123456789/messages/",
            params={"limit": 50},
        )
        assert response.status_code == 503

    def test_get_messages_limit_min(self, client: TestClient):
        """Should accept limit of 1."""
        response = client.get(
            "/api/v1/telegram/channels/123456789/messages/",
            params={"limit": 1},
        )
        assert response.status_code == 503

    def test_get_messages_limit_max(self, client: TestClient):
        """Should accept limit of 100."""
        response = client.get(
            "/api/v1/telegram/channels/123456789/messages/",
            params={"limit": 100},
        )
        assert response.status_code == 503

    def test_get_messages_limit_too_low(self, client: TestClient):
        """Should reject limit below 1."""
        response = client.get(
            "/api/v1/telegram/channels/123456789/messages/",
            params={"limit": 0},
        )
        assert response.status_code == 422

    def test_get_messages_limit_too_high(self, client: TestClient):
        """Should reject limit above 100."""
        response = client.get(
            "/api/v1/telegram/channels/123456789/messages/",
            params={"limit": 101},
        )
        assert response.status_code == 422

    def test_get_messages_invalid_channel_id(self, client: TestClient):
        """Should reject non-integer channel ID."""
        response = client.get("/api/v1/telegram/channels/not-a-number/messages/")
        assert response.status_code == 422


class TestEndpointPaths:
    """Tests to verify endpoint paths exist."""

    def test_messages_endpoint_exists(self, client: TestClient):
        """Messages endpoint should exist."""
        response = client.get("/api/v1/telegram/channels/123/messages/")
        # Should be 503 (not connected), not 404
        assert response.status_code != 404
