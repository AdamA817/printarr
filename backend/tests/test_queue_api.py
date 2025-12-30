"""Tests for Queue and Activity API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Channel,
    Design,
    DesignSource,
    DesignStatus,
    Job,
    JobStatus,
    JobType,
    TelegramMessage,
)
from app.main import app


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
async def sample_channel(db_session):
    """Create a sample channel for testing."""
    channel = Channel(
        title="Test Channel",
        telegram_peer_id="test_peer_123",
        is_enabled=True,
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


@pytest.fixture
async def sample_design(db_session):
    """Create a sample design for testing."""
    design = Design(
        canonical_title="Test Design",
        canonical_designer="Test Designer",
        status=DesignStatus.DISCOVERED,
    )
    db_session.add(design)
    await db_session.flush()
    return design


@pytest.fixture
async def sample_job(db_session, sample_design):
    """Create a sample job for testing."""
    job = Job(
        type=JobType.DOWNLOAD_DESIGN,
        status=JobStatus.QUEUED,
        priority=5,
        design_id=sample_design.id,
    )
    db_session.add(job)
    await db_session.flush()
    return job


# =============================================================================
# Queue Schema Tests
# =============================================================================


class TestQueueSchemas:
    """Tests for queue response schemas."""

    def test_queue_item_response_schema(self):
        """Test QueueItemResponse schema fields."""
        from app.schemas.queue import QueueItemResponse

        # Verify schema has required fields
        assert "id" in QueueItemResponse.model_fields
        assert "job_type" in QueueItemResponse.model_fields
        assert "status" in QueueItemResponse.model_fields
        assert "priority" in QueueItemResponse.model_fields
        assert "design" in QueueItemResponse.model_fields

    def test_activity_item_response_schema(self):
        """Test ActivityItemResponse schema fields."""
        from app.schemas.queue import ActivityItemResponse

        # Verify schema has required fields
        assert "id" in ActivityItemResponse.model_fields
        assert "job_type" in ActivityItemResponse.model_fields
        assert "status" in ActivityItemResponse.model_fields
        assert "finished_at" in ActivityItemResponse.model_fields
        assert "duration_ms" in ActivityItemResponse.model_fields

    def test_queue_stats_response_schema(self):
        """Test QueueStatsResponse schema fields."""
        from app.schemas.queue import QueueStatsResponse

        # Verify schema has required fields
        assert "queued" in QueueStatsResponse.model_fields
        assert "downloading" in QueueStatsResponse.model_fields
        assert "extracting" in QueueStatsResponse.model_fields
        assert "importing" in QueueStatsResponse.model_fields
        assert "total_active" in QueueStatsResponse.model_fields


# =============================================================================
# Queue Service Tests
# =============================================================================


class TestQueueService:
    """Tests for queue service functionality."""

    @pytest.mark.asyncio
    async def test_job_queue_enqueue(self, db_session, sample_design):
        """Test enqueueing a job."""
        from app.services.job_queue import JobQueueService

        queue = JobQueueService(db_session)
        job = await queue.enqueue(
            JobType.DOWNLOAD_DESIGN,
            design_id=sample_design.id,
            priority=10,
        )

        assert job is not None
        assert job.type == JobType.DOWNLOAD_DESIGN
        assert job.status == JobStatus.QUEUED
        assert job.priority == 10
        assert job.design_id == sample_design.id

    @pytest.mark.asyncio
    async def test_job_queue_cancel(self, db_session, sample_job):
        """Test cancelling a job."""
        from app.services.job_queue import JobQueueService

        queue = JobQueueService(db_session)
        job = await queue.cancel(sample_job.id)

        assert job is not None
        assert job.status == JobStatus.CANCELED

    @pytest.mark.asyncio
    async def test_job_queue_stats(self, db_session, sample_job):
        """Test getting queue stats."""
        from app.services.job_queue import JobQueueService

        queue = JobQueueService(db_session)
        stats = await queue.get_queue_stats()

        assert "by_status" in stats
        assert "by_type" in stats
        assert "total" in stats


# =============================================================================
# Download Actions Tests
# =============================================================================


class TestDownloadActions:
    """Tests for design download action endpoints."""

    @pytest.mark.asyncio
    async def test_want_design_creates_job(self, db_session, sample_design):
        """Test that want action creates a download job."""
        from app.services.download import DownloadService

        service = DownloadService(db_session)
        job_id = await service.queue_download(sample_design.id, priority=5)

        assert job_id is not None

        # Verify design status changed
        await db_session.refresh(sample_design)
        assert sample_design.status == DesignStatus.WANTED

    @pytest.mark.asyncio
    async def test_cancel_jobs_for_design(self, db_session, sample_design):
        """Test cancelling all jobs for a design."""
        from app.services.job_queue import JobQueueService

        # Create multiple jobs
        queue = JobQueueService(db_session)
        await queue.enqueue(JobType.DOWNLOAD_DESIGN, design_id=sample_design.id)
        await queue.enqueue(JobType.EXTRACT_ARCHIVE, design_id=sample_design.id)
        await db_session.flush()

        # Cancel all
        count = await queue.cancel_jobs_for_design(sample_design.id)

        assert count == 2


# =============================================================================
# Route Handler Tests (Unit)
# =============================================================================


class TestQueueRoutes:
    """Unit tests for queue route handlers."""

    def test_progress_message_queued(self):
        """Test progress message for queued job."""
        from app.api.routes.queue import _get_progress_message

        job = Job(type=JobType.DOWNLOAD_DESIGN, status=JobStatus.QUEUED)
        msg = _get_progress_message(job)

        assert msg == "Waiting..."

    def test_progress_message_downloading(self):
        """Test progress message for downloading job."""
        from app.api.routes.queue import _get_progress_message

        job = Job(
            type=JobType.DOWNLOAD_DESIGN,
            status=JobStatus.RUNNING,
            progress_current=50,
            progress_total=100,
        )
        msg = _get_progress_message(job)

        assert "Downloading" in msg
        assert "50%" in msg

    def test_progress_message_extracting(self):
        """Test progress message for extracting job."""
        from app.api.routes.queue import _get_progress_message

        job = Job(type=JobType.EXTRACT_ARCHIVE, status=JobStatus.RUNNING)
        msg = _get_progress_message(job)

        assert "Extracting" in msg

    def test_progress_message_importing(self):
        """Test progress message for importing job."""
        from app.api.routes.queue import _get_progress_message

        job = Job(type=JobType.IMPORT_TO_LIBRARY, status=JobStatus.RUNNING)
        msg = _get_progress_message(job)

        assert "Organizing" in msg
