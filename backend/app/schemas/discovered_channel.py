"""Schemas for discovered channels API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import BackfillMode, DownloadMode


class DiscoveredChannelResponse(BaseModel):
    """Response schema for a discovered channel."""

    id: str
    telegram_peer_id: str | None = None
    title: str | None = None
    username: str | None = None
    invite_hash: str | None = None
    is_private: bool = False
    reference_count: int = 1
    first_seen_at: datetime
    last_seen_at: datetime
    source_types: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DiscoveredChannelList(BaseModel):
    """Paginated list of discovered channels."""

    items: list[DiscoveredChannelResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AddDiscoveredChannelRequest(BaseModel):
    """Request to promote a discovered channel to monitored."""

    download_mode: DownloadMode = Field(
        default=DownloadMode.MANUAL,
        description="Download mode for the new channel",
    )
    backfill_mode: BackfillMode = Field(
        default=BackfillMode.LAST_N_MESSAGES,
        description="Backfill mode for initial sync",
    )
    backfill_value: int = Field(
        default=100,
        ge=1,
        description="Backfill value (message count or days)",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether the channel should be enabled",
    )
    remove_from_discovered: bool = Field(
        default=True,
        description="Whether to remove from discovered list after adding",
    )


class AddDiscoveredChannelResponse(BaseModel):
    """Response after adding a discovered channel."""

    channel_id: str = Field(description="ID of the newly created monitored channel")
    title: str = Field(description="Channel title")
    was_existing: bool = Field(
        default=False,
        description="True if channel was already monitored",
    )


class DiscoveredChannelStats(BaseModel):
    """Statistics about discovered channels."""

    total: int = Field(description="Total number of discovered channels")
    new_this_week: int = Field(
        description="Number discovered in the last 7 days",
    )
    most_referenced: list[DiscoveredChannelResponse] = Field(
        default=[],
        description="Top channels by reference count",
    )
