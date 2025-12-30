"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PRINTARR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Printarr"
    version: str = "0.1.0"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = Field(default=3333, description="Server port (DEC-006)")

    # Paths - Container volume mounts
    config_path: Path = Field(
        default=Path("/config"),
        description="Path for configuration files and database",
    )
    data_path: Path = Field(
        default=Path("/data"),
        description="Path for temporary/staging data",
    )
    library_path: Path = Field(
        default=Path("/library"),
        description="Path for organized design library",
    )
    cache_path: Path = Field(
        default=Path("/cache"),
        description="Path for preview images and cache",
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./config/printarr.db",
        description="Database connection URL",
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins",
    )

    # Telegram MTProto (from https://my.telegram.org)
    telegram_api_id: Optional[int] = Field(
        default=None,
        description="Telegram API ID from my.telegram.org",
    )
    telegram_api_hash: Optional[str] = Field(
        default=None,
        description="Telegram API Hash from my.telegram.org",
    )

    @property
    def telegram_session_path(self) -> Path:
        """Get the Telegram session file path."""
        return self.config_path / "telegram.session"

    @property
    def telegram_configured(self) -> bool:
        """Check if Telegram API credentials are configured."""
        return self.telegram_api_id is not None and self.telegram_api_hash is not None

    @property
    def db_path(self) -> Path:
        """Get the SQLite database file path."""
        return self.config_path / "printarr.db"


# Global settings instance
settings = Settings()
