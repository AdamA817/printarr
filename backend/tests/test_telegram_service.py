"""Tests for the TelegramService."""

import pytest

from app.core.config import settings
from app.telegram import (
    TelegramNotConfiguredError,
    TelegramNotConnectedError,
    TelegramService,
    get_telegram_service,
)


@pytest.fixture(autouse=True)
def reset_telegram_service():
    """Reset the TelegramService singleton before and after each test."""
    TelegramService.reset_instance()
    yield
    TelegramService.reset_instance()


class TestTelegramServiceSingleton:
    """Tests for the singleton pattern."""

    def test_get_instance_returns_same_instance(self):
        """get_instance should return the same instance."""
        instance1 = TelegramService.get_instance()
        instance2 = TelegramService.get_instance()
        assert instance1 is instance2

    def test_get_telegram_service_returns_singleton(self):
        """get_telegram_service should return the singleton."""
        service = get_telegram_service()
        instance = TelegramService.get_instance()
        assert service is instance

    def test_reset_instance_clears_singleton(self):
        """reset_instance should clear the singleton."""
        instance1 = TelegramService.get_instance()
        TelegramService.reset_instance()
        instance2 = TelegramService.get_instance()
        assert instance1 is not instance2


class TestTelegramServiceUnconfigured:
    """Tests for when Telegram is not configured."""

    def test_is_connected_returns_false_initially(self):
        """is_connected should return False before connecting."""
        service = TelegramService.get_instance()
        assert service.is_connected() is False

    @pytest.mark.asyncio
    async def test_is_authenticated_returns_false_when_not_connected(self):
        """is_authenticated should return False when not connected."""
        service = TelegramService.get_instance()
        assert await service.is_authenticated() is False

    @pytest.mark.asyncio
    async def test_get_current_user_returns_none_when_not_connected(self):
        """get_current_user should return None when not connected."""
        service = TelegramService.get_instance()
        assert await service.get_current_user() is None

    @pytest.mark.asyncio
    async def test_connect_raises_not_configured_without_credentials(self):
        """connect should raise TelegramNotConfiguredError without credentials."""
        # Ensure credentials are not set
        assert settings.telegram_api_id is None
        assert settings.telegram_api_hash is None

        service = TelegramService.get_instance()
        with pytest.raises(TelegramNotConfiguredError) as exc_info:
            await service.connect()
        assert exc_info.value.code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_start_auth_raises_not_connected(self):
        """start_auth should raise TelegramNotConnectedError when not connected."""
        service = TelegramService.get_instance()
        with pytest.raises(TelegramNotConnectedError) as exc_info:
            await service.start_auth("+1234567890")
        assert exc_info.value.code == "NOT_CONNECTED"


class TestTelegramConfigCheck:
    """Tests for configuration checking."""

    def test_telegram_configured_false_without_credentials(self):
        """telegram_configured should be False without credentials."""
        assert settings.telegram_configured is False

    def test_telegram_session_path(self):
        """telegram_session_path should be in config directory."""
        path = settings.telegram_session_path
        assert path.name == "telegram.session"
        assert path.parent == settings.config_path
