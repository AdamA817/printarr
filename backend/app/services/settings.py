"""Settings service for managing application configuration."""

from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.core.logging import get_logger
from app.db.models import AppSetting

logger = get_logger(__name__)

T = TypeVar("T")


# Default settings values
SETTINGS_DEFAULTS: dict[str, Any] = {
    "library_template": "{designer}/{channel}/{title}",
    "max_concurrent_downloads": 3,
    "delete_archives_after_extraction": True,
}

# Required variables for library_template validation
LIBRARY_TEMPLATE_REQUIRED_VARS = ["{title}"]


class SettingsError(Exception):
    """Base exception for settings errors."""

    pass


class SettingsValidationError(SettingsError):
    """Raised when a setting value is invalid."""

    pass


class SettingsService:
    """Service for managing application settings.

    Provides methods to get/set settings with:
    - In-memory caching with TTL
    - JSON encoding/decoding
    - Fallback to env vars and defaults
    - Validation for specific settings
    """

    # Class-level cache shared across instances
    _cache: dict[str, tuple[Any, float]] = {}
    _cache_ttl: float = 60.0  # 60 seconds

    def __init__(self, db: AsyncSession):
        """Initialize the settings service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db

    async def get(self, key: str, default: T | None = None) -> T | None:
        """Get a setting value.

        Lookup order:
        1. In-memory cache (if not expired)
        2. Database
        3. Environment variable (for specific keys)
        4. Default value from SETTINGS_DEFAULTS
        5. Provided default argument

        Args:
            key: The setting key to retrieve.
            default: Default value if not found anywhere.

        Returns:
            The setting value or default.
        """
        # Check cache first
        cached = self._get_from_cache(key)
        if cached is not None:
            return cached

        # Check database
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting is not None:
            value = json.loads(setting.value)
            self._set_cache(key, value)
            return value

        # Check environment variables for specific keys
        env_value = self._get_env_fallback(key)
        if env_value is not None:
            return env_value

        # Check defaults
        if key in SETTINGS_DEFAULTS:
            return SETTINGS_DEFAULTS[key]

        return default

    async def set(self, key: str, value: Any) -> None:
        """Set a setting value.

        Args:
            key: The setting key to set.
            value: The value to store (will be JSON-encoded).

        Raises:
            SettingsValidationError: If the value is invalid.
        """
        # Validate the setting
        self._validate_setting(key, value)

        # JSON encode the value
        json_value = json.dumps(value)

        # Upsert the setting
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting is not None:
            setting.value = json_value
        else:
            setting = AppSetting(key=key, value=json_value)
            self.db.add(setting)

        # Update cache
        self._set_cache(key, value)

        logger.info(
            "setting_updated",
            key=key,
            value_type=type(value).__name__,
        )

    async def get_all(self) -> dict[str, Any]:
        """Get all settings with defaults merged in.

        Returns:
            Dictionary of all settings.
        """
        # Start with defaults
        all_settings = dict(SETTINGS_DEFAULTS)

        # Fetch all from database
        result = await self.db.execute(select(AppSetting))
        db_settings = result.scalars().all()

        for setting in db_settings:
            try:
                all_settings[setting.key] = json.loads(setting.value)
            except json.JSONDecodeError:
                logger.warning(
                    "invalid_setting_json",
                    key=setting.key,
                )

        return all_settings

    async def reset_to_defaults(self) -> dict[str, Any]:
        """Reset all settings to their default values.

        Returns:
            Dictionary of default settings.
        """
        # Delete all settings from database
        result = await self.db.execute(select(AppSetting))
        db_settings = result.scalars().all()

        for setting in db_settings:
            await self.db.delete(setting)

        # Clear cache
        self._cache.clear()

        logger.info("settings_reset_to_defaults")

        return dict(SETTINGS_DEFAULTS)

    async def delete(self, key: str) -> bool:
        """Delete a setting (reverts to default).

        Args:
            key: The setting key to delete.

        Returns:
            True if setting was deleted, False if not found.
        """
        result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting is None:
            return False

        await self.db.delete(setting)

        # Remove from cache
        self._cache.pop(key, None)

        logger.info("setting_deleted", key=key)
        return True

    # Convenience methods

    async def get_library_template(self) -> str:
        """Get the library template setting.

        Returns:
            The library template string.
        """
        return await self.get("library_template", SETTINGS_DEFAULTS["library_template"])

    async def get_max_concurrent_downloads(self) -> int:
        """Get max concurrent downloads setting.

        Returns:
            The max concurrent downloads count.
        """
        return await self.get(
            "max_concurrent_downloads", SETTINGS_DEFAULTS["max_concurrent_downloads"]
        )

    async def get_delete_archives_after_extraction(self) -> bool:
        """Get delete archives after extraction setting.

        Returns:
            Whether to delete archives after extraction.
        """
        return await self.get(
            "delete_archives_after_extraction",
            SETTINGS_DEFAULTS["delete_archives_after_extraction"],
        )

    # Private methods

    def _get_from_cache(self, key: str) -> Any | None:
        """Get a value from cache if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            # Expired, remove from cache
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        """Set a value in the cache."""
        self._cache[key] = (value, time.time())

    def _get_env_fallback(self, key: str) -> Any | None:
        """Get fallback value from environment variables."""
        if key == "max_concurrent_downloads":
            return env_settings.max_concurrent_downloads
        if key == "library_template":
            return env_settings.library_template_global
        return None

    def _validate_setting(self, key: str, value: Any) -> None:
        """Validate a setting value.

        Raises:
            SettingsValidationError: If the value is invalid.
        """
        if key == "library_template":
            if not isinstance(value, str):
                raise SettingsValidationError("library_template must be a string")
            # Check required variables
            for var in LIBRARY_TEMPLATE_REQUIRED_VARS:
                if var not in value:
                    raise SettingsValidationError(
                        f"library_template must contain {var}"
                    )

        elif key == "max_concurrent_downloads":
            if not isinstance(value, int) or value < 1 or value > 10:
                raise SettingsValidationError(
                    "max_concurrent_downloads must be an integer between 1 and 10"
                )

        elif key == "delete_archives_after_extraction":
            if not isinstance(value, bool):
                raise SettingsValidationError(
                    "delete_archives_after_extraction must be a boolean"
                )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the settings cache (useful for testing)."""
        cls._cache.clear()
