"""PhpbbCredentials model for phpBB forum authentication (v1.0).

Stores encrypted username/password and session cookies for phpBB forum access.
Used by PHPBB_FORUM import sources for sites like Hex3D Patreon.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.import_source import ImportSource


class PhpbbCredentials(Base):
    """Stores credentials for phpBB forum authentication.

    Username and password are stored encrypted using Fernet.
    Session cookies are cached to avoid re-login on every sync.

    See issue #239 for phpBB integration design.
    """

    __tablename__ = "phpbb_credentials"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Forum identification
    base_url: Mapped[str] = mapped_column(
        String(512), nullable=False, doc="Base URL of the phpBB forum (e.g., https://hex3dpatreon.com)"
    )

    # Encrypted credentials (use app.core.security for encryption)
    username_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Encrypted username"
    )
    password_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Encrypted password"
    )

    # Cached session (to avoid re-login on every sync)
    session_cookies_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Encrypted session cookies JSON"
    )
    session_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When the cached session expires"
    )

    # Last successful login
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Last successful login time"
    )
    last_login_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Last login error message if failed"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    import_sources: Mapped[list[ImportSource]] = relationship(
        "ImportSource", back_populates="phpbb_credentials"
    )
