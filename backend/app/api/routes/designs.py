"""Design API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db
from app.services.count_cache import get_approximate_count, count_cache
from app.db.models import Design, DesignSource, ExternalMetadataSource, ExternalSourceType
from app.db.models.design_tag import DesignTag
from app.db.models.enums import DesignStatus, MatchMethod, MetadataAuthority, MulticolorStatus
from app.db.models.preview_asset import PreviewAsset
from app.db.models.tag import Tag
from app.schemas.design import (
    ChannelSummary,
    DesignDetail,
    DesignList,
    DesignListItem,
    DesignSourceResponse,
    ExternalMetadataResponse,
    PreviewSummary,
    TagSummary,
)
from app.services.preview import PreviewService
from app.services.tag import TagService
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


class TagMatch(str, Enum):
    """Tag matching mode for filtering."""

    ANY = "any"  # Match designs with any of the specified tags (OR)
    ALL = "all"  # Match designs with all specified tags (AND)


class RefreshMetadataResponse(BaseModel):
    """Response for metadata refresh endpoint."""

    design_id: str
    sources_refreshed: int
    sources_failed: int
    images_cached: int = 0
    tags_imported: int = 0


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
    fetched_title: str | None = None
    fetched_designer: str | None = None
    fetched_tags: str | None = None
    last_fetched_at: datetime | None = None
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
    status: DesignStatus | None = Query(None, description="Filter by status"),
    channel_id: str | None = Query(None, description="Filter by channel ID"),
    file_type: str | None = Query(None, description="Filter by primary file type (STL, 3MF, OBJ, etc.)"),
    multicolor: MulticolorStatus | None = Query(None, description="Filter by multicolor status"),
    has_thangs_link: bool | None = Query(None, description="Filter by Thangs link status"),
    designer: str | None = Query(None, description="Filter by designer (partial match)"),
    tags: list[str] | None = Query(None, description="Filter by tag IDs"),
    tag_match: TagMatch = Query(TagMatch.ANY, description="Tag matching mode: 'any' (OR) or 'all' (AND)"),
    q: str | None = Query(None, description="Full-text search on title and designer"),
    sort_by: SortField = Query(SortField.CREATED_AT, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order (ASC or DESC)"),
    db: AsyncSession = Depends(get_db),
) -> DesignList:
    """List all designs with pagination, filtering, search, and sorting."""
    # Build base query with eager loading
    query = select(Design).options(
        selectinload(Design.sources).selectinload(DesignSource.channel),
        selectinload(Design.external_metadata_sources),
        selectinload(Design.design_tags).selectinload(DesignTag.tag),
        selectinload(Design.preview_assets),
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

    if tags:
        # Filter by tags - supports both "any" and "all" matching modes
        if tag_match == TagMatch.ALL:
            # All tags must match - use intersection of subqueries
            for tag_id in tags:
                designs_with_tag = select(DesignTag.design_id).where(
                    DesignTag.tag_id == tag_id
                )
                query = query.where(Design.id.in_(designs_with_tag))
        else:
            # Any tag matches - single subquery with OR
            designs_with_any_tag = select(DesignTag.design_id).where(
                DesignTag.tag_id.in_(tags)
            )
            query = query.where(Design.id.in_(designs_with_any_tag))

    if q:
        # Full-text search using PostgreSQL tsvector (#218)
        # Uses the search_vector generated column with GIN index for performance
        # For short queries (< 3 chars), fall back to trigram ILIKE for partial matching
        if len(q) >= 3:
            # Use full-text search with plainto_tsquery for natural language queries
            # Also include partial match via trigram for better UX
            search_condition = or_(
                text("search_vector @@ plainto_tsquery('english', :q)"),
                Design.canonical_title.ilike(f"%{q}%"),
            )
            query = query.where(search_condition).params(q=q)
        else:
            # Short queries use ILIKE with trigram index
            search_pattern = f"%{q}%"
            query = query.where(
                or_(
                    Design.canonical_title.ilike(search_pattern),
                    Design.canonical_designer.ilike(search_pattern),
                )
            )

    # Get total count (before pagination) - optimized (#219)
    # Use approximate count for unfiltered queries on large tables
    has_filters = any([status, channel_id, multicolor, file_type, designer, has_thangs_link, tags, q])
    is_approximate = False

    if not has_filters:
        # Try approximate count for unfiltered queries
        approx_count = await get_approximate_count(db, "designs")
        if approx_count is not None and approx_count > 10000:
            # Use approximate count for large tables
            total = approx_count
            is_approximate = True
        else:
            # Small table or no stats, use exact count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0
    else:
        # Filtered query - must use exact count
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

        # Build tag summaries
        design_tags = [
            TagSummary(
                id=dt.tag.id,
                name=dt.tag.name,
                category=dt.tag.category,
                source=dt.source,
            )
            for dt in design.design_tags
            if dt.tag is not None
        ]

        # Get primary preview (first one marked as primary, or first by sort order)
        primary_preview = None
        if design.preview_assets:
            # Find primary preview, or fall back to first by sort order
            primary = next(
                (p for p in design.preview_assets if p.is_primary),
                min(design.preview_assets, key=lambda p: p.sort_order)
            )
            primary_preview = PreviewSummary(
                id=primary.id,
                source=primary.source,
                file_path=primary.file_path,
                width=primary.width,
                height=primary.height,
            )

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
                tags=design_tags,
                primary_preview=primary_preview,
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

    # Prepare for fetching - collect source info before closing DB
    sources_to_fetch = [
        {"id": s.id, "external_id": s.external_id}
        for s in thangs_sources
    ]

    # Commit current transaction to avoid greenlet conflicts
    await db.commit()

    # Fetch metadata using ThangsAdapter (supports FlareSolverr for Cloudflare bypass)
    fetched_results = []
    thangs_adapter = ThangsAdapter(db)
    try:
        for source_info in sources_to_fetch:
            try:
                metadata = await thangs_adapter.fetch_thangs_metadata(source_info["external_id"])
                fetched_results.append({
                    "source_id": source_info["id"],
                    "success": metadata is not None,
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
    finally:
        await thangs_adapter.close()

    # Update database with fetched metadata
    sources_refreshed = 0
    sources_failed = 0
    total_images_cached = 0
    total_tags_imported = 0

    # Collect metadata for processing
    successful_metadata: list[dict] = []

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
                    last_fetched_at=datetime.now(timezone.utc),
                )
            )
            sources_refreshed += 1
            successful_metadata.append(metadata)

            # Update design with Thangs metadata (v0.7 - auto-apply on refresh)
            if metadata.get("title") or metadata.get("designer"):
                await db.execute(
                    update(Design)
                    .where(Design.id == design_id)
                    .values(
                        canonical_title=metadata.get("title") or Design.canonical_title,
                        canonical_designer=metadata.get("designer") or Design.canonical_designer,
                        metadata_authority=MetadataAuthority.THANGS,
                    )
                )
                logger.info(
                    "thangs_metadata_applied_on_refresh",
                    design_id=design_id,
                    title=metadata.get("title"),
                    designer=metadata.get("designer"),
                )
        else:
            sources_failed += 1

    await db.commit()

    # Cache images and import tags for successful fetches
    if successful_metadata:
        preview_service = PreviewService(db)
        tag_service = TagService(db)
        thangs_adapter = ThangsAdapter(db)

        for metadata in successful_metadata:
            # Cache images from Thangs (up to 10 per model)
            image_urls = metadata.get("images", [])
            if image_urls:
                try:
                    cached = await thangs_adapter.cache_thangs_images(
                        design_id=design_id,
                        image_urls=image_urls,
                        preview_service=preview_service,
                    )
                    total_images_cached += cached
                except Exception as e:
                    logger.warning(
                        "thangs_image_cache_failed",
                        design_id=design_id,
                        error=str(e),
                    )

            # Import tags from Thangs
            tags = metadata.get("tags", [])
            if tags:
                try:
                    imported = await thangs_adapter.import_thangs_tags(
                        design_id=design_id,
                        tags=tags,
                        tag_service=tag_service,
                    )
                    total_tags_imported += imported
                except Exception as e:
                    logger.warning(
                        "thangs_tag_import_failed",
                        design_id=design_id,
                        error=str(e),
                    )

        # Auto-select primary preview if images were cached
        if total_images_cached > 0:
            await preview_service.auto_select_primary(design_id)

        await db.commit()

    logger.info(
        "metadata_refreshed",
        design_id=design_id,
        refreshed=sources_refreshed,
        failed=sources_failed,
        images_cached=total_images_cached,
        tags_imported=total_tags_imported,
    )

    return RefreshMetadataResponse(
        design_id=design_id,
        sources_refreshed=sources_refreshed,
        sources_failed=sources_failed,
        images_cached=total_images_cached,
        tags_imported=total_tags_imported,
    )


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
            source.last_fetched_at = datetime.now(timezone.utc)
            logger.info(
                "thangs_metadata_fetched_on_link",
                design_id=design_id,
                model_id=request.model_id,
                title=source.fetched_title,
            )

            # Update design with Thangs metadata (v0.7 - auto-apply on link)
            if source.fetched_title:
                design.canonical_title = source.fetched_title
            if source.fetched_designer:
                design.canonical_designer = source.fetched_designer
            design.metadata_authority = MetadataAuthority.THANGS
            logger.info(
                "thangs_metadata_applied",
                design_id=design_id,
                title=design.canonical_title,
                designer=design.canonical_designer,
            )

            # Cache Thangs images (v0.7 - auto-cache on link)
            images = metadata.get("images", [])
            if images:
                preview_service = PreviewService(db)
                cached = await adapter.cache_thangs_images(
                    design_id=design_id,
                    image_urls=images,
                    preview_service=preview_service,
                )
                if cached > 0:
                    logger.info(
                        "thangs_images_cached_on_link",
                        design_id=design_id,
                        model_id=request.model_id,
                        images_cached=cached,
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
    sources_to_move[0]
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


# =============================================================================
# Download Actions
# =============================================================================


class WantResponse(BaseModel):
    """Response for want/download actions."""

    design_id: str
    job_id: str
    status: str
    message: str


class CancelDownloadResponse(BaseModel):
    """Response for cancel download action."""

    design_id: str
    jobs_cancelled: int
    status: str


class DeleteFilesResponse(BaseModel):
    """Response for delete files action."""

    design_id: str
    status: str
    message: str


@router.post("/{design_id}/want", response_model=WantResponse)
async def want_design(
    design_id: str,
    priority: int = Query(0, ge=0, le=100, description="Download priority"),
    db: AsyncSession = Depends(get_db),
) -> WantResponse:
    """Mark a design as wanted and queue download.

    Changes status to WANTED and creates a DOWNLOAD_DESIGN job.
    """
    from app.services.download import DownloadError, DownloadService

    # Get design
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Check if already downloading or downloaded
    if design.status in (DesignStatus.DOWNLOADING, DesignStatus.DOWNLOADED, DesignStatus.ORGANIZED):
        raise HTTPException(
            status_code=400,
            detail=f"Design already has status {design.status.value}",
        )

    try:
        service = DownloadService(db)
        job_id = await service.queue_download(design_id, priority=priority)
        await db.commit()

        logger.info(
            "design_wanted",
            design_id=design_id,
            job_id=job_id,
            priority=priority,
        )

        return WantResponse(
            design_id=design_id,
            job_id=job_id,
            status="WANTED",
            message="Download queued",
        )

    except DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{design_id}/download", response_model=WantResponse)
async def force_download(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> WantResponse:
    """Force immediate download with high priority.

    Creates a high-priority DOWNLOAD_DESIGN job (priority=100).
    """
    from app.services.download import DownloadError, DownloadService

    # Get design
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    try:
        service = DownloadService(db)
        job_id = await service.queue_download(design_id, priority=100)
        await db.commit()

        logger.info(
            "design_force_download",
            design_id=design_id,
            job_id=job_id,
        )

        return WantResponse(
            design_id=design_id,
            job_id=job_id,
            status="WANTED",
            message="High-priority download queued",
        )

    except DownloadError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{design_id}/cancel", response_model=CancelDownloadResponse)
async def cancel_download(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> CancelDownloadResponse:
    """Cancel pending/in-progress download for a design.

    Cancels all QUEUED or RUNNING jobs for the design.
    """
    from app.db.models import DesignStatus
    from app.services.job_queue import JobQueueService

    # Get design
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Cancel all jobs for this design
    queue = JobQueueService(db)
    cancelled = await queue.cancel_jobs_for_design(design_id)

    # Reset design status if it was in a download state
    if design.status in (DesignStatus.WANTED, DesignStatus.DOWNLOADING):
        design.status = DesignStatus.DISCOVERED

    await db.commit()

    logger.info(
        "design_download_cancelled",
        design_id=design_id,
        jobs_cancelled=cancelled,
    )

    return CancelDownloadResponse(
        design_id=design_id,
        jobs_cancelled=cancelled,
        status=design.status.value,
    )


@router.delete("/{design_id}/files", response_model=DeleteFilesResponse)
async def delete_files(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeleteFilesResponse:
    """Delete downloaded files and reset design to DISCOVERED.

    Removes files from staging/library and resets design status.
    Note: This deletes actual files from disk!
    """
    import shutil
    from pathlib import Path

    from app.core.config import settings
    from app.db.models import DesignFile, DesignStatus

    # Get design
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Check design has files
    if design.status == DesignStatus.DISCOVERED:
        raise HTTPException(
            status_code=400,
            detail="Design has no downloaded files",
        )

    # Delete staging directory if exists
    staging_dir = settings.staging_path / design_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
        logger.info("staging_deleted", design_id=design_id, path=str(staging_dir))

    # Delete DesignFile records
    from sqlalchemy import delete
    await db.execute(
        delete(DesignFile).where(DesignFile.design_id == design_id)
    )

    # Reset design status
    design.status = DesignStatus.DISCOVERED

    await db.commit()

    logger.info(
        "design_files_deleted",
        design_id=design_id,
    )

    return DeleteFilesResponse(
        design_id=design_id,
        status=design.status.value,
        message="Files deleted and design reset",
    )


# =============================================================================
# Delete Actions
# =============================================================================


class BulkDeleteRequest(BaseModel):
    """Request body for bulk delete."""

    design_ids: list[str]


class BulkDeleteResponse(BaseModel):
    """Response for bulk delete."""

    deleted_count: int
    deleted_ids: list[str]


@router.delete("/bulk", response_model=BulkDeleteResponse)
async def bulk_delete_designs(
    request: BulkDeleteRequest,
    delete_files: bool = Query(False, description="Also delete library files from disk"),
    db: AsyncSession = Depends(get_db),
) -> BulkDeleteResponse:
    """Delete multiple designs at once.

    Returns list of successfully deleted design IDs.
    Designs that don't exist are silently skipped.

    Note: This endpoint must be defined BEFORE /{design_id} to prevent
    FastAPI from matching "bulk" as a design_id (#193).
    """
    deleted_ids = []

    for design_id in request.design_ids:
        design = await db.get(Design, design_id)
        if design is None:
            continue

        try:
            # Reuse the single delete logic but without committing
            import shutil
            from sqlalchemy import delete as sql_delete

            from app.db.models import DesignFile, DesignSource, Job
            from app.db.models.external_metadata_source import ExternalMetadataSource
            from app.services.job_queue import JobQueueService

            # Cancel pending/running jobs before deletion (#191)
            queue = JobQueueService(db)
            await queue.cancel_jobs_for_design(design_id)

            # Delete preview assets and their files
            preview_service = PreviewService(db)
            await preview_service.delete_design_previews(design_id)

            # Always delete staging directory (partial downloads) (#191)
            staging_dir = settings.staging_path / design_id
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

            # Optionally delete library files
            if delete_files:
                files_result = await db.execute(
                    select(DesignFile).where(DesignFile.design_id == design_id)
                )
                design_files = files_result.scalars().all()
                for df in design_files:
                    if df.relative_path:
                        file_path = settings.library_path / df.relative_path
                        if file_path.exists():
                            file_path.unlink()

            # Delete related records
            await db.execute(sql_delete(DesignFile).where(DesignFile.design_id == design_id))
            await db.execute(sql_delete(DesignSource).where(DesignSource.design_id == design_id))
            await db.execute(sql_delete(ExternalMetadataSource).where(ExternalMetadataSource.design_id == design_id))
            await db.execute(sql_delete(DesignTag).where(DesignTag.design_id == design_id))
            await db.execute(sql_delete(Job).where(Job.design_id == design_id))

            await db.delete(design)
            deleted_ids.append(design_id)

        except Exception as e:
            logger.warning(
                "bulk_delete_failed_for_design",
                design_id=design_id,
                error=str(e),
            )

    await db.commit()

    logger.info(
        "designs_bulk_deleted",
        count=len(deleted_ids),
        delete_files=delete_files,
    )

    return BulkDeleteResponse(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )


@router.delete("/{design_id}", status_code=204)
async def delete_design(
    design_id: str,
    delete_files: bool = Query(False, description="Also delete library files from disk"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a design and all related records.

    Cascade deletes:
    - DesignSource records
    - DesignFile records
    - PreviewAsset records (and files)
    - ExternalMetadataSource records
    - DesignTag records
    - Jobs associated with the design

    Always deletes:
    - Staging directory (partial downloads) (#191)
    - Cancels pending/running jobs before deletion (#191)

    If delete_files=True, also deletes:
    - Library files
    """
    import shutil
    from sqlalchemy import delete as sql_delete

    from app.db.models import DesignFile, DesignSource, Job
    from app.db.models.external_metadata_source import ExternalMetadataSource
    from app.services.job_queue import JobQueueService

    # Get design
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Cancel pending/running jobs before deletion (#191)
    # This prevents workers from processing deleted designs
    queue = JobQueueService(db)
    canceled_count = await queue.cancel_jobs_for_design(design_id)
    if canceled_count > 0:
        logger.info(
            "design_jobs_canceled",
            design_id=design_id,
            canceled_count=canceled_count,
        )

    # Delete preview assets and their files
    preview_service = PreviewService(db)
    await preview_service.delete_design_previews(design_id)

    # Always delete staging directory (partial downloads) (#191)
    staging_dir = settings.staging_path / design_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
        logger.info("staging_deleted", design_id=design_id)

    # Optionally delete library files
    if delete_files:

        # Delete library files (get paths before deleting records)
        files_result = await db.execute(
            select(DesignFile).where(DesignFile.design_id == design_id)
        )
        design_files = files_result.scalars().all()
        for df in design_files:
            if df.relative_path:
                file_path = settings.library_path / df.relative_path
                if file_path.exists():
                    file_path.unlink()
                    logger.debug("library_file_deleted", path=str(file_path))

    # Delete related records (cascade)
    await db.execute(sql_delete(DesignFile).where(DesignFile.design_id == design_id))
    await db.execute(sql_delete(DesignSource).where(DesignSource.design_id == design_id))
    await db.execute(sql_delete(ExternalMetadataSource).where(ExternalMetadataSource.design_id == design_id))
    await db.execute(sql_delete(DesignTag).where(DesignTag.design_id == design_id))
    await db.execute(sql_delete(Job).where(Job.design_id == design_id))

    # Delete the design itself
    await db.delete(design)
    await db.commit()

    logger.info(
        "design_deleted",
        design_id=design_id,
        delete_files=delete_files,
    )


# =============================================================================
# File List & Download Actions (#172, #175)
# =============================================================================


class DesignFileResponse(BaseModel):
    """Response schema for a design file (#175)."""

    id: str
    filename: str
    ext: str
    size_bytes: int | None
    file_kind: str
    is_primary: bool

    model_config = {"from_attributes": True}


@router.get("/{design_id}/files", response_model=list[DesignFileResponse])
async def list_design_files(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[DesignFileResponse]:
    """List all files for a design (#175).

    Returns file metadata for building download links in the UI.
    Only returns files that exist in the library.
    """
    from app.db.models import DesignFile

    # Verify design exists
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Get all files for this design
    files_result = await db.execute(
        select(DesignFile)
        .where(DesignFile.design_id == design_id)
        .order_by(DesignFile.is_primary.desc(), DesignFile.filename.asc())
    )
    design_files = files_result.scalars().all()

    # Filter to files that exist on disk
    result = []
    for df in design_files:
        file_path = settings.library_path / df.relative_path
        if file_path.exists():
            result.append(
                DesignFileResponse(
                    id=df.id,
                    filename=df.filename,
                    ext=df.ext,
                    size_bytes=df.size_bytes,
                    file_kind=df.file_kind.value if df.file_kind else "OTHER",
                    is_primary=df.is_primary,
                )
            )

    return result


@router.get("/{design_id}/download")
async def download_design_files(
    design_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download all design files as a ZIP archive.

    Creates a ZIP file on-the-fly and streams it to the client.
    Only includes files that exist in the library.
    """
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    from app.db.models import DesignFile

    # Get design
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Get all files for this design
    files_result = await db.execute(
        select(DesignFile).where(DesignFile.design_id == design_id)
    )
    design_files = files_result.scalars().all()

    if not design_files:
        raise HTTPException(status_code=404, detail="Design has no files")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for df in design_files:
            file_path = settings.library_path / df.relative_path
            if file_path.exists():
                # Use relative_path as the path in the ZIP
                zip_file.write(file_path, df.relative_path)

    zip_buffer.seek(0)

    # Generate safe filename
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in design.canonical_title)
    filename = f"{safe_title}.zip"

    logger.info(
        "design_download_started",
        design_id=design_id,
        file_count=len(design_files),
    )

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{design_id}/files/{file_id}/download")
async def download_single_file(
    design_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download a single file from a design.

    Returns the file with proper Content-Disposition header for browser download.
    Uses streaming for large files.
    """
    from fastapi.responses import FileResponse

    from app.db.models import DesignFile

    # Get design (for ownership validation)
    design = await db.get(Design, design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Get the file
    file_result = await db.execute(
        select(DesignFile).where(
            DesignFile.id == file_id,
            DesignFile.design_id == design_id,
        )
    )
    design_file = file_result.scalar_one_or_none()

    if design_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    # Build full path
    file_path = settings.library_path / design_file.relative_path

    # Validate path exists and is within library (prevent directory traversal)
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(settings.library_path.resolve())):
            logger.warning(
                "directory_traversal_attempt",
                design_id=design_id,
                file_id=file_id,
                path=str(design_file.relative_path),
            )
            raise HTTPException(status_code=404, detail="File not found")
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    logger.info(
        "file_download_started",
        design_id=design_id,
        file_id=file_id,
        filename=design_file.filename,
    )

    return FileResponse(
        path=str(file_path),
        filename=design_file.filename,
        media_type="application/octet-stream",
    )


# ==================== Duplicate Checking Endpoints ====================


class FileInfo(BaseModel):
    """File info for pre-download duplicate check."""

    filename: str
    size: int


class CheckDuplicateRequest(BaseModel):
    """Request body for pre-download duplicate check."""

    title: str
    designer: str
    files: list[FileInfo] = []
    thangs_id: str | None = None


class CheckDuplicateResponse(BaseModel):
    """Response for pre-download duplicate check."""

    has_duplicate: bool
    match_design_id: str | None = None
    match_design_title: str | None = None
    match_design_designer: str | None = None
    match_type: str | None = None
    confidence: float = 0.0
    should_skip_download: bool = False
    message: str


@router.post("/check-duplicate", response_model=CheckDuplicateResponse)
async def check_duplicate(
    request: CheckDuplicateRequest,
    dry_run: bool = Query(False, description="If true, only report matches without taking action"),
    db: AsyncSession = Depends(get_db),
) -> CheckDuplicateResponse:
    """Check for potential duplicates before download (DEC-041).

    Uses heuristic matching (title, designer, filename/size, Thangs ID)
    to detect likely duplicates without needing file hashes.

    Args:
        request: Contains title, designer, file info, and optional Thangs ID.
        dry_run: If true, only report what would match without taking action.

    Returns:
        Duplicate check result with confidence score and recommendation.
    """
    from app.services.duplicate import DuplicateService

    duplicate_service = DuplicateService(db)

    # Convert FileInfo to dict format
    files = [{"filename": f.filename, "size": f.size} for f in request.files]

    # Check for duplicates
    match, match_type, confidence = await duplicate_service.check_pre_download(
        title=request.title,
        designer=request.designer,
        files=files,
        thangs_id=request.thangs_id,
    )

    if match is None:
        return CheckDuplicateResponse(
            has_duplicate=False,
            confidence=0.0,
            should_skip_download=False,
            message="No duplicate found. Safe to download.",
        )

    # Determine if download should be skipped (confidence >= 0.8)
    should_skip = confidence >= 0.8 and not dry_run

    message = f"Potential duplicate found: '{match.canonical_title}' by {match.canonical_designer}"
    if should_skip:
        message += f" (confidence: {confidence:.0%}). Download will be skipped."
    else:
        message += f" (confidence: {confidence:.0%}). Recommend manual review."

    logger.info(
        "duplicate_check_result",
        title=request.title,
        designer=request.designer,
        match_design_id=match.id,
        match_type=match_type.value if match_type else None,
        confidence=confidence,
        should_skip=should_skip,
        dry_run=dry_run,
    )

    return CheckDuplicateResponse(
        has_duplicate=True,
        match_design_id=match.id,
        match_design_title=match.canonical_title,
        match_design_designer=match.canonical_designer,
        match_type=match_type.value if match_type else None,
        confidence=confidence,
        should_skip_download=should_skip,
        message=message,
    )


# ==================== Design Split/Unmerge Endpoints ====================


class SplitDesignRequest(BaseModel):
    """Request body for design split."""

    source_id: str


class SplitDesignResponse(BaseModel):
    """Response for design split."""

    new_design_id: str
    new_design_title: str | None
    original_design_id: str
    message: str


@router.post("/{design_id}/split", response_model=SplitDesignResponse)
async def split_design(
    design_id: str,
    request: SplitDesignRequest,
    db: AsyncSession = Depends(get_db),
) -> SplitDesignResponse:
    """Split a design by extracting a source into a new independent design (DEC-041).

    Allows users to undo auto-merge by splitting out one source.
    The new design will be in DISCOVERED status and may need re-downloading.

    Args:
        design_id: The design to split from.
        request: Contains the source_id to split out.

    Returns:
        Information about the newly created design.
    """
    from app.services.duplicate import DuplicateService

    duplicate_service = DuplicateService(db)

    try:
        new_design = await duplicate_service.split_design(
            design_id=design_id,
            source_id=request.source_id,
        )
        await db.commit()

        logger.info(
            "design_split_api",
            original_design_id=design_id,
            new_design_id=new_design.id,
            source_id=request.source_id,
        )

        return SplitDesignResponse(
            new_design_id=new_design.id,
            new_design_title=new_design.canonical_title,
            original_design_id=design_id,
            message=f"Successfully split source into new design '{new_design.canonical_title}'",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
