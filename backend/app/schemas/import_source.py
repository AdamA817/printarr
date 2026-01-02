"""Pydantic schemas for Import Source API (v0.8)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import ConflictResolution, ImportSourceStatus, ImportSourceType


class ImportSourceCreate(BaseModel):
    """Schema for creating a new import source."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: ImportSourceType

    # Google Drive specific
    google_drive_url: str | None = Field(
        None, max_length=1024, description="Google Drive folder/file URL"
    )

    # Bulk folder specific
    folder_path: str | None = Field(
        None, max_length=1024, description="Local folder path"
    )

    # Optional settings
    import_profile_id: str | None = Field(None, description="Import profile to use")
    default_designer: str | None = Field(
        None, max_length=255, description="Default designer for imported designs"
    )
    default_tags: list[str] | None = Field(
        None, description="Default tags for imported designs"
    )
    sync_enabled: bool = Field(True, description="Enable automatic syncing")
    sync_interval_hours: int = Field(
        1, ge=1, le=168, description="Hours between sync checks"
    )


class ImportSourceUpdate(BaseModel):
    """Schema for updating an import source (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)

    # Note: source_type cannot be changed after creation

    # Google Drive specific
    google_drive_url: str | None = Field(None, max_length=1024)

    # Bulk folder specific
    folder_path: str | None = Field(None, max_length=1024)

    # Optional settings
    import_profile_id: str | None = None
    default_designer: str | None = Field(None, max_length=255)
    default_tags: list[str] | None = None
    sync_enabled: bool | None = None
    sync_interval_hours: int | None = Field(None, ge=1, le=168)


class ImportProfileSummary(BaseModel):
    """Summary of an import profile for embedding in source responses."""

    id: str
    name: str
    is_builtin: bool


class ImportSourceResponse(BaseModel):
    """Schema for import source response."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    source_type: ImportSourceType
    status: ImportSourceStatus

    # Type-specific fields
    google_drive_url: str | None = None
    google_drive_folder_id: str | None = None
    folder_path: str | None = None

    # Settings
    import_profile_id: str | None = None
    default_designer: str | None = None
    default_tags: list[str] | None = None
    sync_enabled: bool
    sync_interval_hours: int

    # State
    last_sync_at: datetime | None = None
    last_sync_error: str | None = None
    items_imported: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Embedded profile (optional)
    profile: ImportProfileSummary | None = None


class ImportSourceList(BaseModel):
    """Schema for paginated import source list response."""

    items: list[ImportSourceResponse]
    total: int


class ImportSourceDetailResponse(ImportSourceResponse):
    """Detailed import source response with additional info."""

    # Include import records summary
    pending_count: int = 0
    imported_count: int = 0
    error_count: int = 0


class SyncTriggerRequest(BaseModel):
    """Request to trigger a sync for an import source."""

    conflict_resolution: ConflictResolution = Field(
        ConflictResolution.SKIP, description="How to handle conflicts"
    )
    auto_import: bool = Field(
        False, description="Automatically import detected designs"
    )


class SyncTriggerResponse(BaseModel):
    """Response after triggering a sync."""

    source_id: str
    job_id: str | None = None  # If async job was created
    message: str
    designs_detected: int = 0
    designs_imported: int = 0


class ImportHistoryItem(BaseModel):
    """Single item in import history."""

    id: str
    source_path: str
    status: str
    detected_title: str | None = None
    design_id: str | None = None
    error_message: str | None = None
    detected_at: datetime
    imported_at: datetime | None = None


class ImportHistoryResponse(BaseModel):
    """Paginated import history response."""

    items: list[ImportHistoryItem]
    total: int
    page: int
    page_size: int


class GoogleOAuthStatusResponse(BaseModel):
    """Status of Google OAuth authentication."""

    configured: bool
    authenticated: bool
    email: str | None = None
    expires_at: datetime | None = None
