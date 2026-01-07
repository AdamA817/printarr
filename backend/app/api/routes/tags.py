"""Tag API endpoints for managing design tags."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Design, Tag
from app.db.models.enums import TagSource
from app.services.tag import TagError, TagService

logger = get_logger(__name__)

router = APIRouter(prefix="/tags", tags=["tags"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class TagResponse(BaseModel):
    """Tag response schema."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    category: str | None
    is_predefined: bool
    usage_count: int


class DesignTagResponse(BaseModel):
    """Design tag response with assignment info."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    category: str | None
    is_predefined: bool
    source: str
    assigned_at: str | None


class TagListResponse(BaseModel):
    """List of tags response."""

    items: list[TagResponse]
    total: int


class TagCategoriesResponse(BaseModel):
    """Tags grouped by category."""

    categories: dict[str, list[TagResponse]]


class AddTagsRequest(BaseModel):
    """Request to add tags to a design."""

    tags: list[str] = Field(..., min_length=1, max_length=20)
    source: TagSource = TagSource.USER


class AddTagsResponse(BaseModel):
    """Response after adding tags."""

    added: list[str]
    already_present: list[str]
    created: list[str]


class RemoveTagResponse(BaseModel):
    """Response after removing a tag."""

    design_id: str
    tag_id: str
    message: str


# =============================================================================
# Tag Endpoints
# =============================================================================


@router.get("", response_model=TagListResponse)
async def list_tags(
    category: str | None = Query(None, description="Filter by category"),
    include_zero_usage: bool = Query(True, description="Include unused tags"),
    db: AsyncSession = Depends(get_db),
) -> TagListResponse:
    """List all tags with usage counts."""
    service = TagService(db)
    tags = await service.get_all_tags(
        category=category,
        include_zero_usage=include_zero_usage,
    )

    return TagListResponse(
        items=[TagResponse(**t) for t in tags],
        total=len(tags),
    )


@router.get("/categories", response_model=TagCategoriesResponse)
async def get_tag_categories(
    db: AsyncSession = Depends(get_db),
) -> TagCategoriesResponse:
    """Get all tags grouped by category."""
    service = TagService(db)
    categories = await service.get_tags_by_category()

    return TagCategoriesResponse(
        categories={
            cat: [TagResponse(**t) for t in tags]
            for cat, tags in categories.items()
        }
    )


@router.get("/search", response_model=TagListResponse)
async def search_tags(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    db: AsyncSession = Depends(get_db),
) -> TagListResponse:
    """Search tags for autocomplete."""
    service = TagService(db)
    tags = await service.search_tags(query=q, limit=limit)

    return TagListResponse(
        items=[TagResponse(**t) for t in tags],
        total=len(tags),
    )


@router.get("/top", response_model=list[str])
async def get_top_tags(
    limit: int = Query(300, ge=1, le=500, description="Max tags to return"),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Get top tags by usage count for AI prompt context.

    Returns a list of tag names sorted by usage count descending.
    This is used by the AI service to build prompt context for tag normalization.
    """
    result = await db.execute(
        select(Tag.name)
        .where(Tag.usage_count > 0)
        .order_by(Tag.usage_count.desc())
        .limit(limit)
    )
    return [row[0] for row in result.all()]


# =============================================================================
# Design Tag Endpoints
# =============================================================================


@router.get("/design/{design_id}/", response_model=list[DesignTagResponse])
async def get_design_tags(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[DesignTagResponse]:
    """Get all tags for a design."""
    # Verify design exists
    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    service = TagService(db)
    tags = await service.get_design_tags(design_id)

    return [DesignTagResponse(**t) for t in tags]


@router.post("/design/{design_id}/", response_model=AddTagsResponse)
async def add_tags_to_design(
    design_id: str,
    request: AddTagsRequest,
    db: AsyncSession = Depends(get_db),
) -> AddTagsResponse:
    """Add tags to a design.

    Tags are created if they don't exist. Returns info about which tags
    were added, which were already present, and which were newly created.
    """
    # Verify design exists
    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    service = TagService(db)
    added: list[str] = []
    already_present: list[str] = []
    created: list[str] = []

    for tag_name in request.tags:
        # Check if tag already exists
        existing_result = await db.execute(
            select(Tag).where(Tag.name == tag_name.strip().lower())
        )
        tag_existed = existing_result.scalar_one_or_none() is not None

        tag = await service.get_or_create_tag(tag_name)

        if not tag_existed:
            created.append(tag_name)

        # Try to add to design
        try:
            await service.add_tag_to_design(design_id, tag.id, request.source)
            added.append(tag_name)
        except TagError as e:
            if "already assigned" in str(e):
                already_present.append(tag_name)
            else:
                raise HTTPException(status_code=400, detail=str(e))

    await db.commit()

    logger.info(
        "tags_added_to_design",
        design_id=design_id,
        added=added,
        already_present=already_present,
        created=created,
    )

    return AddTagsResponse(
        added=added,
        already_present=already_present,
        created=created,
    )


@router.delete("/design/{design_id}/{tag_id}", response_model=RemoveTagResponse)
async def remove_tag_from_design(
    design_id: str,
    tag_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemoveTagResponse:
    """Remove a tag from a design."""
    # Verify design exists
    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    service = TagService(db)
    removed = await service.remove_tag_from_design(design_id, tag_id)

    if not removed:
        raise HTTPException(status_code=404, detail="Tag not found on design")

    await db.commit()

    return RemoveTagResponse(
        design_id=design_id,
        tag_id=tag_id,
        message="Tag removed from design",
    )
