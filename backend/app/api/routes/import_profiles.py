"""Import Profile API endpoints for v0.8 Manual Imports."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import ImportProfile, ImportSource
from app.schemas.import_profile import (
    ImportProfileConfig,
    ImportProfileCreate,
    ImportProfileList,
    ImportProfileResponse,
    ImportProfileUpdate,
)
from app.services.import_profile import (
    BuiltinProfileModificationError,
    ImportProfileService,
    ProfileNotFoundError,
    ProfileValidationError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/import-profiles", tags=["import-profiles"])


# =============================================================================
# Helper Functions
# =============================================================================


def _build_profile_response(profile: ImportProfile) -> ImportProfileResponse:
    """Build response from profile model."""
    if profile.config_json:
        config = ImportProfileConfig.model_validate_json(profile.config_json)
    else:
        config = ImportProfileConfig()

    return ImportProfileResponse(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        is_builtin=profile.is_builtin,
        config=config,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


# =============================================================================
# List and Create
# =============================================================================


@router.get("/", response_model=ImportProfileList)
async def list_import_profiles(
    include_builtin: bool = Query(True, description="Include built-in profiles"),
    db: AsyncSession = Depends(get_db),
) -> ImportProfileList:
    """List all import profiles.

    Returns both built-in and custom profiles by default.
    Built-in profiles are listed first.
    """
    service = ImportProfileService(db)

    # Ensure built-in profiles exist
    await service.ensure_builtin_profiles()
    await db.commit()

    profiles = await service.list_profiles(include_builtin=include_builtin)
    items = [_build_profile_response(p) for p in profiles]

    return ImportProfileList(items=items, total=len(items))


@router.post("/", response_model=ImportProfileResponse, status_code=201)
async def create_import_profile(
    data: ImportProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> ImportProfileResponse:
    """Create a new custom import profile.

    The profile configuration can be customized for specific folder structures.
    Use the built-in profiles as templates.
    """
    service = ImportProfileService(db)

    try:
        profile = await service.create_profile(data)
        await db.commit()
        await db.refresh(profile)

        logger.info(
            "import_profile_created",
            profile_id=profile.id,
            name=data.name,
        )

        return _build_profile_response(profile)

    except ProfileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Get, Update, Delete
# =============================================================================


@router.get("/{profile_id}", response_model=ImportProfileResponse)
async def get_import_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportProfileResponse:
    """Get import profile details."""
    service = ImportProfileService(db)

    try:
        profile = await service.get_profile(profile_id)
        return _build_profile_response(profile)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="Import profile not found")


@router.put("/{profile_id}", response_model=ImportProfileResponse)
async def update_import_profile(
    profile_id: str,
    data: ImportProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> ImportProfileResponse:
    """Update a custom import profile.

    Built-in profiles cannot be modified.
    """
    service = ImportProfileService(db)

    try:
        profile = await service.update_profile(profile_id, data)
        await db.commit()
        await db.refresh(profile)

        logger.info("import_profile_updated", profile_id=profile_id)

        return _build_profile_response(profile)

    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="Import profile not found")
    except BuiltinProfileModificationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ProfileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{profile_id}", status_code=204)
async def delete_import_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a custom import profile.

    Built-in profiles cannot be deleted.
    Profiles that are in use by import sources cannot be deleted.
    """
    service = ImportProfileService(db)

    try:
        # Check if profile exists
        profile = await service.get_profile(profile_id)

        # Check if profile is in use
        usage_result = await db.execute(
            select(func.count(ImportSource.id)).where(
                ImportSource.import_profile_id == profile_id
            )
        )
        usage_count = usage_result.scalar() or 0

        if usage_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Profile is in use by {usage_count} import source(s)",
            )

        await service.delete_profile(profile_id)
        await db.commit()

        logger.info("import_profile_deleted", profile_id=profile_id)

    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="Import profile not found")
    except BuiltinProfileModificationError as e:
        raise HTTPException(status_code=403, detail=str(e))


# =============================================================================
# Profile Usage
# =============================================================================


@router.get("/{profile_id}/usage", response_model=dict)
async def get_profile_usage(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get usage information for an import profile.

    Returns the count and list of import sources using this profile.
    """
    service = ImportProfileService(db)

    try:
        await service.get_profile(profile_id)
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="Import profile not found")

    # Get sources using this profile
    result = await db.execute(
        select(ImportSource).where(ImportSource.import_profile_id == profile_id)
    )
    sources = result.scalars().all()

    return {
        "profile_id": profile_id,
        "usage_count": len(sources),
        "sources": [
            {
                "id": s.id,
                "name": s.name,
                "source_type": s.source_type.value,
            }
            for s in sources
        ],
    }
