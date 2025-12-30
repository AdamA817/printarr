"""Tests for Designs API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.db.base import Base
from app.db.models import (
    Channel,
    Design,
    DesignSource,
    DesignStatus,
    ExternalMetadataSource,
    ExternalSourceType,
    MatchMethod,
    MetadataAuthority,
    MulticolorStatus,
    TelegramMessage,
)
from app.main import app


# =============================================================================
# Fixtures
# =============================================================================


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


async def create_test_channel(session: AsyncSession, title: str = "Test Channel") -> Channel:
    """Helper to create a test channel."""
    channel = Channel(
        title=title,
        telegram_peer_id=f"peer_{title.replace(' ', '_').lower()}",
        is_enabled=True,
    )
    session.add(channel)
    await session.flush()
    return channel


async def create_test_message(
    session: AsyncSession,
    channel: Channel,
    telegram_message_id: int = 1,
) -> TelegramMessage:
    """Helper to create a test message."""
    from datetime import datetime

    message = TelegramMessage(
        channel_id=channel.id,
        telegram_message_id=telegram_message_id,
        date_posted=datetime.utcnow(),
        caption_text="Test caption",
        has_media=True,
    )
    session.add(message)
    await session.flush()
    return message


async def create_test_design(
    session: AsyncSession,
    channel: Channel,
    message: TelegramMessage,
    title: str = "Test Design",
    status: DesignStatus = DesignStatus.DISCOVERED,
) -> Design:
    """Helper to create a test design with source."""
    design = Design(
        canonical_title=title,
        canonical_designer="Test Designer",
        status=status,
        multicolor=MulticolorStatus.UNKNOWN,
        primary_file_types="STL,ZIP",
        metadata_authority=MetadataAuthority.TELEGRAM,
    )
    session.add(design)
    await session.flush()

    source = DesignSource(
        design_id=design.id,
        channel_id=channel.id,
        message_id=message.id,
        source_rank=1,
        is_preferred=True,
        caption_snapshot="Test caption",
    )
    session.add(source)
    await session.flush()

    return design


# =============================================================================
# List Designs Tests
# =============================================================================


class TestListDesigns:
    """Tests for GET /api/v1/designs/ endpoint."""

    @pytest.mark.asyncio
    async def test_list_designs_empty(self, client: AsyncClient) -> None:
        """Test listing designs when none exist."""
        response = await client.get("/api/v1/designs/")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["pages"] == 1

    @pytest.mark.asyncio
    async def test_list_designs_returns_items(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test listing designs returns created items."""
        # Create test data directly in DB
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)
            await create_test_design(session, channel, message1, title="Design 1")
            await create_test_design(
                session, channel, message2, title="Design 2"
            )
            await session.commit()

        response = await client.get("/api/v1/designs/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_designs_pagination(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test design list pagination."""
        # Create 5 designs
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            for i in range(5):
                message = await create_test_message(session, channel, telegram_message_id=i)
                await create_test_design(
                    session, channel, message, title=f"Design {i}"
                )
            await session.commit()

        # Get first page with 2 items
        response = await client.get("/api/v1/designs/?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["pages"] == 3

        # Get second page
        response = await client.get("/api/v1/designs/?page=2&page_size=2")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2

    @pytest.mark.asyncio
    async def test_list_designs_filter_by_status(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test filtering designs by status."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)
            await create_test_design(
                session, channel, message1,
                title="Discovered Design",
                status=DesignStatus.DISCOVERED,
            )
            await create_test_design(
                session, channel, message2,
                title="Wanted Design",
                status=DesignStatus.WANTED,
            )
            await session.commit()

        # Filter by DISCOVERED
        response = await client.get("/api/v1/designs/?status=DISCOVERED")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Discovered Design"

        # Filter by WANTED
        response = await client.get("/api/v1/designs/?status=WANTED")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Wanted Design"

    @pytest.mark.asyncio
    async def test_list_designs_filter_by_channel(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test filtering designs by channel_id."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel1 = await create_test_channel(session, title="Channel 1")
            channel2 = await create_test_channel(session, title="Channel 2")
            message1 = await create_test_message(session, channel1)
            message2 = await create_test_message(session, channel2)
            await create_test_design(
                session, channel1, message1, title="Design from Channel 1"
            )
            await create_test_design(
                session, channel2, message2, title="Design from Channel 2"
            )
            channel1_id = channel1.id
            await session.commit()

        # Filter by channel1
        response = await client.get(f"/api/v1/designs/?channel_id={channel1_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Design from Channel 1"

    @pytest.mark.asyncio
    async def test_list_designs_includes_channel_info(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test that design list includes channel information."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session, title="My Channel")
            message = await create_test_message(session, channel)
            await create_test_design(session, channel, message)
            await session.commit()

        response = await client.get("/api/v1/designs/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["channel"] is not None
        assert item["channel"]["title"] == "My Channel"

    @pytest.mark.asyncio
    async def test_list_designs_includes_file_types(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test that design list includes file types."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            await create_test_design(session, channel, message)
            await session.commit()

        response = await client.get("/api/v1/designs/")

        assert response.status_code == 200
        data = response.json()
        item = data["items"][0]
        assert "file_types" in item
        assert "STL" in item["file_types"]


# =============================================================================
# Get Design Detail Tests
# =============================================================================


class TestGetDesignDetail:
    """Tests for GET /api/v1/designs/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_design_returns_detail(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test getting a single design returns full detail."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(
                session, channel, message, title="Detail Test"
            )
            design_id = design.id
            await session.commit()

        response = await client.get(f"/api/v1/designs/{design_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == design_id
        assert data["canonical_title"] == "Detail Test"
        assert data["canonical_designer"] == "Test Designer"
        assert data["status"] == "DISCOVERED"
        assert "sources" in data
        assert len(data["sources"]) == 1

    @pytest.mark.asyncio
    async def test_get_design_not_found(self, client: AsyncClient) -> None:
        """Test getting non-existent design returns 404."""
        response = await client.get("/api/v1/designs/nonexistent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Design not found"

    @pytest.mark.asyncio
    async def test_get_design_includes_sources(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test design detail includes source information."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session, title="Source Channel")
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id
            await session.commit()

        response = await client.get(f"/api/v1/designs/{design_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 1
        source = data["sources"][0]
        assert source["is_preferred"] is True
        assert source["caption_snapshot"] == "Test caption"
        assert source["channel"]["title"] == "Source Channel"

    @pytest.mark.asyncio
    async def test_get_design_includes_external_metadata(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test design detail includes external metadata sources."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)

            # Add Thangs metadata source
            ext_source = ExternalMetadataSource(
                design_id=design.id,
                source_type=ExternalSourceType.THANGS,
                external_id="12345",
                external_url="https://thangs.com/m/12345",
                confidence_score=1.0,
                match_method=MatchMethod.LINK,
                fetched_title="Thangs Title",
                fetched_designer="Thangs Designer",
            )
            session.add(ext_source)
            design_id = design.id
            await session.commit()

        response = await client.get(f"/api/v1/designs/{design_id}")

        assert response.status_code == 200
        data = response.json()
        assert "external_metadata" in data
        assert len(data["external_metadata"]) == 1
        ext = data["external_metadata"][0]
        assert ext["source_type"] == "THANGS"
        assert ext["external_id"] == "12345"
        assert ext["fetched_title"] == "Thangs Title"


# =============================================================================
# Refresh Metadata Tests
# =============================================================================


class TestRefreshMetadata:
    """Tests for POST /api/v1/designs/{id}/refresh-metadata endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_metadata_not_found(self, client: AsyncClient) -> None:
        """Test refresh on non-existent design returns 404."""
        response = await client.post(
            "/api/v1/designs/nonexistent-id/refresh-metadata"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_metadata_no_sources(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test refresh with no external sources returns zero counts."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id
            await session.commit()

        response = await client.post(
            f"/api/v1/designs/{design_id}/refresh-metadata"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["design_id"] == design_id
        assert data["sources_refreshed"] == 0
        assert data["sources_failed"] == 0


# =============================================================================
# Response Schema Validation Tests
# =============================================================================


class TestResponseSchemas:
    """Tests that responses match expected schemas."""

    @pytest.mark.asyncio
    async def test_list_response_schema(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test list response matches DesignList schema."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            await create_test_design(session, channel, message)
            await session.commit()

        response = await client.get("/api/v1/designs/")

        assert response.status_code == 200
        data = response.json()

        # Check top-level schema
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data

        # Check item schema
        item = data["items"][0]
        assert "id" in item
        assert "canonical_title" in item
        assert "canonical_designer" in item
        assert "status" in item
        assert "multicolor" in item
        assert "file_types" in item
        assert "created_at" in item
        assert "updated_at" in item
        assert "has_thangs_link" in item

    @pytest.mark.asyncio
    async def test_detail_response_schema(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test detail response matches DesignDetail schema."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id
            await session.commit()

        response = await client.get(f"/api/v1/designs/{design_id}")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "id" in data
        assert "canonical_title" in data
        assert "canonical_designer" in data
        assert "status" in data
        assert "multicolor" in data
        assert "metadata_authority" in data
        assert "display_title" in data
        assert "display_designer" in data
        assert "display_multicolor" in data
        assert "sources" in data
        assert "external_metadata" in data
