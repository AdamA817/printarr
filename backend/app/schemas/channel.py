"""Pydantic schemas for Channel API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.models.enums import BackfillMode, DesignerSource, DownloadMode, TitleSource


class ChannelBase(BaseModel):
    """Base schema for channel data."""

    title: str = Field(..., min_length=1, max_length=255)
    username: Optional[str] = Field(None, max_length=255)
    invite_link: Optional[str] = Field(None, max_length=512)
    is_private: bool = False


class ChannelCreate(ChannelBase):
    """Schema for creating a new channel."""

    # For v0.1, we accept a telegram_peer_id or generate one
    # In v0.2+, this will be resolved from Telegram
    telegram_peer_id: Optional[str] = Field(
        None,
        max_length=64,
        description="Telegram peer ID (optional for v0.1, will be auto-generated if not provided)",
    )


class ChannelUpdate(BaseModel):
    """Schema for updating a channel (all fields optional)."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, max_length=255)
    invite_link: Optional[str] = Field(None, max_length=512)
    is_private: Optional[bool] = None
    is_enabled: Optional[bool] = None

    # Channel settings
    backfill_mode: Optional[BackfillMode] = None
    backfill_value: Optional[int] = Field(None, ge=1)
    download_mode: Optional[DownloadMode] = None
    library_template_override: Optional[str] = Field(None, max_length=512)
    title_source_override: Optional[TitleSource] = None
    designer_source_override: Optional[DesignerSource] = None


class ChannelResponse(ChannelBase):
    """Schema for channel response."""

    id: str
    telegram_peer_id: str
    is_enabled: bool

    # Settings
    backfill_mode: BackfillMode
    backfill_value: int
    download_mode: DownloadMode
    library_template_override: Optional[str] = None
    title_source_override: Optional[TitleSource] = None
    designer_source_override: Optional[DesignerSource] = None

    # Sync state
    last_ingested_message_id: Optional[int] = None
    last_backfill_checkpoint: Optional[int] = None
    last_sync_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelList(BaseModel):
    """Schema for paginated channel list response."""

    items: list[ChannelResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BackfillRequest(BaseModel):
    """Schema for backfill request parameters."""

    mode: Optional[str] = Field(
        None,
        description="Override backfill mode: ALL_HISTORY, LAST_N_MESSAGES, LAST_N_DAYS",
    )
    value: Optional[int] = Field(
        None, ge=1, description="Override backfill value (N messages or N days)"
    )


class BackfillResponse(BaseModel):
    """Schema for backfill response."""

    channel_id: str
    messages_processed: int
    designs_created: int
    last_message_id: int


class BackfillStatusResponse(BaseModel):
    """Schema for backfill status response."""

    channel_id: str
    last_backfill_checkpoint: Optional[int] = None
    last_ingested_message_id: Optional[int] = None
    last_sync_at: Optional[str] = None
    backfill_mode: str
    backfill_value: int
