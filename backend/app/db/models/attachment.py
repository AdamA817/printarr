"""Attachment model for Telegram message attachments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import AttachmentDownloadStatus, MediaType

if TYPE_CHECKING:
    from app.db.models.design_file import DesignFile
    from app.db.models.preview_asset import PreviewAsset
    from app.db.models.telegram_message import TelegramMessage


class Attachment(Base):
    """A file or media item attached to a Telegram message."""

    __tablename__ = "attachments"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Message reference
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("telegram_messages.id", ondelete="CASCADE"), nullable=False
    )

    # Telegram file identification
    telegram_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_unique_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # File metadata
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType), default=MediaType.DOCUMENT)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ext: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Design file detection
    is_candidate_design_file: Mapped[bool] = mapped_column(Boolean, default=False)

    # Download state
    download_status: Mapped[AttachmentDownloadStatus] = mapped_column(
        Enum(AttachmentDownloadStatus), default=AttachmentDownloadStatus.NOT_DOWNLOADED
    )
    download_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow
    )

    # Relationships
    message: Mapped[TelegramMessage] = relationship(
        "TelegramMessage", back_populates="attachments"
    )
    design_files: Mapped[list[DesignFile]] = relationship(
        "DesignFile", back_populates="source_attachment"
    )
    preview_assets: Mapped[list[PreviewAsset]] = relationship(
        "PreviewAsset", back_populates="source_attachment"
    )

    # Indexes
    __table_args__ = (
        Index("ix_attachments_message_id", "message_id"),
        Index("ix_attachments_candidate", "is_candidate_design_file"),
        Index("ix_attachments_sha256", "sha256"),
    )
