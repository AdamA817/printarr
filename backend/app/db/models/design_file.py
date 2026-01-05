"""DesignFile model for files belonging to a design."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import FileKind, ModelKind

if TYPE_CHECKING:
    from app.db.models.attachment import Attachment
    from app.db.models.design import Design


class DesignFile(Base):
    """Represents a file that belongs to a design."""

    __tablename__ = "design_files"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References
    design_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
    )
    source_attachment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True
    )

    # File metadata
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    ext: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # File classification
    file_kind: Mapped[FileKind] = mapped_column(Enum(FileKind), default=FileKind.OTHER)
    model_kind: Mapped[ModelKind] = mapped_column(Enum(ModelKind), default=ModelKind.UNKNOWN)

    # Archive handling
    is_from_archive: Mapped[bool] = mapped_column(Boolean, default=False)
    archive_parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("design_files.id", ondelete="SET NULL"), nullable=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    design: Mapped[Design] = relationship("Design", back_populates="files")
    source_attachment: Mapped[Attachment | None] = relationship(
        "Attachment", back_populates="design_files"
    )
    archive_parent: Mapped[DesignFile | None] = relationship(
        "DesignFile", remote_side=[id], backref="extracted_files"
    )

    # Indexes
    __table_args__ = (
        Index("ix_design_files_design_id", "design_id"),
        Index("ix_design_files_sha256", "sha256"),
        Index("ix_design_files_ext_kind", "ext", "file_kind"),
    )
