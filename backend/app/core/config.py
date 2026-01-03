"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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
    version: str = "0.8.0"
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
    staging_path: Path = Field(
        default=Path("/staging"),
        description="Path for staging downloaded files before import",
    )

    # Worker settings
    max_concurrent_downloads: int = Field(
        default=2,
        description="Maximum concurrent download workers",
    )

    # Sync settings (v0.6)
    sync_poll_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Interval in seconds for catch-up sync polling (60-3600, default 5 minutes)",
    )
    sync_enabled: bool = Field(
        default=True,
        description="Enable live monitoring service",
    )
    sync_batch_size: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Maximum messages to process per sync batch (10-500)",
    )

    # Library settings
    library_template_global: str = Field(
        default="{designer}/{channel}/{title}",
        description="Global template for library folder structure",
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
    telegram_api_id: int | None = Field(
        default=None,
        description="Telegram API ID from my.telegram.org",
    )
    telegram_api_hash: str | None = Field(
        default=None,
        description="Telegram API Hash from my.telegram.org",
    )

    # FlareSolverr (optional, for bypassing Cloudflare on Thangs)
    flaresolverr_url: str | None = Field(
        default=None,
        description="FlareSolverr URL (e.g., http://flaresolverr:8191/v1)",
    )

    # Google Drive OAuth (v0.8 - for private folder access)
    google_client_id: str | None = Field(
        default=None,
        description="Google OAuth Client ID from Google Cloud Console",
    )
    google_client_secret: str | None = Field(
        default=None,
        description="Google OAuth Client Secret from Google Cloud Console",
    )
    google_api_key: str | None = Field(
        default=None,
        description="Google API Key for public folder access (no OAuth)",
    )
    google_redirect_uri: str = Field(
        default="http://localhost:3333/api/v1/google/oauth/callback",
        description="OAuth redirect URI",
    )

    # Google API rate limiting settings
    google_request_delay: float = Field(
        default=0.5,
        ge=0.0,
        le=10.0,
        description="Delay in seconds between Google API requests (0.5-10)",
    )
    google_requests_per_minute: int = Field(
        default=60,
        ge=10,
        le=1000,
        description="Maximum Google API requests per minute (10-1000)",
    )

    # Encryption key for storing OAuth tokens (auto-generated if not set)
    encryption_key: str | None = Field(
        default=None,
        description="Fernet encryption key for storing sensitive data",
    )

    # File upload settings (v0.8)
    upload_max_size_mb: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum upload size in MB",
    )
    upload_allowed_extensions: list[str] = Field(
        default=[".stl", ".3mf", ".obj", ".step", ".zip", ".rar", ".7z"],
        description="Allowed file extensions for upload",
    )
    upload_retention_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours to retain unprocessed uploads before cleanup",
    )

    # Auto-render settings (v0.8)
    auto_queue_render_after_import: bool = Field(
        default=True,
        description="Automatically queue preview render jobs after design import",
    )
    auto_queue_render_priority: int = Field(
        default=-1,
        ge=-10,
        le=10,
        description="Priority for auto-queued render jobs (-10 to 10, negative = background)",
    )

    @property
    def upload_staging_path(self) -> Path:
        """Get the upload staging directory path."""
        return self.data_path / "uploads"

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

    @property
    def google_oauth_configured(self) -> bool:
        """Check if Google OAuth credentials are configured."""
        return self.google_client_id is not None and self.google_client_secret is not None

    @property
    def google_api_configured(self) -> bool:
        """Check if Google API key is configured (for public folders)."""
        return self.google_api_key is not None


# Global settings instance
settings = Settings()
