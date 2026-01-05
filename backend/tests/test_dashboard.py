"""Tests for Dashboard Stats API (Issue #103)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Channel,
    Design,
    DesignStatus,
    DiscoveredChannel,
    DiscoverySourceType,
    DownloadMode,
    Job,
    JobStatus,
    JobType,
)
from app.services.dashboard import DashboardService, clear_storage_cache


def unique_peer_id() -> str:
    """Generate a unique telegram_peer_id for tests."""
    return f"test_{uuid.uuid4().hex[:12]}"


class TestDashboardStatsEndpoint:
    """Tests for GET /api/v1/stats/dashboard."""

    def test_response_structure(self, client: TestClient):
        """Test stats endpoint returns correct structure."""
        response = client.get("/api/v1/stats/dashboard")
        assert response.status_code == 200
        data = response.json()

        # Verify structure exists
        assert "designs" in data
        assert "total" in data["designs"]
        assert "discovered" in data["designs"]
        assert "channels" in data
        assert "total" in data["channels"]
        assert "discovered_channels" in data
        assert "downloads" in data
        assert "today" in data["downloads"]

    @pytest.mark.asyncio
    async def test_with_data(self, client: TestClient, test_session: AsyncSession):
        """Test stats with actual data."""
        # Get initial counts
        initial_response = client.get("/api/v1/stats/dashboard")
        initial_data = initial_response.json()
        initial_designs = initial_data["designs"]["total"]
        initial_discovered = initial_data["designs"]["discovered"]

        # Create a channel
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Test Channel",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.flush()

        # Create designs with different statuses
        statuses = [
            DesignStatus.DISCOVERED,
            DesignStatus.DISCOVERED,
            DesignStatus.WANTED,
            DesignStatus.DOWNLOADED,
            DesignStatus.ORGANIZED,
        ]
        for i, status in enumerate(statuses):
            design = Design(
                canonical_title=f"Stats Test Design {i}",
                status=status,
            )
            test_session.add(design)

        # Create discovered channel
        dc = DiscoveredChannel(
            username=f"discovered_{uuid.uuid4().hex[:8]}",
            source_types=[DiscoverySourceType.MENTION.value],
        )
        test_session.add(dc)

        await test_session.commit()

        response = client.get("/api/v1/stats/dashboard")
        assert response.status_code == 200
        data = response.json()

        # Check that counts increased by expected amounts
        assert data["designs"]["total"] >= initial_designs + 5
        assert data["designs"]["discovered"] >= initial_discovered + 2
        assert data["channels"]["total"] >= 1
        assert data["discovered_channels"] >= 1


class TestDashboardCalendarEndpoint:
    """Tests for GET /api/v1/stats/dashboard/calendar."""

    def test_calendar_structure(self, client: TestClient):
        """Test calendar endpoint returns correct structure."""
        response = client.get("/api/v1/stats/dashboard/calendar")
        assert response.status_code == 200
        data = response.json()

        assert "days" in data
        assert len(data["days"]) == 14  # Default 14 days
        assert "total_period" in data

        # Check each day has expected structure
        for day in data["days"]:
            assert "date" in day
            assert "count" in day
            assert "designs" in day

    @pytest.mark.asyncio
    async def test_calendar_with_designs(
        self, client: TestClient, test_session: AsyncSession
    ):
        """Test calendar with designs on different dates."""
        now = datetime.now(timezone.utc)

        # Get initial count
        initial_response = client.get("/api/v1/stats/dashboard/calendar")
        initial_data = initial_response.json()
        initial_total = initial_data["total_period"]

        # Create designs on different days
        for i in range(3):
            design = Design(
                canonical_title=f"Calendar Test Design {i}",
                status=DesignStatus.DISCOVERED,
                created_at=now - timedelta(days=i),
            )
            test_session.add(design)

        await test_session.commit()

        response = client.get("/api/v1/stats/dashboard/calendar")
        assert response.status_code == 200
        data = response.json()

        # Check total increased
        assert data["total_period"] >= initial_total + 3

        # Check that today has at least 1 design
        today_data = next(
            (day for day in data["days"] if day["date"] == now.date().isoformat()),
            None,
        )
        assert today_data is not None
        assert today_data["count"] >= 1

    def test_calendar_custom_days(self, client: TestClient):
        """Test calendar with custom day count."""
        response = client.get("/api/v1/stats/dashboard/calendar?days=7")
        assert response.status_code == 200
        data = response.json()

        assert len(data["days"]) == 7

    def test_calendar_invalid_days(self, client: TestClient):
        """Test calendar with invalid day count."""
        response = client.get("/api/v1/stats/dashboard/calendar?days=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/v1/stats/dashboard/calendar?days=100")
        assert response.status_code == 422  # Validation error


class TestDashboardQueueEndpoint:
    """Tests for GET /api/v1/stats/dashboard/queue."""

    def test_empty_queue(self, client: TestClient):
        """Test queue with no jobs."""
        response = client.get("/api/v1/stats/dashboard/queue")
        assert response.status_code == 200
        data = response.json()

        assert data["running"] == 0
        assert data["queued"] == 0
        assert data["recent_completions"] == []
        assert data["recent_failures"] == []

    @pytest.mark.asyncio
    async def test_queue_with_jobs(
        self, client: TestClient, test_session: AsyncSession
    ):
        """Test queue with active and completed jobs."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Queue Test Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.flush()

        # Create queued job
        queued_job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.QUEUED,
            channel_id=channel.id,
        )
        test_session.add(queued_job)

        # Create running job
        running_job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.RUNNING,
            channel_id=channel.id,
            started_at=datetime.now(timezone.utc),
        )
        test_session.add(running_job)

        # Create completed job
        completed_job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.SUCCESS,
            channel_id=channel.id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            finished_at=datetime.now(timezone.utc) - timedelta(minutes=4),
        )
        test_session.add(completed_job)

        # Create failed job
        failed_job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.FAILED,
            channel_id=channel.id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            finished_at=datetime.now(timezone.utc) - timedelta(minutes=9),
            last_error="Test error",
        )
        test_session.add(failed_job)

        await test_session.commit()

        response = client.get("/api/v1/stats/dashboard/queue")
        assert response.status_code == 200
        data = response.json()

        assert data["running"] >= 1
        assert data["queued"] >= 1
        assert len(data["recent_completions"]) >= 1
        assert len(data["recent_failures"]) >= 1

        # Check failure has error message
        failure = data["recent_failures"][0]
        assert failure["error"] == "Test error"


class TestDashboardStorageEndpoint:
    """Tests for GET /api/v1/stats/dashboard/storage."""

    def test_storage_endpoint(self, client: TestClient):
        """Test storage endpoint returns valid response."""
        clear_storage_cache()

        response = client.get("/api/v1/stats/dashboard/storage")
        assert response.status_code == 200
        data = response.json()

        # All sizes should be non-negative
        assert data["library_size_bytes"] >= 0
        assert data["staging_size_bytes"] >= 0
        assert data["cache_size_bytes"] >= 0
        assert data["available_bytes"] >= 0
        assert data["total_bytes"] >= 0


class TestDashboardServiceUnit:
    """Unit tests for DashboardService."""

    @pytest.mark.asyncio
    async def test_get_design_status_counts_structure(self, test_session: AsyncSession):
        """Test design status counting returns correct structure."""
        service = DashboardService(test_session)
        counts = await service._get_design_status_counts()

        # Verify structure
        assert hasattr(counts, 'discovered')
        assert hasattr(counts, 'wanted')
        assert hasattr(counts, 'downloaded')
        assert hasattr(counts, 'imported')
        assert hasattr(counts, 'failed')
        assert hasattr(counts, 'total')

        # All counts should be non-negative
        assert counts.discovered >= 0
        assert counts.total >= 0

    @pytest.mark.asyncio
    async def test_get_channel_counts(self, test_session: AsyncSession):
        """Test channel counting."""
        # Get initial counts
        service = DashboardService(test_session)
        initial = await service._get_channel_counts()

        channel1 = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Enabled",
            is_enabled=True,
            download_mode=DownloadMode.MANUAL,
        )
        channel2 = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Disabled",
            is_enabled=False,
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add_all([channel1, channel2])
        await test_session.commit()

        counts = await service._get_channel_counts()

        assert counts.enabled >= initial.enabled + 1
        assert counts.disabled >= initial.disabled + 1
        assert counts.total >= initial.total + 2

    @pytest.mark.asyncio
    async def test_get_download_stats_today(self, test_session: AsyncSession):
        """Test download stats for today."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Download Test",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.flush()

        # Create completed job today
        job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.SUCCESS,
            channel_id=channel.id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            finished_at=datetime.now(timezone.utc),
        )
        test_session.add(job)
        await test_session.commit()

        service = DashboardService(test_session)
        stats = await service._get_download_stats()

        assert stats.today >= 1
        assert stats.this_week >= 1

    @pytest.mark.asyncio
    async def test_storage_cache(self, test_session: AsyncSession):
        """Test that storage results are cached."""
        clear_storage_cache()

        service = DashboardService(test_session)

        # First call - should calculate
        result1 = await service.get_storage()

        # Second call - should use cache
        result2 = await service.get_storage()

        # Results should be identical (from cache)
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_calendar_includes_all_days(self, test_session: AsyncSession):
        """Test calendar includes all days even without designs."""
        service = DashboardService(test_session)
        response = await service.get_calendar(days=7)

        assert len(response.days) == 7

        # All days should be present even if count is 0
        for day in response.days:
            assert day.count >= 0


class TestLegacyStatsEndpoint:
    """Tests for legacy GET /api/v1/stats/ endpoint."""

    def test_legacy_stats(self, client: TestClient):
        """Test that legacy stats endpoint still works."""
        response = client.get("/api/v1/stats/")
        assert response.status_code == 200
        data = response.json()

        assert "channels_count" in data
        assert "designs_count" in data
        assert "downloads_active" in data
