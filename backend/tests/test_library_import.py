"""Tests for LibraryImportService - library file organization."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Channel,
    Design,
    DesignFile,
    DesignSource,
    DesignStatus,
    FileKind,
    JobType,
    ModelKind,
    TelegramMessage,
)
from app.services.library import (
    DEFAULT_TEMPLATE,
    INVALID_CHARS,
    LibraryError,
    LibraryImportService,
)


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
def mock_session_maker(db_engine):
    """Create a mock session maker that uses the test database."""
    test_session_maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    @asynccontextmanager
    async def mock_maker():
        async with test_session_maker() as session:
            yield session

    return mock_maker


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
async def sample_message(db_session, sample_channel):
    """Create a sample Telegram message."""
    from datetime import datetime

    message = TelegramMessage(
        channel_id=sample_channel.id,
        telegram_message_id=12345,
        date_posted=datetime.utcnow(),
        caption_text="Test message",
    )
    db_session.add(message)
    await db_session.flush()
    return message


@pytest.fixture
async def sample_design(db_session):
    """Create a sample design for testing."""
    design = Design(
        canonical_title="Test Design",
        canonical_designer="Test Designer",
        status=DesignStatus.EXTRACTED,
    )
    db_session.add(design)
    await db_session.flush()
    return design


@pytest.fixture
async def design_with_source(db_session, sample_design, sample_message, sample_channel):
    """Create a design with a linked source."""
    source = DesignSource(
        design_id=sample_design.id,
        message_id=sample_message.id,
        channel_id=sample_channel.id,
    )
    db_session.add(source)
    await db_session.flush()
    return sample_design


@pytest.fixture
def temp_dirs(tmp_path, sample_design):
    """Create temporary staging and library directories."""
    staging = tmp_path / "staging" / sample_design.id
    staging.mkdir(parents=True)
    library = tmp_path / "library"
    library.mkdir(parents=True)
    return {"staging": staging, "library": library, "staging_root": tmp_path / "staging"}


# =============================================================================
# Constants Tests
# =============================================================================


class TestLibraryConstants:
    """Tests for library import constants."""

    def test_default_template(self):
        """Verify default template structure."""
        assert DEFAULT_TEMPLATE == "{designer}/{channel}/{title}"

    def test_invalid_chars_pattern(self):
        """Verify invalid characters pattern."""
        test_string = 'file/with\\invalid:chars*and?"more<>|'
        sanitized = INVALID_CHARS.sub("_", test_string)
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert ":" not in sanitized
        assert "*" not in sanitized
        assert "?" not in sanitized
        assert '"' not in sanitized
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "|" not in sanitized


# =============================================================================
# LibraryImportService Initialization Tests
# =============================================================================


class TestLibraryImportServiceInit:
    """Tests for LibraryImportService initialization."""

    def test_init_creates_service(self, db_session):
        """Test that service can be initialized."""
        service = LibraryImportService(db_session)
        assert service.db == db_session


# =============================================================================
# Sanitize Name Tests
# =============================================================================


class TestSanitizeName:
    """Tests for _sanitize_name method."""

    def test_sanitizes_invalid_characters(self, db_session):
        """Test that invalid characters are replaced."""
        service = LibraryImportService(db_session)

        result = service._sanitize_name('Test/Design\\With:Invalid*Chars?"<>|')

        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result
        assert "*" not in result

    def test_collapses_multiple_underscores(self, db_session):
        """Test that multiple underscores are collapsed."""
        service = LibraryImportService(db_session)

        result = service._sanitize_name("Test___Name")

        assert "___" not in result
        assert result == "Test_Name"

    def test_trims_whitespace_and_underscores(self, db_session):
        """Test that leading/trailing whitespace and underscores are trimmed."""
        service = LibraryImportService(db_session)

        result = service._sanitize_name("  _Test Name_  ")

        assert not result.startswith(" ")
        assert not result.endswith(" ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_limits_length(self, db_session):
        """Test that long names are truncated."""
        service = LibraryImportService(db_session)
        long_name = "A" * 300

        result = service._sanitize_name(long_name)

        assert len(result) <= 200

    def test_fallback_for_empty_name(self, db_session):
        """Test that empty names fallback to 'Unknown'."""
        service = LibraryImportService(db_session)

        result = service._sanitize_name("   ")

        assert result == "Unknown"


# =============================================================================
# Resolve Collision Tests
# =============================================================================


class TestResolveCollision:
    """Tests for _resolve_collision method."""

    def test_returns_original_if_no_collision(self, db_session, tmp_path):
        """Test that original filename is returned if no collision."""
        service = LibraryImportService(db_session)

        result = service._resolve_collision(tmp_path, "model.stl")

        assert result == "model.stl"

    def test_appends_suffix_on_collision(self, db_session, tmp_path):
        """Test that numeric suffix is appended on collision."""
        # Create existing file
        (tmp_path / "model.stl").touch()

        service = LibraryImportService(db_session)

        result = service._resolve_collision(tmp_path, "model.stl")

        assert result == "model_1.stl"

    def test_increments_suffix_for_multiple_collisions(self, db_session, tmp_path):
        """Test that suffix increments for multiple collisions."""
        # Create existing files
        (tmp_path / "model.stl").touch()
        (tmp_path / "model_1.stl").touch()
        (tmp_path / "model_2.stl").touch()

        service = LibraryImportService(db_session)

        result = service._resolve_collision(tmp_path, "model.stl")

        assert result == "model_3.stl"

    def test_preserves_extension(self, db_session, tmp_path):
        """Test that file extension is preserved."""
        (tmp_path / "model.3mf").touch()

        service = LibraryImportService(db_session)

        result = service._resolve_collision(tmp_path, "model.3mf")

        assert result.endswith(".3mf")


# =============================================================================
# Import Design Tests
# =============================================================================


class TestImportDesign:
    """Tests for import_design method."""

    @pytest.mark.asyncio
    async def test_import_design_not_found(self, db_session, mock_session_maker):
        """Test import raises error for non-existent design."""
        service = LibraryImportService(db_session)

        with patch("app.services.library.async_session_maker", mock_session_maker):
            with pytest.raises(LibraryError) as exc_info:
                await service.import_design("nonexistent-id")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_import_staging_not_found(self, db_session, sample_design, mock_session_maker):
        """Test import raises error when staging dir missing."""
        await db_session.commit()

        with patch("app.services.library.settings") as mock_settings:
            mock_settings.staging_path = Path("/nonexistent")

            with patch("app.services.library.async_session_maker", mock_session_maker):
                service = LibraryImportService(db_session)

                with pytest.raises(LibraryError) as exc_info:
                    await service.import_design(sample_design.id)

                assert "staging directory not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_import_moves_files(
        self, db_session, design_with_source, temp_dirs, mock_session_maker
    ):
        """Test that files are moved from staging to library."""
        # Create a test file in staging
        test_file = temp_dirs["staging"] / "model.stl"
        test_file.write_bytes(b"STL content")

        # Create DesignFile record
        design_file = DesignFile(
            design_id=design_with_source.id,
            relative_path="model.stl",
            filename="model.stl",
            ext=".stl",
            size_bytes=11,
            file_kind=FileKind.MODEL,
            model_kind=ModelKind.STL,
            is_from_archive=True,
        )
        db_session.add(design_file)
        await db_session.flush()
        await db_session.commit()

        with patch("app.services.library.settings") as mock_settings:
            mock_settings.staging_path = temp_dirs["staging_root"]
            mock_settings.library_path = temp_dirs["library"]
            mock_settings.library_template_global = "{designer}/{title}"

            with patch("app.services.library.async_session_maker", mock_session_maker):
                service = LibraryImportService(db_session)
                result = await service.import_design(design_with_source.id)

                assert result["files_imported"] == 1
                assert not test_file.exists()  # Original moved

    @pytest.mark.asyncio
    async def test_import_updates_design_status(
        self, db_session, design_with_source, temp_dirs, mock_session_maker
    ):
        """Test that design status is updated to ORGANIZED."""
        # Create a test file in staging
        test_file = temp_dirs["staging"] / "model.stl"
        test_file.write_bytes(b"STL content")

        # Create DesignFile record
        design_file = DesignFile(
            design_id=design_with_source.id,
            relative_path="model.stl",
            filename="model.stl",
            ext=".stl",
            size_bytes=11,
            file_kind=FileKind.MODEL,
            model_kind=ModelKind.STL,
            is_from_archive=True,
        )
        db_session.add(design_file)
        await db_session.flush()
        await db_session.commit()

        with patch("app.services.library.settings") as mock_settings:
            mock_settings.staging_path = temp_dirs["staging_root"]
            mock_settings.library_path = temp_dirs["library"]
            mock_settings.library_template_global = "{designer}/{title}"

            with patch("app.services.library.async_session_maker", mock_session_maker):
                service = LibraryImportService(db_session)
                await service.import_design(design_with_source.id)

                await db_session.refresh(design_with_source)
                assert design_with_source.status == DesignStatus.ORGANIZED


# =============================================================================
# ImportToLibraryWorker Tests
# =============================================================================


class TestImportToLibraryWorker:
    """Tests for ImportToLibraryWorker class."""

    def test_worker_handles_import_jobs(self):
        """Test worker is configured to handle IMPORT_TO_LIBRARY jobs."""
        from app.workers.library_import import ImportToLibraryWorker

        worker = ImportToLibraryWorker()

        assert JobType.IMPORT_TO_LIBRARY in worker.job_types

    def test_worker_has_default_poll_interval(self):
        """Test worker has sensible default poll interval."""
        from app.workers.library_import import ImportToLibraryWorker

        worker = ImportToLibraryWorker()

        assert worker.poll_interval == 1.0

    def test_worker_accepts_custom_poll_interval(self):
        """Test worker accepts custom poll interval."""
        from app.workers.library_import import ImportToLibraryWorker

        worker = ImportToLibraryWorker(poll_interval=2.0)

        assert worker.poll_interval == 2.0

    def test_worker_accepts_worker_id(self):
        """Test worker accepts custom worker ID."""
        from app.workers.library_import import ImportToLibraryWorker

        worker = ImportToLibraryWorker(worker_id="import-worker-1")

        assert worker.worker_id == "import-worker-1"
