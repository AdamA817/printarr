"""Channel model for Telegram channels."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import BackfillMode, DesignerSource, DownloadMode, TitleSource

if TYPE_CHECKING:
    from app.db.models.design_source import DesignSource
    from app.db.models.import_source import ImportSource
    from app.db.models.job import Job
    from app.db.models.telegram_message import TelegramMessage


class Channel(Base):
    """Represents a monitored Telegram channel or virtual import source channel (#237)."""

    __tablename__ = "channels"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Virtual channel flag (#237) - True for import source channels, False for Telegram channels
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False)

    # Import source link (#237) - Only set for virtual channels
    import_source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_sources.id", ondelete="CASCADE"), nullable=True
    )

    # Telegram identification (nullable for virtual channels)
    telegram_peer_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
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
    download_mode_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When download mode was changed from MANUAL"
    )
    library_template_override: Mapped[str | None] = mapped_column(String(512), nullable=True)
    title_source_override: Mapped[TitleSource | None] = mapped_column(
        Enum(TitleSource), nullable=True
    )
    designer_source_override: Mapped[DesignerSource | None] = mapped_column(
        Enum(DesignerSource), nullable=True
    )

    # Sync state
    last_ingested_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_backfill_checkpoint: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    messages: Mapped[list[TelegramMessage]] = relationship(
        "TelegramMessage", back_populates="channel", cascade="all, delete-orphan"
    )
    design_sources: Mapped[list[DesignSource]] = relationship(
        "DesignSource", back_populates="channel", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="channel", cascade="all, delete-orphan"
    )
    import_source: Mapped[ImportSource | None] = relationship(
        "ImportSource", back_populates="channel"
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_channels_enabled_sync", "is_enabled", "last_sync_at"),
        Index("ix_channels_import_source", "import_source_id"),
        Index("ix_channels_virtual", "is_virtual"),
        # Each import source can only have one virtual channel
        UniqueConstraint("import_source_id", name="uq_channels_import_source"),
    )
