"""Pydantic schemas for Design API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models.enums import (
    DesignStatus,
    ExternalSourceType,
    MatchMethod,
    MetadataAuthority,
    MulticolorStatus,
    PreviewSource,
    TagSource,
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
    caption_snapshot: str | None = None
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
    fetched_title: str | None = None
    fetched_designer: str | None = None
    fetched_tags: str | None = None
    last_fetched_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TagSummary(BaseModel):
    """Summary of tag info for design responses."""

    id: str
    name: str
    category: str | None = None
    source: TagSource

    model_config = {"from_attributes": True}


class PreviewSummary(BaseModel):
    """Summary of preview info for design list responses."""

    id: str
    source: PreviewSource
    file_path: str
    width: int | None = None
    height: int | None = None

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

    # Computed display values (use overrides if present)
    display_title: str
    display_designer: str

    # Summary of first source channel
    channel: ChannelSummary | None = None

    # Whether design has Thangs link
    has_thangs_link: bool = False

    # Tags assigned to this design
    tags: list[TagSummary] = []

    # Primary preview image (for catalog display)
    primary_preview: PreviewSummary | None = None

    # Design family info (DEC-044)
    family_id: str | None = None
    variant_name: str | None = None

    model_config = {"from_attributes": True}


class DesignDetail(BaseModel):
    """Schema for single design detail response."""

    id: str
    canonical_title: str
    canonical_designer: str
    status: DesignStatus
    multicolor: MulticolorStatus
    primary_file_types: str | None = None
    total_size_bytes: int | None = None

    # User overrides
    title_override: str | None = None
    designer_override: str | None = None
    multicolor_override: MulticolorStatus | None = None
    notes: str | None = None

    # Metadata authority
    metadata_authority: MetadataAuthority
    metadata_confidence: float | None = None

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

    # Design family info (DEC-044)
    family_id: str | None = None
    variant_name: str | None = None

    model_config = {"from_attributes": True}


class DesignList(BaseModel):
    """Schema for paginated design list response."""

    items: list[DesignListItem]
    total: int
    page: int
    page_size: int
    pages: int
