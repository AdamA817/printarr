"""Pydantic schemas for Telegram API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# === Auth Request Schemas ===


class AuthStartRequest(BaseModel):
    """Request to start Telegram authentication."""

    phone: str = Field(
        ...,
        min_length=5,
        max_length=20,
        description="Phone number in international format (e.g., +1234567890)",
        examples=["+1234567890"],
    )


class AuthVerifyRequest(BaseModel):
    """Request to verify authentication code."""

    phone: str = Field(..., description="Phone number used in start request")
    code: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Verification code received via SMS/Telegram",
    )
    phone_code_hash: str = Field(..., description="Hash returned from start request")
    password: str | None = Field(
        None, description="2FA password if required"
    )


# === Auth Response Schemas ===


class AuthStartResponse(BaseModel):
    """Response after starting authentication."""

    status: str = Field(..., description="Status: 'code_required'")
    phone_code_hash: str = Field(..., description="Hash to use in verify request")


class AuthVerifyResponse(BaseModel):
    """Response after verifying code."""

    status: str = Field(..., description="Status: 'authenticated' or '2fa_required'")


class TelegramUser(BaseModel):
    """Telegram user information."""

    id: int = Field(..., description="Telegram user ID")
    username: str | None = Field(None, description="Telegram username")
    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    phone: str | None = Field(None, description="Phone number")


class AuthStatusResponse(BaseModel):
    """Response with current authentication status."""

    authenticated: bool = Field(..., description="Whether the session is authenticated")
    configured: bool = Field(..., description="Whether API credentials are configured")
    connected: bool = Field(..., description="Whether connected to Telegram")
    user: TelegramUser | None = Field(None, description="Current user if authenticated")


class AuthLogoutResponse(BaseModel):
    """Response after logout."""

    status: str = Field(default="logged_out", description="Status: 'logged_out'")


# === Error Response Schemas ===


class TelegramErrorResponse(BaseModel):
    """Error response for Telegram operations."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    retry_after: int | None = Field(
        None, description="Seconds to wait before retrying (for rate limits)"
    )
