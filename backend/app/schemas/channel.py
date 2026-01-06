"""Pydantic schemas for Channel API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import BackfillMode, DesignerSource, DownloadMode, TitleSource


class ChannelBase(BaseModel):
    """Base schema for channel data."""

    title: str = Field(..., min_length=1, max_length=255)
    username: str | None = Field(None, max_length=255)
    invite_link: str | None = Field(None, max_length=512)
    is_private: bool = False


class ChannelCreate(ChannelBase):
    """Schema for creating a new channel."""

    # For v0.1, we accept a telegram_peer_id or generate one
    # In v0.2+, this will be resolved from Telegram
    telegram_peer_id: str | None = Field(
        None,
        max_length=64,
        description="Telegram peer ID (optional for v0.1, will be auto-generated if not provided)",
    )


class ChannelUpdate(BaseModel):
    """Schema for updating a channel (all fields optional)."""

    title: str | None = Field(None, min_length=1, max_length=255)
    username: str | None = Field(None, max_length=255)
    invite_link: str | None = Field(None, max_length=512)
    is_private: bool | None = None
    is_enabled: bool | None = None

    # Channel settings
    backfill_mode: BackfillMode | None = None
    backfill_value: int | None = Field(None, ge=1)
    download_mode: DownloadMode | None = None
    library_template_override: str | None = Field(None, max_length=512)
    title_source_override: TitleSource | None = None
    designer_source_override: DesignerSource | None = None


class ChannelResponse(ChannelBase):
    """Schema for channel response."""

    id: str
    telegram_peer_id: str | None = None  # Nullable for virtual channels
    is_enabled: bool

    # Settings
    backfill_mode: BackfillMode
    backfill_value: int
    download_mode: DownloadMode
    library_template_override: str | None = None
    title_source_override: TitleSource | None = None
    designer_source_override: DesignerSource | None = None

    # Sync state
    last_ingested_message_id: int | None = None
    last_backfill_checkpoint: int | None = None
    last_sync_at: datetime | None = None
    download_mode_enabled_at: datetime | None = None

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

    mode: str | None = Field(
        None,
        description="Override backfill mode: ALL_HISTORY, LAST_N_MESSAGES, LAST_N_DAYS",
    )
    value: int | None = Field(
        None, ge=1, description="Override backfill value (N messages or N days)"
    )


class BackfillResponse(BaseModel):
    """Schema for backfill response."""

    channel_id: str
    messages_processed: int
    designs_created: int
    last_message_id: int
    metadata_fetched: int = 0
    metadata_failed: int = 0


class BackfillStatusResponse(BaseModel):
    """Schema for backfill status response."""

    channel_id: str
    last_backfill_checkpoint: int | None = None
    last_ingested_message_id: int | None = None
    last_sync_at: str | None = None
    backfill_mode: str
    backfill_value: int


class DownloadModeRequest(BaseModel):
    """Schema for changing download mode."""

    download_mode: DownloadMode = Field(
        ...,
        description="New download mode",
    )
    confirm_bulk_download: bool = Field(
        default=False,
        description="Confirm bulk download when setting DOWNLOAD_ALL mode",
    )


class DownloadModePreviewResponse(BaseModel):
    """Schema for download mode change preview."""

    channel_id: str
    current_mode: DownloadMode
    new_mode: DownloadMode
    designs_to_queue: int = Field(
        description="Number of designs that would be queued (for DOWNLOAD_ALL)",
    )


class DownloadModeResponse(BaseModel):
    """Schema for download mode change response."""

    channel_id: str
    old_mode: str
    new_mode: str
    changed: bool
    enabled_at: str | None = None
    bulk_download: dict | None = Field(
        default=None,
        description="Bulk download results if DOWNLOAD_ALL was triggered",
    )
