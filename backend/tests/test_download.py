"""Tests for DownloadService - design file downloads from Telegram."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Attachment,
    AttachmentDownloadStatus,
    Channel,
    Design,
    DesignSource,
    DesignStatus,
    JobType,
    TelegramMessage,
)
from app.services.download import ARCHIVE_EXTENSIONS, DownloadError, DownloadService


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
async def sample_message(db_session, sample_channel):
    """Create a sample Telegram message."""
    message = TelegramMessage(
        channel_id=sample_channel.id,
        telegram_message_id=12345,
        message_text="Test message with STL",
    )
    db_session.add(message)
    await db_session.flush()
    return message


@pytest.fixture
async def sample_attachment(db_session, sample_message):
    """Create a sample attachment."""
    attachment = Attachment(
        message_id=sample_message.id,
        filename="model.stl",
        ext=".stl",
        size_bytes=1000,
        is_candidate_design_file=True,
        download_status=AttachmentDownloadStatus.PENDING,
    )
    db_session.add(attachment)
    await db_session.flush()
    return attachment


@pytest.fixture
async def design_with_source(db_session, sample_design, sample_message, sample_attachment):
    """Create a design with a linked source and attachment."""
    source = DesignSource(
        design_id=sample_design.id,
        message_id=sample_message.id,
    )
    db_session.add(source)
    await db_session.flush()
    return sample_design


# =============================================================================
# Constants Tests
# =============================================================================


class TestArchiveExtensions:
    """Tests for archive extension constants."""

    def test_archive_extensions_contains_common_formats(self):
        """Verify common archive formats are included."""
        assert ".zip" in ARCHIVE_EXTENSIONS
        assert ".rar" in ARCHIVE_EXTENSIONS
        assert ".7z" in ARCHIVE_EXTENSIONS
        assert ".tar.gz" in ARCHIVE_EXTENSIONS
        assert ".tgz" in ARCHIVE_EXTENSIONS

    def test_archive_extensions_excludes_non_archives(self):
        """Verify non-archive formats are excluded."""
        assert ".stl" not in ARCHIVE_EXTENSIONS
        assert ".3mf" not in ARCHIVE_EXTENSIONS
        assert ".obj" not in ARCHIVE_EXTENSIONS


# =============================================================================
# DownloadService Initialization Tests
# =============================================================================


class TestDownloadServiceInit:
    """Tests for DownloadService initialization."""

    def test_init_creates_service(self, db_session):
        """Test that service can be initialized."""
        service = DownloadService(db_session)

        assert service.db == db_session
        assert service._telegram is None

    def test_telegram_property_lazy_loads(self, db_session):
        """Test that telegram property lazy-loads the service."""
        service = DownloadService(db_session)

        with patch("app.services.download.TelegramService") as mock_tg:
            mock_instance = MagicMock()
            mock_tg.get_instance.return_value = mock_instance

            result = service.telegram

            assert result == mock_instance
            mock_tg.get_instance.assert_called_once()


# =============================================================================
# Queue Download Tests
# =============================================================================


class TestQueueDownload:
    """Tests for queue_download method."""

    @pytest.mark.asyncio
    async def test_queue_download_creates_job(self, db_session, sample_design):
        """Test that queue_download creates a download job."""
        service = DownloadService(db_session)

        job_id = await service.queue_download(sample_design.id)
        await db_session.commit()

        assert job_id is not None
        # Design should be marked as WANTED
        await db_session.refresh(sample_design)
        assert sample_design.status == DesignStatus.WANTED

    @pytest.mark.asyncio
    async def test_queue_download_with_priority(self, db_session, sample_design):
        """Test queue_download respects priority."""
        service = DownloadService(db_session)

        job_id = await service.queue_download(sample_design.id, priority=10)
        await db_session.commit()

        assert job_id is not None

    @pytest.mark.asyncio
    async def test_queue_download_design_not_found(self, db_session):
        """Test queue_download raises error for non-existent design."""
        service = DownloadService(db_session)

        with pytest.raises(DownloadError) as exc_info:
            await service.queue_download("nonexistent-id")

        assert "not found" in str(exc_info.value).lower()


# =============================================================================
# Queue Extraction Tests
# =============================================================================


class TestQueueExtraction:
    """Tests for queue_extraction method."""

    @pytest.mark.asyncio
    async def test_queue_extraction_with_archives(
        self, db_session, design_with_source, sample_attachment
    ):
        """Test queue_extraction creates job when archives present."""
        # Update attachment to be an archive
        sample_attachment.ext = ".zip"
        sample_attachment.download_status = AttachmentDownloadStatus.DOWNLOADED
        await db_session.flush()

        service = DownloadService(db_session)

        job_id = await service.queue_extraction(design_with_source.id)
        await db_session.commit()

        assert job_id is not None

    @pytest.mark.asyncio
    async def test_queue_extraction_without_archives(
        self, db_session, design_with_source, sample_attachment
    ):
        """Test queue_extraction returns None when no archives."""
        # Attachment is .stl, not an archive
        sample_attachment.download_status = AttachmentDownloadStatus.DOWNLOADED
        await db_session.flush()

        service = DownloadService(db_session)

        job_id = await service.queue_extraction(design_with_source.id)

        assert job_id is None


# =============================================================================
# Get Design With Attachments Tests
# =============================================================================


class TestGetDesignWithAttachments:
    """Tests for _get_design_with_attachments method."""

    @pytest.mark.asyncio
    async def test_get_design_loads_relationships(
        self, db_session, design_with_source, sample_attachment
    ):
        """Test that design is loaded with all relationships."""
        service = DownloadService(db_session)

        design = await service._get_design_with_attachments(design_with_source.id)

        assert design is not None
        assert len(design.sources) == 1
        assert design.sources[0].message is not None
        assert len(design.sources[0].message.attachments) == 1

    @pytest.mark.asyncio
    async def test_get_design_not_found(self, db_session):
        """Test returns None for non-existent design."""
        service = DownloadService(db_session)

        design = await service._get_design_with_attachments("nonexistent-id")

        assert design is None


# =============================================================================
# Get Downloadable Attachments Tests
# =============================================================================


class TestGetDownloadableAttachments:
    """Tests for _get_downloadable_attachments method."""

    @pytest.mark.asyncio
    async def test_filters_candidate_files(
        self, db_session, design_with_source, sample_message, sample_attachment
    ):
        """Test that only candidate design files are returned."""
        # Add a non-candidate attachment
        non_candidate = Attachment(
            message_id=sample_message.id,
            filename="image.jpg",
            ext=".jpg",
            size_bytes=500,
            is_candidate_design_file=False,
            download_status=AttachmentDownloadStatus.PENDING,
        )
        db_session.add(non_candidate)
        await db_session.flush()

        service = DownloadService(db_session)
        design = await service._get_design_with_attachments(design_with_source.id)

        attachments = await service._get_downloadable_attachments(design)

        assert len(attachments) == 1
        assert attachments[0].filename == "model.stl"


# =============================================================================
# Staging Directory Tests
# =============================================================================


class TestStagingDir:
    """Tests for _get_staging_dir method."""

    def test_staging_dir_includes_design_id(self, db_session):
        """Test staging directory is based on design ID."""
        service = DownloadService(db_session)

        staging_dir = service._get_staging_dir("test-design-123")

        assert "test-design-123" in str(staging_dir)


# =============================================================================
# File Hash Tests
# =============================================================================


class TestComputeFileHash:
    """Tests for _compute_file_hash method."""

    @pytest.mark.asyncio
    async def test_computes_sha256(self, db_session, tmp_path):
        """Test that SHA256 is correctly computed."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        service = DownloadService(db_session)

        # Known SHA256 of "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        result = await service._compute_file_hash(test_file)

        assert result == expected


# =============================================================================
# Download Design Integration Tests
# =============================================================================


class TestDownloadDesign:
    """Integration tests for download_design method."""

    @pytest.mark.asyncio
    async def test_download_design_not_found(self, db_session):
        """Test download_design raises error for non-existent design."""
        service = DownloadService(db_session)

        with pytest.raises(DownloadError) as exc_info:
            await service.download_design("nonexistent-id")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_download_design_no_attachments(self, db_session, sample_design):
        """Test download_design raises error when no attachments."""
        # Create design source without attachment
        channel = Channel(
            title="Test Channel",
            telegram_peer_id="test_peer",
            is_enabled=True,
        )
        db_session.add(channel)
        await db_session.flush()

        message = TelegramMessage(
            channel_id=channel.id,
            telegram_message_id=999,
            message_text="Test",
        )
        db_session.add(message)
        await db_session.flush()

        source = DesignSource(
            design_id=sample_design.id,
            message_id=message.id,
        )
        db_session.add(source)
        await db_session.flush()

        service = DownloadService(db_session)

        with pytest.raises(DownloadError) as exc_info:
            await service.download_design(sample_design.id)

        assert "no attachments" in str(exc_info.value).lower()


# =============================================================================
# DownloadWorker Tests
# =============================================================================


class TestDownloadWorker:
    """Tests for DownloadWorker class."""

    def test_worker_handles_download_design_jobs(self):
        """Test worker is configured to handle DOWNLOAD_DESIGN jobs."""
        from app.workers.download import DownloadWorker

        worker = DownloadWorker()

        assert JobType.DOWNLOAD_DESIGN in worker.job_types

    def test_worker_has_default_poll_interval(self):
        """Test worker has sensible default poll interval."""
        from app.workers.download import DownloadWorker

        worker = DownloadWorker()

        assert worker.poll_interval == 1.0

    def test_worker_accepts_custom_poll_interval(self):
        """Test worker accepts custom poll interval."""
        from app.workers.download import DownloadWorker

        worker = DownloadWorker(poll_interval=2.0)

        assert worker.poll_interval == 2.0

    def test_worker_accepts_worker_id(self):
        """Test worker accepts custom worker ID."""
        from app.workers.download import DownloadWorker

        worker = DownloadWorker(worker_id="download-worker-1")

        assert worker.worker_id == "download-worker-1"
