"""Telegram integration module for MTProto communication."""

from app.telegram.exceptions import (
    TelegramAccessDeniedError,
    TelegramAuthenticationError,
    TelegramChannelNotFoundError,
    TelegramCodeExpiredError,
    TelegramCodeInvalidError,
    TelegramError,
    TelegramInvalidLinkError,
    TelegramNotAuthenticatedError,
    TelegramNotConfiguredError,
    TelegramNotConnectedError,
    TelegramPasswordInvalidError,
    TelegramPasswordRequiredError,
    TelegramPhoneInvalidError,
    TelegramRateLimitError,
)
from app.telegram.service import TelegramService, get_telegram_service

__all__ = [
    # Service
    "TelegramService",
    "get_telegram_service",
    # Exceptions
    "TelegramError",
    "TelegramNotConfiguredError",
    "TelegramNotConnectedError",
    "TelegramNotAuthenticatedError",
    "TelegramAuthenticationError",
    "TelegramPhoneInvalidError",
    "TelegramCodeInvalidError",
    "TelegramCodeExpiredError",
    "TelegramPasswordRequiredError",
    "TelegramPasswordInvalidError",
    "TelegramRateLimitError",
    "TelegramChannelNotFoundError",
    "TelegramAccessDeniedError",
    "TelegramInvalidLinkError",
]
