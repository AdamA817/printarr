"""Channel CRUD API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.db.models import BackfillMode, Channel
from app.schemas.channel import (
    BackfillRequest,
    BackfillResponse,
    BackfillStatusResponse,
    ChannelCreate,
    ChannelList,
    ChannelResponse,
    ChannelUpdate,
)
from app.services.backfill import BackfillService

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/", response_model=ChannelList)
async def list_channels(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_enabled: bool | None = Query(None, description="Filter by enabled status"),
    db: AsyncSession = Depends(get_db),
) -> ChannelList:
    """List all channels with pagination."""
    # Build query
    query = select(Channel)

    if is_enabled is not None:
        query = query.where(Channel.is_enabled == is_enabled)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Channel.created_at.desc()).offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    channels = result.scalars().all()

    # Calculate total pages
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return ChannelList(
        items=[ChannelResponse.model_validate(c) for c in channels],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Get a single channel by ID."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    return ChannelResponse.model_validate(channel)


@router.post("/", response_model=ChannelResponse, status_code=201)
async def create_channel(
    channel_in: ChannelCreate,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Create a new channel."""
    # Generate telegram_peer_id if not provided (v0.1 behavior)
    telegram_peer_id = channel_in.telegram_peer_id or f"local_{uuid.uuid4().hex[:12]}"

    # Check for duplicate telegram_peer_id
    existing = await db.execute(
        select(Channel).where(Channel.telegram_peer_id == telegram_peer_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Channel with this telegram_peer_id already exists",
        )

    # Create channel
    channel = Channel(
        telegram_peer_id=telegram_peer_id,
        title=channel_in.title,
        username=channel_in.username,
        invite_link=channel_in.invite_link,
        is_private=channel_in.is_private,
    )

    db.add(channel)
    await db.flush()
    await db.refresh(channel)

    return ChannelResponse.model_validate(channel)


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    channel_in: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Update a channel's settings."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Update only provided fields
    update_data = channel_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)

    await db.flush()
    await db.refresh(channel)

    return ChannelResponse.model_validate(channel)


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    await db.delete(channel)
    await db.commit()


@router.post("/{channel_id}/backfill", response_model=BackfillResponse)
async def backfill_channel(
    channel_id: str,
    request: BackfillRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> BackfillResponse:
    """Trigger a backfill for a channel.

    This fetches historical messages from Telegram and processes them
    through the ingestion pipeline.
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    service = BackfillService(db)

    # Extract override parameters
    mode = None
    value = None
    if request:
        if request.mode:
            mode = BackfillMode(request.mode)
        value = request.value

    try:
        result_data = await service.backfill_channel(channel, mode=mode, value=value)
        return BackfillResponse(
            channel_id=channel_id,
            messages_processed=result_data["messages_processed"],
            designs_created=result_data["designs_created"],
            last_message_id=result_data["last_message_id"],
            metadata_fetched=result_data.get("metadata_fetched", 0),
            metadata_failed=result_data.get("metadata_failed", 0),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")


@router.get("/{channel_id}/backfill/status", response_model=BackfillStatusResponse)
async def get_backfill_status(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
) -> BackfillStatusResponse:
    """Get the current backfill status for a channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    service = BackfillService(db)
    status = await service.get_backfill_status(channel)

    return BackfillStatusResponse(**status)
