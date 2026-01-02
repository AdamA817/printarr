"""E2E tests for Import Profiles API endpoints (v0.8).

Tests the complete flow of:
- Listing import profiles (built-in and custom)
- Creating custom profiles
- Updating profiles
- Deleting profiles
- Checking profile usage
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.db.base import Base
from app.db.models import ImportProfile, ImportSource, ImportSourceStatus, ImportSourceType
from app.main import app
from app.services.import_profile import BUILTIN_PROFILES, ImportProfileService


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


# =============================================================================
# List Import Profiles Tests
# =============================================================================


class TestListImportProfiles:
    """Tests for GET /api/v1/import-profiles endpoint."""

    @pytest.mark.asyncio
    async def test_list_profiles_includes_builtin(self, client: AsyncClient, seeded_db):
        """Test that listing profiles includes built-in profiles."""
        response = await client.get("/api/v1/import-profiles")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == len(BUILTIN_PROFILES)

        # Check built-in profiles are present
        names = {p["name"] for p in data["items"]}
        assert "Standard" in names
        assert "Yosh Studios" in names
        assert "Flat Archive" in names

    @pytest.mark.asyncio
    async def test_list_profiles_includes_custom(self, client: AsyncClient, seeded_db, db_session):
        """Test that listing profiles includes custom profiles."""
        # Create a custom profile
        profile = ImportProfile(
            name="My Custom Profile",
            description="Custom description",
            is_builtin=False,
            config_json="{}",
        )
        db_session.add(profile)
        await db_session.commit()

        response = await client.get("/api/v1/import-profiles")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == len(BUILTIN_PROFILES) + 1

        names = {p["name"] for p in data["items"]}
        assert "My Custom Profile" in names


# =============================================================================
# Create Import Profile Tests
# =============================================================================


class TestCreateImportProfile:
    """Tests for POST /api/v1/import-profiles endpoint."""

    @pytest.mark.asyncio
    async def test_create_profile_success(self, client: AsyncClient, seeded_db):
        """Test creating a custom profile."""
        response = await client.post(
            "/api/v1/import-profiles",
            json={
                "name": "My Creator Profile",
                "description": "Profile for my favorite creator",
                "config": {
                    "detection": {
                        "model_extensions": [".stl", ".3mf"],
                        "min_model_files": 1,
                        "structure": "nested",
                        "model_subfolders": ["Supported", "Unsupported"],
                    },
                    "title": {
                        "source": "folder_name",
                        "case_transform": "title",
                    },
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Creator Profile"
        assert data["is_builtin"] is False

    @pytest.mark.asyncio
    async def test_create_profile_duplicate_name_fails(self, client: AsyncClient, seeded_db):
        """Test creating profile with duplicate name fails."""
        # First create
        await client.post(
            "/api/v1/import-profiles",
            json={
                "name": "Unique Name",
                "config": {},
            },
        )

        # Try to create with same name
        response = await client.post(
            "/api/v1/import-profiles",
            json={
                "name": "Unique Name",
                "config": {},
            },
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_profile_minimal_config(self, client: AsyncClient, seeded_db):
        """Test creating profile with minimal configuration."""
        response = await client.post(
            "/api/v1/import-profiles",
            json={
                "name": "Minimal Profile",
                "config": {},
            },
        )
        assert response.status_code == 201


# =============================================================================
# Get Import Profile Tests
# =============================================================================


class TestGetImportProfile:
    """Tests for GET /api/v1/import-profiles/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, client: AsyncClient, seeded_db):
        """Test getting non-existent profile returns 404."""
        response = await client.get("/api/v1/import-profiles/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_profile_success(self, client: AsyncClient, seeded_db, db_session):
        """Test getting existing profile."""
        from sqlalchemy import select
        # Get a built-in profile ID
        result = await db_session.execute(
            select(ImportProfile.id).where(ImportProfile.name == "Standard")
        )
        profile_id = result.scalar()

        response = await client.get(f"/api/v1/import-profiles/{profile_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Standard"
        assert data["is_builtin"] is True


# =============================================================================
# Update Import Profile Tests
# =============================================================================


class TestUpdateImportProfile:
    """Tests for PUT /api/v1/import-profiles/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_custom_profile(self, client: AsyncClient, seeded_db, db_session):
        """Test updating a custom profile."""
        # Create custom profile
        profile = ImportProfile(
            name="Editable Profile",
            description="Original description",
            is_builtin=False,
            config_json="{}",
        )
        db_session.add(profile)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/import-profiles/{profile.id}",
            json={
                "name": "Renamed Profile",
                "description": "Updated description",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed Profile"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_builtin_profile_fails(self, client: AsyncClient, seeded_db, db_session):
        """Test updating built-in profile fails."""
        from sqlalchemy import select
        # Get a built-in profile
        result = await db_session.execute(
            select(ImportProfile.id).where(ImportProfile.is_builtin == True).limit(1)
        )
        profile_id = result.scalar()

        response = await client.put(
            f"/api/v1/import-profiles/{profile_id}",
            json={"name": "Hacked Name"},
        )
        assert response.status_code == 403  # Forbidden for builtin modification
        assert "built-in" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_profile_config(self, client: AsyncClient, seeded_db, db_session):
        """Test updating profile configuration."""
        profile = ImportProfile(
            name="Config Test Profile",
            is_builtin=False,
            config_json="{}",
        )
        db_session.add(profile)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/import-profiles/{profile.id}",
            json={
                "config": {
                    "detection": {
                        "min_model_files": 2,
                    },
                },
            },
        )
        assert response.status_code == 200


# =============================================================================
# Delete Import Profile Tests
# =============================================================================


class TestDeleteImportProfile:
    """Tests for DELETE /api/v1/import-profiles/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_custom_profile(self, client: AsyncClient, seeded_db, db_session):
        """Test deleting a custom profile."""
        profile = ImportProfile(
            name="To Be Deleted",
            is_builtin=False,
            config_json="{}",
        )
        db_session.add(profile)
        await db_session.commit()

        response = await client.delete(f"/api/v1/import-profiles/{profile.id}")
        assert response.status_code == 204

        # Verify deleted
        response = await client.get(f"/api/v1/import-profiles/{profile.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_builtin_profile_fails(self, client: AsyncClient, seeded_db, db_session):
        """Test deleting built-in profile fails."""
        from sqlalchemy import select
        result = await db_session.execute(
            select(ImportProfile.id).where(ImportProfile.is_builtin == True).limit(1)
        )
        profile_id = result.scalar()

        response = await client.delete(f"/api/v1/import-profiles/{profile_id}")
        assert response.status_code == 403
        assert "built-in" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, client: AsyncClient, seeded_db):
        """Test deleting non-existent profile returns 404."""
        response = await client.delete("/api/v1/import-profiles/nonexistent")
        assert response.status_code == 404


# =============================================================================
# Profile Usage Tests
# =============================================================================


class TestProfileUsage:
    """Tests for GET /api/v1/import-profiles/{id}/usage endpoint."""

    @pytest.mark.asyncio
    async def test_get_usage_no_sources(self, client: AsyncClient, seeded_db, db_session):
        """Test getting usage for profile with no sources."""
        profile = ImportProfile(
            name="Unused Profile",
            is_builtin=False,
            config_json="{}",
        )
        db_session.add(profile)
        await db_session.commit()

        response = await client.get(f"/api/v1/import-profiles/{profile.id}/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["usage_count"] == 0
        assert data["sources"] == []

    @pytest.mark.asyncio
    async def test_get_usage_with_sources(self, client: AsyncClient, seeded_db, db_session):
        """Test getting usage for profile with sources."""
        profile = ImportProfile(
            name="Used Profile",
            is_builtin=False,
            config_json="{}",
        )
        db_session.add(profile)
        await db_session.flush()

        # Create sources using this profile
        db_session.add_all([
            ImportSource(
                name="Source 1",
                source_type=ImportSourceType.BULK_FOLDER,
                status=ImportSourceStatus.ACTIVE,
                folder_path="/test1",
                import_profile_id=profile.id,
            ),
            ImportSource(
                name="Source 2",
                source_type=ImportSourceType.UPLOAD,
                status=ImportSourceStatus.ACTIVE,
                import_profile_id=profile.id,
            ),
        ])
        await db_session.commit()

        response = await client.get(f"/api/v1/import-profiles/{profile.id}/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["usage_count"] == 2
        assert len(data["sources"]) == 2


# =============================================================================
# Full Profile Flow E2E Test
# =============================================================================


class TestFullProfileFlow:
    """End-to-end test for complete profile workflow."""

    @pytest.mark.asyncio
    async def test_complete_profile_flow(self, client: AsyncClient, seeded_db, db_session):
        """Test the complete flow: list -> create -> use -> update -> delete."""
        # Step 1: List existing profiles
        list_response = await client.get("/api/v1/import-profiles")
        assert list_response.status_code == 200
        initial_count = len(list_response.json()["items"])

        # Step 2: Create new profile
        create_response = await client.post(
            "/api/v1/import-profiles",
            json={
                "name": "E2E Test Profile",
                "description": "Created for E2E testing",
                "config": {
                    "detection": {
                        "model_extensions": [".stl"],
                        "min_model_files": 1,
                    },
                },
            },
        )
        assert create_response.status_code == 201
        profile_id = create_response.json()["id"]

        # Step 3: Verify profile appears in list
        list_response = await client.get("/api/v1/import-profiles")
        assert len(list_response.json()["items"]) == initial_count + 1

        # Step 4: Get profile details
        get_response = await client.get(f"/api/v1/import-profiles/{profile_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "E2E Test Profile"

        # Step 5: Create import source using profile
        source_response = await client.post(
            "/api/v1/import-sources",
            json={
                "name": "Test Source",
                "source_type": "UPLOAD",
                "import_profile_id": profile_id,
            },
        )
        assert source_response.status_code == 201

        # Step 6: Check profile usage
        usage_response = await client.get(f"/api/v1/import-profiles/{profile_id}/usage")
        assert usage_response.status_code == 200
        assert usage_response.json()["usage_count"] == 1

        # Step 7: Update profile
        update_response = await client.put(
            f"/api/v1/import-profiles/{profile_id}",
            json={"description": "Updated description"},
        )
        assert update_response.status_code == 200

        # Step 8: Delete source first (to allow profile deletion)
        source_id = source_response.json()["id"]
        await client.delete(f"/api/v1/import-sources/{source_id}")

        # Step 9: Delete profile
        delete_response = await client.delete(f"/api/v1/import-profiles/{profile_id}")
        assert delete_response.status_code == 204

        # Step 10: Verify deletion
        get_response = await client.get(f"/api/v1/import-profiles/{profile_id}")
        assert get_response.status_code == 404
