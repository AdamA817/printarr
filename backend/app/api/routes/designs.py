"""Design API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.db.models import Design, DesignSource, ExternalMetadataSource, ExternalSourceType
from app.schemas.design import (
    ChannelSummary,
    DesignDetail,
    DesignList,
    DesignListItem,
    DesignSourceResponse,
    ExternalMetadataResponse,
)

router = APIRouter(prefix="/designs", tags=["designs"])


@router.get("/", response_model=DesignList)
async def list_designs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    channel_id: Optional[str] = Query(None, description="Filter by channel ID"),
    db: AsyncSession = Depends(get_db),
) -> DesignList:
    """List all designs with pagination and filtering."""
    # Build base query with eager loading
    query = select(Design).options(
        selectinload(Design.sources).selectinload(DesignSource.channel),
        selectinload(Design.external_metadata_sources),
    )

    # Apply filters
    if status:
        query = query.where(Design.status == status)

    if channel_id:
        # Filter by designs that have a source from this channel
        query = query.where(
            Design.id.in_(
                select(DesignSource.design_id).where(DesignSource.channel_id == channel_id)
            )
        )

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Design.created_at.desc()).offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    designs = result.scalars().all()

    # Calculate total pages
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Transform to response items
    items = []
    for design in designs:
        # Get first source's channel
        channel = None
        if design.sources:
            preferred = next((s for s in design.sources if s.is_preferred), design.sources[0])
            if preferred.channel:
                channel = ChannelSummary(
                    id=preferred.channel.id,
                    title=preferred.channel.title,
                )

        # Check for Thangs link
        has_thangs = any(
            em.source_type == ExternalSourceType.THANGS
            for em in design.external_metadata_sources
        )

        # Derive file types from primary_file_types field
        file_types = []
        if design.primary_file_types:
            file_types = [ft.strip() for ft in design.primary_file_types.split(",") if ft.strip()]

        items.append(
            DesignListItem(
                id=design.id,
                canonical_title=design.canonical_title,
                canonical_designer=design.canonical_designer,
                status=design.status,
                multicolor=design.multicolor,
                file_types=file_types,
                created_at=design.created_at,
                updated_at=design.updated_at,
                channel=channel,
                has_thangs_link=has_thangs,
            )
        )

    return DesignList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{design_id}", response_model=DesignDetail)
async def get_design(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> DesignDetail:
    """Get a single design by ID with full details."""
    # Query with eager loading of relationships
    query = (
        select(Design)
        .options(
            selectinload(Design.sources).selectinload(DesignSource.channel),
            selectinload(Design.external_metadata_sources),
        )
        .where(Design.id == design_id)
    )

    result = await db.execute(query)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Transform sources
    sources = []
    for source in design.sources:
        channel_summary = None
        if source.channel:
            channel_summary = ChannelSummary(
                id=source.channel.id,
                title=source.channel.title,
            )
        sources.append(
            DesignSourceResponse(
                id=source.id,
                channel_id=source.channel_id,
                message_id=source.message_id,
                source_rank=source.source_rank,
                is_preferred=source.is_preferred,
                caption_snapshot=source.caption_snapshot,
                created_at=source.created_at,
                channel=channel_summary,
            )
        )

    # Transform external metadata
    external_metadata = [
        ExternalMetadataResponse(
            id=em.id,
            source_type=em.source_type,
            external_id=em.external_id,
            external_url=em.external_url,
            confidence_score=em.confidence_score,
            match_method=em.match_method,
            is_user_confirmed=em.is_user_confirmed,
            fetched_title=em.fetched_title,
            fetched_designer=em.fetched_designer,
            fetched_tags=em.fetched_tags,
            last_fetched_at=em.last_fetched_at,
            created_at=em.created_at,
        )
        for em in design.external_metadata_sources
    ]

    return DesignDetail(
        id=design.id,
        canonical_title=design.canonical_title,
        canonical_designer=design.canonical_designer,
        status=design.status,
        multicolor=design.multicolor,
        primary_file_types=design.primary_file_types,
        total_size_bytes=design.total_size_bytes,
        title_override=design.title_override,
        designer_override=design.designer_override,
        multicolor_override=design.multicolor_override,
        notes=design.notes,
        metadata_authority=design.metadata_authority,
        metadata_confidence=design.metadata_confidence,
        display_title=design.display_title,
        display_designer=design.display_designer,
        display_multicolor=design.display_multicolor,
        created_at=design.created_at,
        updated_at=design.updated_at,
        sources=sources,
        external_metadata=external_metadata,
    )
