"""DuplicateCandidate model for tracking potential duplicate designs (DEC-041)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import DuplicateCandidateStatus, DuplicateMatchType

if TYPE_CHECKING:
    from app.db.models.design import Design


class DuplicateCandidate(Base):
    """Tracks potential duplicate designs for review and merge.

    Created during two-stage deduplication:
    - Pre-download: Heuristic matching (title/designer, filename/size)
    - Post-download: SHA-256 hash matching

    Confidence scoring per DEC-041:
    - HASH: 1.0 (exact file match)
    - THANGS_ID: 1.0 (same external source)
    - TITLE_DESIGNER: 0.7 (fuzzy match)
    - FILENAME_SIZE: 0.5 (weak heuristic)
    """

    __tablename__ = "duplicate_candidates"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The design being checked (newer/incoming design)
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )

    # The potential duplicate (existing design)
    candidate_design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )

    # Match details
    match_type: Mapped[DuplicateMatchType] = mapped_column(
        Enum(DuplicateMatchType), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Status tracking
    status: Mapped[DuplicateCandidateStatus] = mapped_column(
        Enum(DuplicateCandidateStatus), default=DuplicateCandidateStatus.PENDING
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    design: Mapped[Design] = relationship(
        "Design", foreign_keys=[design_id], backref="duplicate_candidates_as_source"
    )
    candidate_design: Mapped[Design] = relationship(
        "Design", foreign_keys=[candidate_design_id], backref="duplicate_candidates_as_target"
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_duplicate_candidates_design_id", "design_id"),
        Index("ix_duplicate_candidates_candidate_design_id", "candidate_design_id"),
        Index("ix_duplicate_candidates_status", "status"),
        Index("ix_duplicate_candidates_match_type_confidence", "match_type", "confidence"),
    )
