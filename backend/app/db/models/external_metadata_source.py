"""ExternalMetadataSource model for linking designs to external platforms."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import ExternalSourceType, MatchMethod

if TYPE_CHECKING:
    from app.db.models.design import Design


class ExternalMetadataSource(Base):
    """Links a Design to an external metadata authority (Thangs, Printables, etc.)."""

    __tablename__ = "external_metadata_sources"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Design reference
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )

    # External source identification
    source_type: Mapped[ExternalSourceType] = mapped_column(
        Enum(ExternalSourceType), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Match confidence
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    match_method: Mapped[MatchMethod] = mapped_column(
        Enum(MatchMethod), default=MatchMethod.LINK
    )
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Fetched metadata from external source
    fetched_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fetched_designer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fetched_tags: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array stored as text

    # Timestamps
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    design: Mapped[Design] = relationship("Design", back_populates="external_metadata_sources")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("design_id", "source_type", name="uq_design_source_type"),
        Index("ix_external_metadata_sources_source_type", "source_type"),
        Index("ix_external_metadata_sources_external_id", "external_id"),
    )
