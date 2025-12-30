"""TelegramMessage model for raw message metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.attachment import Attachment
    from app.db.models.channel import Channel
    from app.db.models.design_source import DesignSource


class TelegramMessage(Base):
    """Raw message metadata from Telegram."""

    __tablename__ = "telegram_messages"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Channel reference
    channel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )

    # Telegram identification
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Message metadata
    date_posted: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    caption_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    caption_text_normalized: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="message", cascade="all, delete-orphan"
    )
    design_source: Mapped[Optional["DesignSource"]] = relationship(
        "DesignSource", back_populates="message", uselist=False
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("channel_id", "telegram_message_id", name="uq_channel_message"),
        Index("ix_telegram_messages_channel_date", "channel_id", "date_posted"),
    )
