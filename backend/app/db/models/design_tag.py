"""DesignTag model for design-tag associations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import TagSource

if TYPE_CHECKING:
    from app.db.models.design import Design
    from app.db.models.tag import Tag


class DesignTag(Base):
    """Association between designs and tags."""

    __tablename__ = "design_tags"

    # Composite primary key via foreign keys
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    # Tag metadata
    source: Mapped[TagSource] = mapped_column(Enum(TagSource), default=TagSource.AUTO)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    design: Mapped[Design] = relationship("Design", back_populates="design_tags")
    tag: Mapped[Tag] = relationship("Tag", back_populates="design_tags")

    # Indexes
    __table_args__ = (
        Index("ix_design_tags_tag_id", "tag_id"),
        Index("ix_design_tags_design_id", "design_id"),
    )
