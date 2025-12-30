"""Pydantic schemas for Design API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.db.models.enums import (
    DesignStatus,
    ExternalSourceType,
    MatchMethod,
    MetadataAuthority,
    MulticolorStatus,
)


class ChannelSummary(BaseModel):
    """Summary of channel info for design response."""

    id: str
    title: str

    model_config = {"from_attributes": True}


class DesignSourceResponse(BaseModel):
    """Schema for design source in detail response."""

    id: str
    channel_id: str
    message_id: str
    source_rank: int
    is_preferred: bool
    caption_snapshot: Optional[str] = None
    created_at: datetime

    # Include channel info
    channel: ChannelSummary

    model_config = {"from_attributes": True}


class ExternalMetadataResponse(BaseModel):
    """Schema for external metadata source response."""

    id: str
    source_type: ExternalSourceType
    external_id: str
    external_url: str
    confidence_score: float
    match_method: MatchMethod
    is_user_confirmed: bool
    fetched_title: Optional[str] = None
    fetched_designer: Optional[str] = None
    fetched_tags: Optional[str] = None
    last_fetched_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DesignListItem(BaseModel):
    """Schema for design in list response."""

    id: str
    canonical_title: str
    canonical_designer: str
    status: DesignStatus
    multicolor: MulticolorStatus
    file_types: list[str] = []
    created_at: datetime
    updated_at: datetime

    # Summary of first source channel
    channel: Optional[ChannelSummary] = None

    # Whether design has Thangs link
    has_thangs_link: bool = False

    model_config = {"from_attributes": True}


class DesignDetail(BaseModel):
    """Schema for single design detail response."""

    id: str
    canonical_title: str
    canonical_designer: str
    status: DesignStatus
    multicolor: MulticolorStatus
    primary_file_types: Optional[str] = None
    total_size_bytes: Optional[int] = None

    # User overrides
    title_override: Optional[str] = None
    designer_override: Optional[str] = None
    multicolor_override: Optional[MulticolorStatus] = None
    notes: Optional[str] = None

    # Metadata authority
    metadata_authority: MetadataAuthority
    metadata_confidence: Optional[float] = None

    # Computed display values
    display_title: str
    display_designer: str
    display_multicolor: MulticolorStatus

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related data
    sources: list[DesignSourceResponse] = []
    external_metadata: list[ExternalMetadataResponse] = []

    model_config = {"from_attributes": True}


class DesignList(BaseModel):
    """Schema for paginated design list response."""

    items: list[DesignListItem]
    total: int
    page: int
    page_size: int
    pages: int
