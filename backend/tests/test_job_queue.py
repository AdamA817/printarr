"""Tests for JobQueueService - job queue management."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Channel, Design, DesignStatus, Job, JobStatus, JobType
from app.services.job_queue import JobQueueService


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


# =============================================================================
# Enqueue Tests
# =============================================================================


class TestEnqueue:
    """Tests for enqueue method."""

    @pytest.mark.asyncio
    async def test_enqueue_creates_job(self, db_session):
        """Test that enqueue creates a new job."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)

        assert job is not None
        assert job.id is not None
        assert job.type == JobType.DOWNLOAD_DESIGN
        assert job.status == JobStatus.QUEUED
        assert job.priority == 0
        assert job.attempts == 0

    @pytest.mark.asyncio
    async def test_enqueue_with_design_id(self, db_session, sample_design):
        """Test that enqueue can link to a design."""
        service = JobQueueService(db_session)

        job = await service.enqueue(
            JobType.DOWNLOAD_DESIGN,
            design_id=sample_design.id,
        )

        assert job.design_id == sample_design.id

    @pytest.mark.asyncio
    async def test_enqueue_with_channel_id(self, db_session, sample_channel):
        """Test that enqueue can link to a channel."""
        service = JobQueueService(db_session)

        job = await service.enqueue(
            JobType.BACKFILL_CHANNEL,
            channel_id=sample_channel.id,
        )

        assert job.channel_id == sample_channel.id

    @pytest.mark.asyncio
    async def test_enqueue_with_payload(self, db_session):
        """Test that enqueue stores payload as JSON."""
        service = JobQueueService(db_session)

        payload = {"file_id": "abc123", "size": 1000}
        job = await service.enqueue(
            JobType.DOWNLOAD_DESIGN,
            payload=payload,
        )

        assert job.payload_json is not None
        # Verify round-trip
        parsed = service.get_payload(job)
        assert parsed == payload

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, db_session):
        """Test that enqueue respects priority."""
        service = JobQueueService(db_session)

        job = await service.enqueue(
            JobType.DOWNLOAD_DESIGN,
            priority=10,
        )

        assert job.priority == 10

    @pytest.mark.asyncio
    async def test_enqueue_with_max_attempts(self, db_session):
        """Test that enqueue respects max_attempts."""
        service = JobQueueService(db_session)

        job = await service.enqueue(
            JobType.DOWNLOAD_DESIGN,
            max_attempts=5,
        )

        assert job.max_attempts == 5


# =============================================================================
# Dequeue Tests
# =============================================================================


class TestDequeue:
    """Tests for dequeue method."""

    @pytest.mark.asyncio
    async def test_dequeue_returns_job(self, db_session):
        """Test that dequeue returns a queued job."""
        service = JobQueueService(db_session)

        # Create a job
        created = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()

        # Dequeue it
        job = await service.dequeue()

        assert job is not None
        assert job.id == created.id
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.attempts == 1

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_empty(self, db_session):
        """Test that dequeue returns None when no jobs available."""
        service = JobQueueService(db_session)

        job = await service.dequeue()

        assert job is None

    @pytest.mark.asyncio
    async def test_dequeue_respects_priority(self, db_session):
        """Test that dequeue returns highest priority job first."""
        service = JobQueueService(db_session)

        # Create jobs with different priorities
        low = await service.enqueue(JobType.DOWNLOAD_DESIGN, priority=1)
        high = await service.enqueue(JobType.DOWNLOAD_DESIGN, priority=10)
        medium = await service.enqueue(JobType.DOWNLOAD_DESIGN, priority=5)
        await db_session.flush()

        # Dequeue should return highest priority first
        job = await service.dequeue()
        assert job.id == high.id

    @pytest.mark.asyncio
    async def test_dequeue_respects_created_at_for_same_priority(self, db_session):
        """Test that dequeue returns oldest job when priority is same."""
        service = JobQueueService(db_session)

        # Create jobs with same priority
        first = await service.enqueue(JobType.DOWNLOAD_DESIGN, priority=5)
        await db_session.flush()
        await asyncio.sleep(0.01)  # Ensure different timestamps
        second = await service.enqueue(JobType.DOWNLOAD_DESIGN, priority=5)
        await db_session.flush()

        # Dequeue should return first (oldest) job
        job = await service.dequeue()
        assert job.id == first.id

    @pytest.mark.asyncio
    async def test_dequeue_filters_by_job_type(self, db_session):
        """Test that dequeue can filter by job types."""
        service = JobQueueService(db_session)

        # Create different job types
        download = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        backfill = await service.enqueue(JobType.BACKFILL_CHANNEL)
        await db_session.flush()

        # Dequeue only backfill jobs
        job = await service.dequeue([JobType.BACKFILL_CHANNEL])

        assert job is not None
        assert job.id == backfill.id
        assert job.type == JobType.BACKFILL_CHANNEL

    @pytest.mark.asyncio
    async def test_dequeue_skips_running_jobs(self, db_session):
        """Test that dequeue doesn't return jobs that are already running."""
        service = JobQueueService(db_session)

        # Create and claim a job
        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()
        await service.dequeue()

        # Try to dequeue again - should return None
        result = await service.dequeue()
        assert result is None


# =============================================================================
# Complete Tests
# =============================================================================


class TestComplete:
    """Tests for complete method."""

    @pytest.mark.asyncio
    async def test_complete_success(self, db_session):
        """Test marking a job as successfully completed."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()
        await service.dequeue()

        result = await service.complete(job.id, success=True)

        assert result is not None
        assert result.status == JobStatus.SUCCESS
        assert result.finished_at is not None
        assert result.last_error is None

    @pytest.mark.asyncio
    async def test_complete_failure_with_retry(self, db_session):
        """Test that failed job is re-queued for retry."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN, max_attempts=3)
        await db_session.flush()
        await service.dequeue()

        result = await service.complete(job.id, success=False, error="Network error")

        assert result is not None
        assert result.status == JobStatus.QUEUED  # Re-queued for retry
        assert result.last_error == "Network error"
        assert result.started_at is None
        assert result.finished_at is None

    @pytest.mark.asyncio
    async def test_complete_failure_max_attempts_reached(self, db_session):
        """Test that job fails when max attempts reached."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN, max_attempts=1)
        await db_session.flush()
        await service.dequeue()

        result = await service.complete(job.id, success=False, error="Network error")

        assert result is not None
        assert result.status == JobStatus.FAILED  # No more retries
        assert result.last_error == "Network error"
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_complete_not_found(self, db_session):
        """Test completing a non-existent job."""
        service = JobQueueService(db_session)

        result = await service.complete("nonexistent-id", success=True)

        assert result is None


# =============================================================================
# Cancel Tests
# =============================================================================


class TestCancel:
    """Tests for cancel method."""

    @pytest.mark.asyncio
    async def test_cancel_queued_job(self, db_session):
        """Test canceling a queued job."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()

        result = await service.cancel(job.id)

        assert result is not None
        assert result.status == JobStatus.CANCELED
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, db_session):
        """Test canceling a running job."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()
        await service.dequeue()

        result = await service.cancel(job.id)

        assert result is not None
        assert result.status == JobStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(self, db_session):
        """Test that canceling a completed job returns None."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()
        await service.dequeue()
        await service.complete(job.id, success=True)

        result = await service.cancel(job.id)

        assert result is None  # Can't cancel completed job

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, db_session):
        """Test canceling a non-existent job."""
        service = JobQueueService(db_session)

        result = await service.cancel("nonexistent-id")

        assert result is None


# =============================================================================
# Progress Update Tests
# =============================================================================


class TestUpdateProgress:
    """Tests for update_progress method."""

    @pytest.mark.asyncio
    async def test_update_progress(self, db_session):
        """Test updating job progress."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()

        await service.update_progress(job.id, 50, 100)
        await db_session.refresh(job)

        assert job.progress_current == 50
        assert job.progress_total == 100
        assert job.progress_percent == 50.0

    @pytest.mark.asyncio
    async def test_update_progress_current_only(self, db_session):
        """Test updating only current progress."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()

        await service.update_progress(job.id, 75)
        await db_session.refresh(job)

        assert job.progress_current == 75
        assert job.progress_total is None


# =============================================================================
# Queue Stats Tests
# =============================================================================


class TestGetQueueStats:
    """Tests for get_queue_stats method."""

    @pytest.mark.asyncio
    async def test_get_queue_stats_empty(self, db_session):
        """Test stats when queue is empty."""
        service = JobQueueService(db_session)

        stats = await service.get_queue_stats()

        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["by_type"] == {}

    @pytest.mark.asyncio
    async def test_get_queue_stats_with_jobs(self, db_session):
        """Test stats with various job states."""
        service = JobQueueService(db_session)

        # Create jobs in different states
        await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await service.enqueue(JobType.DOWNLOAD_DESIGN)
        job = await service.enqueue(JobType.BACKFILL_CHANNEL)
        await db_session.flush()
        await service.dequeue()  # Start one download job
        await service.cancel(job.id)  # Cancel the backfill job

        stats = await service.get_queue_stats()

        assert stats["total"] == 3
        assert stats["by_status"]["QUEUED"] == 1
        assert stats["by_status"]["RUNNING"] == 1
        assert stats["by_status"]["CANCELED"] == 1
        # by_type only counts active jobs (QUEUED + RUNNING)
        assert stats["by_type"]["DOWNLOAD_DESIGN"] == 2


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    async def test_get_job(self, db_session):
        """Test getting a job by ID."""
        service = JobQueueService(db_session)

        created = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()

        job = await service.get_job(created.id)

        assert job is not None
        assert job.id == created.id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, db_session):
        """Test getting a non-existent job."""
        service = JobQueueService(db_session)

        job = await service.get_job("nonexistent-id")

        assert job is None

    @pytest.mark.asyncio
    async def test_get_jobs_for_design(self, db_session, sample_design):
        """Test getting all jobs for a design."""
        service = JobQueueService(db_session)

        # Create multiple jobs for same design
        await service.enqueue(JobType.DOWNLOAD_DESIGN, design_id=sample_design.id)
        await service.enqueue(JobType.EXTRACT_ARCHIVE, design_id=sample_design.id)
        # And one for different design
        await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()

        jobs = await service.get_jobs_for_design(sample_design.id)

        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_get_jobs_for_design_with_status_filter(
        self, db_session, sample_design
    ):
        """Test getting jobs for design filtered by status."""
        service = JobQueueService(db_session)

        await service.enqueue(JobType.DOWNLOAD_DESIGN, design_id=sample_design.id)
        await service.enqueue(JobType.EXTRACT_ARCHIVE, design_id=sample_design.id)
        await db_session.flush()
        await service.dequeue()  # Start one job

        jobs = await service.get_jobs_for_design(
            sample_design.id, status=JobStatus.QUEUED
        )

        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_cancel_jobs_for_design(self, db_session, sample_design):
        """Test canceling all jobs for a design."""
        service = JobQueueService(db_session)

        await service.enqueue(JobType.DOWNLOAD_DESIGN, design_id=sample_design.id)
        await service.enqueue(JobType.EXTRACT_ARCHIVE, design_id=sample_design.id)
        await db_session.flush()

        count = await service.cancel_jobs_for_design(sample_design.id)

        assert count == 2

        # Verify jobs are canceled
        jobs = await service.get_jobs_for_design(sample_design.id)
        assert all(j.status == JobStatus.CANCELED for j in jobs)

    @pytest.mark.asyncio
    async def test_requeue_stale_jobs(self, db_session):
        """Test re-queuing stale jobs."""
        service = JobQueueService(db_session)

        # Create and start a job
        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)
        await db_session.flush()
        await service.dequeue()

        # Manually set started_at to be old
        job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.flush()

        # Requeue stale jobs (threshold: 30 minutes)
        count = await service.requeue_stale_jobs(stale_minutes=30)

        assert count == 1

        # Verify job is requeued
        await db_session.refresh(job)
        assert job.status == JobStatus.QUEUED
        assert job.started_at is None

    @pytest.mark.asyncio
    async def test_get_payload_none(self, db_session):
        """Test get_payload with no payload."""
        service = JobQueueService(db_session)

        job = await service.enqueue(JobType.DOWNLOAD_DESIGN)

        payload = service.get_payload(job)

        assert payload is None

    @pytest.mark.asyncio
    async def test_get_payload_returns_dict(self, db_session):
        """Test get_payload returns parsed dict."""
        service = JobQueueService(db_session)

        job = await service.enqueue(
            JobType.DOWNLOAD_DESIGN,
            payload={"test": "value", "number": 42},
        )

        payload = service.get_payload(job)

        assert payload == {"test": "value", "number": 42}
