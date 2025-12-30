"""Tests for database models."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Channel,
    BackfillMode,
    DownloadMode,
)


@pytest.fixture
async def db_session():
    """Create an in-memory test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_channel(db_session: AsyncSession) -> None:
    """Test creating a channel."""
    channel = Channel(
        telegram_peer_id="123456789",
        title="Test Channel",
        username="testchannel",
        is_private=False,
        is_enabled=True,
        backfill_mode=BackfillMode.LAST_N_MESSAGES,
        backfill_value=100,
        download_mode=DownloadMode.MANUAL,
    )

    db_session.add(channel)
    await db_session.commit()

    # Query the channel back
    result = await db_session.execute(
        select(Channel).where(Channel.telegram_peer_id == "123456789")
    )
    retrieved = result.scalar_one()

    assert retrieved.title == "Test Channel"
    assert retrieved.username == "testchannel"
    assert retrieved.backfill_mode == BackfillMode.LAST_N_MESSAGES
    assert retrieved.download_mode == DownloadMode.MANUAL
    assert retrieved.id is not None


@pytest.mark.asyncio
async def test_channel_defaults(db_session: AsyncSession) -> None:
    """Test channel default values."""
    channel = Channel(
        telegram_peer_id="987654321",
        title="Minimal Channel",
    )

    db_session.add(channel)
    await db_session.commit()

    result = await db_session.execute(
        select(Channel).where(Channel.telegram_peer_id == "987654321")
    )
    retrieved = result.scalar_one()

    assert retrieved.is_private is False
    assert retrieved.is_enabled is True
    assert retrieved.backfill_mode == BackfillMode.LAST_N_MESSAGES
    assert retrieved.backfill_value == 100
    assert retrieved.download_mode == DownloadMode.MANUAL
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None
