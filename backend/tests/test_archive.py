"""Tests for ArchiveExtractor - archive extraction service."""

from __future__ import annotations

import tarfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Design,
    DesignFile,
    DesignStatus,
    FileKind,
    JobType,
    ModelKind,
)
from app.services.archive import (
    ARCHIVE_EXTENSIONS,
    MULTIPART_RAR_PATTERN,
    MULTIPART_RAR_SECONDARY,
    ArchiveError,
    ArchiveExtractor,
    CorruptedArchiveError,
    MissingPartError,
    PasswordProtectedError,
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
async def sample_design(db_session):
    """Create a sample design for testing."""
    design = Design(
        canonical_title="Test Design",
        canonical_designer="Test Designer",
        status=DesignStatus.DOWNLOADED,
    )
    db_session.add(design)
    await db_session.flush()
    return design


@pytest.fixture
def temp_staging(tmp_path, sample_design):
    """Create a temporary staging directory for a design."""
    staging = tmp_path / sample_design.id
    staging.mkdir(parents=True)
    return staging


# =============================================================================
# Constants Tests
# =============================================================================


class TestArchiveConstants:
    """Tests for archive extension constants."""

    def test_archive_extensions_contains_common_formats(self):
        """Verify common archive formats are included."""
        assert ".zip" in ARCHIVE_EXTENSIONS
        assert ".rar" in ARCHIVE_EXTENSIONS
        assert ".7z" in ARCHIVE_EXTENSIONS
        assert ".tar" in ARCHIVE_EXTENSIONS
        assert ".tar.gz" in ARCHIVE_EXTENSIONS
        assert ".tgz" in ARCHIVE_EXTENSIONS

    def test_multipart_rar_pattern_matches_part1(self):
        """Test multi-part RAR pattern matches first part."""
        assert MULTIPART_RAR_PATTERN.search("file.part1.rar")
        assert MULTIPART_RAR_PATTERN.search("file.part01.rar")
        assert MULTIPART_RAR_PATTERN.search("file.part001.rar")

    def test_multipart_rar_pattern_case_insensitive(self):
        """Test multi-part RAR pattern is case insensitive."""
        assert MULTIPART_RAR_PATTERN.search("FILE.PART1.RAR")
        assert MULTIPART_RAR_PATTERN.search("File.Part01.Rar")

    def test_multipart_rar_pattern_does_not_match_other_parts(self):
        """Test multi-part RAR pattern does not match parts 2+."""
        assert not MULTIPART_RAR_PATTERN.search("file.part2.rar")
        assert not MULTIPART_RAR_PATTERN.search("file.part10.rar")

    def test_multipart_rar_secondary_matches_parts_2_plus(self):
        """Test secondary pattern matches parts 2 and higher."""
        assert MULTIPART_RAR_SECONDARY.search("file.part2.rar")
        assert MULTIPART_RAR_SECONDARY.search("file.part02.rar")
        assert MULTIPART_RAR_SECONDARY.search("file.part10.rar")

    def test_multipart_rar_secondary_does_not_match_part1(self):
        """Test secondary pattern does not match part 1."""
        assert not MULTIPART_RAR_SECONDARY.search("file.part1.rar")
        assert not MULTIPART_RAR_SECONDARY.search("file.part01.rar")


# =============================================================================
# ArchiveExtractor Initialization Tests
# =============================================================================


class TestArchiveExtractorInit:
    """Tests for ArchiveExtractor initialization."""

    def test_init_creates_extractor(self, db_session):
        """Test that extractor can be initialized."""
        extractor = ArchiveExtractor(db_session)
        assert extractor.db == db_session


# =============================================================================
# Find Archives Tests
# =============================================================================


class TestFindArchives:
    """Tests for _find_archives method."""

    def test_finds_zip_files(self, db_session, temp_staging):
        """Test finding ZIP archives."""
        (temp_staging / "model.zip").touch()
        (temp_staging / "model.stl").touch()

        extractor = ArchiveExtractor(db_session)
        archives = extractor._find_archives(temp_staging)

        assert len(archives) == 1
        assert archives[0].name == "model.zip"

    def test_finds_multiple_formats(self, db_session, temp_staging):
        """Test finding multiple archive formats."""
        (temp_staging / "a.zip").touch()
        (temp_staging / "b.rar").touch()
        (temp_staging / "c.7z").touch()

        extractor = ArchiveExtractor(db_session)
        archives = extractor._find_archives(temp_staging)

        assert len(archives) == 3

    def test_finds_tar_gz_files(self, db_session, temp_staging):
        """Test finding .tar.gz archives."""
        (temp_staging / "archive.tar.gz").touch()
        (temp_staging / "archive.tgz").touch()

        extractor = ArchiveExtractor(db_session)
        archives = extractor._find_archives(temp_staging)

        assert len(archives) == 2

    def test_skips_secondary_multipart_rar(self, db_session, temp_staging):
        """Test that secondary multi-part RAR files are skipped."""
        (temp_staging / "archive.part1.rar").touch()
        (temp_staging / "archive.part2.rar").touch()
        (temp_staging / "archive.part3.rar").touch()

        extractor = ArchiveExtractor(db_session)
        archives = extractor._find_archives(temp_staging)

        assert len(archives) == 1
        assert archives[0].name == "archive.part1.rar"

    def test_returns_sorted_by_name(self, db_session, temp_staging):
        """Test archives are returned sorted by name."""
        (temp_staging / "c.zip").touch()
        (temp_staging / "a.zip").touch()
        (temp_staging / "b.zip").touch()

        extractor = ArchiveExtractor(db_session)
        archives = extractor._find_archives(temp_staging)

        names = [a.name for a in archives]
        assert names == ["a.zip", "b.zip", "c.zip"]


# =============================================================================
# File Classification Tests
# =============================================================================


class TestClassifyFile:
    """Tests for _classify_file method."""

    def test_classifies_model_files(self, db_session):
        """Test MODEL classification for 3D model files."""
        extractor = ArchiveExtractor(db_session)

        assert extractor._classify_file(".stl") == FileKind.MODEL
        assert extractor._classify_file(".3mf") == FileKind.MODEL
        assert extractor._classify_file(".obj") == FileKind.MODEL
        assert extractor._classify_file(".step") == FileKind.MODEL
        assert extractor._classify_file(".stp") == FileKind.MODEL

    def test_classifies_archive_files(self, db_session):
        """Test ARCHIVE classification for archive files."""
        extractor = ArchiveExtractor(db_session)

        assert extractor._classify_file(".zip") == FileKind.ARCHIVE
        assert extractor._classify_file(".rar") == FileKind.ARCHIVE
        assert extractor._classify_file(".7z") == FileKind.ARCHIVE

    def test_classifies_image_files(self, db_session):
        """Test IMAGE classification for image files."""
        extractor = ArchiveExtractor(db_session)

        assert extractor._classify_file(".jpg") == FileKind.IMAGE
        assert extractor._classify_file(".png") == FileKind.IMAGE
        assert extractor._classify_file(".gif") == FileKind.IMAGE

    def test_classifies_other_files(self, db_session):
        """Test OTHER classification for unknown files."""
        extractor = ArchiveExtractor(db_session)

        assert extractor._classify_file(".txt") == FileKind.OTHER
        assert extractor._classify_file(".pdf") == FileKind.OTHER
        assert extractor._classify_file(".gcode") == FileKind.OTHER


# =============================================================================
# ZIP Extraction Tests
# =============================================================================


class TestExtractZip:
    """Tests for _extract_zip method."""

    @pytest.mark.asyncio
    async def test_extracts_zip_files(self, db_session, temp_staging):
        """Test extracting files from a ZIP archive."""
        # Create a test ZIP file
        zip_path = temp_staging / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("model.stl", b"STL content")
            zf.writestr("readme.txt", b"README content")

        extractor = ArchiveExtractor(db_session)
        extracted = await extractor._extract_zip(zip_path, temp_staging)

        assert len(extracted) == 2
        assert (temp_staging / "model.stl").exists()
        assert (temp_staging / "readme.txt").exists()

    @pytest.mark.asyncio
    async def test_preserves_directory_structure(self, db_session, temp_staging):
        """Test that ZIP extraction preserves directory structure."""
        zip_path = temp_staging / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("models/part1.stl", b"Part 1")
            zf.writestr("models/part2.stl", b"Part 2")
            zf.writestr("docs/readme.txt", b"README")

        extractor = ArchiveExtractor(db_session)
        extracted = await extractor._extract_zip(zip_path, temp_staging)

        assert len(extracted) == 3
        assert (temp_staging / "models" / "part1.stl").exists()
        assert (temp_staging / "models" / "part2.stl").exists()
        assert (temp_staging / "docs" / "readme.txt").exists()

    @pytest.mark.asyncio
    async def test_skips_macosx_entries(self, db_session, temp_staging):
        """Test that __MACOSX entries are skipped."""
        zip_path = temp_staging / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("model.stl", b"STL content")
            zf.writestr("__MACOSX/model.stl", b"Mac metadata")

        extractor = ArchiveExtractor(db_session)
        extracted = await extractor._extract_zip(zip_path, temp_staging)

        assert len(extracted) == 1
        assert not (temp_staging / "__MACOSX").exists()


# =============================================================================
# TAR Extraction Tests
# =============================================================================


class TestExtractTar:
    """Tests for _extract_tar method."""

    @pytest.mark.asyncio
    async def test_extracts_tar_files(self, db_session, temp_staging):
        """Test extracting files from a TAR archive."""
        tar_path = temp_staging / "test.tar"

        # Create test file to add to tar
        test_file = temp_staging / "model.stl"
        test_file.write_bytes(b"STL content")

        with tarfile.open(tar_path, "w") as tf:
            tf.add(test_file, arcname="model.stl")

        # Remove original to verify extraction
        test_file.unlink()

        extractor = ArchiveExtractor(db_session)
        extracted = await extractor._extract_tar(tar_path, temp_staging)

        assert len(extracted) == 1
        assert (temp_staging / "model.stl").exists()

    @pytest.mark.asyncio
    async def test_extracts_tar_gz_files(self, db_session, temp_staging):
        """Test extracting files from a .tar.gz archive."""
        tar_path = temp_staging / "test.tar.gz"

        # Create test file to add to tar
        test_file = temp_staging / "model.stl"
        test_file.write_bytes(b"STL content")

        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(test_file, arcname="model.stl")

        # Remove original to verify extraction
        test_file.unlink()

        extractor = ArchiveExtractor(db_session)
        extracted = await extractor._extract_tar(tar_path, temp_staging)

        assert len(extracted) == 1
        assert (temp_staging / "model.stl").exists()


# =============================================================================
# File Hash Tests
# =============================================================================


class TestComputeFileHash:
    """Tests for _compute_file_hash method."""

    @pytest.mark.asyncio
    async def test_computes_sha256(self, db_session, tmp_path):
        """Test that SHA256 is correctly computed."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Hello, World!")

        extractor = ArchiveExtractor(db_session)

        # Known SHA256 of "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        result = await extractor._compute_file_hash(test_file)

        assert result == expected


# =============================================================================
# Create Design File Tests
# =============================================================================


class TestPrepareFileInfo:
    """Tests for _prepare_file_info method."""

    @pytest.mark.asyncio
    async def test_prepares_file_info(
        self, db_session, sample_design, temp_staging
    ):
        """Test preparing file info for an extracted file."""
        # Create a test file
        test_file = temp_staging / "model.stl"
        test_file.write_bytes(b"STL content")

        extractor = ArchiveExtractor(db_session)
        file_info = await extractor._prepare_file_info(test_file, temp_staging)

        assert file_info.filename == "model.stl"
        assert file_info.ext == ".stl"
        assert file_info.file_kind == FileKind.MODEL
        assert file_info.model_kind == ModelKind.STL
        assert file_info.size_bytes == len(b"STL content")
        assert file_info.sha256 is not None

    @pytest.mark.asyncio
    async def test_creates_relative_path(
        self, db_session, sample_design, temp_staging
    ):
        """Test that relative path is correctly set."""
        # Create a file in a subdirectory
        subdir = temp_staging / "models"
        subdir.mkdir()
        test_file = subdir / "part.stl"
        test_file.write_bytes(b"STL content")

        extractor = ArchiveExtractor(db_session)
        file_info = await extractor._prepare_file_info(test_file, temp_staging)

        assert file_info.relative_path == "models/part.stl"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_extract_design_not_found(self, db_session, mock_session_maker):
        """Test extraction raises error for non-existent design."""
        extractor = ArchiveExtractor(db_session)

        with patch("app.services.archive.async_session_maker", mock_session_maker):
            with pytest.raises(ArchiveError) as exc_info:
                await extractor.extract_design_archives("nonexistent-id")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_staging_not_found(
        self, db_session, sample_design, mock_session_maker
    ):
        """Test extraction raises error when staging dir missing."""
        extractor = ArchiveExtractor(db_session)

        # Mock session maker and settings
        with patch("app.services.archive.async_session_maker", mock_session_maker):
            with patch("app.services.archive.settings") as mock_settings:
                mock_settings.staging_path = Path("/nonexistent")

                with pytest.raises(ArchiveError) as exc_info:
                    await extractor.extract_design_archives(sample_design.id)

                assert "staging directory not found" in str(exc_info.value).lower()


# =============================================================================
# Queue Import Tests
# =============================================================================


class TestQueueImport:
    """Tests for queue_import method."""

    @pytest.mark.asyncio
    async def test_queues_import_job(self, db_session, sample_design):
        """Test that import job is queued correctly."""
        extractor = ArchiveExtractor(db_session)

        job_id = await extractor.queue_import(sample_design.id)
        await db_session.commit()

        assert job_id is not None


# =============================================================================
# ExtractArchiveWorker Tests
# =============================================================================


class TestExtractArchiveWorker:
    """Tests for ExtractArchiveWorker class."""

    def test_worker_handles_extract_archive_jobs(self):
        """Test worker is configured to handle EXTRACT_ARCHIVE jobs."""
        from app.workers.extract import ExtractArchiveWorker

        worker = ExtractArchiveWorker()

        assert JobType.EXTRACT_ARCHIVE in worker.job_types

    def test_worker_has_default_poll_interval(self):
        """Test worker has sensible default poll interval."""
        from app.workers.extract import ExtractArchiveWorker

        worker = ExtractArchiveWorker()

        assert worker.poll_interval == 1.0

    def test_worker_accepts_custom_poll_interval(self):
        """Test worker accepts custom poll interval."""
        from app.workers.extract import ExtractArchiveWorker

        worker = ExtractArchiveWorker(poll_interval=2.0)

        assert worker.poll_interval == 2.0

    def test_worker_accepts_worker_id(self):
        """Test worker accepts custom worker ID."""
        from app.workers.extract import ExtractArchiveWorker

        worker = ExtractArchiveWorker(worker_id="extract-worker-1")

        assert worker.worker_id == "extract-worker-1"
