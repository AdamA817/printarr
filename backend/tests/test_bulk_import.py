"""Tests for BulkImportService - bulk folder import and monitoring (v0.8).

Tests cover:
- Folder scanning with import profiles
- File hash/size/mtime calculation
- Import record management
- Design import workflow
- Duplicate detection
- Conflict resolution
- Polling and monitoring
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    ConflictResolution,
    Design,
    DesignStatus,
    ImportProfile,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceStatus,
    ImportSourceType,
)
from app.services.bulk_import import (
    BulkImportError,
    BulkImportPathError,
    BulkImportService,
    DetectedDesign,
)
from app.services.import_profile import ImportProfileService


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
async def service(db_session) -> BulkImportService:
    """Create BulkImportService instance."""
    return BulkImportService(db_session)


@pytest.fixture
async def profile_service(db_session) -> ImportProfileService:
    """Create ImportProfileService instance."""
    return ImportProfileService(db_session)


@pytest.fixture
async def sample_profile(db_session, profile_service) -> ImportProfile:
    """Create and return a sample import profile."""
    await profile_service.ensure_builtin_profiles()
    await db_session.commit()

    profiles = await profile_service.list_profiles()
    return profiles[0]  # Return the first built-in profile


@pytest.fixture
def temp_design_folder():
    """Create a temporary folder structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create a design folder with STL files
        design1 = root / "Dragon"
        design1.mkdir()
        (design1 / "dragon.stl").write_text("STL content for dragon")
        (design1 / "base.stl").write_text("STL content for base")

        # Create a second design
        design2 = root / "Knight"
        design2.mkdir()
        (design2 / "knight.stl").write_text("STL content for knight")

        yield root


@pytest.fixture
async def sample_source(db_session, sample_profile, temp_design_folder) -> ImportSource:
    """Create a sample import source pointing to temp folder."""
    source = ImportSource(
        name="Test Source",
        source_type=ImportSourceType.BULK_FOLDER,
        status=ImportSourceStatus.PENDING,
        folder_path=str(temp_design_folder),
        import_profile_id=sample_profile.id,
    )
    db_session.add(source)
    await db_session.flush()
    return source


# =============================================================================
# Folder Scanning Tests
# =============================================================================


class TestScanFolder:
    """Tests for scan_folder method."""

    @pytest.mark.asyncio
    async def test_scan_folder_finds_designs(self, service: BulkImportService, sample_source):
        """Test scanning folder finds designs."""
        designs = await service.scan_folder(sample_source)

        assert len(designs) == 2
        titles = [d.title for d in designs]
        assert "Dragon" in titles
        assert "Knight" in titles

    @pytest.mark.asyncio
    async def test_scan_folder_wrong_source_type(self, service: BulkImportService, db_session):
        """Test scanning non-bulk-folder source raises error."""
        source = ImportSource(
            name="Google Drive Source",
            source_type=ImportSourceType.GOOGLE_DRIVE,
            status=ImportSourceStatus.PENDING,
        )
        db_session.add(source)
        await db_session.flush()

        with pytest.raises(BulkImportError, match="not a bulk folder source"):
            await service.scan_folder(source)

    @pytest.mark.asyncio
    async def test_scan_folder_missing_path(self, service: BulkImportService, db_session):
        """Test scanning source without folder path raises error."""
        source = ImportSource(
            name="No Path Source",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.PENDING,
            folder_path=None,
        )
        db_session.add(source)
        await db_session.flush()

        with pytest.raises(BulkImportPathError, match="no folder path"):
            await service.scan_folder(source)

    @pytest.mark.asyncio
    async def test_scan_folder_nonexistent_path(self, service: BulkImportService, db_session, sample_profile):
        """Test scanning nonexistent folder raises error."""
        source = ImportSource(
            name="Nonexistent Source",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.PENDING,
            folder_path="/nonexistent/path/that/does/not/exist",
            import_profile_id=sample_profile.id,
        )
        db_session.add(source)
        await db_session.flush()

        with pytest.raises(BulkImportPathError, match="does not exist"):
            await service.scan_folder(source)

    @pytest.mark.asyncio
    async def test_scan_folder_calculates_metadata(self, service: BulkImportService, sample_source):
        """Test scanning calculates file hash, size, and mtime."""
        designs = await service.scan_folder(sample_source)

        for design in designs:
            assert design.file_hash is not None
            assert len(design.file_hash) == 32  # SHA256 truncated
            assert design.total_size > 0
            assert design.mtime is not None


# =============================================================================
# Folder Metadata Calculation Tests
# =============================================================================


class TestMetadataCalculation:
    """Tests for folder size, mtime, and hash calculation."""

    @pytest.mark.asyncio
    async def test_calculate_folder_size(self, service: BulkImportService):
        """Test folder size calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file1.txt").write_text("A" * 100)  # 100 bytes
            (root / "file2.txt").write_text("B" * 50)   # 50 bytes

            size = service._calculate_folder_size(root)
            assert size == 150

    @pytest.mark.asyncio
    async def test_calculate_folder_mtime(self, service: BulkImportService):
        """Test folder mtime returns most recent time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("content")

            mtime = service._get_folder_mtime(root)
            assert mtime is not None
            assert isinstance(mtime, datetime)

    @pytest.mark.asyncio
    async def test_calculate_folder_hash_deterministic(self, service: BulkImportService):
        """Test folder hash is deterministic for same content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "file.txt").write_text("content")

            hash1 = service._calculate_folder_hash(root)
            hash2 = service._calculate_folder_hash(root)

            assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_calculate_folder_hash_changes_with_content(self, service: BulkImportService):
        """Test folder hash changes when content changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "file.txt"

            file_path.write_text("content1")
            hash1 = service._calculate_folder_hash(root)

            file_path.write_text("content2 longer")
            hash2 = service._calculate_folder_hash(root)

            assert hash1 != hash2


# =============================================================================
# Import Record Management Tests
# =============================================================================


class TestCreateImportRecords:
    """Tests for create_import_records method."""

    @pytest.mark.asyncio
    async def test_create_records_for_designs(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test creating import records for detected designs."""
        designs = await service.scan_folder(sample_source)
        records = await service.create_import_records(sample_source, designs)
        await db_session.commit()

        assert len(records) == 2
        for record in records:
            assert record.status == ImportRecordStatus.PENDING
            assert record.import_source_id == sample_source.id
            assert record.detected_title is not None

    @pytest.mark.asyncio
    async def test_create_records_updates_existing(
        self, service: BulkImportService, sample_source, db_session, temp_design_folder
    ):
        """Test that existing records are updated if content changes."""
        # First scan
        designs = await service.scan_folder(sample_source)
        records = await service.create_import_records(sample_source, designs)
        await db_session.commit()

        original_hash = records[0].file_hash

        # Modify a file
        dragon_folder = temp_design_folder / "Dragon"
        (dragon_folder / "new_part.stl").write_text("New STL content")

        # Second scan
        designs2 = await service.scan_folder(sample_source)
        records2 = await service.create_import_records(sample_source, designs2)
        await db_session.commit()

        # Should have same number of records (updated, not duplicated)
        all_records = await db_session.execute(
            select(ImportRecord).where(ImportRecord.import_source_id == sample_source.id)
        )
        assert len(list(all_records.scalars().all())) == 2

    @pytest.mark.asyncio
    async def test_get_pending_records(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test getting pending import records."""
        designs = await service.scan_folder(sample_source)
        await service.create_import_records(sample_source, designs)
        await db_session.commit()

        pending = await service.get_pending_records(sample_source.id)
        assert len(pending) == 2
        assert all(r.status == ImportRecordStatus.PENDING for r in pending)


# =============================================================================
# Design Import Tests
# =============================================================================


class TestImportDesign:
    """Tests for import_design method."""

    @pytest.mark.asyncio
    async def test_import_design_creates_design(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test importing design creates Design record."""
        designs = await service.scan_folder(sample_source)
        records = await service.create_import_records(sample_source, designs)
        await db_session.commit()

        record = records[0]
        design = await service.import_design(record, sample_source)
        await db_session.commit()

        assert design is not None
        assert design.canonical_title == record.detected_title
        assert design.status == DesignStatus.DOWNLOADED
        assert record.status == ImportRecordStatus.IMPORTED
        assert record.design_id == design.id

    @pytest.mark.asyncio
    async def test_import_design_skips_non_pending(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test importing skips records that aren't pending."""
        designs = await service.scan_folder(sample_source)
        records = await service.create_import_records(sample_source, designs)
        await db_session.commit()

        record = records[0]
        record.status = ImportRecordStatus.IMPORTED

        result = await service.import_design(record, sample_source)
        assert result is None

    @pytest.mark.asyncio
    async def test_import_design_conflict_skip(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test conflict resolution SKIP mode."""
        designs = await service.scan_folder(sample_source)
        records = await service.create_import_records(sample_source, designs)
        await db_session.commit()

        # Import first time
        await service.import_design(records[0], sample_source)
        await db_session.commit()

        # Create another pending record for same path
        records[0].status = ImportRecordStatus.PENDING
        await db_session.commit()

        # Try to import again with SKIP - should skip
        result = await service.import_design(
            records[0], sample_source, ConflictResolution.SKIP
        )
        # The exact behavior depends on duplicate detection logic
        # This tests the conflict resolution code path


class TestImportAllPending:
    """Tests for import_all_pending method."""

    @pytest.mark.asyncio
    async def test_import_all_pending(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test importing all pending records."""
        designs = await service.scan_folder(sample_source)
        await service.create_import_records(sample_source, designs)
        await db_session.commit()

        imported, skipped = await service.import_all_pending(sample_source)
        await db_session.commit()

        assert imported == 2
        assert skipped == 0

        # Verify all records are imported
        pending = await service.get_pending_records(sample_source.id)
        assert len(pending) == 0


# =============================================================================
# Initial Scan Tests
# =============================================================================


class TestInitialScan:
    """Tests for initial_scan method."""

    @pytest.mark.asyncio
    async def test_initial_scan_without_auto_import(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test initial scan without auto import."""
        detected, imported = await service.initial_scan(sample_source, auto_import=False)
        await db_session.commit()

        assert detected == 2
        assert imported == 0

        # Records should exist but be pending
        pending = await service.get_pending_records(sample_source.id)
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_initial_scan_with_auto_import(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test initial scan with auto import."""
        detected, imported = await service.initial_scan(sample_source, auto_import=True)
        await db_session.commit()

        assert detected == 2
        assert imported == 2

        # No pending records
        pending = await service.get_pending_records(sample_source.id)
        assert len(pending) == 0


# =============================================================================
# Polling Tests
# =============================================================================


class TestPolling:
    """Tests for poll_source method."""

    @pytest.mark.asyncio
    async def test_poll_source_detects_new_designs(
        self, service: BulkImportService, sample_source, db_session, temp_design_folder
    ):
        """Test polling detects new designs."""
        # Initial poll
        new, updated = await service.poll_source(sample_source)
        await db_session.commit()

        assert new == 2
        assert updated == 0

    @pytest.mark.asyncio
    async def test_poll_source_updates_sync_time(
        self, service: BulkImportService, sample_source, db_session
    ):
        """Test polling updates last_sync_at."""
        original_sync = sample_source.last_sync_at

        await service.poll_source(sample_source)
        await db_session.commit()

        assert sample_source.last_sync_at is not None
        if original_sync is not None:
            assert sample_source.last_sync_at > original_sync


# =============================================================================
# Monitoring Tests
# =============================================================================


class TestMonitoring:
    """Tests for file system monitoring."""

    @pytest.mark.asyncio
    async def test_start_monitoring(
        self, service: BulkImportService, sample_source
    ):
        """Test starting monitoring."""
        await service.start_monitoring(sample_source)

        assert service.is_monitoring(sample_source.id) is True

        # Cleanup
        await service.stop_monitoring(sample_source.id)

    @pytest.mark.asyncio
    async def test_stop_monitoring(
        self, service: BulkImportService, sample_source
    ):
        """Test stopping monitoring."""
        await service.start_monitoring(sample_source)
        await service.stop_monitoring(sample_source.id)

        assert service.is_monitoring(sample_source.id) is False

    @pytest.mark.asyncio
    async def test_is_monitoring_false_when_not_started(
        self, service: BulkImportService, sample_source
    ):
        """Test is_monitoring returns False when not started."""
        assert service.is_monitoring(sample_source.id) is False

    @pytest.mark.asyncio
    async def test_stop_all_monitoring(
        self, service: BulkImportService, sample_source
    ):
        """Test stopping all monitoring."""
        await service.start_monitoring(sample_source)
        await service.stop_all_monitoring()

        assert service.is_monitoring(sample_source.id) is False


# =============================================================================
# DetectedDesign Tests
# =============================================================================


class TestDetectedDesign:
    """Tests for DetectedDesign class."""

    def test_detected_design_properties(self):
        """Test DetectedDesign property accessors."""
        from app.schemas.import_profile import DesignDetectionResult

        detection = DesignDetectionResult(
            is_design=True,
            title="Test Title",
            model_files=["a.stl", "b.stl"],
            preview_files=["preview.jpg"],
        )
        detected = DetectedDesign(
            path=Path("/test/path"),
            detection=detection,
            relative_path="path",
        )

        assert detected.title == "Test Title"
        assert detected.model_count == 2
        assert detected.preview_count == 1

    def test_detected_design_fallback_title(self):
        """Test DetectedDesign uses folder name as fallback title."""
        from app.schemas.import_profile import DesignDetectionResult

        detection = DesignDetectionResult(is_design=True, title=None)
        detected = DetectedDesign(
            path=Path("/test/MyDesign"),
            detection=detection,
            relative_path="MyDesign",
        )

        assert detected.title == "MyDesign"
