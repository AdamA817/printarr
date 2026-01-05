"""Telegram rate limiting and flood wait handling (DEC-042).

Provides proactive rate limiting using token bucket algorithm and
proper FloodWaitError handling for Telegram API calls.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

from telethon.errors import FloodWaitError

from app.core.config import settings
from app.core.logging import get_logger
from app.telegram.exceptions import TelegramRateLimitError

logger = get_logger(__name__)

T = TypeVar("T")


class TelegramRateLimiter:
    """Rate limiter for Telegram API calls using token bucket algorithm.

    Features:
    - Global rate limiting (configurable RPM)
    - Per-channel request spacing
    - FloodWaitError handling with per-channel backoff
    - Thread-safe for concurrent workers

    Usage:
        rate_limiter = TelegramRateLimiter.get_instance()
        await rate_limiter.acquire(channel_id=12345)
        # make telegram call
    """

    _instance: TelegramRateLimiter | None = None
    _lock: asyncio.Lock | None = None

    def __init__(
        self,
        rpm: int | None = None,
        channel_spacing: float | None = None,
    ):
        """Initialize the rate limiter.

        Args:
            rpm: Requests per minute limit (default from settings).
            channel_spacing: Minimum seconds between same-channel requests.
        """
        self.rpm = rpm or settings.telegram_rate_limit_rpm
        self.channel_spacing = channel_spacing or settings.telegram_channel_spacing

        # Token bucket state
        self.tokens = float(self.rpm)
        self.max_tokens = float(self.rpm)
        self.last_refill = time.monotonic()
        self._token_lock = asyncio.Lock()

        # Per-channel tracking
        self.channel_backoff: dict[int, datetime] = {}  # FloodWait backoffs
        self.channel_last_request: dict[int, float] = defaultdict(float)  # Last request time
        self._channel_lock = asyncio.Lock()

        # Metrics
        self._requests_total = 0
        self._throttled_count = 0
        self._flood_wait_count = 0

        logger.info(
            "rate_limiter_initialized",
            rpm=self.rpm,
            channel_spacing=self.channel_spacing,
        )

    @classmethod
    async def get_instance(cls) -> TelegramRateLimiter:
        """Get the singleton rate limiter instance."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._instance is None:
                cls._instance = TelegramRateLimiter()
            return cls._instance

    async def acquire(self, channel_id: int | None = None) -> None:
        """Acquire permission to make a Telegram API call.

        Blocks until a token is available and channel-specific limits are met.

        Args:
            channel_id: Optional channel ID for per-channel limiting.

        Raises:
            TelegramRateLimitError: If channel is in FloodWait backoff.
        """
        # Check channel-specific FloodWait backoff
        if channel_id:
            async with self._channel_lock:
                if channel_id in self.channel_backoff:
                    backoff_until = self.channel_backoff[channel_id]
                    if datetime.now(timezone.utc) < backoff_until:
                        wait_seconds = int((backoff_until - datetime.now(timezone.utc)).total_seconds())
                        logger.warning(
                            "channel_in_backoff",
                            channel_id=channel_id,
                            wait_seconds=wait_seconds,
                        )
                        raise TelegramRateLimitError(
                            retry_after=wait_seconds,
                            message=f"Channel {channel_id} is in FloodWait backoff for {wait_seconds}s",
                        )
                    else:
                        # Backoff expired, remove it
                        del self.channel_backoff[channel_id]

        # Wait for channel spacing
        if channel_id:
            await self._wait_for_channel_spacing(channel_id)

        # Wait for global token
        await self._wait_for_token()

        self._requests_total += 1

    async def _wait_for_token(self) -> None:
        """Wait until a token is available (token bucket algorithm)."""
        async with self._token_lock:
            # Refill tokens based on time elapsed
            now = time.monotonic()
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * (self.rpm / 60.0)  # Tokens per second
            self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
            self.last_refill = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60.0 / self.rpm)
                self._throttled_count += 1
                logger.debug(
                    "rate_limiter_throttling",
                    wait_time=wait_time,
                    tokens=self.tokens,
                )
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

    async def _wait_for_channel_spacing(self, channel_id: int) -> None:
        """Ensure minimum time between requests to the same channel."""
        async with self._channel_lock:
            last_request = self.channel_last_request[channel_id]
            now = time.monotonic()
            elapsed = now - last_request

            if elapsed < self.channel_spacing:
                wait_time = self.channel_spacing - elapsed
                logger.debug(
                    "channel_spacing_wait",
                    channel_id=channel_id,
                    wait_time=wait_time,
                )
                await asyncio.sleep(wait_time)

            self.channel_last_request[channel_id] = time.monotonic()

    def handle_flood_wait(
        self, error: FloodWaitError, channel_id: int | None = None
    ) -> None:
        """Handle a FloodWaitError by setting channel backoff.

        Args:
            error: The FloodWaitError from Telethon.
            channel_id: The channel ID that triggered the error.
        """
        wait_seconds = error.seconds
        self._flood_wait_count += 1

        logger.warning(
            "flood_wait_error",
            channel_id=channel_id,
            wait_seconds=wait_seconds,
        )

        if channel_id:
            # Set per-channel backoff
            from datetime import timedelta
            backoff_until = datetime.now(timezone.utc) + timedelta(seconds=wait_seconds)
            self.channel_backoff[channel_id] = backoff_until

            logger.info(
                "channel_backoff_set",
                channel_id=channel_id,
                backoff_until=backoff_until.isoformat(),
            )

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary with rate limiter stats.
        """
        return {
            "rpm_limit": self.rpm,
            "tokens_available": self.tokens,
            "requests_total": self._requests_total,
            "throttled_count": self._throttled_count,
            "flood_wait_count": self._flood_wait_count,
            "channels_in_backoff": len(self.channel_backoff),
            "backoff_channels": list(self.channel_backoff.keys()),
        }


def rate_limited(channel_id_arg: str | None = None) -> Callable:
    """Decorator to apply rate limiting to a function.

    Args:
        channel_id_arg: Name of the argument containing the channel ID.

    Usage:
        @rate_limited(channel_id_arg="channel_id")
        async def get_messages(channel_id: int, ...):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Get rate limiter instance
            rate_limiter = await TelegramRateLimiter.get_instance()

            # Extract channel_id from arguments if specified
            channel_id = None
            if channel_id_arg:
                channel_id = kwargs.get(channel_id_arg)
                if channel_id is None and args:
                    # Try to find it in positional args by function signature
                    import inspect
                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if channel_id_arg in params:
                        idx = params.index(channel_id_arg)
                        if idx < len(args):
                            channel_id = args[idx]

            # Acquire rate limit
            await rate_limiter.acquire(channel_id=channel_id)

            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                rate_limiter.handle_flood_wait(e, channel_id)
                raise TelegramRateLimitError(
                    retry_after=e.seconds,
                    message=f"FloodWait: {e.seconds}s",
                )

        return wrapper

    return decorator
