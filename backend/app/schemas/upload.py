"""Pydantic schemas for File Upload API (v0.8)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class UploadStatus(str, Enum):
    """Status of an upload."""

    PENDING = "PENDING"  # File received, awaiting processing
    PROCESSING = "PROCESSING"  # Currently being processed
    COMPLETED = "COMPLETED"  # Successfully processed
    FAILED = "FAILED"  # Processing failed
    EXPIRED = "EXPIRED"  # Retention period exceeded


class UploadInfo(BaseModel):
    """Information about an uploaded file."""

    id: str
    filename: str
    size: int
    mime_type: str | None = None
    status: UploadStatus
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    design_id: str | None = Field(None, description="Created design ID after processing")


class UploadResponse(BaseModel):
    """Response after file upload."""

    upload_id: str
    filename: str
    size: int
    status: UploadStatus


class BatchUploadResponse(BaseModel):
    """Response after batch file upload."""

    batch_id: str
    uploads: list[UploadResponse]
    total_size: int


class UploadStatusResponse(BaseModel):
    """Response for upload status check."""

    upload_id: str
    filename: str
    status: UploadStatus
    error_message: str | None = None
    design_id: str | None = None
    progress: int = Field(0, ge=0, le=100, description="Processing progress percentage")


class ProcessUploadRequest(BaseModel):
    """Request to process an uploaded file."""

    import_profile_id: str | None = Field(
        None, description="Import profile to use (default if not specified)"
    )
    designer: str | None = Field(None, description="Designer name override")
    tags: list[str] | None = Field(None, description="Tags to apply to created design")
    title: str | None = Field(None, description="Title override for single-file uploads")


class ProcessUploadResponse(BaseModel):
    """Response after processing an upload."""

    upload_id: str
    status: UploadStatus
    design_id: str | None = None
    design_title: str | None = None
    files_extracted: int = 0
    model_files: int = 0
    preview_files: int = 0
    error_message: str | None = None
