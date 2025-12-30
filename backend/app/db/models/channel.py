"""Channel model for Telegram channels."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import BackfillMode, DesignerSource, DownloadMode, TitleSource

if TYPE_CHECKING:
    from app.db.models.design_source import DesignSource
    from app.db.models.job import Job
    from app.db.models.telegram_message import TelegramMessage


class Channel(Base):
    """Represents a monitored Telegram channel/group."""

    __tablename__ = "channels"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Telegram identification
    telegram_peer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Channel settings
    backfill_mode: Mapped[BackfillMode] = mapped_column(
        Enum(BackfillMode), default=BackfillMode.LAST_N_MESSAGES
    )
    backfill_value: Mapped[int] = mapped_column(Integer, default=100)
    download_mode: Mapped[DownloadMode] = mapped_column(
        Enum(DownloadMode), default=DownloadMode.MANUAL
    )
    library_template_override: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    title_source_override: Mapped[Optional[TitleSource]] = mapped_column(
        Enum(TitleSource), nullable=True
    )
    designer_source_override: Mapped[Optional[DesignerSource]] = mapped_column(
        Enum(DesignerSource), nullable=True
    )

    # Sync state
    last_ingested_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_backfill_checkpoint: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    messages: Mapped[list["TelegramMessage"]] = relationship(
        "TelegramMessage", back_populates="channel", cascade="all, delete-orphan"
    )
    design_sources: Mapped[list["DesignSource"]] = relationship(
        "DesignSource", back_populates="channel"
    )
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="channel")

    # Indexes
    __table_args__ = (Index("ix_channels_enabled_sync", "is_enabled", "last_sync_at"),)
