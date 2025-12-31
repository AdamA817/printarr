"""Discovered channels API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Channel, DiscoveredChannel
from app.schemas.discovered_channel import (
    AddDiscoveredChannelRequest,
    AddDiscoveredChannelResponse,
    DiscoveredChannelList,
    DiscoveredChannelResponse,
    DiscoveredChannelStats,
)
from app.telegram.service import TelegramService

logger = get_logger(__name__)

router = APIRouter(prefix="/discovered-channels", tags=["discovered-channels"])


@router.get("/", response_model=DiscoveredChannelList)
async def list_discovered_channels(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: Literal["reference_count", "last_seen_at", "first_seen_at"] = Query(
        "reference_count",
        description="Field to sort by",
    ),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    exclude_added: bool = Query(
        True,
        description="Exclude channels already added to monitoring",
    ),
    db: AsyncSession = Depends(get_db),
) -> DiscoveredChannelList:
    """List discovered channels with pagination and filtering."""
    # Build base query
    query = select(DiscoveredChannel)

    # Optionally exclude already-monitored channels
    if exclude_added:
        # Get list of monitored channel identifiers
        monitored_usernames_query = select(Channel.username).where(
            Channel.username.isnot(None)
        )
        monitored_usernames_result = await db.execute(monitored_usernames_query)
        monitored_usernames = {u.lower() for u in monitored_usernames_result.scalars().all() if u}

        monitored_peer_ids_query = select(Channel.telegram_peer_id)
        monitored_peer_ids_result = await db.execute(monitored_peer_ids_query)
        monitored_peer_ids = set(monitored_peer_ids_result.scalars().all())

        # Filter out monitored channels
        # We do this in Python since SQLite doesn't support NOT IN with subqueries well
        pass  # We'll filter after fetching

    # Get total count (before filtering)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total_unfiltered = total_result.scalar() or 0

    # Apply sorting
    sort_column = {
        "reference_count": DiscoveredChannel.reference_count,
        "last_seen_at": DiscoveredChannel.last_seen_at,
        "first_seen_at": DiscoveredChannel.first_seen_at,
    }.get(sort_by, DiscoveredChannel.reference_count)

    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Execute query without pagination first if filtering
    result = await db.execute(query)
    all_channels = result.scalars().all()

    # Filter out monitored channels in Python
    if exclude_added:
        filtered_channels = []
        for dc in all_channels:
            is_monitored = False
            if dc.username and dc.username.lower() in monitored_usernames:
                is_monitored = True
            if dc.telegram_peer_id and dc.telegram_peer_id in monitored_peer_ids:
                is_monitored = True
            if not is_monitored:
                filtered_channels.append(dc)
        all_channels = filtered_channels

    # Apply pagination to filtered results
    total = len(all_channels)
    offset = (page - 1) * page_size
    channels = all_channels[offset : offset + page_size]

    # Calculate total pages
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return DiscoveredChannelList(
        items=[DiscoveredChannelResponse.model_validate(c) for c in channels],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/stats", response_model=DiscoveredChannelStats)
async def get_discovered_channel_stats(
    db: AsyncSession = Depends(get_db),
) -> DiscoveredChannelStats:
    """Get statistics about discovered channels."""
    # Total count
    total_result = await db.execute(select(func.count(DiscoveredChannel.id)))
    total = total_result.scalar() or 0

    # New this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_week_result = await db.execute(
        select(func.count(DiscoveredChannel.id)).where(
            DiscoveredChannel.first_seen_at >= week_ago
        )
    )
    new_this_week = new_week_result.scalar() or 0

    # Most referenced (top 5)
    most_ref_result = await db.execute(
        select(DiscoveredChannel)
        .order_by(DiscoveredChannel.reference_count.desc())
        .limit(5)
    )
    most_referenced = most_ref_result.scalars().all()

    return DiscoveredChannelStats(
        total=total,
        new_this_week=new_this_week,
        most_referenced=[
            DiscoveredChannelResponse.model_validate(c) for c in most_referenced
        ],
    )


@router.get("/{discovered_id}", response_model=DiscoveredChannelResponse)
async def get_discovered_channel(
    discovered_id: str,
    db: AsyncSession = Depends(get_db),
) -> DiscoveredChannelResponse:
    """Get a single discovered channel by ID."""
    result = await db.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.id == discovered_id)
    )
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Discovered channel not found")

    return DiscoveredChannelResponse.model_validate(channel)


@router.delete("/{discovered_id}", status_code=204)
async def dismiss_discovered_channel(
    discovered_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dismiss (delete) a discovered channel.

    Use this to ignore/hide a discovered channel that you don't want to add.
    """
    result = await db.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.id == discovered_id)
    )
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Discovered channel not found")

    await db.delete(channel)
    await db.commit()


@router.post("/{discovered_id}/add", response_model=AddDiscoveredChannelResponse)
async def add_discovered_channel(
    discovered_id: str,
    request: AddDiscoveredChannelRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AddDiscoveredChannelResponse:
    """Promote a discovered channel to a monitored channel.

    This will:
    1. Resolve the channel via Telegram API to get full info
    2. Create a new Channel record with the specified settings
    3. Optionally remove the DiscoveredChannel record
    """
    # Get the discovered channel
    result = await db.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.id == discovered_id)
    )
    discovered = result.scalar_one_or_none()

    if discovered is None:
        raise HTTPException(status_code=404, detail="Discovered channel not found")

    # Default request if none provided
    if request is None:
        request = AddDiscoveredChannelRequest()

    # Check if already monitored by username or peer_id
    existing_channel = None
    if discovered.username:
        result = await db.execute(
            select(Channel).where(Channel.username == discovered.username)
        )
        existing_channel = result.scalar_one_or_none()

    if existing_channel is None and discovered.telegram_peer_id:
        result = await db.execute(
            select(Channel).where(
                Channel.telegram_peer_id == discovered.telegram_peer_id
            )
        )
        existing_channel = result.scalar_one_or_none()

    if existing_channel:
        # Already monitored - return existing
        logger.info(
            "discovered_channel_already_monitored",
            discovered_id=discovered_id,
            channel_id=existing_channel.id,
        )

        # Optionally remove from discovered
        if request.remove_from_discovered:
            await db.delete(discovered)
            await db.commit()

        return AddDiscoveredChannelResponse(
            channel_id=existing_channel.id,
            title=existing_channel.title,
            was_existing=True,
        )

    # Resolve channel via Telegram to get full info
    telegram = TelegramService.get_instance()

    if not telegram.is_connected() or not await telegram.is_authenticated():
        raise HTTPException(
            status_code=503,
            detail="Telegram not connected. Please authenticate first.",
        )

    try:
        # Build the link to resolve
        if discovered.username:
            link = f"@{discovered.username}"
        elif discovered.invite_hash:
            link = f"t.me/+{discovered.invite_hash}"
        else:
            raise HTTPException(
                status_code=400,
                detail="Cannot resolve channel - no username or invite hash",
            )

        channel_info = await telegram.resolve_channel(link)

    except Exception as e:
        logger.error(
            "resolve_discovered_channel_error",
            discovered_id=discovered_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to resolve channel: {str(e)}",
        )

    # Check if this resolved channel is already monitored
    if channel_info.get("id"):
        result = await db.execute(
            select(Channel).where(
                Channel.telegram_peer_id == str(channel_info["id"])
            )
        )
        existing_channel = result.scalar_one_or_none()
        if existing_channel:
            if request.remove_from_discovered:
                await db.delete(discovered)
                await db.commit()

            return AddDiscoveredChannelResponse(
                channel_id=existing_channel.id,
                title=existing_channel.title,
                was_existing=True,
            )

    # Create new monitored channel
    new_channel = Channel(
        telegram_peer_id=str(channel_info.get("id") or discovered.telegram_peer_id),
        title=channel_info.get("title") or discovered.title or "Unknown",
        username=channel_info.get("username") or discovered.username,
        invite_link=f"t.me/+{discovered.invite_hash}" if discovered.invite_hash else None,
        is_private=channel_info.get("is_invite", discovered.is_private),
        is_enabled=request.is_enabled,
        download_mode=request.download_mode,
        backfill_mode=request.backfill_mode,
        backfill_value=request.backfill_value,
    )

    db.add(new_channel)
    await db.flush()

    logger.info(
        "discovered_channel_added",
        discovered_id=discovered_id,
        channel_id=new_channel.id,
        title=new_channel.title,
    )

    # Optionally remove from discovered
    if request.remove_from_discovered:
        await db.delete(discovered)

    await db.commit()

    return AddDiscoveredChannelResponse(
        channel_id=new_channel.id,
        title=new_channel.title,
        was_existing=False,
    )
