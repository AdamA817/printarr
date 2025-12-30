"""Pydantic schemas for stats API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    """Dashboard statistics response."""

    channels_count: int = Field(..., description="Total number of channels")
    designs_count: int = Field(
        default=0, description="Total number of designs (not yet implemented)"
    )
    downloads_active: int = Field(
        default=0, description="Number of active downloads (not yet implemented)"
    )
