"""PreviewAsset model for design preview images.

Also known as DesignPreview in issue specs. Stores preview images from
multiple sources: Telegram posts, Thangs, embedded 3MF thumbnails,
rendered STL previews, and archive contents.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import PreviewKind, PreviewSource

if TYPE_CHECKING:
    from app.db.models.attachment import Attachment
    from app.db.models.design import Design


class PreviewAsset(Base):
    """Stores references to preview images for designs.

    Per DEC-027, images are stored in /cache/previews/ with subdirectories by source.
    Per DEC-032, primary preview is auto-selected based on source priority.
    """

    __tablename__ = "preview_assets"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )
    source_attachment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True
    )

    # Preview source and type
    source: Mapped[PreviewSource] = mapped_column(
        Enum(PreviewSource), nullable=False, default=PreviewSource.TELEGRAM
    )
    kind: Mapped[PreviewKind] = mapped_column(
        Enum(PreviewKind), nullable=False, default=PreviewKind.THUMBNAIL
    )

    # File information (path relative to /cache/previews)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Image dimensions
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Telegram-specific fields
    telegram_file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Display ordering
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    design: Mapped[Design] = relationship("Design", back_populates="preview_assets")
    source_attachment: Mapped[Attachment | None] = relationship(
        "Attachment", back_populates="preview_assets"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_preview_assets_design_id", "design_id"),
        Index("ix_preview_assets_design_source", "design_id", "source"),
        Index("ix_preview_assets_is_primary", "is_primary"),
    )
