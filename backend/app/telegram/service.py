"""Telegram service for MTProto communication using Telethon."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from telethon import TelegramClient
from telethon.errors import (
    AuthKeyError,
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.telegram.exceptions import (
    TelegramCodeExpiredError,
    TelegramCodeInvalidError,
    TelegramNotAuthenticatedError,
    TelegramNotConfiguredError,
    TelegramNotConnectedError,
    TelegramPasswordInvalidError,
    TelegramPasswordRequiredError,
    TelegramPhoneInvalidError,
    TelegramRateLimitError,
)

if TYPE_CHECKING:
    from telethon.types import User

logger = get_logger(__name__)


class TelegramService:
    """Singleton service managing the Telethon MTProto client.

    This service handles:
    - Client connection and disconnection
    - Session persistence across restarts
    - Authentication state tracking

    Usage:
        telegram = TelegramService.get_instance()
        await telegram.connect()

        if await telegram.is_authenticated():
            # Ready to use
            ...
    """

    _instance: TelegramService | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the Telegram service.

        Note: Use TelegramService.get_instance() instead of direct instantiation.
        """
        self._client: TelegramClient | None = None
        self._connected: bool = False
        self._phone_code_hash: str | None = None
        self._pending_phone: str | None = None

    @classmethod
    def get_instance(cls) -> TelegramService:
        """Get the singleton instance of TelegramService.

        Returns:
            The singleton TelegramService instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        cls._instance = None

    def _ensure_configured(self) -> None:
        """Ensure Telegram API credentials are configured.

        Raises:
            TelegramNotConfiguredError: If credentials are not set.
        """
        if not settings.telegram_configured:
            raise TelegramNotConfiguredError(
                "Telegram API credentials not configured. "
                "Set PRINTARR_TELEGRAM_API_ID and PRINTARR_TELEGRAM_API_HASH environment variables."
            )

    def _ensure_connected(self) -> None:
        """Ensure the client is connected.

        Raises:
            TelegramNotConnectedError: If the client is not connected.
        """
        if not self._connected or self._client is None:
            raise TelegramNotConnectedError()

    async def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated.

        Raises:
            TelegramNotConnectedError: If the client is not connected.
            TelegramNotAuthenticatedError: If the session is not authenticated.
        """
        self._ensure_connected()
        if not await self.is_authenticated():
            raise TelegramNotAuthenticatedError()

    def _get_client(self) -> TelegramClient:
        """Get or create the Telethon client.

        Returns:
            The Telethon client instance.

        Raises:
            TelegramNotConfiguredError: If credentials are not set.
        """
        self._ensure_configured()

        if self._client is None:
            session_path = str(settings.telegram_session_path)
            self._client = TelegramClient(
                session_path,
                settings.telegram_api_id,
                settings.telegram_api_hash,
            )
            logger.info(
                "telegram_client_created",
                session_path=session_path,
            )

        return self._client

    async def connect(self) -> dict:
        """Connect to Telegram.

        This establishes the network connection but does not authenticate.
        If a valid session exists, the client will be authenticated automatically.

        Returns:
            Status dict with 'status' key ('connected' or 'needs_auth').

        Raises:
            TelegramNotConfiguredError: If credentials are not set.
            TelegramRateLimitError: If rate limited by Telegram.
        """
        async with self._lock:
            self._ensure_configured()

            client = self._get_client()

            try:
                await client.connect()
                self._connected = True

                if await client.is_user_authorized():
                    user = await client.get_me()
                    logger.info(
                        "telegram_connected_authenticated",
                        user_id=user.id if user else None,
                        username=user.username if user else None,
                    )
                    return {"status": "connected", "authenticated": True}
                else:
                    logger.info("telegram_connected_not_authenticated")
                    return {"status": "connected", "authenticated": False}

            except AuthKeyError:
                # Session is invalid, need to re-authenticate
                logger.warning("telegram_session_invalid")
                self._connected = True
                return {"status": "connected", "authenticated": False}

            except FloodWaitError as e:
                logger.warning("telegram_rate_limited", retry_after=e.seconds)
                raise TelegramRateLimitError(e.seconds)

    async def disconnect(self) -> None:
        """Disconnect from Telegram and clean up resources."""
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.disconnect()
                except Exception as e:
                    logger.warning("telegram_disconnect_error", error=str(e))
                finally:
                    self._connected = False
                    logger.info("telegram_disconnected")

    def is_connected(self) -> bool:
        """Check if the client is connected.

        Returns:
            True if connected, False otherwise.
        """
        return self._connected and self._client is not None

    async def is_authenticated(self) -> bool:
        """Check if the session is authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        if not self.is_connected() or self._client is None:
            return False

        try:
            return await self._client.is_user_authorized()
        except Exception:
            return False

    async def get_current_user(self) -> User | None:
        """Get the currently authenticated user.

        Returns:
            The authenticated User object, or None if not authenticated.
        """
        if not self.is_connected() or self._client is None:
            return None

        try:
            if await self._client.is_user_authorized():
                return await self._client.get_me()
        except Exception as e:
            logger.warning("telegram_get_user_error", error=str(e))

        return None

    async def start_auth(self, phone: str) -> dict:
        """Start the authentication process by sending a verification code.

        Args:
            phone: Phone number in international format (e.g., +1234567890).

        Returns:
            Dict with 'status' and 'phone_code_hash' keys.

        Raises:
            TelegramNotConnectedError: If the client is not connected.
            TelegramPhoneInvalidError: If the phone number is invalid.
            TelegramRateLimitError: If rate limited by Telegram.
        """
        self._ensure_connected()
        assert self._client is not None

        try:
            result = await self._client.send_code_request(phone)
            self._phone_code_hash = result.phone_code_hash
            self._pending_phone = phone

            logger.info("telegram_code_sent", phone=phone[:4] + "****")
            return {
                "status": "code_required",
                "phone_code_hash": result.phone_code_hash,
            }

        except PhoneNumberInvalidError:
            logger.warning("telegram_phone_invalid", phone=phone[:4] + "****")
            raise TelegramPhoneInvalidError()

        except FloodWaitError as e:
            logger.warning("telegram_rate_limited", retry_after=e.seconds)
            raise TelegramRateLimitError(e.seconds)

    async def complete_auth(
        self,
        phone: str,
        code: str,
        phone_code_hash: str,
        password: str | None = None,
    ) -> dict:
        """Complete authentication with the verification code.

        Args:
            phone: Phone number used in start_auth.
            code: Verification code received via SMS/Telegram.
            phone_code_hash: Hash returned from start_auth.
            password: 2FA password if required.

        Returns:
            Dict with 'status' key ('authenticated' or '2fa_required').

        Raises:
            TelegramNotConnectedError: If the client is not connected.
            TelegramCodeInvalidError: If the code is wrong.
            TelegramCodeExpiredError: If the code has expired.
            TelegramPasswordRequiredError: If 2FA is needed.
            TelegramPasswordInvalidError: If 2FA password is wrong.
            TelegramRateLimitError: If rate limited by Telegram.
        """
        self._ensure_connected()
        assert self._client is not None

        try:
            await self._client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash,
            )

            # Clear pending auth state
            self._phone_code_hash = None
            self._pending_phone = None

            user = await self._client.get_me()
            logger.info(
                "telegram_authenticated",
                user_id=user.id if user else None,
                username=user.username if user else None,
            )
            return {"status": "authenticated"}

        except SessionPasswordNeededError:
            if password:
                # Try to complete 2FA
                try:
                    await self._client.sign_in(password=password)

                    # Clear pending auth state
                    self._phone_code_hash = None
                    self._pending_phone = None

                    user = await self._client.get_me()
                    logger.info(
                        "telegram_authenticated_2fa",
                        user_id=user.id if user else None,
                        username=user.username if user else None,
                    )
                    return {"status": "authenticated"}
                except Exception as e:
                    if "password" in str(e).lower():
                        logger.warning("telegram_2fa_password_invalid")
                        raise TelegramPasswordInvalidError()
                    raise
            else:
                logger.info("telegram_2fa_required")
                raise TelegramPasswordRequiredError()

        except PhoneCodeInvalidError:
            logger.warning("telegram_code_invalid")
            raise TelegramCodeInvalidError()

        except PhoneCodeExpiredError:
            logger.warning("telegram_code_expired")
            raise TelegramCodeExpiredError()

        except FloodWaitError as e:
            logger.warning("telegram_rate_limited", retry_after=e.seconds)
            raise TelegramRateLimitError(e.seconds)

    async def logout(self) -> dict:
        """Log out and clear the session.

        Returns:
            Dict with 'status' key.
        """
        if self._client is not None and self.is_connected():
            try:
                await self._client.log_out()
                logger.info("telegram_logged_out")
            except Exception as e:
                logger.warning("telegram_logout_error", error=str(e))

        # Clear state
        self._phone_code_hash = None
        self._pending_phone = None

        return {"status": "logged_out"}

    @property
    def client(self) -> TelegramClient:
        """Get the underlying Telethon client.

        This is exposed for advanced operations not covered by the service.
        Use with caution.

        Returns:
            The Telethon client.

        Raises:
            TelegramNotConnectedError: If the client is not connected.
        """
        self._ensure_connected()
        assert self._client is not None
        return self._client


# Convenience function for dependency injection
def get_telegram_service() -> TelegramService:
    """Get the TelegramService singleton instance.

    This is intended for use as a FastAPI dependency.

    Returns:
        The TelegramService singleton.
    """
    return TelegramService.get_instance()
