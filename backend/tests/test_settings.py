"""Tests for Settings Storage & API."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AppSetting


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


# =============================================================================
# AppSetting Model Tests
# =============================================================================


class TestAppSettingModel:
    """Tests for the AppSetting database model."""

    @pytest.mark.asyncio
    async def test_create_setting(self, db_session):
        """Test creating a setting."""
        setting = AppSetting(key="test_key", value='{"foo": "bar"}')
        db_session.add(setting)
        await db_session.flush()

        assert setting.key == "test_key"
        assert setting.value == '{"foo": "bar"}'
        assert setting.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_setting(self, db_session):
        """Test updating a setting value."""
        setting = AppSetting(key="test_key", value='"initial"')
        db_session.add(setting)
        await db_session.flush()

        original_updated_at = setting.updated_at

        # Update the value
        setting.value = '"updated"'
        await db_session.flush()

        assert setting.value == '"updated"'


# =============================================================================
# SettingsService Tests
# =============================================================================


class TestSettingsService:
    """Tests for SettingsService functionality."""

    @pytest.mark.asyncio
    async def test_get_default_value(self, db_session):
        """Test getting a setting returns default when not in database."""
        from app.services.settings import SettingsService, SETTINGS_DEFAULTS

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        value = await service.get("library_template")
        assert value == SETTINGS_DEFAULTS["library_template"]

    @pytest.mark.asyncio
    async def test_set_and_get(self, db_session):
        """Test setting and getting a value."""
        from app.services.settings import SettingsService

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        await service.set("library_template", "{designer}/{title}")
        await db_session.flush()

        value = await service.get("library_template")
        assert value == "{designer}/{title}"

    @pytest.mark.asyncio
    async def test_get_all_settings(self, db_session):
        """Test getting all settings."""
        from app.services.settings import SettingsService, SETTINGS_DEFAULTS

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        all_settings = await service.get_all()

        # Should include all default keys
        for key in SETTINGS_DEFAULTS:
            assert key in all_settings

    @pytest.mark.asyncio
    async def test_reset_to_defaults(self, db_session):
        """Test resetting settings to defaults."""
        from app.services.settings import SettingsService, SETTINGS_DEFAULTS

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        # Set a custom value
        await service.set("max_concurrent_downloads", 5)
        await db_session.flush()

        # Reset
        defaults = await service.reset_to_defaults()
        await db_session.flush()

        assert defaults == SETTINGS_DEFAULTS

        # Verify value is back to default
        value = await service.get("max_concurrent_downloads")
        assert value == SETTINGS_DEFAULTS["max_concurrent_downloads"]

    @pytest.mark.asyncio
    async def test_delete_setting(self, db_session):
        """Test deleting a setting reverts to default."""
        from app.services.settings import SettingsService, SETTINGS_DEFAULTS

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        # Set a custom value
        await service.set("max_concurrent_downloads", 7)
        await db_session.flush()

        # Delete it
        deleted = await service.delete("max_concurrent_downloads")
        assert deleted is True

        # Should return default now
        value = await service.get("max_concurrent_downloads")
        assert value == SETTINGS_DEFAULTS["max_concurrent_downloads"]

    @pytest.mark.asyncio
    async def test_validation_library_template(self, db_session):
        """Test library_template validation."""
        from app.services.settings import SettingsService, SettingsValidationError

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        # Missing required {title} variable
        with pytest.raises(SettingsValidationError):
            await service.set("library_template", "{designer}/{channel}")

        # Non-string value
        with pytest.raises(SettingsValidationError):
            await service.set("library_template", 123)

    @pytest.mark.asyncio
    async def test_validation_max_concurrent_downloads(self, db_session):
        """Test max_concurrent_downloads validation."""
        from app.services.settings import SettingsService, SettingsValidationError

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        # Out of range (too low)
        with pytest.raises(SettingsValidationError):
            await service.set("max_concurrent_downloads", 0)

        # Out of range (too high)
        with pytest.raises(SettingsValidationError):
            await service.set("max_concurrent_downloads", 100)

        # Non-integer
        with pytest.raises(SettingsValidationError):
            await service.set("max_concurrent_downloads", "five")

    @pytest.mark.asyncio
    async def test_validation_delete_archives(self, db_session):
        """Test delete_archives_after_extraction validation."""
        from app.services.settings import SettingsService, SettingsValidationError

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        # Non-boolean
        with pytest.raises(SettingsValidationError):
            await service.set("delete_archives_after_extraction", "yes")

    @pytest.mark.asyncio
    async def test_convenience_methods(self, db_session):
        """Test convenience getter methods."""
        from app.services.settings import SettingsService

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        template = await service.get_library_template()
        assert isinstance(template, str)
        assert "{title}" in template

        downloads = await service.get_max_concurrent_downloads()
        assert isinstance(downloads, int)
        assert 1 <= downloads <= 10

        delete_archives = await service.get_delete_archives_after_extraction()
        assert isinstance(delete_archives, bool)


# =============================================================================
# Settings Schema Tests
# =============================================================================


class TestSettingsSchemas:
    """Tests for settings Pydantic schemas."""

    def test_setting_response_schema(self):
        """Test SettingResponse schema."""
        from app.schemas.settings import SettingResponse

        assert "key" in SettingResponse.model_fields
        assert "value" in SettingResponse.model_fields
        assert "is_default" in SettingResponse.model_fields

    def test_all_settings_response_schema(self):
        """Test AllSettingsResponse schema."""
        from app.schemas.settings import AllSettingsResponse

        assert "settings" in AllSettingsResponse.model_fields

    def test_setting_update_schema(self):
        """Test SettingUpdate schema."""
        from app.schemas.settings import SettingUpdate

        assert "value" in SettingUpdate.model_fields

    def test_library_template_settings_schema(self):
        """Test LibraryTemplateSettings schema."""
        from app.schemas.settings import LibraryTemplateSettings

        assert "library_template" in LibraryTemplateSettings.model_fields

    def test_download_settings_schema(self):
        """Test DownloadSettings schema."""
        from app.schemas.settings import DownloadSettings

        assert "max_concurrent_downloads" in DownloadSettings.model_fields
        assert "delete_archives_after_extraction" in DownloadSettings.model_fields


# =============================================================================
# Caching Tests
# =============================================================================


class TestSettingsCache:
    """Tests for settings caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, db_session):
        """Test that cached values are returned."""
        from app.services.settings import SettingsService

        service = SettingsService(db_session)
        SettingsService.clear_cache()

        # Set a value
        await service.set("max_concurrent_downloads", 4)
        await db_session.flush()

        # First get should populate cache
        value1 = await service.get("max_concurrent_downloads")

        # Manually modify the cache to verify it's being used
        SettingsService._cache["max_concurrent_downloads"] = (99, SettingsService._cache["max_concurrent_downloads"][1])

        # Second get should return cached value
        value2 = await service.get("max_concurrent_downloads")
        assert value2 == 99

    def test_clear_cache(self):
        """Test cache clearing."""
        from app.services.settings import SettingsService

        # Add something to cache
        SettingsService._cache["test"] = ("value", 0)

        # Clear it
        SettingsService.clear_cache()

        assert len(SettingsService._cache) == 0
