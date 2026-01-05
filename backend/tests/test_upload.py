"""Tests for UploadService - file upload and processing (v0.8).

Tests cover:
- File upload to staging
- File validation (extension, size)
- Archive extraction
- Design creation from uploads
- Upload cleanup
- Upload listing and deletion
"""

from __future__ import annotations

import io
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Design, DesignStatus, ImportProfile
from app.schemas.upload import UploadStatus
from app.services.import_profile import ImportProfileService
from app.services.upload import (
    UploadError,
    UploadNotFoundError,
    UploadProcessingError,
    UploadService,
    UploadValidationError,
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
def staging_dir():
    """Create a temporary staging directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def service(db_session, staging_dir) -> UploadService:
    """Create UploadService instance with mocked staging path."""
    svc = UploadService(db_session)
    svc._staging_path = staging_dir
    return svc


@pytest.fixture
def sample_stl_content():
    """Sample STL file content."""
    return b"solid test\nendsolid test"


@pytest.fixture
def sample_zip_content():
    """Sample ZIP file content."""
    import zipfile
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("model.stl", b"solid model\nendsolid model")
        zf.writestr("readme.txt", b"Test readme")
    return buffer.getvalue()


# =============================================================================
# Upload Creation Tests
# =============================================================================


class TestCreateUpload:
    """Tests for create_upload method."""

    @pytest.mark.asyncio
    async def test_create_upload_success(self, service: UploadService, sample_stl_content):
        """Test successful file upload."""
        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_allowed_extensions = [".stl", ".3mf", ".zip"]
            mock_settings.upload_max_size_mb = 100

            result = await service.create_upload(
                filename="model.stl",
                file_content=sample_stl_content,
                content_type="application/sla",
            )

            assert result.upload_id is not None
            assert result.filename == "model.stl"
            assert result.size > 0
            assert result.status == UploadStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_upload_invalid_extension(self, service: UploadService):
        """Test upload with invalid file extension."""
        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_allowed_extensions = [".stl", ".3mf", ".zip"]

            with pytest.raises(UploadValidationError, match="not allowed"):
                await service.create_upload(
                    filename="script.exe",
                    file_content=b"malicious content",
                )

    @pytest.mark.asyncio
    async def test_create_upload_file_too_large(self, service: UploadService, staging_dir):
        """Test upload exceeding size limit."""
        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_allowed_extensions = [".stl"]
            mock_settings.upload_max_size_mb = 1  # 1MB limit
            mock_settings.upload_staging_path = staging_dir

            # Create content larger than 1MB
            large_content = b"X" * (2 * 1024 * 1024)  # 2MB

            with pytest.raises(UploadValidationError, match="exceeds maximum"):
                await service.create_upload(
                    filename="large.stl",
                    file_content=large_content,
                )

    @pytest.mark.asyncio
    async def test_create_upload_with_file_object(self, service: UploadService):
        """Test upload with file-like object."""
        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_allowed_extensions = [".stl"]
            mock_settings.upload_max_size_mb = 100

            file_obj = io.BytesIO(b"solid test\nendsolid test")

            result = await service.create_upload(
                filename="model.stl",
                file_content=file_obj,
            )

            assert result.upload_id is not None


# =============================================================================
# Upload Retrieval Tests
# =============================================================================


class TestGetUpload:
    """Tests for get_upload method."""

    @pytest.mark.asyncio
    async def test_get_upload_not_found(self, service: UploadService):
        """Test getting non-existent upload."""
        with pytest.raises(UploadNotFoundError):
            await service.get_upload("nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_upload_success(self, service: UploadService, staging_dir):
        """Test getting existing upload."""
        # Create upload manually
        upload_id = "test-upload-123"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()

        import json
        meta = {
            "filename": "model.stl",
            "size": 100,
            "mime_type": "application/sla",
            "status": UploadStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        result = await service.get_upload(upload_id)

        assert result.id == upload_id
        assert result.filename == "model.stl"
        assert result.size == 100
        assert result.status == UploadStatus.PENDING


class TestListUploads:
    """Tests for list_uploads method."""

    @pytest.mark.asyncio
    async def test_list_uploads_empty(self, service: UploadService, staging_dir):
        """Test listing uploads when none exist."""
        result = await service.list_uploads()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_uploads_excludes_expired(self, service: UploadService, staging_dir):
        """Test that expired uploads are excluded by default."""
        import json

        # Create an expired upload
        upload_id = "expired-upload"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()

        meta = {
            "filename": "old.stl",
            "size": 100,
            "status": UploadStatus.EXPIRED.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        result = await service.list_uploads(include_expired=False)
        assert len(result) == 0

        result_with_expired = await service.list_uploads(include_expired=True)
        assert len(result_with_expired) == 1


# =============================================================================
# Upload Deletion Tests
# =============================================================================


class TestDeleteUpload:
    """Tests for delete_upload method."""

    @pytest.mark.asyncio
    async def test_delete_upload_not_found(self, service: UploadService):
        """Test deleting non-existent upload."""
        with pytest.raises(UploadNotFoundError):
            await service.delete_upload("nonexistent-id")

    @pytest.mark.asyncio
    async def test_delete_upload_success(self, service: UploadService, staging_dir):
        """Test successful upload deletion."""
        import json

        # Create upload
        upload_id = "to-delete"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()
        (upload_dir / "model.stl").write_text("content")

        meta = {
            "filename": "model.stl",
            "size": 7,
            "status": UploadStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        await service.delete_upload(upload_id)

        # Verify directory is removed
        assert not upload_dir.exists()


# =============================================================================
# Upload Processing Tests
# =============================================================================


class TestProcessUpload:
    """Tests for process_upload method."""

    @pytest.mark.asyncio
    async def test_process_upload_not_found(self, service: UploadService):
        """Test processing non-existent upload."""
        with pytest.raises(UploadNotFoundError):
            await service.process_upload("nonexistent-id")

    @pytest.mark.asyncio
    async def test_process_upload_already_processed(self, service: UploadService, staging_dir):
        """Test processing already processed upload."""
        import json

        upload_id = "already-processed"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()

        meta = {
            "filename": "model.stl",
            "size": 100,
            "status": UploadStatus.COMPLETED.value,  # Already completed
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        with pytest.raises(UploadProcessingError, match="already processed"):
            await service.process_upload(upload_id)

    @pytest.mark.asyncio
    async def test_process_single_stl_file(
        self, service: UploadService, staging_dir, db_session
    ):
        """Test processing a single STL file."""
        import json

        # Seed built-in profiles
        profile_service = ImportProfileService(db_session)
        await profile_service.ensure_builtin_profiles()
        await db_session.commit()

        upload_id = "single-stl"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()
        (upload_dir / "dragon.stl").write_text("solid dragon\nendsolid dragon")

        meta = {
            "filename": "dragon.stl",
            "size": 30,
            "status": UploadStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        # Mock auto_queue_render_for_design to avoid job queue issues
        with patch("app.services.upload.auto_queue_render_for_design", return_value=None):
            result = await service.process_upload(
                upload_id,
                title="Dragon Model",
                designer="Test Designer",
            )
            await db_session.commit()

        assert result.status == UploadStatus.COMPLETED
        assert result.design_id is not None
        assert result.design_title == "Dragon Model"
        assert result.files_extracted == 1
        assert result.model_files == 1

    @pytest.mark.asyncio
    async def test_process_zip_archive(
        self, service: UploadService, staging_dir, db_session, sample_zip_content
    ):
        """Test processing a ZIP archive."""
        import json

        # Seed built-in profiles
        profile_service = ImportProfileService(db_session)
        await profile_service.ensure_builtin_profiles()
        await db_session.commit()

        upload_id = "zip-archive"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()
        (upload_dir / "models.zip").write_bytes(sample_zip_content)

        # Pre-create the extracted directory with a model file
        # (simulating what the extractor would do)
        extracted_dir = upload_dir / "extracted"
        extracted_dir.mkdir()
        (extracted_dir / "model.stl").write_text("solid model\nendsolid model")

        meta = {
            "filename": "models.zip",
            "size": len(sample_zip_content),
            "status": UploadStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        # Mock archive extraction and auto render
        with patch("app.services.upload.auto_queue_render_for_design", return_value=None):
            # Mock the ArchiveExtractor to return success
            mock_extractor = MagicMock()
            mock_result = MagicMock()
            mock_result.files_extracted = 2
            mock_extractor.extract = AsyncMock(return_value=mock_result)

            with patch("app.services.upload.ArchiveExtractor", return_value=mock_extractor):
                result = await service.process_upload(upload_id)
                await db_session.commit()

        assert result.status == UploadStatus.COMPLETED
        assert result.design_id is not None


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestCleanupExpired:
    """Tests for cleanup_expired method."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_uploads(
        self, service: UploadService, staging_dir
    ):
        """Test that expired uploads are cleaned up."""
        import json

        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_retention_hours = 24

            # Create an old pending upload
            upload_id = "old-pending"
            upload_dir = staging_dir / upload_id
            upload_dir.mkdir()
            (upload_dir / "model.stl").write_text("content")

            # Set created_at to 2 days ago
            old_time = datetime.now(timezone.utc) - timedelta(days=2)
            meta = {
                "filename": "model.stl",
                "size": 7,
                "status": UploadStatus.PENDING.value,
                "created_at": old_time.isoformat(),
            }
            (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

            cleaned = await service.cleanup_expired()

            assert cleaned == 1
            assert not upload_dir.exists()

    @pytest.mark.asyncio
    async def test_cleanup_expired_keeps_completed_uploads(
        self, service: UploadService, staging_dir
    ):
        """Test that completed uploads are not cleaned up."""
        import json

        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_retention_hours = 24

            # Create an old completed upload
            upload_id = "old-completed"
            upload_dir = staging_dir / upload_id
            upload_dir.mkdir()

            old_time = datetime.now(timezone.utc) - timedelta(days=2)
            meta = {
                "filename": "model.stl",
                "size": 7,
                "status": UploadStatus.COMPLETED.value,  # Completed
                "created_at": old_time.isoformat(),
            }
            (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

            cleaned = await service.cleanup_expired()

            assert cleaned == 0
            assert upload_dir.exists()

    @pytest.mark.asyncio
    async def test_cleanup_expired_empty_staging(self, service: UploadService, staging_dir):
        """Test cleanup with empty staging directory."""
        # Don't create the staging dir
        service._staging_path = staging_dir / "nonexistent"

        cleaned = await service.cleanup_expired()
        assert cleaned == 0


# =============================================================================
# Metadata Tests
# =============================================================================


class TestMetadata:
    """Tests for metadata save/load helpers."""

    @pytest.mark.asyncio
    async def test_save_and_load_meta(self, service: UploadService, staging_dir):
        """Test saving and loading metadata."""
        upload_id = "meta-test"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()

        meta = {
            "filename": "test.stl",
            "size": 100,
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await service._save_meta(upload_id, meta)
        loaded = await service._load_meta(upload_id)

        assert loaded is not None
        assert loaded["filename"] == "test.stl"
        assert loaded["size"] == 100

    @pytest.mark.asyncio
    async def test_load_meta_not_found(self, service: UploadService, staging_dir):
        """Test loading metadata for non-existent upload."""
        loaded = await service._load_meta("nonexistent")
        assert loaded is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling during processing."""

    @pytest.mark.asyncio
    async def test_process_upload_handles_extraction_error(
        self, service: UploadService, staging_dir, db_session
    ):
        """Test that extraction errors are handled gracefully."""
        import json

        # Seed built-in profiles
        profile_service = ImportProfileService(db_session)
        await profile_service.ensure_builtin_profiles()
        await db_session.commit()

        upload_id = "corrupt-archive"
        upload_dir = staging_dir / upload_id
        upload_dir.mkdir()
        (upload_dir / "corrupt.zip").write_text("not a real zip")

        meta = {
            "filename": "corrupt.zip",
            "size": 15,
            "status": UploadStatus.PENDING.value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / ".upload_meta.json").write_text(json.dumps(meta))

        # The extraction should fail and return FAILED status
        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(side_effect=Exception("Corrupt archive"))

        with patch("app.services.upload.ArchiveExtractor", return_value=mock_extractor):
            result = await service.process_upload(upload_id)

        assert result.status == UploadStatus.FAILED
        assert result.error_message is not None


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Tests for file validation logic."""

    @pytest.mark.asyncio
    async def test_allowed_extensions(self, service: UploadService):
        """Test that allowed extensions are validated."""
        valid_extensions = [".stl", ".3mf", ".obj", ".zip", ".rar", ".7z"]

        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_allowed_extensions = valid_extensions
            mock_settings.upload_max_size_mb = 100

            for ext in valid_extensions:
                filename = f"model{ext}"
                # Should not raise
                try:
                    await service.create_upload(
                        filename=filename,
                        file_content=b"test content",
                    )
                except UploadValidationError as e:
                    if "not allowed" in str(e):
                        pytest.fail(f"Extension {ext} should be allowed")

    @pytest.mark.asyncio
    async def test_disallowed_extensions(self, service: UploadService):
        """Test that disallowed extensions are rejected."""
        dangerous_extensions = [".exe", ".bat", ".sh", ".py", ".js"]

        with patch("app.services.upload.settings") as mock_settings:
            mock_settings.upload_allowed_extensions = [".stl", ".3mf"]

            for ext in dangerous_extensions:
                with pytest.raises(UploadValidationError, match="not allowed"):
                    await service.create_upload(
                        filename=f"file{ext}",
                        file_content=b"malicious",
                    )
