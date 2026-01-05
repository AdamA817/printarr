"""E2E tests for Import Sources API endpoints (v0.8).

Tests the complete flow of:
- Creating import sources (BULK_FOLDER, GOOGLE_DRIVE, UPLOAD)
- Listing and filtering import sources
- Updating and deleting import sources
- Triggering sync operations
- Viewing import history
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.db.base import Base
from app.db.models import (
    ImportProfile,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceStatus,
    ImportSourceType,
)
from app.main import app
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
async def client(db_engine):
    """Create a test client with overridden database dependency."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_db(db_session):
    """Seed the database with built-in profiles."""
    profile_service = ImportProfileService(db_session)
    await profile_service.ensure_builtin_profiles()
    await db_session.commit()
    return db_session


@pytest.fixture
def temp_folder():
    """Create a temporary folder with some STL files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create a design folder
        design = root / "TestDesign"
        design.mkdir()
        (design / "model.stl").write_text("solid test\nendsolid test")

        yield root


# =============================================================================
# List Import Sources Tests
# =============================================================================


class TestListImportSources:
    """Tests for GET /api/v1/import-sources/ endpoint."""

    @pytest.mark.asyncio
    async def test_list_empty_sources(self, client: AsyncClient, seeded_db):
        """Test listing import sources when none exist."""
        response = await client.get("/api/v1/import-sources/")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_sources_with_data(self, client: AsyncClient, seeded_db, db_session):
        """Test listing import sources returns created sources."""
        # Create a source
        source = ImportSource(
            name="Test Bulk Source",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test/path",
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.get("/api/v1/import-sources/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Test Bulk Source"
        assert data["items"][0]["source_type"] == "BULK_FOLDER"

    @pytest.mark.asyncio
    async def test_list_sources_filter_by_type(self, client: AsyncClient, seeded_db, db_session):
        """Test filtering import sources by type."""
        # Create multiple sources
        db_session.add_all([
            ImportSource(
                name="Bulk Source",
                source_type=ImportSourceType.BULK_FOLDER,
                status=ImportSourceStatus.ACTIVE,
                folder_path="/test/bulk",
            ),
            ImportSource(
                name="Upload Source",
                source_type=ImportSourceType.UPLOAD,
                status=ImportSourceStatus.ACTIVE,
            ),
        ])
        await db_session.commit()

        # Filter by BULK_FOLDER
        response = await client.get("/api/v1/import-sources/?source_type=BULK_FOLDER")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["source_type"] == "BULK_FOLDER"

    @pytest.mark.asyncio
    async def test_list_sources_filter_by_status(self, client: AsyncClient, seeded_db, db_session):
        """Test filtering import sources by status."""
        db_session.add_all([
            ImportSource(
                name="Active Source",
                source_type=ImportSourceType.BULK_FOLDER,
                status=ImportSourceStatus.ACTIVE,
                folder_path="/active",
            ),
            ImportSource(
                name="Error Source",
                source_type=ImportSourceType.BULK_FOLDER,
                status=ImportSourceStatus.ERROR,
                folder_path="/error",
            ),
        ])
        await db_session.commit()

        response = await client.get("/api/v1/import-sources/?status=ACTIVE")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Active Source"


# =============================================================================
# Create Import Source Tests
# =============================================================================


class TestCreateImportSource:
    """Tests for POST /api/v1/import-sources/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_bulk_folder_source(self, client: AsyncClient, seeded_db):
        """Test creating a bulk folder import source."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "My Downloads",
                "source_type": "BULK_FOLDER",
                "folder_path": "/downloads/3dmodels",
                "sync_enabled": True,
                "sync_interval_hours": 24,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Downloads"
        assert data["source_type"] == "BULK_FOLDER"
        assert data["folder_path"] == "/downloads/3dmodels"
        assert data["sync_enabled"] is True
        assert data["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_create_bulk_folder_without_path_fails(self, client: AsyncClient, seeded_db):
        """Test creating bulk folder source without path fails."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "Invalid Source",
                "source_type": "BULK_FOLDER",
            },
        )
        assert response.status_code == 400
        assert "folder_path is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_google_drive_source(self, client: AsyncClient, seeded_db):
        """Test creating a Google Drive import source."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "My Google Drive",
                "source_type": "GOOGLE_DRIVE",
                "google_drive_url": "https://drive.google.com/drive/folders/1ABC123def",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Google Drive"
        assert data["source_type"] == "GOOGLE_DRIVE"
        assert data["google_drive_folder_id"] == "1ABC123def"

    @pytest.mark.asyncio
    async def test_create_google_drive_invalid_url_fails(self, client: AsyncClient, seeded_db):
        """Test creating Google Drive source with invalid URL fails."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "Invalid Drive",
                "source_type": "GOOGLE_DRIVE",
                "google_drive_url": "https://example.com/not-drive",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_upload_source(self, client: AsyncClient, seeded_db):
        """Test creating an upload import source."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "Manual Uploads",
                "source_type": "UPLOAD",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Manual Uploads"
        assert data["source_type"] == "UPLOAD"

    @pytest.mark.asyncio
    async def test_create_source_with_profile(self, client: AsyncClient, seeded_db, db_session):
        """Test creating source with import profile."""
        from sqlalchemy import select
        # Get a built-in profile
        profile = await db_session.execute(
            select(ImportProfile.id).where(ImportProfile.is_builtin == True).limit(1)
        )
        profile_id = profile.scalar()

        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "Profiled Source",
                "source_type": "BULK_FOLDER",
                "folder_path": "/test/path",
                "import_profile_id": profile_id,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["import_profile_id"] == profile_id
        assert data["profile"] is not None

    @pytest.mark.asyncio
    async def test_create_source_with_invalid_profile_fails(self, client: AsyncClient, seeded_db):
        """Test creating source with non-existent profile fails."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "Bad Profile Source",
                "source_type": "BULK_FOLDER",
                "folder_path": "/test/path",
                "import_profile_id": "nonexistent-profile-id",
            },
        )
        assert response.status_code == 400
        assert "profile not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_source_with_default_tags(self, client: AsyncClient, seeded_db):
        """Test creating source with default tags."""
        response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "Tagged Source",
                "source_type": "UPLOAD",
                "default_tags": ["miniature", "patreon"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["default_tags"] == ["miniature", "patreon"]


# =============================================================================
# Get Import Source Tests
# =============================================================================


class TestGetImportSource:
    """Tests for GET /api/v1/import-sources/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_source_not_found(self, client: AsyncClient, seeded_db):
        """Test getting non-existent source returns 404."""
        response = await client.get("/api/v1/import-sources/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_source_success(self, client: AsyncClient, seeded_db, db_session):
        """Test getting existing source returns details."""
        source = ImportSource(
            name="Test Source",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test",
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.get(f"/api/v1/import-sources/{source.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Source"
        assert "pending_count" in data
        assert "imported_count" in data
        assert "error_count" in data

    @pytest.mark.asyncio
    async def test_get_source_shows_record_counts(self, client: AsyncClient, seeded_db, db_session):
        """Test that getting source shows accurate record counts."""
        source = ImportSource(
            name="Source With Records",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test",
        )
        db_session.add(source)
        await db_session.flush()

        # Add some import records
        db_session.add_all([
            ImportRecord(
                import_source_id=source.id,
                source_path="/design1",
                status=ImportRecordStatus.PENDING,
            ),
            ImportRecord(
                import_source_id=source.id,
                source_path="/design2",
                status=ImportRecordStatus.IMPORTED,
            ),
            ImportRecord(
                import_source_id=source.id,
                source_path="/design3",
                status=ImportRecordStatus.ERROR,
                error_message="Failed",
            ),
        ])
        await db_session.commit()

        response = await client.get(f"/api/v1/import-sources/{source.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["pending_count"] == 1
        assert data["imported_count"] == 1
        assert data["error_count"] == 1


# =============================================================================
# Update Import Source Tests
# =============================================================================


class TestUpdateImportSource:
    """Tests for PUT /api/v1/import-sources/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_source_name(self, client: AsyncClient, seeded_db, db_session):
        """Test updating source name."""
        source = ImportSource(
            name="Original Name",
            source_type=ImportSourceType.UPLOAD,
            status=ImportSourceStatus.ACTIVE,
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/import-sources/{source.id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_source_sync_settings(self, client: AsyncClient, seeded_db, db_session):
        """Test updating sync settings."""
        source = ImportSource(
            name="Sync Source",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test",
            sync_enabled=False,
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/import-sources/{source.id}",
            json={
                "sync_enabled": True,
                "sync_interval_hours": 12,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sync_enabled"] is True
        assert data["sync_interval_hours"] == 12

    @pytest.mark.asyncio
    async def test_update_nonexistent_source(self, client: AsyncClient, seeded_db):
        """Test updating non-existent source returns 404."""
        response = await client.put(
            "/api/v1/import-sources/nonexistent",
            json={"name": "New Name"},
        )
        assert response.status_code == 404


# =============================================================================
# Delete Import Source Tests
# =============================================================================


class TestDeleteImportSource:
    """Tests for DELETE /api/v1/import-sources/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_source_success(self, client: AsyncClient, seeded_db, db_session):
        """Test deleting an import source."""
        source = ImportSource(
            name="To Delete",
            source_type=ImportSourceType.UPLOAD,
            status=ImportSourceStatus.ACTIVE,
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.delete(f"/api/v1/import-sources/{source.id}")
        assert response.status_code == 204

        # Verify deleted
        response = await client.get(f"/api/v1/import-sources/{source.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_source(self, client: AsyncClient, seeded_db):
        """Test deleting non-existent source returns 404."""
        response = await client.delete("/api/v1/import-sources/nonexistent")
        assert response.status_code == 404


# =============================================================================
# Sync Trigger Tests
# =============================================================================


class TestTriggerSync:
    """Tests for POST /api/v1/import-sources/{id}/sync endpoint.

    Note: Sync now queues an async job instead of running synchronously.
    Tests verify job creation rather than immediate results.
    """

    @pytest.mark.asyncio
    async def test_trigger_sync_bulk_folder(
        self, client: AsyncClient, seeded_db, db_session, temp_folder
    ):
        """Test triggering sync queues a job for bulk folder source."""
        source = ImportSource(
            name="Sync Test",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.PENDING,
            folder_path=str(temp_folder),
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.post(f"/api/v1/import-sources/{source.id}/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["source_id"] == source.id
        assert data["job_id"] is not None  # Async job was queued
        assert data["message"] == "Sync job queued"
        assert data["designs_detected"] == 0  # Job hasn't run yet
        assert data["designs_imported"] == 0

    @pytest.mark.asyncio
    async def test_trigger_sync_with_auto_import(
        self, client: AsyncClient, seeded_db, db_session, temp_folder
    ):
        """Test triggering sync with auto_import passes option to job."""
        source = ImportSource(
            name="Auto Import Test",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.PENDING,
            folder_path=str(temp_folder),
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/import-sources/{source.id}/sync",
            json={"auto_import": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] is not None  # Job queued with auto_import option

    @pytest.mark.asyncio
    async def test_trigger_sync_missing_folder_path(self, client: AsyncClient, seeded_db, db_session):
        """Test sync with missing folder path returns error (validation before job queue)."""
        source = ImportSource(
            name="Missing Path",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.PENDING,
            folder_path=None,  # Missing required path
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.post(f"/api/v1/import-sources/{source.id}/sync")
        assert response.status_code == 400
        assert "folder path" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_trigger_sync_nonexistent_source(self, client: AsyncClient, seeded_db):
        """Test sync for non-existent source returns 404."""
        response = await client.post("/api/v1/import-sources/nonexistent/sync")
        assert response.status_code == 404


# =============================================================================
# Import History Tests
# =============================================================================


class TestImportHistory:
    """Tests for GET /api/v1/import-sources/{id}/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_empty(self, client: AsyncClient, seeded_db, db_session):
        """Test getting history for source with no records."""
        source = ImportSource(
            name="Empty History",
            source_type=ImportSourceType.UPLOAD,
            status=ImportSourceStatus.ACTIVE,
        )
        db_session.add(source)
        await db_session.commit()

        response = await client.get(f"/api/v1/import-sources/{source.id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_history_with_records(self, client: AsyncClient, seeded_db, db_session):
        """Test getting history returns import records."""
        source = ImportSource(
            name="With History",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test",
        )
        db_session.add(source)
        await db_session.flush()

        # Add records
        db_session.add_all([
            ImportRecord(
                import_source_id=source.id,
                source_path="/design1",
                status=ImportRecordStatus.IMPORTED,
                detected_title="Design 1",
                detected_at=datetime.now(timezone.utc),
            ),
            ImportRecord(
                import_source_id=source.id,
                source_path="/design2",
                status=ImportRecordStatus.PENDING,
                detected_title="Design 2",
                detected_at=datetime.now(timezone.utc),
            ),
        ])
        await db_session.commit()

        response = await client.get(f"/api/v1/import-sources/{source.id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_history_filter_by_status(self, client: AsyncClient, seeded_db, db_session):
        """Test filtering history by status."""
        source = ImportSource(
            name="Filter History",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test",
        )
        db_session.add(source)
        await db_session.flush()

        db_session.add_all([
            ImportRecord(
                import_source_id=source.id,
                source_path="/imported",
                status=ImportRecordStatus.IMPORTED,
            ),
            ImportRecord(
                import_source_id=source.id,
                source_path="/pending",
                status=ImportRecordStatus.PENDING,
            ),
        ])
        await db_session.commit()

        response = await client.get(
            f"/api/v1/import-sources/{source.id}/history?status=IMPORTED"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "IMPORTED"

    @pytest.mark.asyncio
    async def test_get_history_pagination(self, client: AsyncClient, seeded_db, db_session):
        """Test history pagination."""
        source = ImportSource(
            name="Paginated History",
            source_type=ImportSourceType.BULK_FOLDER,
            status=ImportSourceStatus.ACTIVE,
            folder_path="/test",
        )
        db_session.add(source)
        await db_session.flush()

        # Add many records
        for i in range(25):
            db_session.add(
                ImportRecord(
                    import_source_id=source.id,
                    source_path=f"/design{i}",
                    status=ImportRecordStatus.PENDING,
                )
            )
        await db_session.commit()

        # Get first page
        response = await client.get(
            f"/api/v1/import-sources/{source.id}/history?page=1&page_size=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 1

        # Get second page
        response = await client.get(
            f"/api/v1/import-sources/{source.id}/history?page=2&page_size=10"
        )
        data = response.json()
        assert len(data["items"]) == 10
        assert data["page"] == 2


# =============================================================================
# Full Import Flow E2E Test
# =============================================================================


class TestFullImportFlow:
    """End-to-end test for complete import workflow.

    Note: Sync operations now queue async jobs, so this test verifies
    the API flow without waiting for job completion.
    """

    @pytest.mark.asyncio
    async def test_complete_import_flow(
        self, client: AsyncClient, seeded_db, db_session, temp_folder
    ):
        """Test the complete flow: create source -> queue sync -> CRUD operations."""
        # Step 1: Create import source
        create_response = await client.post(
            "/api/v1/import-sources/",
            json={
                "name": "E2E Test Source",
                "source_type": "BULK_FOLDER",
                "folder_path": str(temp_folder),
                "default_designer": "Test Creator",
            },
        )
        assert create_response.status_code == 201
        source_id = create_response.json()["id"]

        # Step 2: Get source details
        get_response = await client.get(f"/api/v1/import-sources/{source_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "PENDING"

        # Step 3: Trigger sync (queues async job)
        sync_response = await client.post(f"/api/v1/import-sources/{source_id}/sync")
        assert sync_response.status_code == 200
        sync_data = sync_response.json()
        assert sync_data["job_id"] is not None  # Job was queued
        assert sync_data["message"] == "Sync job queued"

        # Step 4: View import history (empty until job completes)
        history_response = await client.get(f"/api/v1/import-sources/{source_id}/history")
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert isinstance(history_data["items"], list)

        # Step 5: Update source
        update_response = await client.put(
            f"/api/v1/import-sources/{source_id}",
            json={"name": "Updated E2E Source"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Updated E2E Source"

        # Step 6: Delete source
        delete_response = await client.delete(f"/api/v1/import-sources/{source_id}")
        assert delete_response.status_code == 204
