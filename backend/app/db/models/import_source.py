"""ImportSource model for manual import sources (v0.8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import ImportSourceStatus, ImportSourceType

if TYPE_CHECKING:
    from app.db.models.design import Design
    from app.db.models.google_credentials import GoogleCredentials
    from app.db.models.import_profile import ImportProfile


class ImportSource(Base):
    """Represents a source for importing designs beyond Telegram.

    Supports three source types:
    - GOOGLE_DRIVE: Patreon/creator shared folders (public or OAuth authenticated)
    - UPLOAD: Direct file/archive upload via web UI
    - BULK_FOLDER: Local folder monitoring for existing collections

    See DEC-033 for design decisions.
    """

    __tablename__ = "import_sources"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Source identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[ImportSourceType] = mapped_column(
        Enum(ImportSourceType), nullable=False
    )
    status: Mapped[ImportSourceStatus] = mapped_column(
        Enum(ImportSourceStatus), default=ImportSourceStatus.PENDING
    )

    # Google Drive specific fields
    google_drive_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, doc="Google Drive folder/file URL"
    )
    google_drive_folder_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, doc="Extracted folder ID from URL"
    )
    google_credentials_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("google_credentials.id"), nullable=True
    )

    # Bulk folder specific fields
    folder_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, doc="Local filesystem path for bulk import"
    )

    # Import profile (optional - uses default if not set)
    import_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_profiles.id"), nullable=True
    )

    # Default metadata for imported designs
    default_designer: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Designer name applied to all imports"
    )
    default_tags_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="JSON array of default tags"
    )

    # Sync settings
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_interval_hours: Mapped[int] = mapped_column(
        Integer, default=1, doc="Hours between sync checks"
    )

    # Sync state
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Last sync error message if status=ERROR"
    )
    items_imported: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total items imported from this source"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    google_credentials: Mapped[GoogleCredentials | None] = relationship(
        "GoogleCredentials", back_populates="import_sources"
    )
    import_profile: Mapped[ImportProfile | None] = relationship(
        "ImportProfile", back_populates="import_sources"
    )
    designs: Mapped[list[Design]] = relationship(
        "Design", back_populates="import_source"
    )

    # Indexes
    __table_args__ = (
        Index("ix_import_sources_type", "source_type"),
        Index("ix_import_sources_status", "status"),
        Index("ix_import_sources_sync", "sync_enabled", "last_sync_at"),
    )
