"""Pydantic schemas for settings API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SettingResponse(BaseModel):
    """Response for a single setting."""

    key: str = Field(description="Setting key")
    value: Any = Field(description="Setting value (type varies)")
    is_default: bool = Field(
        description="Whether this is the default value (not stored in database)"
    )

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    """Request to update a setting."""

    value: Any = Field(description="New value for the setting")


class AllSettingsResponse(BaseModel):
    """Response for all settings."""

    settings: dict[str, Any] = Field(description="All settings as key-value pairs")


class ResetSettingsResponse(BaseModel):
    """Response after resetting settings to defaults."""

    settings: dict[str, Any] = Field(description="Default settings")
    message: str = Field(default="Settings reset to defaults")


class SettingDeleteResponse(BaseModel):
    """Response after deleting a setting."""

    key: str = Field(description="Deleted setting key")
    message: str = Field(description="Result message")


# Specific settings schemas for validation

class LibraryTemplateSettings(BaseModel):
    """Library template setting schema."""

    library_template: str = Field(
        default="{designer}/{channel}/{title}",
        description=(
            "Template for library folder structure. "
            "Variables: {title}, {designer}, {channel}, {date}"
        ),
    )


class DownloadSettings(BaseModel):
    """Download-related settings."""

    max_concurrent_downloads: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent downloads (1-10)",
    )
    delete_archives_after_extraction: bool = Field(
        default=True,
        description="Whether to delete archive files after extraction",
    )
