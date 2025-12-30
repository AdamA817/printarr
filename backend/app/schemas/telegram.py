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


# === Channel Resolution Schemas ===


class ChannelResolveRequest(BaseModel):
    """Request to resolve a channel link."""

    link: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Channel link in various formats",
        examples=[
            "https://t.me/channelname",
            "t.me/channelname",
            "@channelname",
            "https://t.me/+abcdef",
        ],
    )


class ChannelResolveResponse(BaseModel):
    """Response with resolved channel information."""

    id: int | None = Field(
        ..., description="Telegram channel ID (None for unjoined invite links)"
    )
    title: str = Field(..., description="Channel title")
    username: str | None = Field(None, description="Channel username (if public)")
    type: str = Field(
        ..., description="Channel type: 'channel', 'supergroup', or 'group'"
    )
    members_count: int | None = Field(None, description="Member count (if available)")
    photo_url: str | None = Field(None, description="Channel photo URL (if available)")
    is_invite: bool = Field(
        default=False, description="True if resolved from invite link without joining"
    )
    invite_hash: str | None = Field(
        None, description="Invite hash for private channels"
    )


# === Message Schemas ===


class MessageSender(BaseModel):
    """Sender information for a message."""

    id: int | None = Field(None, description="Sender ID")
    name: str = Field(..., description="Sender display name")
    username: str | None = Field(None, description="Sender username")


class MessageAttachment(BaseModel):
    """Attachment information for a message."""

    type: str = Field(
        ..., description="Attachment type: 'photo', 'document', 'video', 'audio'"
    )
    filename: str | None = Field(None, description="Filename if available")
    size: int | None = Field(None, description="File size in bytes")
    mime_type: str | None = Field(None, description="MIME type")


class Message(BaseModel):
    """A Telegram message."""

    id: int = Field(..., description="Message ID")
    date: str | None = Field(None, description="Message date in ISO format")
    text: str = Field(default="", description="Message text content")
    sender: MessageSender | None = Field(None, description="Message sender")
    attachments: list[MessageAttachment] = Field(
        default_factory=list, description="Message attachments"
    )
    has_media: bool = Field(default=False, description="Whether message has media")
    forward_from: str | None = Field(
        None, description="Original source if forwarded"
    )


class ChannelInfo(BaseModel):
    """Basic channel information."""

    id: int = Field(..., description="Channel ID")
    title: str = Field(..., description="Channel title")


class MessagesResponse(BaseModel):
    """Response with channel messages."""

    messages: list[Message] = Field(..., description="List of messages")
    channel: ChannelInfo = Field(..., description="Channel information")


# === Error Response Schemas ===


class TelegramErrorResponse(BaseModel):
    """Error response for Telegram operations."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    retry_after: int | None = Field(
        None, description="Seconds to wait before retrying (for rate limits)"
    )
