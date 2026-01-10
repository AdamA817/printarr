"""FamilyTag model for family-tag associations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import TagSource

if TYPE_CHECKING:
    from app.db.models.design_family import DesignFamily
    from app.db.models.tag import Tag


class FamilyTag(Base):
    """Association between design families and tags.

    Tags at the family level are inherited by all variant designs.
    Per DEC-044: Tag Inheritance Strategy - collect manual + Telegram tags
    from all variants; regenerate AI tags at family level.
    """

    __tablename__ = "family_tags"

    # Composite primary key via foreign keys
    family_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("design_families.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    # Tag metadata - source indicates how the tag was assigned
    source: Mapped[TagSource] = mapped_column(Enum(TagSource), default=TagSource.USER)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    family: Mapped[DesignFamily] = relationship("DesignFamily", back_populates="family_tags")
    tag: Mapped[Tag] = relationship("Tag")

    # Indexes
    __table_args__ = (
        Index("ix_family_tags_tag_id", "tag_id"),
        Index("ix_family_tags_family_id", "family_id"),
    )
