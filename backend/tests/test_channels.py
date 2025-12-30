"""Tests for Channel CRUD API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.db.base import Base
from app.db.models import Channel
from app.main import app


@pytest.fixture
async def db_engine():
    """Create an in-memory test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    """Create a test client with overridden database dependency."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_channels_empty(client: AsyncClient) -> None:
    """Test listing channels when none exist."""
    response = await client.get("/api/v1/channels/")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pages"] == 1


@pytest.mark.asyncio
async def test_create_channel(client: AsyncClient) -> None:
    """Test creating a new channel."""
    response = await client.post(
        "/api/v1/channels/",
        json={
            "title": "Test Channel",
            "username": "testchannel",
            "is_private": False,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Channel"
    assert data["username"] == "testchannel"
    assert data["is_private"] is False
    assert data["is_enabled"] is True
    assert data["id"] is not None
    assert data["telegram_peer_id"].startswith("local_")


@pytest.mark.asyncio
async def test_create_channel_with_peer_id(client: AsyncClient) -> None:
    """Test creating a channel with explicit telegram_peer_id."""
    response = await client.post(
        "/api/v1/channels/",
        json={
            "title": "Custom ID Channel",
            "telegram_peer_id": "custom_123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["telegram_peer_id"] == "custom_123"


@pytest.mark.asyncio
async def test_create_duplicate_channel(client: AsyncClient) -> None:
    """Test that duplicate telegram_peer_id is rejected."""
    # Create first channel
    await client.post(
        "/api/v1/channels/",
        json={"title": "First", "telegram_peer_id": "duplicate_id"},
    )

    # Try to create duplicate
    response = await client.post(
        "/api/v1/channels/",
        json={"title": "Second", "telegram_peer_id": "duplicate_id"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_channel(client: AsyncClient) -> None:
    """Test getting a single channel by ID."""
    # Create a channel first
    create_response = await client.post(
        "/api/v1/channels/",
        json={"title": "Get Test Channel"},
    )
    channel_id = create_response.json()["id"]

    # Get the channel
    response = await client.get(f"/api/v1/channels/{channel_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == channel_id
    assert data["title"] == "Get Test Channel"


@pytest.mark.asyncio
async def test_get_channel_not_found(client: AsyncClient) -> None:
    """Test getting a non-existent channel."""
    response = await client.get("/api/v1/channels/nonexistent-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Channel not found"


@pytest.mark.asyncio
async def test_update_channel(client: AsyncClient) -> None:
    """Test updating a channel."""
    # Create a channel first
    create_response = await client.post(
        "/api/v1/channels/",
        json={"title": "Original Title"},
    )
    channel_id = create_response.json()["id"]

    # Update the channel
    response = await client.patch(
        f"/api/v1/channels/{channel_id}",
        json={
            "title": "Updated Title",
            "is_enabled": False,
            "backfill_mode": "ALL_HISTORY",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["is_enabled"] is False
    assert data["backfill_mode"] == "ALL_HISTORY"


@pytest.mark.asyncio
async def test_update_channel_partial(client: AsyncClient) -> None:
    """Test partial update only modifies specified fields."""
    # Create a channel
    create_response = await client.post(
        "/api/v1/channels/",
        json={"title": "Original", "username": "original_user"},
    )
    channel_id = create_response.json()["id"]

    # Update only title
    response = await client.patch(
        f"/api/v1/channels/{channel_id}",
        json={"title": "New Title"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["username"] == "original_user"  # Unchanged


@pytest.mark.asyncio
async def test_update_channel_not_found(client: AsyncClient) -> None:
    """Test updating a non-existent channel."""
    response = await client.patch(
        "/api/v1/channels/nonexistent-id",
        json={"title": "New Title"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_channel(client: AsyncClient) -> None:
    """Test deleting a channel."""
    # Create a channel
    create_response = await client.post(
        "/api/v1/channels/",
        json={"title": "To Delete"},
    )
    channel_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(f"/api/v1/channels/{channel_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/v1/channels/{channel_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_channel_not_found(client: AsyncClient) -> None:
    """Test deleting a non-existent channel."""
    response = await client.delete("/api/v1/channels/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_channels_pagination(client: AsyncClient) -> None:
    """Test channel list pagination."""
    # Create 5 channels
    for i in range(5):
        await client.post(
            "/api/v1/channels/",
            json={"title": f"Channel {i}", "telegram_peer_id": f"peer_{i}"},
        )

    # Get first page with 2 items
    response = await client.get("/api/v1/channels/?page=1&page_size=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["pages"] == 3

    # Get second page
    response = await client.get("/api/v1/channels/?page=2&page_size=2")
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_list_channels_filter_enabled(client: AsyncClient) -> None:
    """Test filtering channels by enabled status."""
    # Create enabled and disabled channels
    await client.post(
        "/api/v1/channels/",
        json={"title": "Enabled", "telegram_peer_id": "enabled_1"},
    )

    create_response = await client.post(
        "/api/v1/channels/",
        json={"title": "Disabled", "telegram_peer_id": "disabled_1"},
    )
    disabled_id = create_response.json()["id"]

    # Disable the second one
    await client.patch(f"/api/v1/channels/{disabled_id}", json={"is_enabled": False})

    # Filter by enabled
    response = await client.get("/api/v1/channels/?is_enabled=true")
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Enabled"

    # Filter by disabled
    response = await client.get("/api/v1/channels/?is_enabled=false")
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Disabled"
