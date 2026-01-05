"""API routes for application settings management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.schemas.settings import (
    AllSettingsResponse,
    ResetSettingsResponse,
    SettingDeleteResponse,
    SettingResponse,
    SettingUpdate,
)
from app.services.settings import (
    SETTINGS_DEFAULTS,
    SettingsService,
    SettingsValidationError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# Valid setting keys
VALID_KEYS = set(SETTINGS_DEFAULTS.keys())


@router.get("/", response_model=AllSettingsResponse)
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
) -> AllSettingsResponse:
    """Get all application settings.

    Returns all settings with defaults merged in for any
    settings not explicitly set.
    """
    service = SettingsService(db)
    settings = await service.get_all()

    return AllSettingsResponse(settings=settings)


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Get a single setting by key.

    Returns the setting value along with whether it's using the default.
    """
    if key not in VALID_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting key: {key}. Valid keys: {', '.join(sorted(VALID_KEYS))}",
        )

    service = SettingsService(db)

    # Check if value is in database
    from sqlalchemy import select
    from app.db.models import AppSetting

    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    db_setting = result.scalar_one_or_none()

    value = await service.get(key)
    is_default = db_setting is None

    return SettingResponse(
        key=key,
        value=value,
        is_default=is_default,
    )


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    update: SettingUpdate,
    db: AsyncSession = Depends(get_db),
) -> SettingResponse:
    """Update a setting value.

    Validates the value based on the setting type before saving.
    """
    if key not in VALID_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting key: {key}. Valid keys: {', '.join(sorted(VALID_KEYS))}",
        )

    service = SettingsService(db)

    try:
        await service.set(key, update.value)
        await db.commit()
    except SettingsValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "setting_updated_via_api",
        key=key,
    )

    return SettingResponse(
        key=key,
        value=update.value,
        is_default=False,
    )


@router.delete("/{key}", response_model=SettingDeleteResponse)
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> SettingDeleteResponse:
    """Delete a setting (reverts to default value).

    After deletion, the setting will return its default value.
    """
    if key not in VALID_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting key: {key}. Valid keys: {', '.join(sorted(VALID_KEYS))}",
        )

    service = SettingsService(db)
    deleted = await service.delete(key)
    await db.commit()

    if deleted:
        message = f"Setting '{key}' deleted, reverted to default"
    else:
        message = f"Setting '{key}' was already using default value"

    return SettingDeleteResponse(key=key, message=message)


@router.post("/reset", response_model=ResetSettingsResponse)
async def reset_settings(
    db: AsyncSession = Depends(get_db),
) -> ResetSettingsResponse:
    """Reset all settings to their default values.

    This removes all customized settings from the database.
    """
    service = SettingsService(db)
    defaults = await service.reset_to_defaults()
    await db.commit()

    logger.info("all_settings_reset_via_api")

    return ResetSettingsResponse(
        settings=defaults,
        message="All settings reset to defaults",
    )


@router.get("/schema/all")
async def get_settings_schema():
    """Get the settings schema for UI rendering (#221).

    Returns metadata for all available settings including:
    - type (string, int, float, bool)
    - min/max values for numeric types
    - description
    - default value
    - whether a restart is required after changing

    This endpoint is useful for building dynamic settings forms.
    """
    return {
        "schema": SettingsService.get_schema(),
        "keys": list(SETTINGS_DEFAULTS.keys()),
    }
