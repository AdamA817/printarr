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


# Default settings values (#221 - expanded for v1.0)
SETTINGS_DEFAULTS: dict[str, Any] = {
    # Library settings
    "library_template": "{designer}/{channel}/{title}",
    "max_concurrent_downloads": 3,
    "delete_archives_after_extraction": True,

    # Telegram settings (High Priority)
    "telegram_rate_limit_rpm": 30,
    "telegram_channel_spacing": 2.0,

    # Sync settings (Medium Priority)
    "sync_enabled": True,
    "sync_poll_interval": 300,
    "sync_batch_size": 100,

    # Upload settings (Medium Priority)
    "upload_max_size_mb": 500,
    "upload_retention_hours": 24,

    # Render settings (Low Priority)
    "auto_queue_render_after_import": True,
    "auto_queue_render_priority": -1,

    # Google settings (Low Priority)
    "google_request_delay": 0.5,
    "google_requests_per_minute": 60,
}

# Settings metadata for UI (#221)
# Defines type, min, max, description, and whether restart is required
SETTINGS_METADATA: dict[str, dict[str, Any]] = {
    "library_template": {
        "type": "string",
        "description": "Template for library folder structure. Must contain {title}.",
        "requires_restart": False,
    },
    "max_concurrent_downloads": {
        "type": "int",
        "min": 1,
        "max": 10,
        "description": "Maximum concurrent download workers",
        "requires_restart": False,
    },
    "delete_archives_after_extraction": {
        "type": "bool",
        "description": "Delete archive files after successful extraction",
        "requires_restart": False,
    },
    "telegram_rate_limit_rpm": {
        "type": "int",
        "min": 10,
        "max": 100,
        "description": "Maximum Telegram API requests per minute",
        "requires_restart": False,
    },
    "telegram_channel_spacing": {
        "type": "float",
        "min": 0.5,
        "max": 10.0,
        "description": "Minimum seconds between requests to the same channel",
        "requires_restart": False,
    },
    "sync_enabled": {
        "type": "bool",
        "description": "Enable live channel monitoring",
        "requires_restart": True,
    },
    "sync_poll_interval": {
        "type": "int",
        "min": 60,
        "max": 3600,
        "description": "Interval in seconds for catch-up sync polling",
        "requires_restart": False,
    },
    "sync_batch_size": {
        "type": "int",
        "min": 10,
        "max": 500,
        "description": "Maximum messages to process per sync batch",
        "requires_restart": False,
    },
    "upload_max_size_mb": {
        "type": "int",
        "min": 1,
        "max": 10000,
        "description": "Maximum upload size in megabytes",
        "requires_restart": False,
    },
    "upload_retention_hours": {
        "type": "int",
        "min": 1,
        "max": 168,
        "description": "Hours to retain unprocessed uploads before cleanup",
        "requires_restart": False,
    },
    "auto_queue_render_after_import": {
        "type": "bool",
        "description": "Automatically queue preview render jobs after import",
        "requires_restart": False,
    },
    "auto_queue_render_priority": {
        "type": "int",
        "min": -10,
        "max": 10,
        "description": "Priority for auto-queued render jobs (-10 to 10)",
        "requires_restart": False,
    },
    "google_request_delay": {
        "type": "float",
        "min": 0.0,
        "max": 10.0,
        "description": "Delay in seconds between Google API requests",
        "requires_restart": False,
    },
    "google_requests_per_minute": {
        "type": "int",
        "min": 10,
        "max": 1000,
        "description": "Maximum Google API requests per minute",
        "requires_restart": False,
    },
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
        """Get fallback value from environment variables (#221)."""
        env_mapping = {
            "max_concurrent_downloads": env_settings.max_concurrent_downloads,
            "library_template": env_settings.library_template_global,
            "telegram_rate_limit_rpm": env_settings.telegram_rate_limit_rpm,
            "telegram_channel_spacing": env_settings.telegram_channel_spacing,
            "sync_enabled": env_settings.sync_enabled,
            "sync_poll_interval": env_settings.sync_poll_interval,
            "sync_batch_size": env_settings.sync_batch_size,
            "upload_max_size_mb": env_settings.upload_max_size_mb,
            "upload_retention_hours": env_settings.upload_retention_hours,
            "auto_queue_render_after_import": env_settings.auto_queue_render_after_import,
            "auto_queue_render_priority": env_settings.auto_queue_render_priority,
            "google_request_delay": env_settings.google_request_delay,
            "google_requests_per_minute": env_settings.google_requests_per_minute,
        }
        return env_mapping.get(key)

    def _validate_setting(self, key: str, value: Any) -> None:
        """Validate a setting value using metadata (#221).

        Raises:
            SettingsValidationError: If the value is invalid.
        """
        # Special validation for library_template
        if key == "library_template":
            if not isinstance(value, str):
                raise SettingsValidationError("library_template must be a string")
            for var in LIBRARY_TEMPLATE_REQUIRED_VARS:
                if var not in value:
                    raise SettingsValidationError(
                        f"library_template must contain {var}"
                    )
            return

        # Get metadata for this key
        metadata = SETTINGS_METADATA.get(key)
        if metadata is None:
            return  # Unknown key, no validation

        setting_type = metadata.get("type")
        min_val = metadata.get("min")
        max_val = metadata.get("max")

        # Type validation
        if setting_type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise SettingsValidationError(f"{key} must be an integer")
            if min_val is not None and value < min_val:
                raise SettingsValidationError(f"{key} must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise SettingsValidationError(f"{key} must be <= {max_val}")

        elif setting_type == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise SettingsValidationError(f"{key} must be a number")
            if min_val is not None and value < min_val:
                raise SettingsValidationError(f"{key} must be >= {min_val}")
            if max_val is not None and value > max_val:
                raise SettingsValidationError(f"{key} must be <= {max_val}")

        elif setting_type == "bool":
            if not isinstance(value, bool):
                raise SettingsValidationError(f"{key} must be a boolean")

        elif setting_type == "string":
            if not isinstance(value, str):
                raise SettingsValidationError(f"{key} must be a string")

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """Get the settings schema for UI rendering (#221).

        Returns:
            Dictionary mapping setting keys to their metadata.
        """
        schema = {}
        for key, metadata in SETTINGS_METADATA.items():
            schema[key] = {
                **metadata,
                "default": SETTINGS_DEFAULTS.get(key),
            }
        return schema

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the settings cache (useful for testing)."""
        cls._cache.clear()
