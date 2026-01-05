"""GoogleCredentials model for OAuth token storage (v0.8)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.import_source import ImportSource


class GoogleCredentials(Base):
    """Stores OAuth tokens for authenticated Google Drive access.

    Tokens are stored encrypted. Public Google Drive links don't require
    credentials - this is only needed for private/restricted folders.

    See DEC-034 for OAuth flow details.
    """

    __tablename__ = "google_credentials"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Google account info
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Encrypted tokens (use app.core.security for encryption)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Token expiration
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    import_sources: Mapped[list[ImportSource]] = relationship(
        "ImportSource", back_populates="google_credentials"
    )
