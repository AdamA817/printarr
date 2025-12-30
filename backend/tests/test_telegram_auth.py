"""Tests for Telegram authentication API endpoints."""

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


class TestAuthStatus:
    """Tests for GET /api/v1/telegram/auth/status endpoint."""

    def test_auth_status_unconfigured(self, client: TestClient):
        """Should return not configured/connected/authenticated when Telegram is not set up."""
        response = client.get("/api/v1/telegram/auth/status")
        assert response.status_code == 200

        data = response.json()
        assert data["configured"] is False
        assert data["connected"] is False
        assert data["authenticated"] is False
        assert data["user"] is None

    def test_auth_status_response_schema(self, client: TestClient):
        """Should return all required fields in response."""
        response = client.get("/api/v1/telegram/auth/status")
        assert response.status_code == 200

        data = response.json()
        assert "configured" in data
        assert "connected" in data
        assert "authenticated" in data
        assert "user" in data


class TestAuthStart:
    """Tests for POST /api/v1/telegram/auth/start endpoint."""

    def test_auth_start_not_configured(self, client: TestClient):
        """Should return 503 when Telegram credentials are not configured."""
        response = client.post(
            "/api/v1/telegram/auth/start",
            json={"phone": "+1234567890"},
        )
        assert response.status_code == 503

    def test_auth_start_invalid_phone_format(self, client: TestClient):
        """Should reject phone numbers that are too short."""
        response = client.post(
            "/api/v1/telegram/auth/start",
            json={"phone": "123"},
        )
        # Pydantic validation should catch this
        assert response.status_code == 422

    def test_auth_start_missing_phone(self, client: TestClient):
        """Should require phone field."""
        response = client.post(
            "/api/v1/telegram/auth/start",
            json={},
        )
        assert response.status_code == 422


class TestAuthVerify:
    """Tests for POST /api/v1/telegram/auth/verify endpoint."""

    def test_auth_verify_not_connected(self, client: TestClient):
        """Should return 503 when not connected to Telegram."""
        response = client.post(
            "/api/v1/telegram/auth/verify",
            json={
                "phone": "+1234567890",
                "code": "12345",
                "phone_code_hash": "abc123",
            },
        )
        assert response.status_code == 503

    def test_auth_verify_missing_fields(self, client: TestClient):
        """Should require all mandatory fields."""
        # Missing code
        response = client.post(
            "/api/v1/telegram/auth/verify",
            json={
                "phone": "+1234567890",
                "phone_code_hash": "abc123",
            },
        )
        assert response.status_code == 422

        # Missing phone_code_hash
        response = client.post(
            "/api/v1/telegram/auth/verify",
            json={
                "phone": "+1234567890",
                "code": "12345",
            },
        )
        assert response.status_code == 422

    def test_auth_verify_password_optional(self, client: TestClient):
        """Password field should be optional."""
        # This should fail due to not connected, not validation
        response = client.post(
            "/api/v1/telegram/auth/verify",
            json={
                "phone": "+1234567890",
                "code": "12345",
                "phone_code_hash": "abc123",
                # No password - should be OK
            },
        )
        # Should be 503 (not connected), not 422 (validation)
        assert response.status_code == 503


class TestAuthLogout:
    """Tests for POST /api/v1/telegram/auth/logout endpoint."""

    def test_auth_logout_when_not_connected(self, client: TestClient):
        """Should succeed even when not connected."""
        response = client.post("/api/v1/telegram/auth/logout")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "logged_out"


class TestEndpointPaths:
    """Tests to verify endpoint paths follow conventions."""

    def test_endpoints_exist(self, client: TestClient):
        """All auth endpoints should exist."""
        # GET status
        response = client.get("/api/v1/telegram/auth/status")
        assert response.status_code != 404

        # POST start
        response = client.post("/api/v1/telegram/auth/start", json={"phone": "+1234567890"})
        assert response.status_code != 404

        # POST verify
        response = client.post(
            "/api/v1/telegram/auth/verify",
            json={"phone": "+1", "code": "1", "phone_code_hash": "x"},
        )
        assert response.status_code != 404

        # POST logout
        response = client.post("/api/v1/telegram/auth/logout")
        assert response.status_code != 404
