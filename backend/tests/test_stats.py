"""Tests for stats API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


class TestStatsEndpoint:
    """Tests for GET /api/v1/stats/ endpoint."""

    def test_get_stats_returns_200(self, client: TestClient):
        """Should return 200 OK."""
        response = client.get("/api/v1/stats/")
        assert response.status_code == 200

    def test_get_stats_returns_correct_structure(self, client: TestClient):
        """Should return correct response structure."""
        response = client.get("/api/v1/stats/")
        data = response.json()

        assert "channels_count" in data
        assert "designs_count" in data
        assert "downloads_active" in data

    def test_get_stats_returns_integers(self, client: TestClient):
        """Should return integer values."""
        response = client.get("/api/v1/stats/")
        data = response.json()

        assert isinstance(data["channels_count"], int)
        assert isinstance(data["designs_count"], int)
        assert isinstance(data["downloads_active"], int)

    def test_get_stats_channels_count_non_negative(self, client: TestClient):
        """Channel count should be non-negative."""
        response = client.get("/api/v1/stats/")
        data = response.json()

        assert data["channels_count"] >= 0

    def test_get_stats_placeholder_values(self, client: TestClient):
        """Designs and downloads should be 0 (not yet implemented)."""
        response = client.get("/api/v1/stats/")
        data = response.json()

        # These are placeholder values until the features are implemented
        assert data["designs_count"] == 0
        assert data["downloads_active"] == 0


class TestEndpointPaths:
    """Tests to verify endpoint paths exist."""

    def test_stats_endpoint_exists(self, client: TestClient):
        """Stats endpoint should exist."""
        response = client.get("/api/v1/stats/")
        # Should not be 404
        assert response.status_code != 404
