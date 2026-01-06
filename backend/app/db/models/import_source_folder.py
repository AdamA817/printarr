"""ImportSourceFolder model for individual folders within an import source (v0.8).

Per DEC-038, ImportSource is now a parent container and ImportSourceFolder
holds the actual folder locations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.import_profile import ImportProfile
    from app.db.models.import_record import ImportRecord
    from app.db.models.import_source import ImportSource


class ImportSourceFolder(Base):
    """Individual folder within an import source.

    Holds the actual folder path/URL and per-folder overrides.
    Parent ImportSource provides shared settings that can be overridden here.

    See DEC-038 for multi-folder design decisions.
    """

    __tablename__ = "import_source_folders"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Parent reference
    import_source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_sources.id", ondelete="CASCADE"), nullable=False
    )

    # Display name (optional - defaults to folder name from path/URL)
    name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Optional display name (e.g., 'Dec 2025 Release')"
    )

    # Google Drive location (for GOOGLE_DRIVE type)
    google_drive_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, doc="Google Drive folder URL"
    )
    google_folder_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, doc="Extracted folder ID from URL"
    )

    # Local folder location (for BULK_FOLDER type)
    folder_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, doc="Local filesystem path"
    )

    # phpBB forum location (for PHPBB_FORUM type - issue #242)
    phpbb_forum_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, doc="phpBB forum page URL (viewforum.php?f=X)"
    )

    # Per-folder overrides (null = inherit from parent source)
    import_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_profiles.id"), nullable=True,
        doc="Override parent's import profile"
    )
    default_designer: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Override parent's default designer"
    )
    default_tags_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Override parent's default tags (JSON array)"
    )

    # Sync state
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, doc="Whether this folder is enabled for sync"
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(
        String(512), nullable=True, doc="Cursor for incremental sync (page token, etc.)"
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Last sync error message"
    )

    # Stats
    items_detected: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total items detected in this folder"
    )
    items_imported: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total items imported from this folder"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    import_source: Mapped[ImportSource] = relationship(
        "ImportSource", back_populates="folders"
    )
    import_profile: Mapped[ImportProfile | None] = relationship(
        "ImportProfile", back_populates="import_source_folders"
    )
    import_records: Mapped[list[ImportRecord]] = relationship(
        "ImportRecord", back_populates="import_source_folder", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_import_source_folders_source", "import_source_id"),
        Index("ix_import_source_folders_enabled", "enabled"),
        Index("ix_import_source_folders_google_id", "google_folder_id"),
    )

    @property
    def display_name(self) -> str:
        """Get the display name, falling back to folder name from path/URL."""
        if self.name:
            return self.name
        if self.folder_path:
            from pathlib import Path
            return Path(self.folder_path).name
        if self.google_drive_url:
            # Extract folder name from URL or use folder ID
            return self.google_folder_id or "Google Drive Folder"
        if self.phpbb_forum_url:
            # Extract forum ID from URL for display
            import re
            match = re.search(r"f=(\d+)", self.phpbb_forum_url)
            return f"Forum {match.group(1)}" if match else "phpBB Forum"
        return "Unnamed Folder"
