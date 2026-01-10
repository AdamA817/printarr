"""DesignFamily model for grouping related design variants."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import FamilyDetectionMethod

if TYPE_CHECKING:
    from app.db.models.design import Design
    from app.db.models.family_tag import FamilyTag


class DesignFamily(Base):
    """Groups related design variants under a common name.

    A family represents a group of designs that are variations of the same
    base design (e.g., different color variants, versions, or sizes).

    Per DEC-044: Design Families Architecture
    """

    __tablename__ = "design_families"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Family identity (canonical = auto-detected or first assigned)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_designer: Mapped[str] = mapped_column(String(255), default="Unknown")

    # Optional user overrides
    name_override: Mapped[str | None] = mapped_column(String(512), nullable=True)
    designer_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Detection metadata
    detection_method: Mapped[FamilyDetectionMethod] = mapped_column(
        Enum(FamilyDetectionMethod), default=FamilyDetectionMethod.MANUAL
    )
    detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    designs: Mapped[list[Design]] = relationship(
        "Design", back_populates="family", foreign_keys="Design.family_id"
    )
    family_tags: Mapped[list[FamilyTag]] = relationship(
        "FamilyTag", back_populates="family", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_design_families_canonical_name", "canonical_name"),
        Index("ix_design_families_canonical_designer", "canonical_designer"),
        Index("ix_design_families_detection_method", "detection_method"),
        Index("ix_design_families_created_at", "created_at"),
    )

    @property
    def display_name(self) -> str:
        """Get the display name (override or canonical)."""
        return self.name_override or self.canonical_name

    @property
    def display_designer(self) -> str:
        """Get the display designer (override or canonical)."""
        return self.designer_override or self.canonical_designer

    @property
    def variant_count(self) -> int:
        """Get the number of designs in this family."""
        return len(self.designs) if self.designs else 0
