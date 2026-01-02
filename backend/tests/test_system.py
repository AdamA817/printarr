"""Tests for system API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Job, JobStatus, JobType
from app.main import app
from app.db import get_db


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def db_engine():
    """Create an in-memory test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def client(db_session):
    """Create a test client with database override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# =============================================================================
# Tests for GET /api/v1/system/activity
# =============================================================================


class TestSystemActivityEndpoint:
    """Tests for the system activity endpoint."""

    async def test_activity_returns_200(self, client):
        """Test that activity endpoint returns 200."""
        response = await client.get("/api/v1/system/activity")
        assert response.status_code == 200

    async def test_activity_returns_correct_structure(self, client):
        """Test that activity response has correct structure."""
        response = await client.get("/api/v1/system/activity")
        data = response.json()

        # Check top-level keys
        assert "sync" in data
        assert "downloads" in data
        assert "images" in data
        assert "analysis" in data
        assert "summary" in data

        # Check sync structure
        assert "channels_syncing" in data["sync"]
        assert "backfills_running" in data["sync"]

        # Check downloads structure
        assert "active" in data["downloads"]
        assert "queued" in data["downloads"]

        # Check images structure
        assert "telegram_downloading" in data["images"]
        assert "previews_generating" in data["images"]

        # Check analysis structure
        assert "archives_extracting" in data["analysis"]
        assert "importing_to_library" in data["analysis"]
        assert "analyzing_3mf" in data["analysis"]

        # Check summary structure
        assert "total_active" in data["summary"]
        assert "total_queued" in data["summary"]
        assert "is_idle" in data["summary"]

    async def test_activity_idle_when_no_jobs(self, client):
        """Test that is_idle is True when no jobs exist."""
        response = await client.get("/api/v1/system/activity")
        data = response.json()

        assert data["summary"]["is_idle"] is True
        assert data["summary"]["total_active"] == 0
        assert data["summary"]["total_queued"] == 0

    async def test_activity_counts_running_jobs(self, client, db_session):
        """Test that running jobs are counted correctly."""
        # Create running download job
        job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.RUNNING,
        )
        db_session.add(job)
        await db_session.commit()

        response = await client.get("/api/v1/system/activity")
        data = response.json()

        assert data["downloads"]["active"] == 1
        assert data["summary"]["total_active"] == 1
        assert data["summary"]["is_idle"] is False

    async def test_activity_counts_queued_jobs(self, client, db_session):
        """Test that queued jobs are counted correctly."""
        # Create queued download job
        job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.QUEUED,
        )
        db_session.add(job)
        await db_session.commit()

        response = await client.get("/api/v1/system/activity")
        data = response.json()

        assert data["downloads"]["queued"] == 1
        assert data["summary"]["total_queued"] == 1
        assert data["summary"]["is_idle"] is False

    async def test_activity_counts_multiple_job_types(self, client, db_session):
        """Test that multiple job types are counted correctly."""
        # Create various jobs
        jobs = [
            Job(type=JobType.SYNC_CHANNEL_LIVE, status=JobStatus.RUNNING),
            Job(type=JobType.BACKFILL_CHANNEL, status=JobStatus.RUNNING),
            Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.RUNNING),
            Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.QUEUED),
            Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.QUEUED),
            Job(type=JobType.DOWNLOAD_TELEGRAM_IMAGES, status=JobStatus.RUNNING),
            Job(type=JobType.EXTRACT_ARCHIVE, status=JobStatus.RUNNING),
        ]
        for job in jobs:
            db_session.add(job)
        await db_session.commit()

        response = await client.get("/api/v1/system/activity")
        data = response.json()

        assert data["sync"]["channels_syncing"] == 1
        assert data["sync"]["backfills_running"] == 1
        assert data["downloads"]["active"] == 1
        assert data["downloads"]["queued"] == 2
        assert data["images"]["telegram_downloading"] == 1
        assert data["analysis"]["archives_extracting"] == 1
        assert data["summary"]["total_active"] == 5
        assert data["summary"]["total_queued"] == 2

    async def test_activity_ignores_completed_jobs(self, client, db_session):
        """Test that completed jobs are not counted."""
        # Create completed jobs
        jobs = [
            Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.SUCCESS),
            Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.FAILED),
            Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.CANCELED),
        ]
        for job in jobs:
            db_session.add(job)
        await db_session.commit()

        response = await client.get("/api/v1/system/activity")
        data = response.json()

        assert data["summary"]["is_idle"] is True
        assert data["summary"]["total_active"] == 0
        assert data["summary"]["total_queued"] == 0
