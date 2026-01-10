"""Family API endpoints for managing design variant groupings.

Implements DEC-044: Design Families Architecture.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Design, DesignFamily, FamilyDetectionMethod
from app.services.family import FamilyError, FamilyService

logger = get_logger(__name__)

router = APIRouter(prefix="/families", tags=["families"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class DesignSummaryResponse(BaseModel):
    """Summary of a design within a family."""

    model_config = {"from_attributes": True}

    id: str
    canonical_title: str
    canonical_designer: str
    variant_name: str | None
    status: str


class FamilyTagResponse(BaseModel):
    """Tag assigned to a family."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    category: str | None
    is_predefined: bool
    source: str
    assigned_at: str | None


class FamilyResponse(BaseModel):
    """Family response schema."""

    model_config = {"from_attributes": True}

    id: str
    canonical_name: str
    canonical_designer: str
    name_override: str | None
    designer_override: str | None
    description: str | None
    detection_method: str
    detection_confidence: float | None
    display_name: str
    display_designer: str
    variant_count: int
    created_at: datetime
    updated_at: datetime


class FamilyDetailResponse(FamilyResponse):
    """Family response with variants included."""

    designs: list[DesignSummaryResponse]
    tags: list[FamilyTagResponse]


class FamilyListResponse(BaseModel):
    """Paginated list of families."""

    items: list[FamilyResponse]
    total: int
    page: int
    limit: int


class CreateFamilyRequest(BaseModel):
    """Request to create a new family."""

    name: str = Field(..., min_length=1, max_length=512)
    designer: str = Field(default="Unknown", max_length=255)
    description: str | None = Field(default=None, max_length=5000)


class UpdateFamilyRequest(BaseModel):
    """Request to update a family."""

    name_override: str | None = Field(default=None, max_length=512)
    designer_override: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)


class GroupDesignsRequest(BaseModel):
    """Request to group designs into a family."""

    design_ids: list[str] = Field(..., min_length=1, max_length=100)
    family_name: str | None = Field(default=None, max_length=512)
    family_id: str | None = None


class UngroupDesignRequest(BaseModel):
    """Request to remove a design from a family."""

    design_id: str


class DetectionResultResponse(BaseModel):
    """Result of family detection."""

    families_created: int
    designs_grouped: int
    families_updated: int


# =============================================================================
# Family CRUD Endpoints
# =============================================================================


@router.get("", response_model=FamilyListResponse)
async def list_families(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    designer: str | None = Query(None, description="Filter by designer"),
    db: AsyncSession = Depends(get_db),
) -> FamilyListResponse:
    """List all design families with pagination."""
    service = FamilyService(db)
    families, total = await service.list_families(page=page, limit=limit, designer=designer)

    return FamilyListResponse(
        items=[
            FamilyResponse(
                id=f.id,
                canonical_name=f.canonical_name,
                canonical_designer=f.canonical_designer,
                name_override=f.name_override,
                designer_override=f.designer_override,
                description=f.description,
                detection_method=f.detection_method.value,
                detection_confidence=f.detection_confidence,
                display_name=f.display_name,
                display_designer=f.display_designer,
                variant_count=f.variant_count,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in families
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{family_id}", response_model=FamilyDetailResponse)
async def get_family(
    family_id: str,
    db: AsyncSession = Depends(get_db),
) -> FamilyDetailResponse:
    """Get a family with its variants."""
    service = FamilyService(db)
    family = await service.get_family(family_id)

    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    # Get tags
    tags = await service.get_family_tags(family_id)

    return FamilyDetailResponse(
        id=family.id,
        canonical_name=family.canonical_name,
        canonical_designer=family.canonical_designer,
        name_override=family.name_override,
        designer_override=family.designer_override,
        description=family.description,
        detection_method=family.detection_method.value,
        detection_confidence=family.detection_confidence,
        display_name=family.display_name,
        display_designer=family.display_designer,
        variant_count=family.variant_count,
        created_at=family.created_at,
        updated_at=family.updated_at,
        designs=[
            DesignSummaryResponse(
                id=d.id,
                canonical_title=d.canonical_title,
                canonical_designer=d.canonical_designer,
                variant_name=d.variant_name,
                status=d.status.value,
            )
            for d in family.designs
        ],
        tags=[FamilyTagResponse(**t) for t in tags],
    )


@router.post("", response_model=FamilyResponse)
async def create_family(
    request: CreateFamilyRequest,
    db: AsyncSession = Depends(get_db),
) -> FamilyResponse:
    """Create a new design family."""
    service = FamilyService(db)
    family = await service.create_family(
        name=request.name,
        designer=request.designer,
        detection_method=FamilyDetectionMethod.MANUAL,
    )

    if request.description:
        family.description = request.description
        await db.flush()

    await db.commit()

    logger.info("family_created_via_api", family_id=family.id, name=request.name)

    return FamilyResponse(
        id=family.id,
        canonical_name=family.canonical_name,
        canonical_designer=family.canonical_designer,
        name_override=family.name_override,
        designer_override=family.designer_override,
        description=family.description,
        detection_method=family.detection_method.value,
        detection_confidence=family.detection_confidence,
        display_name=family.display_name,
        display_designer=family.display_designer,
        variant_count=family.variant_count,
        created_at=family.created_at,
        updated_at=family.updated_at,
    )


@router.patch("/{family_id}", response_model=FamilyResponse)
async def update_family(
    family_id: str,
    request: UpdateFamilyRequest,
    db: AsyncSession = Depends(get_db),
) -> FamilyResponse:
    """Update a family's metadata."""
    family = await db.get(DesignFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    # Update fields if provided
    if request.name_override is not None:
        family.name_override = request.name_override or None
    if request.designer_override is not None:
        family.designer_override = request.designer_override or None
    if request.description is not None:
        family.description = request.description or None

    await db.commit()

    logger.info("family_updated_via_api", family_id=family.id)

    return FamilyResponse(
        id=family.id,
        canonical_name=family.canonical_name,
        canonical_designer=family.canonical_designer,
        name_override=family.name_override,
        designer_override=family.designer_override,
        description=family.description,
        detection_method=family.detection_method.value,
        detection_confidence=family.detection_confidence,
        display_name=family.display_name,
        display_designer=family.display_designer,
        variant_count=family.variant_count,
        created_at=family.created_at,
        updated_at=family.updated_at,
    )


@router.delete("/{family_id}")
async def delete_family(
    family_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a family (orphans its designs)."""
    family = await db.get(DesignFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    service = FamilyService(db)
    designs_removed = await service.dissolve_family(family)
    await db.commit()

    logger.info(
        "family_deleted_via_api",
        family_id=family_id,
        designs_removed=designs_removed,
    )

    return {"message": "Family deleted", "designs_removed": designs_removed}


# =============================================================================
# Family Grouping Endpoints
# =============================================================================


@router.post("/group", response_model=FamilyResponse)
async def group_designs(
    request: GroupDesignsRequest,
    db: AsyncSession = Depends(get_db),
) -> FamilyResponse:
    """Group multiple designs into a new or existing family."""
    service = FamilyService(db)

    try:
        family = await service.group_designs(
            design_ids=request.design_ids,
            family_name=request.family_name,
            family_id=request.family_id,
        )
        await db.commit()

        logger.info(
            "designs_grouped_via_api",
            family_id=family.id,
            design_count=len(request.design_ids),
        )

        return FamilyResponse(
            id=family.id,
            canonical_name=family.canonical_name,
            canonical_designer=family.canonical_designer,
            name_override=family.name_override,
            designer_override=family.designer_override,
            description=family.description,
            detection_method=family.detection_method.value,
            detection_confidence=family.detection_confidence,
            display_name=family.display_name,
            display_designer=family.display_designer,
            variant_count=family.variant_count,
            created_at=family.created_at,
            updated_at=family.updated_at,
        )

    except FamilyError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{family_id}/ungroup")
async def ungroup_design(
    family_id: str,
    request: UngroupDesignRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a design from a family."""
    # Verify family exists
    family = await db.get(DesignFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    # Get design
    design = await db.get(Design, request.design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if design.family_id != family_id:
        raise HTTPException(status_code=400, detail="Design is not in this family")

    service = FamilyService(db)
    await service.remove_from_family(design)
    await db.commit()

    logger.info(
        "design_ungrouped_via_api",
        design_id=request.design_id,
        family_id=family_id,
    )

    return {"message": "Design removed from family"}


@router.delete("/{family_id}/dissolve")
async def dissolve_family(
    family_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dissolve a family, removing all designs from it."""
    family = await db.get(DesignFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    service = FamilyService(db)
    designs_removed = await service.dissolve_family(family)
    await db.commit()

    logger.info(
        "family_dissolved_via_api",
        family_id=family_id,
        designs_removed=designs_removed,
    )

    return {"message": "Family dissolved", "designs_removed": designs_removed}


# =============================================================================
# Detection Endpoints
# =============================================================================


@router.post("/detect", response_model=DetectionResultResponse)
async def run_detection(
    db: AsyncSession = Depends(get_db),
) -> DetectionResultResponse:
    """Run family detection on all designs without families.

    This endpoint triggers name-pattern-based family detection on all
    designs that are not currently in a family.
    """
    service = FamilyService(db)

    # Get all designs without families
    result = await db.execute(
        select(Design).where(Design.family_id.is_(None))
    )
    orphan_designs = result.scalars().all()

    families_created = 0
    designs_grouped = 0
    families_updated = 0

    for design in orphan_designs:
        # Extract family info
        info = service.extract_family_info(design.canonical_title)

        if not info.variant_name:
            # No variant pattern - skip
            continue

        # Check if family already exists
        existing_family = await service.find_existing_family(
            info.base_name,
            design.canonical_designer,
        )

        if existing_family:
            # Add to existing family
            await service.add_to_family(design, existing_family, info.variant_name)
            designs_grouped += 1
            families_updated += 1
        else:
            # Look for other designs that could form a family
            candidates = await service.find_family_candidates_by_name(design)

            if candidates:
                # Create new family with this design and candidates
                family = await service.create_family(
                    name=info.base_name,
                    designer=design.canonical_designer,
                    detection_method=FamilyDetectionMethod.NAME_PATTERN,
                    detection_confidence=0.8,
                )

                # Add this design
                await service.add_to_family(design, family, info.variant_name)
                designs_grouped += 1

                # Add candidates
                for candidate, variant in candidates:
                    if not candidate.family_id:  # Only if not already in a family
                        await service.add_to_family(candidate, family, variant)
                        designs_grouped += 1

                families_created += 1

    await db.commit()

    logger.info(
        "family_detection_complete",
        families_created=families_created,
        designs_grouped=designs_grouped,
        families_updated=families_updated,
    )

    return DetectionResultResponse(
        families_created=families_created,
        designs_grouped=designs_grouped,
        families_updated=families_updated,
    )


@router.post("/designs/{design_id}/detect-family")
async def detect_family_for_design(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Detect family for a specific design.

    Attempts to find or create a family for the given design based on
    name pattern matching.
    """
    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if design.family_id:
        raise HTTPException(status_code=400, detail="Design already in a family")

    service = FamilyService(db)

    # Extract family info
    info = service.extract_family_info(design.canonical_title)

    if not info.variant_name:
        return {"message": "No variant pattern detected", "family_id": None}

    # Check if family already exists
    existing_family = await service.find_existing_family(
        info.base_name,
        design.canonical_designer,
    )

    if existing_family:
        await service.add_to_family(design, existing_family, info.variant_name)
        await db.commit()
        return {
            "message": "Added to existing family",
            "family_id": existing_family.id,
            "family_name": existing_family.display_name,
        }

    # Look for candidates
    candidates = await service.find_family_candidates_by_name(design)

    if candidates:
        # Create new family
        family = await service.create_family(
            name=info.base_name,
            designer=design.canonical_designer,
            detection_method=FamilyDetectionMethod.NAME_PATTERN,
            detection_confidence=0.8,
        )

        # Add this design
        await service.add_to_family(design, family, info.variant_name)

        # Add candidates
        for candidate, variant in candidates:
            if not candidate.family_id:
                await service.add_to_family(candidate, family, variant)

        await db.commit()
        return {
            "message": "Created new family",
            "family_id": family.id,
            "family_name": family.display_name,
            "variants_found": len(candidates) + 1,
        }

    return {"message": "No family candidates found", "family_id": None}


# =============================================================================
# Family-Design Relationship Endpoints
# =============================================================================


@router.post("/{family_id}/designs")
async def add_design_to_family(
    family_id: str,
    design_id: str = Query(..., description="Design ID to add"),
    variant_name: str | None = Query(None, description="Optional variant name"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a design to a family."""
    family = await db.get(DesignFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if design.family_id and design.family_id != family_id:
        raise HTTPException(
            status_code=400,
            detail="Design already belongs to another family"
        )

    service = FamilyService(db)
    await service.add_to_family(design, family, variant_name)
    await db.commit()

    logger.info(
        "design_added_to_family_via_api",
        design_id=design_id,
        family_id=family_id,
    )

    return {
        "message": "Design added to family",
        "design_id": design_id,
        "family_id": family_id,
        "variant_name": design.variant_name,
    }


@router.delete("/{family_id}/designs/{design_id}")
async def remove_design_from_family(
    family_id: str,
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a design from a family."""
    family = await db.get(DesignFamily, family_id)
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")

    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if design.family_id != family_id:
        raise HTTPException(status_code=400, detail="Design is not in this family")

    service = FamilyService(db)
    await service.remove_from_family(design)
    await db.commit()

    logger.info(
        "design_removed_from_family_via_api",
        design_id=design_id,
        family_id=family_id,
    )

    return {"message": "Design removed from family"}
