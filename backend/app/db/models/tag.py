"""Tag model for design categorization."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.design_tag import DesignTag


class Tag(Base):
    """A tag for categorizing designs."""

    __tablename__ = "tags"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Tag data
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    design_tags: Mapped[list[DesignTag]] = relationship(
        "DesignTag", back_populates="tag", cascade="all, delete-orphan"
    )
