"""Custom exceptions for Telegram integration."""

from __future__ import annotations


class TelegramError(Exception):
    """Base exception for Telegram-related errors."""

    def __init__(self, message: str, code: str = "TELEGRAM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class TelegramNotConfiguredError(TelegramError):
    """Raised when Telegram API credentials are not configured."""

    def __init__(self, message: str = "Telegram API credentials not configured"):
        super().__init__(message, "NOT_CONFIGURED")


class TelegramNotConnectedError(TelegramError):
    """Raised when attempting to use Telegram without an active connection."""

    def __init__(self, message: str = "Telegram client is not connected"):
        super().__init__(message, "NOT_CONNECTED")


class TelegramNotAuthenticatedError(TelegramError):
    """Raised when attempting an operation that requires authentication."""

    def __init__(self, message: str = "Telegram session is not authenticated"):
        super().__init__(message, "NOT_AUTHENTICATED")


class TelegramAuthenticationError(TelegramError):
    """Raised when authentication fails."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message, code)


class TelegramPhoneInvalidError(TelegramAuthenticationError):
    """Raised when phone number format is invalid."""

    def __init__(self, message: str = "Invalid phone number format"):
        super().__init__(message, "PHONE_INVALID")


class TelegramCodeInvalidError(TelegramAuthenticationError):
    """Raised when verification code is incorrect."""

    def __init__(self, message: str = "The verification code is incorrect"):
        super().__init__(message, "INVALID_CODE")


class TelegramCodeExpiredError(TelegramAuthenticationError):
    """Raised when verification code has expired."""

    def __init__(self, message: str = "The verification code has expired"):
        super().__init__(message, "CODE_EXPIRED")


class TelegramPasswordRequiredError(TelegramAuthenticationError):
    """Raised when 2FA password is required."""

    def __init__(self, message: str = "Two-factor authentication password required"):
        super().__init__(message, "2FA_REQUIRED")


class TelegramPasswordInvalidError(TelegramAuthenticationError):
    """Raised when 2FA password is incorrect."""

    def __init__(self, message: str = "Two-factor authentication password is incorrect"):
        super().__init__(message, "PASSWORD_INVALID")


class TelegramRateLimitError(TelegramError):
    """Raised when rate limited by Telegram."""

    def __init__(self, retry_after: int, message: str | None = None):
        self.retry_after = retry_after
        msg = message or f"Rate limited by Telegram. Retry after {retry_after} seconds"
        super().__init__(msg, "RATE_LIMITED")


class TelegramChannelNotFoundError(TelegramError):
    """Raised when a channel cannot be found."""

    def __init__(self, message: str = "Channel not found"):
        super().__init__(message, "CHANNEL_NOT_FOUND")


class TelegramAccessDeniedError(TelegramError):
    """Raised when access to a resource is denied."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, "ACCESS_DENIED")


class TelegramInvalidLinkError(TelegramError):
    """Raised when a channel/invite link format is invalid."""

    def __init__(self, message: str = "Invalid link format"):
        super().__init__(message, "INVALID_LINK")
