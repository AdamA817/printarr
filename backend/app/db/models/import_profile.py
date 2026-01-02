"""ImportProfile model for configurable folder structure parsing (v0.8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.import_source import ImportSource


class ImportProfile(Base):
    """Configurable profile for detecting designs within various folder structures.

    Profiles define how to detect designs, extract titles, find preview images,
    and which files/folders to ignore during import. Built-in presets cover common
    creator folder structures (Yosh Studios, Supported/Unsupported, etc.).

    See DEC-035 for full configuration schema.
    """

    __tablename__ = "import_profiles"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Profile metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Configuration stored as JSON (parsed from YAML in UI)
    # Schema defined in DEC-035
    config_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="JSON-serialized profile configuration"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    import_sources: Mapped[list[ImportSource]] = relationship(
        "ImportSource", back_populates="import_profile"
    )
