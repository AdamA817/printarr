"""DesignSource model linking designs to Telegram messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.channel import Channel
    from app.db.models.design import Design
    from app.db.models.telegram_message import TelegramMessage


class DesignSource(Base):
    """Links a Design to one Telegram message (source)."""

    __tablename__ = "design_sources"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("telegram_messages.id", ondelete="CASCADE"), nullable=False
    )

    # Source metadata
    source_rank: Mapped[int] = mapped_column(Integer, default=0)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    caption_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    design: Mapped[Design] = relationship("Design", back_populates="sources")
    channel: Mapped[Channel] = relationship("Channel", back_populates="design_sources")
    message: Mapped[TelegramMessage] = relationship(
        "TelegramMessage", back_populates="design_source"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_design_source_message"),
        Index("ix_design_sources_design_id", "design_id"),
    )
