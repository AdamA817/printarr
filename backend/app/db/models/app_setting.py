"""Application settings model for configurable preferences."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSetting(Base):
    """Stores application settings as key-value pairs.

    Values are stored as JSON-encoded text to support different types
    (strings, numbers, booleans, objects).
    """

    __tablename__ = "app_settings"

    # Primary key - the setting key
    key: Mapped[str] = mapped_column(String(64), primary_key=True)

    # JSON-encoded value
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
