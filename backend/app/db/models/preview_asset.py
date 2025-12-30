"""PreviewAsset model for design preview images."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import PreviewKind

if TYPE_CHECKING:
    from app.db.models.attachment import Attachment
    from app.db.models.design import Design


class PreviewAsset(Base):
    """Stores references to preview images."""

    __tablename__ = "preview_assets"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )
    source_attachment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True
    )

    # Preview metadata
    kind: Mapped[PreviewKind] = mapped_column(Enum(PreviewKind), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    design: Mapped["Design"] = relationship("Design", back_populates="preview_assets")
    source_attachment: Mapped[Optional["Attachment"]] = relationship(
        "Attachment", back_populates="preview_assets"
    )

    # Indexes
    __table_args__ = (Index("ix_preview_assets_design_kind", "design_id", "kind"),)
