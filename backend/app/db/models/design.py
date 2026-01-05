"""Design model for the deduplicated design catalog."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    DesignStatus,
    MetadataAuthority,
    MulticolorSource,
    MulticolorStatus,
)

if TYPE_CHECKING:
    from app.db.models.design_file import DesignFile
    from app.db.models.design_source import DesignSource
    from app.db.models.design_tag import DesignTag
    from app.db.models.external_metadata_source import ExternalMetadataSource
    from app.db.models.import_record import ImportRecord
    from app.db.models.import_source import ImportSource
    from app.db.models.job import Job
    from app.db.models.preview_asset import PreviewAsset


class Design(Base):
    """A deduplicated catalog item that may have multiple sources."""

    __tablename__ = "designs"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Canonical metadata (computed/auto-detected)
    canonical_title: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_designer: Mapped[str] = mapped_column(String(255), default="Unknown")
    multicolor: Mapped[MulticolorStatus] = mapped_column(
        Enum(MulticolorStatus), default=MulticolorStatus.UNKNOWN
    )
    # Source of multicolor detection (per DEC-029)
    multicolor_source: Mapped[MulticolorSource | None] = mapped_column(
        Enum(MulticolorSource), nullable=True
    )
    status: Mapped[DesignStatus] = mapped_column(
        Enum(DesignStatus), default=DesignStatus.DISCOVERED
    )

    # Derived data
    primary_file_types: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Comma-separated list
    total_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # User overrides
    title_override: Mapped[str | None] = mapped_column(String(512), nullable=True)
    designer_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    multicolor_override: Mapped[MulticolorStatus | None] = mapped_column(
        Enum(MulticolorStatus), nullable=True
    )

    # Notes (user-provided)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Split archive detection
    is_split_archive: Mapped[bool] = mapped_column(Boolean, default=False)
    split_archive_base_name: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    detected_parts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_parts: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata authority (source of truth for canonical metadata)
    metadata_authority: Mapped[MetadataAuthority] = mapped_column(
        Enum(MetadataAuthority), default=MetadataAuthority.TELEGRAM
    )
    metadata_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Import source (v0.8 - for non-Telegram imports)
    import_source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_sources.id"), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    sources: Mapped[list[DesignSource]] = relationship(
        "DesignSource", back_populates="design", cascade="all, delete-orphan"
    )
    files: Mapped[list[DesignFile]] = relationship(
        "DesignFile", back_populates="design", cascade="all, delete-orphan"
    )
    design_tags: Mapped[list[DesignTag]] = relationship(
        "DesignTag", back_populates="design", cascade="all, delete-orphan"
    )
    preview_assets: Mapped[list[PreviewAsset]] = relationship(
        "PreviewAsset", back_populates="design", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="design")
    external_metadata_sources: Mapped[list[ExternalMetadataSource]] = relationship(
        "ExternalMetadataSource", back_populates="design", cascade="all, delete-orphan"
    )
    import_source: Mapped[ImportSource | None] = relationship(
        "ImportSource", back_populates="designs"
    )
    import_records: Mapped[list[ImportRecord]] = relationship(
        "ImportRecord", back_populates="design"
    )

    # Indexes
    __table_args__ = (
        Index("ix_designs_status", "status"),
        Index("ix_designs_designer", "canonical_designer"),
        Index("ix_designs_multicolor", "multicolor"),
        Index("ix_designs_created_at", "created_at"),
    )

    @property
    def display_title(self) -> str:
        """Get the display title (override or canonical)."""
        return self.title_override or self.canonical_title

    @property
    def display_designer(self) -> str:
        """Get the display designer (override or canonical)."""
        return self.designer_override or self.canonical_designer

    @property
    def display_multicolor(self) -> MulticolorStatus:
        """Get the display multicolor status (override or detected)."""
        return self.multicolor_override or self.multicolor
