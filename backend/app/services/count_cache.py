"""Count cache service for optimizing list endpoint pagination (#219).

Provides caching and approximate counts to improve performance
of paginated list endpoints.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


class CountCache:
    """In-memory cache for table counts.

    Caches both approximate and exact counts with TTL.
    Uses PostgreSQL's pg_stat_user_tables for fast approximate counts
    on unfiltered queries.
    """

    _instance: "CountCache | None" = None

    # Cache: {cache_key: (count, timestamp)}
    _cache: dict[str, tuple[int, float]] = {}

    # TTL in seconds
    APPROXIMATE_TTL = 30.0  # Short TTL for approximate counts
    EXACT_TTL = 5.0  # Very short TTL for exact counts

    def __new__(cls) -> "CountCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get(self, key: str) -> int | None:
        """Get a cached count if not expired.

        Args:
            key: Cache key

        Returns:
            Cached count or None if expired/missing
        """
        if key in self._cache:
            count, timestamp = self._cache[key]
            ttl = self.APPROXIMATE_TTL if key.startswith("approx:") else self.EXACT_TTL
            if time.time() - timestamp < ttl:
                return count
            del self._cache[key]
        return None

    def set(self, key: str, count: int) -> None:
        """Set a count in the cache.

        Args:
            key: Cache key
            count: Count value
        """
        self._cache[key] = (count, time.time())

    def invalidate(self, table: str) -> None:
        """Invalidate all cached counts for a table.

        Args:
            table: Table name
        """
        keys_to_delete = [k for k in self._cache if table in k]
        for k in keys_to_delete:
            del self._cache[k]

    def clear(self) -> None:
        """Clear all cached counts."""
        self._cache.clear()


# Global instance
count_cache = CountCache()


async def get_approximate_count(db: AsyncSession, table: str) -> int | None:
    """Get approximate row count using PostgreSQL statistics.

    This is much faster than COUNT(*) for large tables.
    Uses pg_stat_user_tables which PostgreSQL maintains automatically.

    Args:
        db: Database session
        table: Table name

    Returns:
        Approximate count or None if unavailable
    """
    cache_key = f"approx:{table}"
    cached = count_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        result = await db.execute(
            text("""
                SELECT n_live_tup::bigint
                FROM pg_stat_user_tables
                WHERE relname = :table
            """),
            {"table": table},
        )
        row = result.fetchone()
        if row and row[0] is not None:
            count = int(row[0])
            count_cache.set(cache_key, count)
            logger.debug("approximate_count", table=table, count=count)
            return count
    except Exception as e:
        logger.warning("approximate_count_failed", table=table, error=str(e))

    return None


async def get_optimized_count(
    db: AsyncSession,
    table: str,
    filters: dict[str, Any] | None = None,
    exact_threshold: int = 10000,
) -> tuple[int, bool]:
    """Get optimized count with fallback logic (#219).

    Strategy:
    1. If no filters, use approximate count from pg_stat
    2. If approximate count < threshold, compute exact count
    3. Cache results for subsequent requests

    Args:
        db: Database session
        table: Table name
        filters: Dictionary of filters applied (for cache key)
        exact_threshold: Use approximate count if table has more rows than this

    Returns:
        Tuple of (count, is_approximate)
    """
    # For unfiltered queries, try approximate count first
    if not filters:
        approx = await get_approximate_count(db, table)
        if approx is not None and approx > exact_threshold:
            return (approx, True)

    # Need exact count - check cache
    filter_key = str(sorted(filters.items())) if filters else "none"
    cache_key = f"exact:{table}:{filter_key}"

    cached = count_cache.get(cache_key)
    if cached is not None:
        return (cached, False)

    # Compute exact count (this happens in the caller's query)
    # Return None to indicate caller should compute
    return (-1, False)


def invalidate_table_counts(table: str) -> None:
    """Invalidate cached counts for a table.

    Call this when rows are inserted/deleted.

    Args:
        table: Table name
    """
    count_cache.invalidate(table)
