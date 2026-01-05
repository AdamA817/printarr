"""Tag model for design categorization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.design_tag import DesignTag


class Tag(Base):
    """A tag for categorizing designs.

    Supports hybrid taxonomy per DEC-028:
    - Predefined tags with categories (Type, Theme, Scale, etc.)
    - Free-form user tags without category
    """

    __tablename__ = "tags"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Tag data (normalized to lowercase for deduplication)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Category for predefined tags (Type, Theme, Scale, Complexity, Print Type)
    # None for free-form user tags
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Whether this is a predefined tag from the taxonomy
    is_predefined: Mapped[bool] = mapped_column(Boolean, default=False)

    # Cached usage count for efficient sorting/display
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    design_tags: Mapped[list[DesignTag]] = relationship(
        "DesignTag", back_populates="tag", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_tags_name", "name"),
        Index("ix_tags_category", "category"),
        Index("ix_tags_is_predefined", "is_predefined"),
    )
