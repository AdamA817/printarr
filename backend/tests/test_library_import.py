"""Tests for LibraryImportService - library file organization."""

from __future__ import annotations

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
    message = TelegramMessage(
        channel_id=sample_channel.id,
        telegram_message_id=12345,
        message_text="Test message",
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
async def design_with_source(db_session, sample_design, sample_message):
    """Create a design with a linked source."""
    source = DesignSource(
        design_id=sample_design.id,
        message_id=sample_message.id,
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
# Build Library Path Tests
# =============================================================================


class TestBuildLibraryPath:
    """Tests for _build_library_path method."""

    @pytest.mark.asyncio
    async def test_substitutes_designer(self, db_session, design_with_source, tmp_path):
        """Test that {designer} is substituted."""
        with patch("app.services.library.settings") as mock_settings:
            mock_settings.library_path = tmp_path
            mock_settings.library_template_global = "{designer}"

            service = LibraryImportService(db_session)
            design = await service._get_design_with_files(design_with_source.id)

            path = await service._build_library_path(design, "{designer}")

            assert "Test_Designer" in str(path)

    @pytest.mark.asyncio
    async def test_substitutes_channel(
        self, db_session, design_with_source, sample_channel, tmp_path
    ):
        """Test that {channel} is substituted."""
        with patch("app.services.library.settings") as mock_settings:
            mock_settings.library_path = tmp_path
            mock_settings.library_template_global = "{channel}"

            service = LibraryImportService(db_session)
            design = await service._get_design_with_files(design_with_source.id)

            path = await service._build_library_path(design, "{channel}")

            assert "Test_Channel" in str(path)

    @pytest.mark.asyncio
    async def test_substitutes_title(self, db_session, design_with_source, tmp_path):
        """Test that {title} is substituted."""
        with patch("app.services.library.settings") as mock_settings:
            mock_settings.library_path = tmp_path
            mock_settings.library_template_global = "{title}"

            service = LibraryImportService(db_session)
            design = await service._get_design_with_files(design_with_source.id)

            path = await service._build_library_path(design, "{title}")

            assert "Test_Design" in str(path)


# =============================================================================
# Template Resolution Tests
# =============================================================================


class TestGetTemplate:
    """Tests for _get_template method."""

    @pytest.mark.asyncio
    async def test_uses_channel_override_if_set(
        self, db_session, design_with_source, sample_channel
    ):
        """Test that channel override template is used when set."""
        sample_channel.library_template_override = "{designer}/{title}"
        await db_session.flush()

        service = LibraryImportService(db_session)
        design = await service._get_design_with_files(design_with_source.id)

        template = await service._get_template(design)

        assert template == "{designer}/{title}"

    @pytest.mark.asyncio
    async def test_uses_global_template_if_no_override(
        self, db_session, design_with_source
    ):
        """Test that global template is used when no channel override."""
        with patch("app.services.library.settings") as mock_settings:
            mock_settings.library_template_global = "{channel}/{designer}/{title}"

            service = LibraryImportService(db_session)
            design = await service._get_design_with_files(design_with_source.id)

            template = await service._get_template(design)

            assert template == "{channel}/{designer}/{title}"


# =============================================================================
# Import Design Tests
# =============================================================================


class TestImportDesign:
    """Tests for import_design method."""

    @pytest.mark.asyncio
    async def test_import_design_not_found(self, db_session):
        """Test import raises error for non-existent design."""
        service = LibraryImportService(db_session)

        with pytest.raises(LibraryError) as exc_info:
            await service.import_design("nonexistent-id")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_import_staging_not_found(self, db_session, sample_design):
        """Test import raises error when staging dir missing."""
        with patch("app.services.library.settings") as mock_settings:
            mock_settings.staging_path = Path("/nonexistent")

            service = LibraryImportService(db_session)

            with pytest.raises(LibraryError) as exc_info:
                await service.import_design(sample_design.id)

            assert "staging directory not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_import_moves_files(
        self, db_session, design_with_source, temp_dirs
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

        with patch("app.services.library.settings") as mock_settings:
            mock_settings.staging_path = temp_dirs["staging_root"]
            mock_settings.library_path = temp_dirs["library"]
            mock_settings.library_template_global = "{designer}/{title}"

            service = LibraryImportService(db_session)
            result = await service.import_design(design_with_source.id)

            assert result["files_imported"] == 1
            assert not test_file.exists()  # Original moved

    @pytest.mark.asyncio
    async def test_import_updates_design_status(
        self, db_session, design_with_source, temp_dirs
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

        with patch("app.services.library.settings") as mock_settings:
            mock_settings.staging_path = temp_dirs["staging_root"]
            mock_settings.library_path = temp_dirs["library"]
            mock_settings.library_template_global = "{designer}/{title}"

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
