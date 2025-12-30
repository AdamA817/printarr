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


# =============================================================================
# Enhanced Filtering, Search, and Sorting Tests (Issue #57)
# =============================================================================


class TestEnhancedFiltering:
    """Tests for enhanced filtering capabilities."""

    @pytest.mark.asyncio
    async def test_filter_by_file_type(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test filtering designs by file type."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            # Create design with STL files
            design1 = Design(
                canonical_title="STL Design",
                canonical_designer="Designer 1",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.UNKNOWN,
                primary_file_types="STL",
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design1)
            await session.flush()
            source1 = DesignSource(
                design_id=design1.id,
                channel_id=channel.id,
                message_id=message1.id,
                source_rank=1,
                is_preferred=True,
            )
            session.add(source1)

            # Create design with 3MF files
            design2 = Design(
                canonical_title="3MF Design",
                canonical_designer="Designer 2",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.UNKNOWN,
                primary_file_types="3MF,STL",
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design2)
            await session.flush()
            source2 = DesignSource(
                design_id=design2.id,
                channel_id=channel.id,
                message_id=message2.id,
                source_rank=1,
                is_preferred=True,
            )
            session.add(source2)
            await session.commit()

        # Filter by STL (should match both)
        response = await client.get("/api/v1/designs/?file_type=STL")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # Filter by 3MF (should match only second design)
        response = await client.get("/api/v1/designs/?file_type=3MF")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "3MF Design"

    @pytest.mark.asyncio
    async def test_filter_by_multicolor(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test filtering designs by multicolor status."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)
            message3 = await create_test_message(session, channel, telegram_message_id=3)

            # Create SINGLE color design
            design1 = Design(
                canonical_title="Single Color Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.SINGLE,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design1)
            await session.flush()
            session.add(DesignSource(
                design_id=design1.id, channel_id=channel.id,
                message_id=message1.id, source_rank=1, is_preferred=True,
            ))

            # Create MULTI color design
            design2 = Design(
                canonical_title="Multi Color Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.MULTI,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design2)
            await session.flush()
            session.add(DesignSource(
                design_id=design2.id, channel_id=channel.id,
                message_id=message2.id, source_rank=1, is_preferred=True,
            ))

            # Create UNKNOWN color design
            design3 = Design(
                canonical_title="Unknown Color Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.UNKNOWN,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design3)
            await session.flush()
            session.add(DesignSource(
                design_id=design3.id, channel_id=channel.id,
                message_id=message3.id, source_rank=1, is_preferred=True,
            ))
            await session.commit()

        # Filter by SINGLE
        response = await client.get("/api/v1/designs/?multicolor=SINGLE")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Single Color Design"

        # Filter by MULTI
        response = await client.get("/api/v1/designs/?multicolor=MULTI")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Multi Color Design"

    @pytest.mark.asyncio
    async def test_filter_by_has_thangs_link(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test filtering designs by Thangs link status."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            # Create design with Thangs link
            design1 = Design(
                canonical_title="Linked Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design1)
            await session.flush()
            session.add(DesignSource(
                design_id=design1.id, channel_id=channel.id,
                message_id=message1.id, source_rank=1, is_preferred=True,
            ))
            session.add(ExternalMetadataSource(
                design_id=design1.id,
                source_type=ExternalSourceType.THANGS,
                external_id="12345",
                external_url="https://thangs.com/m/12345",
                confidence_score=1.0,
                match_method=MatchMethod.LINK,
            ))

            # Create design without Thangs link
            design2 = Design(
                canonical_title="Unlinked Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design2)
            await session.flush()
            session.add(DesignSource(
                design_id=design2.id, channel_id=channel.id,
                message_id=message2.id, source_rank=1, is_preferred=True,
            ))
            await session.commit()

        # Filter by has_thangs_link=true
        response = await client.get("/api/v1/designs/?has_thangs_link=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Linked Design"

        # Filter by has_thangs_link=false
        response = await client.get("/api/v1/designs/?has_thangs_link=false")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Unlinked Design"

    @pytest.mark.asyncio
    async def test_filter_by_designer(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test filtering designs by designer (partial match)."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            # Create design by "John Smith"
            design1 = Design(
                canonical_title="Design 1",
                canonical_designer="John Smith",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design1)
            await session.flush()
            session.add(DesignSource(
                design_id=design1.id, channel_id=channel.id,
                message_id=message1.id, source_rank=1, is_preferred=True,
            ))

            # Create design by "Jane Doe"
            design2 = Design(
                canonical_title="Design 2",
                canonical_designer="Jane Doe",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design2)
            await session.flush()
            session.add(DesignSource(
                design_id=design2.id, channel_id=channel.id,
                message_id=message2.id, source_rank=1, is_preferred=True,
            ))
            await session.commit()

        # Filter by "John" (partial match)
        response = await client.get("/api/v1/designs/?designer=John")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_designer"] == "John Smith"

        # Filter by "smith" (case-insensitive)
        response = await client.get("/api/v1/designs/?designer=smith")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_designer"] == "John Smith"


class TestSearchFunctionality:
    """Tests for full-text search functionality."""

    @pytest.mark.asyncio
    async def test_search_by_title(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test searching designs by title."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            design1 = Design(
                canonical_title="Batman Figure",
                canonical_designer="Designer A",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design1)
            await session.flush()
            session.add(DesignSource(
                design_id=design1.id, channel_id=channel.id,
                message_id=message1.id, source_rank=1, is_preferred=True,
            ))

            design2 = Design(
                canonical_title="Superman Statue",
                canonical_designer="Designer B",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design2)
            await session.flush()
            session.add(DesignSource(
                design_id=design2.id, channel_id=channel.id,
                message_id=message2.id, source_rank=1, is_preferred=True,
            ))
            await session.commit()

        # Search for "Batman"
        response = await client.get("/api/v1/designs/?q=Batman")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Batman Figure"

        # Search for "figure" (case-insensitive)
        response = await client.get("/api/v1/designs/?q=figure")
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_title"] == "Batman Figure"

    @pytest.mark.asyncio
    async def test_search_by_designer(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test searching designs by designer name."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            design1 = Design(
                canonical_title="Design One",
                canonical_designer="WickedProps",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design1)
            await session.flush()
            session.add(DesignSource(
                design_id=design1.id, channel_id=channel.id,
                message_id=message1.id, source_rank=1, is_preferred=True,
            ))

            design2 = Design(
                canonical_title="Design Two",
                canonical_designer="Gambody",
                status=DesignStatus.DISCOVERED,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design2)
            await session.flush()
            session.add(DesignSource(
                design_id=design2.id, channel_id=channel.id,
                message_id=message2.id, source_rank=1, is_preferred=True,
            ))
            await session.commit()

        # Search for "Wicked" (matches designer)
        response = await client.get("/api/v1/designs/?q=Wicked")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_designer"] == "WickedProps"


class TestSorting:
    """Tests for sorting functionality."""

    @pytest.mark.asyncio
    async def test_sort_by_title_asc(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test sorting designs by title ascending."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)

            for title in ["Zebra", "Apple", "Mango"]:
                message = await create_test_message(
                    session, channel,
                    telegram_message_id=ord(title[0])
                )
                design = Design(
                    canonical_title=title,
                    canonical_designer="Designer",
                    status=DesignStatus.DISCOVERED,
                    metadata_authority=MetadataAuthority.TELEGRAM,
                )
                session.add(design)
                await session.flush()
                session.add(DesignSource(
                    design_id=design.id, channel_id=channel.id,
                    message_id=message.id, source_rank=1, is_preferred=True,
                ))
            await session.commit()

        # Sort by title ASC
        response = await client.get(
            "/api/v1/designs/?sort_by=canonical_title&sort_order=ASC"
        )
        assert response.status_code == 200
        data = response.json()
        titles = [item["canonical_title"] for item in data["items"]]
        assert titles == ["Apple", "Mango", "Zebra"]

    @pytest.mark.asyncio
    async def test_sort_by_title_desc(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test sorting designs by title descending."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)

            for title in ["Zebra", "Apple", "Mango"]:
                message = await create_test_message(
                    session, channel,
                    telegram_message_id=ord(title[0])
                )
                design = Design(
                    canonical_title=title,
                    canonical_designer="Designer",
                    status=DesignStatus.DISCOVERED,
                    metadata_authority=MetadataAuthority.TELEGRAM,
                )
                session.add(design)
                await session.flush()
                session.add(DesignSource(
                    design_id=design.id, channel_id=channel.id,
                    message_id=message.id, source_rank=1, is_preferred=True,
                ))
            await session.commit()

        # Sort by title DESC
        response = await client.get(
            "/api/v1/designs/?sort_by=canonical_title&sort_order=DESC"
        )
        assert response.status_code == 200
        data = response.json()
        titles = [item["canonical_title"] for item in data["items"]]
        assert titles == ["Zebra", "Mango", "Apple"]

    @pytest.mark.asyncio
    async def test_sort_by_designer(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test sorting designs by designer."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)

            for idx, designer in enumerate(["Zack", "Adam", "Mike"]):
                message = await create_test_message(
                    session, channel,
                    telegram_message_id=idx + 1
                )
                design = Design(
                    canonical_title=f"Design by {designer}",
                    canonical_designer=designer,
                    status=DesignStatus.DISCOVERED,
                    metadata_authority=MetadataAuthority.TELEGRAM,
                )
                session.add(design)
                await session.flush()
                session.add(DesignSource(
                    design_id=design.id, channel_id=channel.id,
                    message_id=message.id, source_rank=1, is_preferred=True,
                ))
            await session.commit()

        # Sort by designer ASC
        response = await client.get(
            "/api/v1/designs/?sort_by=canonical_designer&sort_order=ASC"
        )
        assert response.status_code == 200
        data = response.json()
        designers = [item["canonical_designer"] for item in data["items"]]
        assert designers == ["Adam", "Mike", "Zack"]

    @pytest.mark.asyncio
    async def test_combined_filter_and_sort(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test combining filters with sorting."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)

            # Create designs with different statuses
            designs_data = [
                ("Zebra", DesignStatus.DISCOVERED),
                ("Apple", DesignStatus.DISCOVERED),
                ("Mango", DesignStatus.WANTED),
            ]

            for idx, (title, status) in enumerate(designs_data):
                message = await create_test_message(
                    session, channel,
                    telegram_message_id=idx + 1
                )
                design = Design(
                    canonical_title=title,
                    canonical_designer="Designer",
                    status=status,
                    metadata_authority=MetadataAuthority.TELEGRAM,
                )
                session.add(design)
                await session.flush()
                session.add(DesignSource(
                    design_id=design.id, channel_id=channel.id,
                    message_id=message.id, source_rank=1, is_preferred=True,
                ))
            await session.commit()

        # Filter by DISCOVERED and sort by title ASC
        response = await client.get(
            "/api/v1/designs/?status=DISCOVERED&sort_by=canonical_title&sort_order=ASC"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        titles = [item["canonical_title"] for item in data["items"]]
        assert titles == ["Apple", "Zebra"]


# =============================================================================
# Thangs Link/Unlink Tests (Issue #59)
# =============================================================================

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select


class TestThangsLinkUnlink:
    """Tests for Thangs link/unlink endpoints."""

    @pytest.mark.asyncio
    async def test_link_to_thangs_creates_source(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test linking a design to Thangs creates ExternalMetadataSource."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id
            await session.commit()

        with patch("app.api.routes.designs.ThangsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.fetch_thangs_metadata = AsyncMock(
                return_value={
                    "title": "Thangs Title",
                    "designer": "Thangs Designer",
                    "tags": ["tag1", "tag2"],
                }
            )
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            response = await client.post(
                f"/api/v1/designs/{design_id}/thangs-link",
                json={"model_id": "12345", "url": "https://thangs.com/m/12345"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["design_id"] == design_id
        assert data["external_id"] == "12345"
        assert data["external_url"] == "https://thangs.com/m/12345"
        assert data["source_type"] == "THANGS"
        assert data["match_method"] == "MANUAL"
        assert data["confidence_score"] == 1.0
        assert data["is_user_confirmed"] is True
        assert data["fetched_title"] == "Thangs Title"
        assert data["fetched_designer"] == "Thangs Designer"

    @pytest.mark.asyncio
    async def test_link_to_thangs_updates_existing(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test linking when already linked updates the existing source."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)

            # Create existing Thangs link
            existing_source = ExternalMetadataSource(
                design_id=design.id,
                source_type=ExternalSourceType.THANGS,
                external_id="old_id",
                external_url="https://thangs.com/m/old_id",
                confidence_score=0.5,
                match_method=MatchMethod.LINK,
            )
            session.add(existing_source)
            design_id = design.id
            await session.commit()

        with patch("app.api.routes.designs.ThangsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.fetch_thangs_metadata = AsyncMock(return_value=None)
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            response = await client.post(
                f"/api/v1/designs/{design_id}/thangs-link",
                json={"model_id": "new_id", "url": "https://thangs.com/m/new_id"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["external_id"] == "new_id"
        assert data["match_method"] == "MANUAL"
        assert data["confidence_score"] == 1.0
        assert data["is_user_confirmed"] is True

    @pytest.mark.asyncio
    async def test_link_to_thangs_not_found(self, client: AsyncClient) -> None:
        """Test linking non-existent design returns 404."""
        response = await client.post(
            "/api/v1/designs/nonexistent-id/thangs-link",
            json={"model_id": "12345", "url": "https://thangs.com/m/12345"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_link_by_url(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test linking by URL extracts model ID correctly."""
        from app.services.thangs import ThangsAdapter

        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id
            await session.commit()

        # Create a mock class that preserves the static method
        class MockThangsAdapter:
            detect_thangs_url = staticmethod(ThangsAdapter.detect_thangs_url)

            def __init__(self, db):
                pass

            async def fetch_thangs_metadata(self, model_id):
                return None

            async def close(self):
                pass

        with patch("app.api.routes.designs.ThangsAdapter", MockThangsAdapter):
            response = await client.post(
                f"/api/v1/designs/{design_id}/thangs-link-by-url",
                json={"url": "https://thangs.com/designer/cool-model-67890"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["external_id"] == "67890"
        assert data["external_url"] == "https://thangs.com/m/67890"

    @pytest.mark.asyncio
    async def test_link_by_url_invalid(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test linking with invalid URL returns 400."""
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
            f"/api/v1/designs/{design_id}/thangs-link-by-url",
            json={"url": "https://example.com/not-a-thangs-url"},
        )

        assert response.status_code == 400
        assert "Invalid Thangs URL" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unlink_from_thangs(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test unlinking a design from Thangs removes the source."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)

            # Create Thangs link
            source = ExternalMetadataSource(
                design_id=design.id,
                source_type=ExternalSourceType.THANGS,
                external_id="12345",
                external_url="https://thangs.com/m/12345",
                confidence_score=1.0,
                match_method=MatchMethod.LINK,
            )
            session.add(source)
            design_id = design.id
            await session.commit()

        response = await client.delete(f"/api/v1/designs/{design_id}/thangs-link")

        assert response.status_code == 204

        # Verify link was removed
        async with async_session() as session:
            result = await session.execute(
                select(ExternalMetadataSource).where(
                    ExternalMetadataSource.design_id == design_id,
                    ExternalMetadataSource.source_type == ExternalSourceType.THANGS,
                )
            )
            source = result.scalar_one_or_none()
            assert source is None

    @pytest.mark.asyncio
    async def test_unlink_from_thangs_not_linked(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test unlinking when not linked returns 404."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id
            await session.commit()

        response = await client.delete(f"/api/v1/designs/{design_id}/thangs-link")

        assert response.status_code == 404
        assert "not linked" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unlink_design_not_found(self, client: AsyncClient) -> None:
        """Test unlinking non-existent design returns 404."""
        response = await client.delete("/api/v1/designs/nonexistent-id/thangs-link")

        assert response.status_code == 404


# =============================================================================
# Design Merge/Unmerge Tests (Issue #60)
# =============================================================================


class TestMergeDesigns:
    """Tests for design merge endpoint."""

    @pytest.mark.asyncio
    async def test_merge_designs_success(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test merging two designs moves sources to target."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)

            # Create target design with 1 source
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            target = await create_test_design(session, channel, message1)
            target.primary_file_types = "STL"
            target.total_size_bytes = 1000
            target_id = target.id

            # Create source design with 1 source
            message2 = await create_test_message(session, channel, telegram_message_id=2)
            source_design = Design(
                canonical_title="Source Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.UNKNOWN,
                primary_file_types="3MF",
                total_size_bytes=2000,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(source_design)
            await session.flush()
            session.add(DesignSource(
                design_id=source_design.id,
                channel_id=channel.id,
                message_id=message2.id,
                source_rank=1,
                is_preferred=True,
            ))
            source_id = source_design.id
            await session.commit()

        response = await client.post(
            f"/api/v1/designs/{target_id}/merge",
            json={"source_design_ids": [source_id]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["merged_design_id"] == target_id
        assert data["merged_source_count"] == 2
        assert source_id in data["deleted_design_ids"]

        # Verify source design was deleted
        async with async_session() as session:
            result = await session.execute(
                select(Design).where(Design.id == source_id)
            )
            assert result.scalar_one_or_none() is None

            # Verify target has both sources
            result = await session.execute(
                select(DesignSource).where(DesignSource.design_id == target_id)
            )
            sources = result.scalars().all()
            assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_merge_cannot_merge_with_self(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test merging a design with itself returns 400."""
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
            f"/api/v1/designs/{design_id}/merge",
            json={"source_design_ids": [design_id]},
        )

        assert response.status_code == 400
        assert "itself" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_merge_empty_source_list(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test merging with empty source list returns 400."""
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
            f"/api/v1/designs/{design_id}/merge",
            json={"source_design_ids": []},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_merge_target_not_found(self, client: AsyncClient) -> None:
        """Test merging with non-existent target returns 404."""
        response = await client.post(
            "/api/v1/designs/nonexistent-id/merge",
            json={"source_design_ids": ["some-id"]},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_merge_source_not_found(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test merging with non-existent source returns 404."""
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
            f"/api/v1/designs/{design_id}/merge",
            json={"source_design_ids": ["nonexistent-id"]},
        )

        assert response.status_code == 404


class TestUnmergeDesign:
    """Tests for design unmerge endpoint."""

    @pytest.mark.asyncio
    async def test_unmerge_design_success(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test unmerging creates new design and moves sources."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)

            # Create design with 2 sources
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            design = Design(
                canonical_title="Original Design",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.UNKNOWN,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design)
            await session.flush()

            source1 = DesignSource(
                design_id=design.id,
                channel_id=channel.id,
                message_id=message1.id,
                source_rank=1,
                is_preferred=True,
            )
            source2 = DesignSource(
                design_id=design.id,
                channel_id=channel.id,
                message_id=message2.id,
                source_rank=2,
                is_preferred=False,
            )
            session.add_all([source1, source2])
            design_id = design.id
            await session.flush()
            source2_id = source2.id
            await session.commit()

        response = await client.post(
            f"/api/v1/designs/{design_id}/unmerge",
            json={"source_ids": [source2_id]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["original_design_id"] == design_id
        assert data["moved_source_count"] == 1
        new_design_id = data["new_design_id"]
        assert new_design_id != design_id

        # Verify original design still has source1
        async with async_session() as session:
            result = await session.execute(
                select(DesignSource).where(DesignSource.design_id == design_id)
            )
            original_sources = result.scalars().all()
            assert len(original_sources) == 1

            # Verify new design has source2
            result = await session.execute(
                select(DesignSource).where(DesignSource.design_id == new_design_id)
            )
            new_sources = result.scalars().all()
            assert len(new_sources) == 1
            assert new_sources[0].id == source2_id

    @pytest.mark.asyncio
    async def test_unmerge_cannot_remove_all_sources(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test unmerging all sources returns 400."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message = await create_test_message(session, channel)
            design = await create_test_design(session, channel, message)
            design_id = design.id

            # Get the single source ID
            result = await session.execute(
                select(DesignSource).where(DesignSource.design_id == design_id)
            )
            source = result.scalar_one()
            source_id = source.id
            await session.commit()

        response = await client.post(
            f"/api/v1/designs/{design_id}/unmerge",
            json={"source_ids": [source_id]},
        )

        assert response.status_code == 400
        assert "At least one source must remain" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_unmerge_design_not_found(self, client: AsyncClient) -> None:
        """Test unmerging non-existent design returns 404."""
        response = await client.post(
            "/api/v1/designs/nonexistent-id/unmerge",
            json={"source_ids": ["some-id"]},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unmerge_source_not_found(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test unmerging non-existent source returns 404."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            channel = await create_test_channel(session)
            message1 = await create_test_message(session, channel, telegram_message_id=1)
            message2 = await create_test_message(session, channel, telegram_message_id=2)

            design = Design(
                canonical_title="Test",
                canonical_designer="Designer",
                status=DesignStatus.DISCOVERED,
                multicolor=MulticolorStatus.UNKNOWN,
                metadata_authority=MetadataAuthority.TELEGRAM,
            )
            session.add(design)
            await session.flush()

            session.add_all([
                DesignSource(
                    design_id=design.id, channel_id=channel.id,
                    message_id=message1.id, source_rank=1, is_preferred=True,
                ),
                DesignSource(
                    design_id=design.id, channel_id=channel.id,
                    message_id=message2.id, source_rank=2, is_preferred=False,
                ),
            ])
            design_id = design.id
            await session.commit()

        response = await client.post(
            f"/api/v1/designs/{design_id}/unmerge",
            json={"source_ids": ["nonexistent-source-id"]},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unmerge_empty_source_list(
        self, client: AsyncClient, db_engine
    ) -> None:
        """Test unmerging with empty source list returns 400."""
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
            f"/api/v1/designs/{design_id}/unmerge",
            json={"source_ids": []},
        )

        assert response.status_code == 400
