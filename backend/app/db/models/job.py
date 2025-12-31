"""Job model for background task tracking."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import JobStatus, JobType

if TYPE_CHECKING:
    from app.db.models.channel import Channel
    from app.db.models.design import Design


class Job(Base):
    """Tracks background work and feeds the Activity UI."""

    __tablename__ = "jobs"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Job type and status
    type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # Optional references
    channel_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="SET NULL"), nullable=True
    )
    design_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True
    )

    # Job payload (JSON stored as text for SQLite compatibility)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Job result (JSON stored as text for completion stats like bytes, files)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Progress tracking
    progress_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Retry handling
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    channel: Mapped[Channel | None] = relationship("Channel", back_populates="jobs")
    design: Mapped[Design | None] = relationship("Design", back_populates="jobs")

    # Indexes
    __table_args__ = (
        Index("ix_jobs_status_type_priority", "status", "type", "priority"),
        Index("ix_jobs_design_id", "design_id"),
        Index("ix_jobs_channel_id", "channel_id"),
    )

    @property
    def progress_percent(self) -> float | None:
        """Calculate progress percentage."""
        if self.progress_total and self.progress_total > 0:
            return (self.progress_current or 0) / self.progress_total * 100
        return None
