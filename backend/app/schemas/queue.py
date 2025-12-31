"""Pydantic schemas for Queue and Activity API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import DesignStatus, JobStatus, JobType


class DesignSummary(BaseModel):
    """Summary of design info for queue items."""

    id: str
    canonical_title: str
    canonical_designer: str
    channel_title: str | None = None

    model_config = {"from_attributes": True}


class QueueItemResponse(BaseModel):
    """Schema for a job in the queue."""

    id: str
    job_type: JobType
    status: JobStatus
    priority: int

    # Progress
    progress: float | None = None
    progress_message: str | None = None

    # Related design
    design: DesignSummary | None = None

    # Timing
    created_at: datetime
    started_at: datetime | None = None

    # Error info (for failed/retrying)
    last_error: str | None = None
    attempts: int = 0
    max_attempts: int = 3

    model_config = {"from_attributes": True}


class QueueListResponse(BaseModel):
    """Schema for paginated queue list."""

    items: list[QueueItemResponse]
    total: int
    page: int
    page_size: int
    pages: int


class JobResultStats(BaseModel):
    """Job result statistics for activity history."""

    # Download job results
    files_downloaded: int | None = None
    total_bytes: int | None = None
    has_archives: bool | None = None

    # Extraction job results
    archives_extracted: int | None = None
    files_created: int | None = None
    nested_archives: int | None = None

    # Import job results
    files_imported: int | None = None
    library_path: str | None = None


class ActivityItemResponse(BaseModel):
    """Schema for a completed job in activity history."""

    id: str
    job_type: JobType
    status: JobStatus

    # Related design
    design: DesignSummary | None = None

    # Timing
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None

    # Result stats (bytes, files, etc.)
    result: JobResultStats | None = None

    # Error info
    last_error: str | None = None
    attempts: int = 0

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    """Schema for paginated activity list."""

    items: list[ActivityItemResponse]
    total: int
    page: int
    page_size: int
    pages: int


class QueueStatsResponse(BaseModel):
    """Schema for queue statistics."""

    queued: int = 0
    downloading: int = 0
    extracting: int = 0
    importing: int = 0
    total_active: int = 0

    # By status (for debugging)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)


class UpdatePriorityRequest(BaseModel):
    """Request body for updating job priority."""

    priority: int = Field(ge=0, le=100, description="New priority (0-100)")


class DownloadRequest(BaseModel):
    """Request body for download actions."""

    priority: int = Field(default=0, ge=0, le=100, description="Priority for the download job")


class DownloadResponse(BaseModel):
    """Response for download action."""

    design_id: str
    job_id: str
    status: DesignStatus
    message: str


class CancelResponse(BaseModel):
    """Response for cancel action."""

    design_id: str
    jobs_cancelled: int
    status: DesignStatus
