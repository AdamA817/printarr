"""ImportRecord model for tracking imported files (v0.8).

Tracks individual files/folders imported from sources to avoid duplicates
and enable re-import detection.

Per DEC-038, records now reference ImportSourceFolder instead of ImportSource.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import ImportRecordStatus

if TYPE_CHECKING:
    from app.db.models.design import Design
    from app.db.models.import_source import ImportSource
    from app.db.models.import_source_folder import ImportSourceFolder


class ImportRecord(Base):
    """Tracks individual files/folders imported from a folder.

    Used for:
    - Duplicate detection (don't re-import same file)
    - Re-sync detection (file changed, needs update)
    - Import history and audit trail

    See DEC-037 for conflict handling decisions.
    See DEC-038 for multi-folder support.
    """

    __tablename__ = "import_records"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Folder reference (new - per DEC-038)
    import_source_folder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_source_folders.id", ondelete="CASCADE"), nullable=True
    )

    # Source reference (DEPRECATED - kept for backward compatibility during migration)
    import_source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_sources.id", ondelete="CASCADE"), nullable=True
    )

    # File identification
    source_path: Mapped[str] = mapped_column(
        String(2048), nullable=False, doc="Original path relative to source root"
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="SHA-256 hash for deduplication"
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="File size in bytes"
    )
    file_mtime: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, doc="File modification time for change detection"
    )

    # Import status
    status: Mapped[ImportRecordStatus] = mapped_column(
        Enum(ImportRecordStatus), default=ImportRecordStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Error message if status=ERROR"
    )

    # Design reference (set after successful import)
    design_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True
    )

    # Metadata extracted during detection
    detected_title: Mapped[str | None] = mapped_column(
        String(512), nullable=True, doc="Title extracted during scanning"
    )
    detected_designer: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Designer extracted during scanning"
    )
    model_file_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of model files detected"
    )
    preview_file_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of preview files detected"
    )

    # Google Drive specific metadata
    google_folder_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="Google Drive folder ID for this design"
    )

    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    import_source_folder: Mapped[ImportSourceFolder | None] = relationship(
        "ImportSourceFolder", back_populates="import_records"
    )
    import_source: Mapped[ImportSource | None] = relationship(
        "ImportSource"
    )
    design: Mapped[Design | None] = relationship(
        "Design", back_populates="import_records"
    )

    # Indexes
    __table_args__ = (
        # For finding records by folder (new - DEC-038)
        Index("ix_import_records_folder", "import_source_folder_id"),
        # For duplicate detection (folder + path must be unique)
        Index("ix_import_records_folder_path", "import_source_folder_id", "source_path", unique=True),
        # For finding records by source (deprecated but kept for migration)
        Index("ix_import_records_source", "import_source_id"),
        # For finding records by hash
        Index("ix_import_records_hash", "file_hash"),
        # For finding pending records
        Index("ix_import_records_status", "status"),
        # For finding records by design
        Index("ix_import_records_design", "design_id"),
    )
