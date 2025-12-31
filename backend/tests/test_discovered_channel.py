"""Tests for DiscoveredChannel model."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import DiscoveredChannel, DiscoverySourceType


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
async def test_create_discovered_channel(db_session: AsyncSession) -> None:
    """Test creating a discovered channel with all fields."""
    channel = DiscoveredChannel(
        telegram_peer_id="123456789",
        title="Test Channel",
        username="testchannel",
        is_private=False,
        reference_count=5,
        source_types=[DiscoverySourceType.FORWARD.value, DiscoverySourceType.MENTION.value],
    )

    db_session.add(channel)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.telegram_peer_id == "123456789")
    )
    retrieved = result.scalar_one()

    assert retrieved.title == "Test Channel"
    assert retrieved.username == "testchannel"
    assert retrieved.telegram_peer_id == "123456789"
    assert retrieved.is_private is False
    assert retrieved.reference_count == 5
    assert DiscoverySourceType.FORWARD.value in retrieved.source_types
    assert DiscoverySourceType.MENTION.value in retrieved.source_types
    assert retrieved.id is not None


@pytest.mark.asyncio
async def test_discovered_channel_defaults(db_session: AsyncSession) -> None:
    """Test discovered channel default values."""
    channel = DiscoveredChannel(
        username="minimalchannel",
    )

    db_session.add(channel)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.username == "minimalchannel")
    )
    retrieved = result.scalar_one()

    assert retrieved.telegram_peer_id is None
    assert retrieved.title is None
    assert retrieved.is_private is False
    assert retrieved.reference_count == 1
    assert retrieved.source_types == []
    assert retrieved.invite_hash is None
    assert retrieved.first_seen_at is not None
    assert retrieved.last_seen_at is not None
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None


@pytest.mark.asyncio
async def test_discovered_channel_with_invite_hash(db_session: AsyncSession) -> None:
    """Test creating a private discovered channel with invite hash."""
    channel = DiscoveredChannel(
        title="Private Channel",
        invite_hash="abc123xyz",
        is_private=True,
        source_types=[DiscoverySourceType.CAPTION_LINK.value],
    )

    db_session.add(channel)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.invite_hash == "abc123xyz")
    )
    retrieved = result.scalar_one()

    assert retrieved.is_private is True
    assert retrieved.invite_hash == "abc123xyz"
    assert retrieved.username is None
    assert retrieved.telegram_peer_id is None


@pytest.mark.asyncio
async def test_add_source_type(db_session: AsyncSession) -> None:
    """Test adding source types to a discovered channel."""
    channel = DiscoveredChannel(
        username="testchannel",
        source_types=[DiscoverySourceType.FORWARD.value],
    )

    db_session.add(channel)
    await db_session.commit()

    # Add a new source type
    channel.add_source_type(DiscoverySourceType.MENTION.value)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.username == "testchannel")
    )
    retrieved = result.scalar_one()

    assert len(retrieved.source_types) == 2
    assert DiscoverySourceType.FORWARD.value in retrieved.source_types
    assert DiscoverySourceType.MENTION.value in retrieved.source_types


@pytest.mark.asyncio
async def test_add_source_type_no_duplicate(db_session: AsyncSession) -> None:
    """Test that adding duplicate source type doesn't create duplicates."""
    channel = DiscoveredChannel(
        username="testchannel",
        source_types=[DiscoverySourceType.FORWARD.value],
    )

    db_session.add(channel)
    await db_session.commit()

    # Try to add the same source type again
    channel.add_source_type(DiscoverySourceType.FORWARD.value)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.username == "testchannel")
    )
    retrieved = result.scalar_one()

    # Should still only have one entry
    assert len(retrieved.source_types) == 1
    assert retrieved.source_types == [DiscoverySourceType.FORWARD.value]


@pytest.mark.asyncio
async def test_increment_reference(db_session: AsyncSession) -> None:
    """Test incrementing reference count."""
    original_time = datetime.utcnow() - timedelta(hours=1)
    channel = DiscoveredChannel(
        username="testchannel",
        reference_count=1,
        last_seen_at=original_time,
        source_types=[],
    )

    db_session.add(channel)
    await db_session.commit()

    # Increment reference
    channel.increment_reference(DiscoverySourceType.MENTION.value)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.username == "testchannel")
    )
    retrieved = result.scalar_one()

    assert retrieved.reference_count == 2
    assert retrieved.last_seen_at > original_time
    assert DiscoverySourceType.MENTION.value in retrieved.source_types


@pytest.mark.asyncio
async def test_increment_reference_without_source_type(db_session: AsyncSession) -> None:
    """Test incrementing reference count without adding source type."""
    channel = DiscoveredChannel(
        username="testchannel",
        reference_count=1,
        source_types=[],
    )

    db_session.add(channel)
    await db_session.commit()

    # Increment without source type
    channel.increment_reference()
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.username == "testchannel")
    )
    retrieved = result.scalar_one()

    assert retrieved.reference_count == 2
    assert retrieved.source_types == []


@pytest.mark.asyncio
async def test_unique_telegram_peer_id(db_session: AsyncSession) -> None:
    """Test that telegram_peer_id must be unique."""
    channel1 = DiscoveredChannel(
        telegram_peer_id="123456789",
        username="channel1",
    )

    channel2 = DiscoveredChannel(
        telegram_peer_id="123456789",
        username="channel2",
    )

    db_session.add(channel1)
    await db_session.commit()

    db_session.add(channel2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_query_by_reference_count(db_session: AsyncSession) -> None:
    """Test querying channels ordered by reference count."""
    channels = [
        DiscoveredChannel(username="low", reference_count=1),
        DiscoveredChannel(username="high", reference_count=10),
        DiscoveredChannel(username="medium", reference_count=5),
    ]

    for channel in channels:
        db_session.add(channel)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).order_by(DiscoveredChannel.reference_count.desc())
    )
    retrieved = result.scalars().all()

    assert len(retrieved) == 3
    assert retrieved[0].username == "high"
    assert retrieved[1].username == "medium"
    assert retrieved[2].username == "low"


@pytest.mark.asyncio
async def test_all_discovery_source_types(db_session: AsyncSession) -> None:
    """Test that all discovery source types can be stored."""
    all_types = [st.value for st in DiscoverySourceType]

    channel = DiscoveredChannel(
        username="allsources",
        source_types=all_types,
    )

    db_session.add(channel)
    await db_session.commit()

    result = await db_session.execute(
        select(DiscoveredChannel).where(DiscoveredChannel.username == "allsources")
    )
    retrieved = result.scalar_one()

    assert len(retrieved.source_types) == len(DiscoverySourceType)
    for st in DiscoverySourceType:
        assert st.value in retrieved.source_types
