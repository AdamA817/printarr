"""Pydantic schemas for stats API."""

from __future__ import annotations

from datetime import date, datetime

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


# Dashboard Stats Models (expanded for #103)


class DesignStatusCounts(BaseModel):
    """Counts of designs by status."""

    discovered: int = Field(default=0, description="Designs discovered but not downloaded")
    wanted: int = Field(default=0, description="Designs queued for download")
    downloading: int = Field(default=0, description="Designs currently downloading")
    downloaded: int = Field(default=0, description="Designs downloaded but not imported")
    imported: int = Field(default=0, description="Designs imported to library")
    failed: int = Field(default=0, description="Designs that failed processing")
    total: int = Field(default=0, description="Total designs across all statuses")


class ChannelCounts(BaseModel):
    """Counts of channels by state."""

    enabled: int = Field(default=0, description="Enabled channels")
    disabled: int = Field(default=0, description="Disabled channels")
    total: int = Field(default=0, description="Total channels")


class DownloadStats(BaseModel):
    """Download statistics."""

    today: int = Field(default=0, description="Downloads completed today")
    this_week: int = Field(default=0, description="Downloads completed this week")
    active: int = Field(default=0, description="Currently active downloads")
    queued: int = Field(default=0, description="Downloads in queue")


class DashboardStatsResponse(BaseModel):
    """Comprehensive dashboard statistics response."""

    designs: DesignStatusCounts = Field(description="Design counts by status")
    channels: ChannelCounts = Field(description="Channel counts")
    discovered_channels: int = Field(default=0, description="Discovered channels count")
    downloads: DownloadStats = Field(description="Download statistics")
    library_file_count: int = Field(default=0, description="Files in library")
    library_size_bytes: int = Field(default=0, description="Library size in bytes")


class CalendarDesign(BaseModel):
    """Design summary for calendar view."""

    id: str
    title: str
    thumbnail_url: str | None = None


class CalendarDay(BaseModel):
    """Calendar data for a single day."""

    date: date
    count: int = Field(description="Number of designs created on this date")
    designs: list[CalendarDesign] = Field(
        default_factory=list, description="Designs created on this date (limited)"
    )


class CalendarResponse(BaseModel):
    """Calendar data for dashboard."""

    days: list[CalendarDay] = Field(description="Calendar data by day")
    total_period: int = Field(description="Total designs in period")


class JobSummary(BaseModel):
    """Summary of a job for queue display."""

    id: str
    type: str
    status: str
    design_title: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class QueueResponse(BaseModel):
    """Queue summary for dashboard."""

    running: int = Field(default=0, description="Currently running jobs")
    queued: int = Field(default=0, description="Jobs waiting in queue")
    recent_completions: list[JobSummary] = Field(
        default_factory=list, description="Recently completed jobs"
    )
    recent_failures: list[JobSummary] = Field(
        default_factory=list, description="Recently failed jobs"
    )


class StorageResponse(BaseModel):
    """Storage breakdown for dashboard."""

    library_size_bytes: int = Field(default=0, description="Library directory size")
    staging_size_bytes: int = Field(default=0, description="Staging directory size")
    cache_size_bytes: int = Field(default=0, description="Cache directory size")
    available_bytes: int = Field(default=0, description="Available disk space")
    total_bytes: int = Field(default=0, description="Total disk space")
