"""Design API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, and_, cast, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db
from app.services.count_cache import get_approximate_count, count_cache
from app.db.models import (
    Attachment,
    Channel,
    Design,
    DesignSource,
    ExternalMetadataSource,
    ExternalSourceType,
    ImportSource,
    TelegramMessage,
)
from app.db.models.design_tag import DesignTag
from app.db.models.enums import (
    DesignStatus,
    JobType,
    MatchMethod,
    MediaType,
    MetadataAuthority,
    MulticolorStatus,
    PreviewSource,
)
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
from app.services.job_queue import JobQueueService
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


# =============================================================================
# Designer Autocomplete Endpoint
# =============================================================================


class DesignerSuggestion(BaseModel):
    """Designer suggestion for autocomplete."""

    name: str
    count: int


class DesignerSuggestionsResponse(BaseModel):
    """Response for designer autocomplete."""

    items: list[DesignerSuggestion]


@router.get("/designers", response_model=DesignerSuggestionsResponse)
async def list_designers(
    q: str | None = Query(None, description="Search prefix for filtering"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
    db: AsyncSession = Depends(get_db),
) -> DesignerSuggestionsResponse:
    """Get designer names for autocomplete with usage counts.

    Returns unique designer names sorted by frequency (most used first).
    Optionally filters by a search prefix.
    """
    query = (
        select(Design.canonical_designer, func.count(Design.id).label("count"))
        .where(Design.canonical_designer.isnot(None))
        .where(Design.canonical_designer != "")
        .group_by(Design.canonical_designer)
        .order_by(func.count(Design.id).desc())
        .limit(limit)
    )

    if q:
        query = query.where(Design.canonical_designer.ilike(f"%{q}%"))

    result = await db.execute(query)
    rows = result.all()

    return DesignerSuggestionsResponse(
        items=[DesignerSuggestion(name=row[0], count=row[1]) for row in rows]
    )


# --------------------------------------------------------------------------
# Telegram Image Download Backfill
# --------------------------------------------------------------------------

# Time window for finding nearby photo messages (matches ingest service)
NEARBY_PHOTO_WINDOW_MINUTES = 30


class QueueTelegramImagesResponse(BaseModel):
    """Response for queueing telegram image downloads."""

    designs_found: int
    jobs_queued: int
    already_have_telegram_previews: int
    total_photo_messages_found: int
    errors: list[str]


@router.post(
    "/telegram-images/queue-backfill",
    response_model=QueueTelegramImagesResponse,
    summary="Queue telegram image downloads for existing designs",
    description="""
    Queue DOWNLOAD_TELEGRAM_IMAGES jobs for designs that have nearby PHOTO messages
    but don't yet have TELEGRAM source preview assets.

    This looks for photo messages posted in the same channel within 30 minutes
    before the design message, since designers often post preview photos
    separately from the design files.

    This is useful for backfilling telegram preview images for designs that
    were created before the automatic image download feature was added.
    """,
)
async def queue_telegram_image_backfill(
    limit: int = Query(100, ge=1, le=1000, description="Maximum designs to process"),
    window_minutes: int = Query(NEARBY_PHOTO_WINDOW_MINUTES, ge=1, le=1440, description="Minutes before design message to look for photos"),
    dry_run: bool = Query(True, description="If true, only count - don't queue jobs"),
    db: AsyncSession = Depends(get_db),
) -> QueueTelegramImagesResponse:
    """Queue telegram image download jobs for designs missing telegram previews."""

    # Get all designs that don't have TELEGRAM previews yet
    # Subquery for designs that already have TELEGRAM previews
    designs_with_telegram_previews = (
        select(PreviewAsset.design_id)
        .where(cast(PreviewAsset.source, String) == PreviewSource.TELEGRAM.value)
        .distinct()
    )

    # Find designs without telegram previews that have a Telegram source
    result = await db.execute(
        select(Design)
        .options(
            selectinload(Design.sources)
            .selectinload(DesignSource.message)
            .selectinload(TelegramMessage.channel)
        )
        .where(
            Design.id.notin_(designs_with_telegram_previews),
            # Only designs with at least one Telegram source
            Design.sources.any(DesignSource.message_id.isnot(None)),
        )
        .limit(limit)
    )
    designs = result.scalars().all()

    # Count designs that already have telegram previews
    already_count_result = await db.execute(
        select(func.count(func.distinct(PreviewAsset.design_id)))
        .where(cast(PreviewAsset.source, String) == PreviewSource.TELEGRAM.value)
    )
    already_have_telegram = already_count_result.scalar() or 0

    jobs_queued = 0
    total_photo_messages = 0
    errors: list[str] = []
    queue = JobQueueService(db)

    for design in designs:
        try:
            # Find a source with message and channel info
            source_with_message = None
            for source in design.sources:
                if source.message and source.message.channel:
                    source_with_message = source
                    break

            if not source_with_message:
                continue  # Skip designs without Telegram message

            message = source_with_message.message
            channel = message.channel

            if not channel.telegram_peer_id:
                continue  # Skip if no peer ID

            # Find nearby photo messages (within the time window BEFORE the design message)
            # Only from the same author to avoid grabbing unrelated photos
            window_start = message.date_posted - timedelta(minutes=window_minutes)

            # Build conditions - filter by same author if known
            conditions = [
                TelegramMessage.channel_id == channel.id,
                TelegramMessage.date_posted >= window_start,
                TelegramMessage.date_posted <= message.date_posted,
                cast(Attachment.media_type, String) == MediaType.PHOTO.value,
            ]
            if message.author_name:
                conditions.append(TelegramMessage.author_name == message.author_name)

            nearby_photo_result = await db.execute(
                select(TelegramMessage.telegram_message_id)
                .join(Attachment, Attachment.message_id == TelegramMessage.id)
                .where(and_(*conditions))
                .distinct()
            )
            nearby_message_ids = [row[0] for row in nearby_photo_result.all()]

            if not nearby_message_ids:
                continue  # No photo messages found nearby

            total_photo_messages += len(nearby_message_ids)

            if not dry_run:
                await queue.enqueue(
                    JobType.DOWNLOAD_TELEGRAM_IMAGES,
                    design_id=design.id,
                    priority=5,
                    payload={
                        "design_id": design.id,
                        "message_ids": nearby_message_ids,
                        "channel_peer_id": channel.telegram_peer_id,
                        # Legacy field for backwards compatibility
                        "message_id": message.telegram_message_id,
                    },
                )

            jobs_queued += 1

        except Exception as e:
            errors.append(f"Design {design.id}: {str(e)}")
            logger.error(
                "telegram_image_queue_error",
                design_id=design.id,
                error=str(e),
            )

    if not dry_run:
        await db.commit()

    logger.info(
        "telegram_image_backfill_complete",
        dry_run=dry_run,
        designs_found=len(designs),
        jobs_queued=jobs_queued,
        already_have_telegram=already_have_telegram,
        total_photo_messages=total_photo_messages,
        errors=len(errors),
    )

    return QueueTelegramImagesResponse(
        designs_found=len(designs),
        jobs_queued=jobs_queued,
        already_have_telegram_previews=already_have_telegram,
        total_photo_messages_found=total_photo_messages,
        errors=errors,
    )


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
    import_source_id: str | None = Query(None, description="Filter by import source ID"),
    import_source_folder_id: str | None = Query(None, description="Filter by import source folder ID"),
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
        selectinload(Design.import_source).selectinload(ImportSource.channel),
    )

    # Apply filters
    if status:
        query = query.where(Design.status == status)

    if channel_id:
        # Filter by designs that have a source from this channel OR
        # are from an import source with this virtual channel (#237)
        from app.db.models import Channel
        query = query.where(
            or_(
                Design.id.in_(
                    select(DesignSource.design_id).where(DesignSource.channel_id == channel_id)
                ),
                Design.import_source_id.in_(
                    select(ImportSource.id).where(
                        ImportSource.id.in_(
                            select(Channel.import_source_id).where(Channel.id == channel_id)
                        )
                    )
                ),
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

    if import_source_id:
        # Filter by import source
        query = query.where(Design.import_source_id == import_source_id)

    if import_source_folder_id:
        # Filter by import source folder (via ImportRecord relationship)
        from app.db.models.import_record import ImportRecord
        designs_from_folder = select(ImportRecord.design_id).where(
            ImportRecord.import_source_folder_id == import_source_folder_id,
            ImportRecord.design_id.isnot(None),
        )
        query = query.where(Design.id.in_(designs_from_folder))

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
        search_pattern = f"%{q}%"

        # Subquery to find designs with matching tags
        designs_with_matching_tag = (
            select(DesignTag.design_id)
            .join(Tag, DesignTag.tag_id == Tag.id)
            .where(Tag.name.ilike(search_pattern))
        )

        if len(q) >= 3:
            # Use full-text search with plainto_tsquery for natural language queries
            # Also include partial match via trigram for better UX
            # Also search tags by name
            search_condition = or_(
                text("search_vector @@ plainto_tsquery('english', :q)"),
                Design.canonical_title.ilike(search_pattern),
                Design.id.in_(designs_with_matching_tag),
            )
            query = query.where(search_condition).params(q=q)
        else:
            # Short queries use ILIKE with trigram index
            query = query.where(
                or_(
                    Design.canonical_title.ilike(search_pattern),
                    Design.canonical_designer.ilike(search_pattern),
                    Design.id.in_(designs_with_matching_tag),
                )
            )

    # Get total count (before pagination) - optimized (#219)
    # Use approximate count for unfiltered queries on large tables
    has_filters = any([status, channel_id, multicolor, file_type, designer, import_source_id, import_source_folder_id, has_thangs_link, tags, q])
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
        # Get channel from DesignSource or ImportSource's virtual channel (#237)
        channel = None
        if design.sources:
            preferred = next((s for s in design.sources if s.is_preferred), design.sources[0])
            if preferred.channel:
                channel = ChannelSummary(
                    id=preferred.channel.id,
                    title=preferred.channel.title,
                )
        elif design.import_source and design.import_source.channel:
            # Fall back to virtual channel from import source
            channel = ChannelSummary(
                id=design.import_source.channel.id,
                title=design.import_source.channel.title,
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
                display_title=design.display_title,
                display_designer=design.display_designer,
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
            selectinload(Design.import_source).selectinload(ImportSource.channel),
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


class AdjacentDesignsResponse(BaseModel):
    """Response for adjacent designs (prev/next navigation)."""

    prev_id: str | None = None
    next_id: str | None = None


@router.get("/{design_id}/adjacent", response_model=AdjacentDesignsResponse)
async def get_adjacent_designs(
    design_id: str,
    status: DesignStatus | None = Query(None, description="Filter by status"),
    channel_id: str | None = Query(None, description="Filter by channel ID"),
    file_type: str | None = Query(None, description="Filter by primary file type"),
    multicolor: MulticolorStatus | None = Query(None, description="Filter by multicolor status"),
    has_thangs_link: bool | None = Query(None, description="Filter by Thangs link status"),
    designer: str | None = Query(None, description="Filter by designer (partial match)"),
    import_source_id: str | None = Query(None, description="Filter by import source ID"),
    import_source_folder_id: str | None = Query(None, description="Filter by import source folder ID"),
    tags: list[str] | None = Query(None, description="Filter by tag IDs"),
    tag_match: TagMatch = Query(TagMatch.ANY, description="Tag matching mode"),
    q: str | None = Query(None, description="Full-text search on title and designer"),
    sort_by: SortField = Query(SortField.CREATED_AT, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    db: AsyncSession = Depends(get_db),
) -> AdjacentDesignsResponse:
    """Get previous and next design IDs given current filters and sort order.

    This endpoint enables prev/next navigation on the design detail page
    while respecting the current filter state from the designs list view.
    """
    # First, get the current design to know its sort value
    current_design = await db.get(Design, design_id)
    if current_design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Build base query with filters (same as list_designs)
    def build_filtered_query():
        query = select(Design.id)

        if status:
            query = query.where(Design.status == status)

        if channel_id:
            from app.db.models import Channel
            query = query.where(
                or_(
                    Design.id.in_(
                        select(DesignSource.design_id).where(DesignSource.channel_id == channel_id)
                    ),
                    Design.import_source_id.in_(
                        select(ImportSource.id).where(
                            ImportSource.id.in_(
                                select(Channel.import_source_id).where(Channel.id == channel_id)
                            )
                        )
                    ),
                )
            )

        if file_type:
            query = query.where(Design.primary_file_types.ilike(f"%{file_type}%"))

        if multicolor:
            query = query.where(Design.multicolor == multicolor)

        if designer:
            query = query.where(Design.canonical_designer.ilike(f"%{designer}%"))

        if import_source_id:
            query = query.where(Design.import_source_id == import_source_id)

        if import_source_folder_id:
            from app.db.models.import_record import ImportRecord
            designs_from_folder = select(ImportRecord.design_id).where(
                ImportRecord.import_source_folder_id == import_source_folder_id,
                ImportRecord.design_id.isnot(None),
            )
            query = query.where(Design.id.in_(designs_from_folder))

        if has_thangs_link is not None:
            designs_with_thangs = select(ExternalMetadataSource.design_id).where(
                ExternalMetadataSource.source_type == ExternalSourceType.THANGS
            )
            if has_thangs_link:
                query = query.where(Design.id.in_(designs_with_thangs))
            else:
                query = query.where(Design.id.notin_(designs_with_thangs))

        if tags:
            if tag_match == TagMatch.ALL:
                for tag_id in tags:
                    designs_with_tag = select(DesignTag.design_id).where(
                        DesignTag.tag_id == tag_id
                    )
                    query = query.where(Design.id.in_(designs_with_tag))
            else:
                designs_with_any_tag = select(DesignTag.design_id).where(
                    DesignTag.tag_id.in_(tags)
                )
                query = query.where(Design.id.in_(designs_with_any_tag))

        if q:
            search_pattern = f"%{q}%"
            designs_with_matching_tag = (
                select(DesignTag.design_id)
                .join(Tag, DesignTag.tag_id == Tag.id)
                .where(Tag.name.ilike(search_pattern))
            )

            if len(q) >= 3:
                search_condition = or_(
                    text("search_vector @@ plainto_tsquery('english', :q)"),
                    Design.canonical_title.ilike(search_pattern),
                    Design.id.in_(designs_with_matching_tag),
                )
                query = query.where(search_condition).params(q=q)
            else:
                query = query.where(
                    or_(
                        Design.canonical_title.ilike(search_pattern),
                        Design.canonical_designer.ilike(search_pattern),
                        Design.id.in_(designs_with_matching_tag),
                    )
                )

        return query

    # Get the sort column value for the current design
    sort_column = getattr(Design, sort_by.value)
    current_sort_value = getattr(current_design, sort_by.value)

    prev_id = None
    next_id = None

    # For DESC order: prev has higher value, next has lower value
    # For ASC order: prev has lower value, next has higher value
    if sort_order == SortOrder.DESC:
        # Previous design: higher sort value (or same value with smaller id for tie-breaking)
        prev_query = build_filtered_query().where(
            or_(
                sort_column > current_sort_value,
                and_(
                    sort_column == current_sort_value,
                    Design.id < design_id,  # Tie-breaker using ID
                ),
            )
        ).order_by(sort_column.asc(), Design.id.desc()).limit(1)

        # Next design: lower sort value (or same value with larger id for tie-breaking)
        next_query = build_filtered_query().where(
            or_(
                sort_column < current_sort_value,
                and_(
                    sort_column == current_sort_value,
                    Design.id > design_id,  # Tie-breaker using ID
                ),
            )
        ).order_by(sort_column.desc(), Design.id.asc()).limit(1)
    else:
        # ASC order - opposite logic
        prev_query = build_filtered_query().where(
            or_(
                sort_column < current_sort_value,
                and_(
                    sort_column == current_sort_value,
                    Design.id < design_id,
                ),
            )
        ).order_by(sort_column.desc(), Design.id.desc()).limit(1)

        next_query = build_filtered_query().where(
            or_(
                sort_column > current_sort_value,
                and_(
                    sort_column == current_sort_value,
                    Design.id > design_id,
                ),
            )
        ).order_by(sort_column.asc(), Design.id.asc()).limit(1)

    # Execute queries
    prev_result = await db.execute(prev_query)
    prev_row = prev_result.scalar_one_or_none()
    if prev_row:
        prev_id = prev_row

    next_result = await db.execute(next_query)
    next_row = next_result.scalar_one_or_none()
    if next_row:
        next_id = next_row

    return AdjacentDesignsResponse(prev_id=prev_id, next_id=next_id)


class DesignUpdateRequest(BaseModel):
    """Request body for updating design fields."""

    title_override: str | None = None
    designer_override: str | None = None
    notes: str | None = None
    multicolor_override: MulticolorStatus | None = None
    status: DesignStatus | None = None

    class Config:
        use_enum_values = True


@router.patch("/{design_id}", response_model=DesignDetail)
async def update_design(
    design_id: str,
    update_data: DesignUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> DesignDetail:
    """Update design fields (title override, designer override, notes, multicolor, status).

    Any field not provided will not be updated. Set a field to null to clear an override.
    """
    # Get design with all related data
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

    # Update only the fields that were explicitly provided
    update_fields = update_data.model_dump(exclude_unset=True)

    if update_fields:
        for field, value in update_fields.items():
            setattr(design, field, value)

        design.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(design)

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
    For import source designs that already have files downloaded,
    this will queue IMPORT_TO_LIBRARY instead (retry after failed import).
    """
    from app.services.download import DownloadError, DownloadService
    from app.services.job_queue import JobQueueService

    # Get design with files relationship to check if already downloaded
    result = await db.execute(
        select(Design)
        .options(selectinload(Design.files))
        .where(Design.id == design_id)
    )
    design = result.scalar_one_or_none()
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Check if already downloading or downloaded (but not failed)
    if design.status in (DesignStatus.DOWNLOADING, DesignStatus.DOWNLOADED, DesignStatus.ORGANIZED):
        raise HTTPException(
            status_code=400,
            detail=f"Design already has status {design.status.value}",
        )

    # Check if this design has files downloaded but failed during import
    # If so, retry import instead of re-downloading
    if design.files and design.status == DesignStatus.FAILED:
        # Re-queue IMPORT_TO_LIBRARY instead of re-downloading
        queue = JobQueueService(db)
        job = await queue.enqueue(
            JobType.IMPORT_TO_LIBRARY,
            design_id=design_id,
            priority=max(priority, 50),  # Ensure reasonable priority for retry
        )
        design.status = DesignStatus.DOWNLOADED
        await db.commit()

        logger.info(
            "design_retry_import",
            design_id=design_id,
            job_id=job.id,
            message="Re-queued import for design with existing files",
        )

        return WantResponse(
            design_id=design_id,
            job_id=job.id,
            status="DOWNLOADED",
            message="Re-queued import to library",
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
    For import source designs that already have files downloaded,
    this will queue IMPORT_TO_LIBRARY instead (retry after failed import).
    """
    from app.services.download import DownloadError, DownloadService
    from app.services.job_queue import JobQueueService

    # Get design with files relationship to check if already downloaded
    result = await db.execute(
        select(Design)
        .options(selectinload(Design.files))
        .where(Design.id == design_id)
    )
    design = result.scalar_one_or_none()
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")

    # Check if this design has files downloaded but failed during import
    # If so, retry import instead of re-downloading
    if design.files and design.status == DesignStatus.FAILED:
        # Re-queue IMPORT_TO_LIBRARY instead of re-downloading
        queue = JobQueueService(db)
        job = await queue.enqueue(
            JobType.IMPORT_TO_LIBRARY,
            design_id=design_id,
            priority=100,
        )
        design.status = DesignStatus.DOWNLOADED
        await db.commit()

        logger.info(
            "design_retry_import",
            design_id=design_id,
            job_id=job.id,
            message="Re-queued import for design with existing files",
        )

        return WantResponse(
            design_id=design_id,
            job_id=job.id,
            status="DOWNLOADED",
            message="Re-queued import to library",
        )

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

        # Also clean up the design's library folder if it exists
        library_folder = settings.library_path / design_id
        if library_folder.exists() and library_folder.is_dir():
            shutil.rmtree(library_folder)
            logger.info("library_folder_deleted", design_id=design_id)

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


# ==================== Duplicate Scanning & Cleanup Endpoints ====================


class DuplicateGroup(BaseModel):
    """A group of designs with the same canonical title."""

    canonical_title: str
    count: int
    design_ids: list[str]
    statuses: list[str]


class ScanDuplicatesResponse(BaseModel):
    """Response for duplicate scan."""

    total_duplicate_groups: int
    total_duplicate_designs: int
    groups: list[DuplicateGroup]


@router.get("/duplicates/scan", response_model=ScanDuplicatesResponse)
async def scan_duplicates(
    db: AsyncSession = Depends(get_db),
    min_group_size: int = 2,
    limit: int = 100,
) -> ScanDuplicatesResponse:
    """Scan for duplicate designs by canonical title.

    Finds designs with identical canonical_title values that may need merging.
    Only includes non-deleted designs.

    Args:
        min_group_size: Minimum number of designs to consider a group (default 2).
        limit: Maximum number of groups to return (default 100).

    Returns:
        List of duplicate groups with design IDs and counts.
    """
    from sqlalchemy import func

    # Find titles that appear more than once
    subquery = (
        select(
            Design.canonical_title,
            func.count(Design.id).label("count"),
        )
        .where(
            Design.status != DesignStatus.DELETED,
            Design.canonical_title.isnot(None),
            Design.canonical_title != "",
        )
        .group_by(Design.canonical_title)
        .having(func.count(Design.id) >= min_group_size)
        .order_by(func.count(Design.id).desc())
        .limit(limit)
        .subquery()
    )

    # Get the actual designs for each duplicate title
    result = await db.execute(
        select(Design)
        .where(
            Design.canonical_title.in_(
                select(subquery.c.canonical_title)
            ),
            Design.status != DesignStatus.DELETED,
        )
        .order_by(Design.canonical_title, Design.created_at)
    )
    designs = result.scalars().all()

    # Group designs by title
    groups_dict: dict[str, list[Design]] = {}
    for design in designs:
        title = design.canonical_title or ""
        if title not in groups_dict:
            groups_dict[title] = []
        groups_dict[title].append(design)

    # Convert to response format
    groups = []
    total_duplicates = 0
    for title, design_list in groups_dict.items():
        if len(design_list) >= min_group_size:
            groups.append(
                DuplicateGroup(
                    canonical_title=title,
                    count=len(design_list),
                    design_ids=[d.id for d in design_list],
                    statuses=[d.status.value for d in design_list],
                )
            )
            total_duplicates += len(design_list)

    # Sort by count descending
    groups.sort(key=lambda g: g.count, reverse=True)

    logger.info(
        "duplicate_scan_complete",
        total_groups=len(groups),
        total_duplicates=total_duplicates,
    )

    return ScanDuplicatesResponse(
        total_duplicate_groups=len(groups),
        total_duplicate_designs=total_duplicates,
        groups=groups,
    )


class MergeDuplicateGroupRequest(BaseModel):
    """Request to merge a duplicate group."""

    design_ids: list[str]
    keep_design_id: str | None = None  # If None, keep the oldest or first organized


class MergeDuplicateGroupResponse(BaseModel):
    """Response for merging a duplicate group."""

    merged_into_design_id: str
    merged_count: int
    deleted_design_ids: list[str]


@router.post("/duplicates/merge-group", response_model=MergeDuplicateGroupResponse)
async def merge_duplicate_group(
    request: MergeDuplicateGroupRequest,
    db: AsyncSession = Depends(get_db),
) -> MergeDuplicateGroupResponse:
    """Merge a group of duplicate designs into a single design.

    Merges all specified designs into one, preserving all sources.
    By default keeps the first ORGANIZED design, or the oldest if none are organized.

    Args:
        request: Design IDs to merge and optional target design ID.

    Returns:
        Information about the merge operation.
    """
    from app.services.duplicate import DuplicateService

    if len(request.design_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 designs are required for merging",
        )

    # Load all designs
    result = await db.execute(
        select(Design)
        .options(selectinload(Design.sources))
        .where(Design.id.in_(request.design_ids))
    )
    designs = list(result.scalars().all())

    if len(designs) != len(request.design_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more designs not found",
        )

    # Determine which design to keep
    if request.keep_design_id:
        target = next((d for d in designs if d.id == request.keep_design_id), None)
        if not target:
            raise HTTPException(
                status_code=404,
                detail=f"Keep design {request.keep_design_id} not found in design list",
            )
    else:
        # Prefer ORGANIZED designs, then oldest
        organized = [d for d in designs if d.status == DesignStatus.ORGANIZED]
        if organized:
            target = min(organized, key=lambda d: d.created_at)
        else:
            target = min(designs, key=lambda d: d.created_at)

    # Merge all other designs into target
    duplicate_service = DuplicateService(db)
    deleted_ids = []

    for design in designs:
        if design.id != target.id:
            await duplicate_service.merge_designs(source=design, target=target)
            deleted_ids.append(design.id)

    await db.commit()

    logger.info(
        "duplicate_group_merged",
        target_id=target.id,
        merged_count=len(deleted_ids),
        deleted_ids=deleted_ids,
    )

    return MergeDuplicateGroupResponse(
        merged_into_design_id=target.id,
        merged_count=len(deleted_ids),
        deleted_design_ids=deleted_ids,
    )


class AutoMergeDuplicatesResponse(BaseModel):
    """Response for auto-merge duplicates."""

    groups_processed: int
    designs_merged: int
    errors: list[str]


@router.post("/duplicates/auto-merge", response_model=AutoMergeDuplicatesResponse)
async def auto_merge_duplicates(
    db: AsyncSession = Depends(get_db),
    dry_run: bool = True,
    max_groups: int = 50,
) -> AutoMergeDuplicatesResponse:
    """Automatically merge duplicate designs with exact title matches.

    Processes duplicate groups and merges designs with identical titles.
    Prefers ORGANIZED designs as merge targets.

    Args:
        dry_run: If True, only report what would be merged (default True for safety).
        max_groups: Maximum number of groups to process (default 50).

    Returns:
        Summary of merge operations.
    """
    from sqlalchemy import func
    from app.services.duplicate import DuplicateService

    # Find duplicate groups
    subquery = (
        select(
            Design.canonical_title,
            func.count(Design.id).label("count"),
        )
        .where(
            Design.status != DesignStatus.DELETED,
            Design.canonical_title.isnot(None),
            Design.canonical_title != "",
        )
        .group_by(Design.canonical_title)
        .having(func.count(Design.id) >= 2)
        .order_by(func.count(Design.id).desc())
        .limit(max_groups)
        .subquery()
    )

    result = await db.execute(
        select(Design)
        .options(selectinload(Design.sources))
        .where(
            Design.canonical_title.in_(
                select(subquery.c.canonical_title)
            ),
            Design.status != DesignStatus.DELETED,
        )
        .order_by(Design.canonical_title, Design.created_at)
    )
    designs = result.scalars().all()

    # Group by title
    groups_dict: dict[str, list[Design]] = {}
    for design in designs:
        title = design.canonical_title or ""
        if title not in groups_dict:
            groups_dict[title] = []
        groups_dict[title].append(design)

    groups_processed = 0
    designs_merged = 0
    errors: list[str] = []

    duplicate_service = DuplicateService(db)

    for title, design_list in groups_dict.items():
        if len(design_list) < 2:
            continue

        groups_processed += 1

        try:
            # Find target (prefer ORGANIZED, then oldest)
            organized = [d for d in design_list if d.status == DesignStatus.ORGANIZED]
            if organized:
                target = min(organized, key=lambda d: d.created_at)
            else:
                target = min(design_list, key=lambda d: d.created_at)

            if not dry_run:
                for design in design_list:
                    if design.id != target.id:
                        await duplicate_service.merge_designs(source=design, target=target)
                        designs_merged += 1
            else:
                # Dry run - just count
                designs_merged += len(design_list) - 1

        except Exception as e:
            errors.append(f"Error merging '{title}': {str(e)}")
            logger.error(
                "auto_merge_error",
                title=title,
                error=str(e),
            )

    if not dry_run:
        await db.commit()

    logger.info(
        "auto_merge_complete",
        dry_run=dry_run,
        groups_processed=groups_processed,
        designs_merged=designs_merged,
        errors=len(errors),
    )

    return AutoMergeDuplicatesResponse(
        groups_processed=groups_processed,
        designs_merged=designs_merged,
        errors=errors,
    )
