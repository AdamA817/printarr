"""DiscoveredChannel model for channels found via monitored content."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiscoveredChannel(Base):
    """Represents a channel discovered via forwards, mentions, or links in monitored content.

    These are channels that have been referenced but not yet added to monitoring.
    The discovery service extracts channel references from messages and tracks them here.
    """

    __tablename__ = "discovered_channels"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Telegram identification (may be partially known)
    telegram_peer_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    invite_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # For private channel invite links
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)

    # Discovery tracking
    reference_count: Mapped[int] = mapped_column(Integer, default=1, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Source types that discovered this channel (JSON array of DiscoverySourceType values)
    # e.g., ["FORWARD", "MENTION"] if found via both methods
    source_types: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Indexes for common queries
    __table_args__ = (
        # Composite index for sorting by reference count and recency
        Index("ix_discovered_channels_refs_last_seen", "reference_count", "last_seen_at"),
    )

    def add_source_type(self, source_type: str) -> None:
        """Add a source type if not already present."""
        if source_type not in self.source_types:
            # Create new list to trigger SQLAlchemy change detection
            self.source_types = [*self.source_types, source_type]

    def increment_reference(self, source_type: str | None = None) -> None:
        """Increment reference count and update last_seen_at."""
        self.reference_count += 1
        self.last_seen_at = datetime.utcnow()
        if source_type:
            self.add_source_type(source_type)
