"""Pydantic schemas for Import Source API (v0.8).

Updated for DEC-038 multi-folder support.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.enums import ConflictResolution, ImportSourceStatus, ImportSourceType


# ============================================================
# Folder Schemas (DEC-038)
# ============================================================


class ImportSourceFolderCreate(BaseModel):
    """Schema for adding a folder to an import source."""

    name: str | None = Field(
        None, max_length=255, description="Optional display name for the folder"
    )

    # Location (one required based on source type)
    google_drive_url: str | None = Field(
        None, max_length=1024, description="Google Drive folder URL"
    )
    folder_path: str | None = Field(
        None, max_length=1024, description="Local folder path"
    )

    # Per-folder overrides (optional - inherit from source if not set)
    import_profile_id: str | None = Field(
        None, description="Override source's import profile"
    )
    default_designer: str | None = Field(
        None, max_length=255, description="Override source's default designer"
    )
    default_tags: list[str] | None = Field(
        None, description="Override source's default tags"
    )

    enabled: bool = Field(True, description="Whether folder is enabled for sync")


class ImportSourceFolderUpdate(BaseModel):
    """Schema for updating a folder (all fields optional)."""

    name: str | None = Field(None, max_length=255)

    # Location cannot be changed - delete and recreate instead

    # Per-folder overrides
    import_profile_id: str | None = None
    default_designer: str | None = Field(None, max_length=255)
    default_tags: list[str] | None = None

    enabled: bool | None = None


class ImportSourceFolderSummary(BaseModel):
    """Summary of a folder for embedding in source responses."""

    model_config = {"from_attributes": True}

    id: str
    name: str | None = None
    google_drive_url: str | None = None
    google_folder_id: str | None = None
    folder_path: str | None = None
    enabled: bool = True
    items_detected: int = 0
    items_imported: int = 0
    last_synced_at: datetime | None = None
    has_overrides: bool = False  # True if any override is set


class ImportSourceFolderResponse(BaseModel):
    """Full folder response with all details."""

    model_config = {"from_attributes": True}

    id: str
    import_source_id: str
    name: str | None = None

    # Location
    google_drive_url: str | None = None
    google_folder_id: str | None = None
    folder_path: str | None = None

    # Overrides (null = inherit from source)
    import_profile_id: str | None = None
    default_designer: str | None = None
    default_tags: list[str] | None = None

    # Effective values (computed from source + overrides)
    effective_profile_id: str | None = None
    effective_designer: str | None = None
    effective_tags: list[str] = []

    # State
    enabled: bool = True
    last_synced_at: datetime | None = None
    sync_cursor: str | None = None
    last_sync_error: str | None = None

    # Stats
    items_detected: int = 0
    items_imported: int = 0

    # Timestamps
    created_at: datetime


class FolderSyncTriggerResponse(BaseModel):
    """Response after triggering sync for a single folder."""

    folder_id: str
    job_id: str | None = None
    message: str
    designs_detected: int = 0
    designs_imported: int = 0


# ============================================================
# Source Schemas (original, with folder support)
# ============================================================


class ImportSourceCreate(BaseModel):
    """Schema for creating a new import source."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: ImportSourceType

    # Google Drive specific
    google_drive_url: str | None = Field(
        None, max_length=1024, description="Google Drive folder/file URL"
    )
    google_credentials_id: str | None = Field(
        None, description="ID of stored Google OAuth credentials for private folders"
    )

    # Bulk folder specific
    folder_path: str | None = Field(
        None, max_length=1024, description="Local folder path"
    )

    # phpBB Forum specific (v1.0 - issue #239)
    phpbb_credentials_id: str | None = Field(
        None, description="ID of stored phpBB credentials"
    )
    phpbb_forum_url: str | None = Field(
        None, max_length=1024, description="URL of the phpBB forum to import from (viewforum.php?f=X)"
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

    # Google OAuth status (shared across all folders)
    google_connected: bool = False

    # phpBB status (v1.0 - issue #239)
    phpbb_connected: bool = False
    phpbb_forum_url: str | None = None

    # Type-specific fields (DEPRECATED - use folders instead)
    google_drive_url: str | None = None
    google_drive_folder_id: str | None = None
    folder_path: str | None = None

    # Shared settings
    import_profile_id: str | None = None
    default_designer: str | None = None
    default_tags: list[str] | None = None
    sync_enabled: bool
    sync_interval_hours: int

    # State
    last_sync_at: datetime | None = None
    last_sync_error: str | None = None
    items_imported: int = 0

    # Folder info (DEC-038)
    folder_count: int = 0
    enabled_folder_count: int = 0
    folders: list[ImportSourceFolderSummary] = []

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


# ============================================================
# phpBB Forum Schemas (v1.0 - issue #239)
# ============================================================


class PhpbbCredentialsCreate(BaseModel):
    """Schema for creating phpBB forum credentials."""

    base_url: str = Field(
        ..., max_length=512, description="Base URL of the phpBB forum (e.g., https://hex3dpatreon.com)"
    )
    username: str = Field(..., min_length=1, max_length=255, description="Forum username")
    password: str = Field(..., min_length=1, description="Forum password")
    test_login: bool = Field(True, description="Test login before storing credentials")


class PhpbbCredentialsResponse(BaseModel):
    """Schema for phpBB credentials response (excludes sensitive data)."""

    model_config = {"from_attributes": True}

    id: str
    base_url: str
    last_login_at: datetime | None = None
    last_login_error: str | None = None
    session_expires_at: datetime | None = None
    created_at: datetime


class PhpbbCredentialsList(BaseModel):
    """List of phpBB credentials."""

    items: list[PhpbbCredentialsResponse]


class PhpbbTestLoginRequest(BaseModel):
    """Request to test phpBB login."""

    base_url: str = Field(..., max_length=512, description="Base URL of the phpBB forum")
    username: str = Field(..., min_length=1, max_length=255, description="Forum username")
    password: str = Field(..., min_length=1, description="Forum password")


class PhpbbTestLoginResponse(BaseModel):
    """Response from phpBB login test."""

    success: bool
    message: str
    forum_name: str | None = None


class PhpbbForumInfo(BaseModel):
    """Information about a phpBB forum."""

    forum_id: int
    name: str
    url: str
    topic_count: int = 0


class PhpbbForumListRequest(BaseModel):
    """Request to list forums on a phpBB site."""

    credentials_id: str = Field(..., description="ID of stored phpBB credentials")


class PhpbbForumListResponse(BaseModel):
    """Response listing available forums."""

    forums: list[PhpbbForumInfo]
