"""Design API endpoints."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Design, DesignSource, ExternalMetadataSource, ExternalSourceType
from app.db.models.enums import MatchMethod, MulticolorStatus
from app.schemas.design import (
    ChannelSummary,
    DesignDetail,
    DesignList,
    DesignListItem,
    DesignSourceResponse,
    ExternalMetadataResponse,
)
from app.services.thangs import ThangsAdapter

logger = get_logger(__name__)


class SortOrder(str, Enum):
    """Sort order options."""

    ASC = "ASC"
    DESC = "DESC"


class SortField(str, Enum):
    """Sort field options for designs."""

    CREATED_AT = "created_at"
    CANONICAL_TITLE = "canonical_title"
    CANONICAL_DESIGNER = "canonical_designer"
    TOTAL_SIZE_BYTES = "total_size_bytes"


class RefreshMetadataResponse(BaseModel):
    """Response for metadata refresh endpoint."""

    design_id: str
    sources_refreshed: int
    sources_failed: int


class ThangsLinkRequest(BaseModel):
    """Request body for linking a design to Thangs."""

    model_id: str
    url: str


class ThangsLinkByUrlRequest(BaseModel):
    """Request body for linking a design to Thangs by URL."""

    url: str


class ThangsLinkResponse(BaseModel):
    """Response for Thangs link endpoint."""

    id: str
    design_id: str
    source_type: str
    external_id: str
    external_url: str
    confidence_score: float
    match_method: str
    is_user_confirmed: bool
    fetched_title: Optional[str] = None
    fetched_designer: Optional[str] = None
    fetched_tags: Optional[str] = None
    last_fetched_at: Optional[datetime] = None
    created_at: datetime


class MergeDesignsRequest(BaseModel):
    """Request body for merging designs."""

    source_design_ids: list[str]


class UnmergeDesignRequest(BaseModel):
    """Request body for unmerging a design."""

    source_ids: list[str]


class MergeDesignsResponse(BaseModel):
    """Response for merge designs endpoint."""

    merged_design_id: str
    merged_source_count: int
    deleted_design_ids: list[str]


class UnmergeDesignResponse(BaseModel):
    """Response for unmerge design endpoint."""

    original_design_id: str
    new_design_id: str
    moved_source_count: int


router = APIRouter(prefix="/designs", tags=["designs"])


@router.get("/", response_model=DesignList)
async def list_designs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    channel_id: Optional[str] = Query(None, description="Filter by channel ID"),
    file_type: Optional[str] = Query(None, description="Filter by primary file type (STL, 3MF, OBJ, etc.)"),
    multicolor: Optional[MulticolorStatus] = Query(None, description="Filter by multicolor status"),
    has_thangs_link: Optional[bool] = Query(None, description="Filter by Thangs link status"),
    designer: Optional[str] = Query(None, description="Filter by designer (partial match)"),
    q: Optional[str] = Query(None, description="Full-text search on title and designer"),
    sort_by: SortField = Query(SortField.CREATED_AT, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order (ASC or DESC)"),
    db: AsyncSession = Depends(get_db),
) -> DesignList:
    """List all designs with pagination, filtering, search, and sorting."""
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

    if file_type:
        # Filter by primary file type (case-insensitive, using LIKE for partial match in CSV field)
        query = query.where(Design.primary_file_types.ilike(f"%{file_type}%"))

    if multicolor:
        query = query.where(Design.multicolor == multicolor)

    if designer:
        # Case-insensitive partial match on designer
        query = query.where(Design.canonical_designer.ilike(f"%{designer}%"))

    if has_thangs_link is not None:
        # Subquery to find designs with Thangs links
        designs_with_thangs = select(ExternalMetadataSource.design_id).where(
            ExternalMetadataSource.source_type == ExternalSourceType.THANGS
        )
        if has_thangs_link:
            query = query.where(Design.id.in_(designs_with_thangs))
        else:
            query = query.where(Design.id.notin_(designs_with_thangs))

    if q:
        # Full-text search on title and designer (case-insensitive)
        search_pattern = f"%{q}%"
        query = query.where(
            or_(
                Design.canonical_title.ilike(search_pattern),
                Design.canonical_designer.ilike(search_pattern),
            )
        )

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Design, sort_by.value)
    if sort_order == SortOrder.ASC:
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

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


@router.post("/{design_id}/refresh-metadata", response_model=RefreshMetadataResponse)
async def refresh_metadata(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> RefreshMetadataResponse:
    """Refresh external metadata for a design.

    Fetches metadata from Thangs API for any external links that haven't
    been fetched yet or need refreshing.
    """
    # Get design with external sources
    query = (
        select(Design)
        .options(selectinload(Design.external_metadata_sources))
        .where(Design.id == design_id)
    )
    result = await db.execute(query)
    design = result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Collect sources that need fetching (Thangs only for now)
    thangs_sources = [
        em for em in design.external_metadata_sources
        if em.source_type == ExternalSourceType.THANGS
    ]

    if not thangs_sources:
        return RefreshMetadataResponse(
            design_id=design_id,
            sources_refreshed=0,
            sources_failed=0,
        )

    # Prepare for httpx calls - collect source info before closing DB
    sources_to_fetch = [
        {"id": s.id, "external_id": s.external_id}
        for s in thangs_sources
    ]

    # Commit current transaction to avoid greenlet conflicts
    await db.commit()

    # Fetch metadata using httpx (outside DB context)
    fetched_results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for source_info in sources_to_fetch:
            try:
                metadata = await _fetch_thangs_metadata(client, source_info["external_id"])
                fetched_results.append({
                    "source_id": source_info["id"],
                    "success": True,
                    "metadata": metadata,
                })
            except Exception as e:
                logger.warning(
                    "thangs_fetch_failed",
                    source_id=source_info["id"],
                    error=str(e),
                )
                fetched_results.append({
                    "source_id": source_info["id"],
                    "success": False,
                    "metadata": None,
                })

    # Update database with fetched metadata
    sources_refreshed = 0
    sources_failed = 0

    for result_item in fetched_results:
        if result_item["success"] and result_item["metadata"]:
            metadata = result_item["metadata"]
            await db.execute(
                update(ExternalMetadataSource)
                .where(ExternalMetadataSource.id == result_item["source_id"])
                .values(
                    fetched_title=metadata.get("title"),
                    fetched_designer=metadata.get("designer"),
                    fetched_tags=",".join(metadata.get("tags", [])) if metadata.get("tags") else None,
                    last_fetched_at=datetime.utcnow(),
                )
            )
            sources_refreshed += 1
        else:
            sources_failed += 1

    await db.commit()

    logger.info(
        "metadata_refreshed",
        design_id=design_id,
        refreshed=sources_refreshed,
        failed=sources_failed,
    )

    return RefreshMetadataResponse(
        design_id=design_id,
        sources_refreshed=sources_refreshed,
        sources_failed=sources_failed,
    )


async def _fetch_thangs_metadata(client: httpx.AsyncClient, model_id: str) -> dict | None:
    """Fetch metadata from Thangs API."""
    url = f"https://api.thangs.com/models/{model_id}"

    response = await client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Printarr/1.0",
        },
    )

    if response.status_code == 200:
        data = response.json()
        designer = None
        if "owner" in data and isinstance(data["owner"], dict):
            designer = data["owner"].get("username") or data["owner"].get("name")
        elif "creator" in data and isinstance(data["creator"], dict):
            designer = data["creator"].get("username") or data["creator"].get("name")
        elif "author" in data:
            designer = data["author"]

        return {
            "title": data.get("name") or data.get("title"),
            "designer": designer,
            "tags": data.get("tags", []),
        }
    elif response.status_code == 404:
        logger.warning("thangs_model_not_found", model_id=model_id)
        return None
    else:
        logger.warning(
            "thangs_api_error",
            model_id=model_id,
            status=response.status_code,
        )
        return None


@router.post("/{design_id}/thangs-link", response_model=ThangsLinkResponse)
async def link_to_thangs(
    design_id: str,
    request: ThangsLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> ThangsLinkResponse:
    """Manually link a design to a Thangs model.

    Creates or updates an ExternalMetadataSource with:
    - source_type=THANGS
    - match_method=MANUAL
    - confidence_score=1.0
    - is_user_confirmed=True

    Immediately fetches and stores Thangs metadata.
    """
    # Verify design exists
    design_query = select(Design).where(Design.id == design_id)
    design_result = await db.execute(design_query)
    design = design_result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Check if Thangs link already exists
    existing_query = select(ExternalMetadataSource).where(
        ExternalMetadataSource.design_id == design_id,
        ExternalMetadataSource.source_type == ExternalSourceType.THANGS,
    )
    existing_result = await db.execute(existing_query)
    existing_source = existing_result.scalar_one_or_none()

    if existing_source:
        # Update existing source
        existing_source.external_id = request.model_id
        existing_source.external_url = request.url
        existing_source.confidence_score = 1.0
        existing_source.match_method = MatchMethod.MANUAL
        existing_source.is_user_confirmed = True
        source = existing_source
        logger.info(
            "thangs_link_updated",
            design_id=design_id,
            model_id=request.model_id,
        )
    else:
        # Create new source
        source = ExternalMetadataSource(
            design_id=design_id,
            source_type=ExternalSourceType.THANGS,
            external_id=request.model_id,
            external_url=request.url,
            confidence_score=1.0,
            match_method=MatchMethod.MANUAL,
            is_user_confirmed=True,
        )
        db.add(source)
        logger.info(
            "thangs_link_created",
            design_id=design_id,
            model_id=request.model_id,
        )

    await db.flush()

    # Fetch metadata from Thangs API
    adapter = ThangsAdapter(db)
    try:
        metadata = await adapter.fetch_thangs_metadata(request.model_id)
        if metadata:
            source.fetched_title = metadata.get("title")
            source.fetched_designer = metadata.get("designer")
            tags = metadata.get("tags", [])
            source.fetched_tags = ",".join(tags) if tags else None
            source.last_fetched_at = datetime.utcnow()
            logger.info(
                "thangs_metadata_fetched_on_link",
                design_id=design_id,
                model_id=request.model_id,
                title=source.fetched_title,
            )
    finally:
        await adapter.close()

    await db.commit()

    return ThangsLinkResponse(
        id=source.id,
        design_id=source.design_id,
        source_type=source.source_type.value,
        external_id=source.external_id,
        external_url=source.external_url,
        confidence_score=source.confidence_score,
        match_method=source.match_method.value,
        is_user_confirmed=source.is_user_confirmed,
        fetched_title=source.fetched_title,
        fetched_designer=source.fetched_designer,
        fetched_tags=source.fetched_tags,
        last_fetched_at=source.last_fetched_at,
        created_at=source.created_at,
    )


@router.post("/{design_id}/thangs-link-by-url", response_model=ThangsLinkResponse)
async def link_to_thangs_by_url(
    design_id: str,
    request: ThangsLinkByUrlRequest,
    db: AsyncSession = Depends(get_db),
) -> ThangsLinkResponse:
    """Link a design to Thangs using a URL.

    Extracts the model ID from the thangs.com URL and links the design.
    Same behavior as thangs-link but takes URL only.
    """
    # Extract model_id from URL
    detected = ThangsAdapter.detect_thangs_url(request.url)
    if not detected:
        raise HTTPException(
            status_code=400,
            detail="Invalid Thangs URL. Could not extract model ID.",
        )

    model_id = detected[0]["model_id"]
    canonical_url = detected[0]["url"]

    # Delegate to the main link function
    link_request = ThangsLinkRequest(model_id=model_id, url=canonical_url)
    return await link_to_thangs(design_id, link_request, db)


@router.delete("/{design_id}/thangs-link", status_code=204)
async def unlink_from_thangs(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the Thangs link from a design.

    Returns 204 on success, 404 if design not found or not linked.
    """
    # Verify design exists
    design_query = select(Design).where(Design.id == design_id)
    design_result = await db.execute(design_query)
    design = design_result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Find and delete the Thangs link
    source_query = select(ExternalMetadataSource).where(
        ExternalMetadataSource.design_id == design_id,
        ExternalMetadataSource.source_type == ExternalSourceType.THANGS,
    )
    source_result = await db.execute(source_query)
    source = source_result.scalar_one_or_none()

    if source is None:
        raise HTTPException(status_code=404, detail="Design is not linked to Thangs")

    await db.delete(source)
    await db.commit()

    logger.info(
        "thangs_link_removed",
        design_id=design_id,
        model_id=source.external_id,
    )


@router.post("/{design_id}/merge", response_model=MergeDesignsResponse)
async def merge_designs(
    design_id: str,
    request: MergeDesignsRequest,
    db: AsyncSession = Depends(get_db),
) -> MergeDesignsResponse:
    """Merge multiple designs into the target design.

    Consolidates sources from the source designs into the target design.
    The source designs are deleted after their sources are moved.

    - Updates all DesignSource records to point to target design
    - Consolidates file types and total size
    - Preserves ExternalMetadataSource links (deduped by source_type)
    - Deletes the source design records (now empty)
    """
    # Validation: cannot merge with itself
    if design_id in request.source_design_ids:
        raise HTTPException(
            status_code=400,
            detail="Cannot merge a design with itself",
        )

    if not request.source_design_ids:
        raise HTTPException(
            status_code=400,
            detail="source_design_ids must not be empty",
        )

    # Load target design with sources
    target_query = (
        select(Design)
        .options(
            selectinload(Design.sources),
            selectinload(Design.external_metadata_sources),
        )
        .where(Design.id == design_id)
    )
    target_result = await db.execute(target_query)
    target_design = target_result.scalar_one_or_none()

    if target_design is None:
        raise HTTPException(status_code=404, detail="Target design not found")

    # Load source designs with their sources
    source_query = (
        select(Design)
        .options(
            selectinload(Design.sources),
            selectinload(Design.external_metadata_sources),
        )
        .where(Design.id.in_(request.source_design_ids))
    )
    source_result = await db.execute(source_query)
    source_designs = source_result.scalars().all()

    # Validate all source designs exist
    found_ids = {d.id for d in source_designs}
    missing_ids = set(request.source_design_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Source designs not found: {list(missing_ids)}",
        )

    # Track merged info
    merged_source_count = len(target_design.sources)
    deleted_design_ids = []
    all_file_types = set()
    total_size = target_design.total_size_bytes or 0

    # Collect existing file types from target
    if target_design.primary_file_types:
        all_file_types.update(
            ft.strip() for ft in target_design.primary_file_types.split(",") if ft.strip()
        )

    # Track existing external metadata source types
    existing_source_types = {
        em.source_type for em in target_design.external_metadata_sources
    }

    # Process each source design
    source_design_ids = [d.id for d in source_designs]

    for source_design in source_designs:
        merged_source_count += len(source_design.sources)

        # Collect file types
        if source_design.primary_file_types:
            all_file_types.update(
                ft.strip() for ft in source_design.primary_file_types.split(",") if ft.strip()
            )

        # Add to total size
        if source_design.total_size_bytes:
            total_size += source_design.total_size_bytes

        # Handle external metadata sources
        for em in list(source_design.external_metadata_sources):
            if em.source_type not in existing_source_types:
                existing_source_types.add(em.source_type)
            else:
                # Delete duplicate external metadata
                await db.execute(
                    update(ExternalMetadataSource)
                    .where(ExternalMetadataSource.id == em.id)
                    .values(design_id=None)  # Temporarily orphan it
                )

        deleted_design_ids.append(source_design.id)

    # Use SQL UPDATE to move all sources from source designs to target design
    # This avoids the cascade delete issue
    await db.execute(
        update(DesignSource)
        .where(DesignSource.design_id.in_(source_design_ids))
        .values(design_id=target_design.id, is_preferred=False)
    )

    # Move external metadata sources via SQL UPDATE
    await db.execute(
        update(ExternalMetadataSource)
        .where(ExternalMetadataSource.design_id.in_(source_design_ids))
        .values(design_id=target_design.id)
    )

    # Delete any orphaned external metadata (duplicates)
    await db.execute(
        update(ExternalMetadataSource)
        .where(ExternalMetadataSource.design_id == None)
        .values(design_id=target_design.id)  # This won't match if there are none
    )

    # Now refresh and delete the source designs
    for source_design in source_designs:
        # Expire to clear the stale relationship data
        await db.refresh(source_design)
        await db.delete(source_design)

    # Update target design metadata
    target_design.primary_file_types = ",".join(sorted(all_file_types)) if all_file_types else None
    target_design.total_size_bytes = total_size if total_size > 0 else None

    await db.commit()

    logger.info(
        "designs_merged",
        target_id=design_id,
        source_ids=deleted_design_ids,
        total_sources=merged_source_count,
    )

    return MergeDesignsResponse(
        merged_design_id=design_id,
        merged_source_count=merged_source_count,
        deleted_design_ids=deleted_design_ids,
    )


@router.post("/{design_id}/unmerge", response_model=UnmergeDesignResponse)
async def unmerge_design(
    design_id: str,
    request: UnmergeDesignRequest,
    db: AsyncSession = Depends(get_db),
) -> UnmergeDesignResponse:
    """Split specified sources from a design into a new design.

    Creates a new Design from the specified sources and moves them there.
    Recalculates file types and size for both designs.
    """
    if not request.source_ids:
        raise HTTPException(
            status_code=400,
            detail="source_ids must not be empty",
        )

    # Load design with sources
    design_query = (
        select(Design)
        .options(selectinload(Design.sources))
        .where(Design.id == design_id)
    )
    design_result = await db.execute(design_query)
    design = design_result.scalar_one_or_none()

    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Validate: cannot unmerge if only one source remains
    if len(design.sources) <= len(request.source_ids):
        raise HTTPException(
            status_code=400,
            detail="Cannot unmerge all sources. At least one source must remain.",
        )

    # Find the sources to move
    sources_to_move = [s for s in design.sources if s.id in request.source_ids]

    # Validate all source_ids exist in this design
    found_ids = {s.id for s in sources_to_move}
    missing_ids = set(request.source_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Sources not found in this design: {list(missing_ids)}",
        )

    # Create new design for the split sources
    # Use the first source to derive initial metadata
    first_source = sources_to_move[0]
    new_design = Design(
        canonical_title=design.canonical_title,
        canonical_designer=design.canonical_designer,
        status=design.status,
        multicolor=design.multicolor,
        metadata_authority=design.metadata_authority,
    )
    db.add(new_design)
    await db.flush()  # Get the new design ID

    # Move sources to new design
    for source in sources_to_move:
        source.design_id = new_design.id
        source.source_rank = sources_to_move.index(source) + 1

    # Set first moved source as preferred
    if sources_to_move:
        sources_to_move[0].is_preferred = True

    await db.commit()

    logger.info(
        "design_unmerged",
        original_id=design_id,
        new_id=new_design.id,
        moved_sources=len(sources_to_move),
    )

    return UnmergeDesignResponse(
        original_design_id=design_id,
        new_design_id=new_design.id,
        moved_source_count=len(sources_to_move),
    )
