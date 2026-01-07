"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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
    version: str = "1.0.0"
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

    # Database (PostgreSQL embedded in container per DEC-039)
    database_url: str = Field(
        default="postgresql+asyncpg://printarr:printarr@localhost:5432/printarr",
        description="PostgreSQL connection URL",
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

    @field_validator("telegram_api_id", mode="before")
    @classmethod
    def empty_string_to_none_int(cls, v: str | int | None) -> int | None:
        """Convert empty strings to None for optional int fields."""
        if v == "" or v is None:
            return None
        return int(v)

    @field_validator(
        "telegram_api_hash",
        "flaresolverr_url",
        "google_client_id",
        "google_client_secret",
        "google_api_key",
        "encryption_key",
        "ai_api_key",
        mode="before",
    )
    @classmethod
    def empty_string_to_none_str(cls, v: str | None) -> str | None:
        """Convert empty strings to None for optional str fields."""
        if v == "" or v is None:
            return None
        return v

    # Telegram rate limiting (DEC-042)
    telegram_rate_limit_rpm: int = Field(
        default=30,
        ge=10,
        le=100,
        description="Maximum Telegram requests per minute (10-100, default 30)",
    )
    telegram_channel_spacing: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Minimum seconds between requests to the same channel (0.5-10)",
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
        default="http://localhost:3333/oauth/google/callback",
        description="OAuth redirect URI (must match Google Cloud Console)",
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
    google_max_concurrent_downloads: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum concurrent Google Drive file downloads (1-10)",
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

    # phpBB Forum settings (v1.0 - issue #239)
    phpbb_request_delay: float = Field(
        default=1.0,
        ge=0.5,
        le=10.0,
        description="Delay in seconds between phpBB requests to avoid rate limiting (0.5-10)",
    )
    phpbb_max_concurrent_downloads: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent downloads from phpBB forums (1-10)",
    )
    phpbb_session_timeout_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours before phpBB session cookies expire and re-login is required (1-168)",
    )

    # AI Analysis settings (v1.0 - DEC-043)
    ai_enabled: bool = Field(
        default=False,
        description="Enable AI analysis features (requires ai_api_key)",
    )
    ai_api_key: str | None = Field(
        default=None,
        description="Google AI API key for Gemini",
    )
    ai_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model (gemini-1.5-flash, gemini-1.5-pro, gemini-2.0-flash)",
    )
    ai_auto_analyze_on_import: bool = Field(
        default=True,
        description="Automatically analyze new designs after import",
    )
    ai_select_best_preview: bool = Field(
        default=True,
        description="Let AI select the best preview image",
    )
    ai_rate_limit_rpm: int = Field(
        default=15,
        ge=5,
        le=60,
        description="AI requests per minute (5-60, default 15)",
    )
    ai_max_tags_per_design: int = Field(
        default=20,
        ge=1,
        le=30,
        description="Maximum AI-generated tags per design (1-30)",
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
    def google_oauth_configured(self) -> bool:
        """Check if Google OAuth credentials are configured."""
        return self.google_client_id is not None and self.google_client_secret is not None

    @property
    def google_api_configured(self) -> bool:
        """Check if Google API key is configured (for public folders)."""
        return self.google_api_key is not None

    @property
    def ai_configured(self) -> bool:
        """Check if AI analysis is enabled and configured."""
        return self.ai_enabled and self.ai_api_key is not None


# Global settings instance
settings = Settings()
