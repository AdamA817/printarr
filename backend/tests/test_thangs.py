"""Tests for ThangsAdapter URL detection and metadata fetching."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Design,
    DesignStatus,
    ExternalSourceType,
    MatchMethod,
    MulticolorStatus,
)
from app.services.thangs import ThangsAdapter

# =============================================================================
# URL Detection Tests (Static Methods - No DB Required)
# =============================================================================


class TestDetectThangsUrl:
    """Tests for ThangsAdapter.detect_thangs_url static method."""

    def test_detect_designer_slug_pattern(self):
        """Test detecting thangs.com/designer/model-slug-123456 pattern."""
        text = "Check out this model: https://thangs.com/designer/cool-model-name-12345"
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "12345"
        assert result[0]["url"] == "https://thangs.com/m/12345"

    def test_detect_m_pattern(self):
        """Test detecting thangs.com/m/123456 pattern."""
        text = "Model link: https://thangs.com/m/67890"
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "67890"
        assert result[0]["url"] == "https://thangs.com/m/67890"

    def test_detect_model_pattern(self):
        """Test detecting thangs.com/model/123456 pattern."""
        text = "See https://thangs.com/model/11111"
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "11111"
        assert result[0]["url"] == "https://thangs.com/m/11111"

    def test_detect_multiple_urls(self):
        """Test detecting multiple Thangs URLs in same text."""
        text = """
        First model: https://thangs.com/m/111
        Second model: https://thangs.com/designer/name-222
        """
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 2
        model_ids = {r["model_id"] for r in result}
        assert model_ids == {"111", "222"}

    def test_deduplicates_same_model(self):
        """Test that same model ID is not returned twice."""
        text = """
        https://thangs.com/m/12345
        Also here: https://thangs.com/designer/foo-12345
        """
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "12345"

    def test_empty_text_returns_empty(self):
        """Test that empty text returns empty list."""
        assert ThangsAdapter.detect_thangs_url("") == []
        assert ThangsAdapter.detect_thangs_url(None) == []

    def test_no_thangs_urls(self):
        """Test text with no Thangs URLs."""
        text = "Check out https://example.com and https://google.com"
        result = ThangsAdapter.detect_thangs_url(text)

        assert result == []

    def test_url_with_query_params(self):
        """Test detecting URL with query parameters."""
        text = "https://thangs.com/m/12345?ref=telegram"
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "12345"

    def test_case_insensitive(self):
        """Test URL detection is case insensitive."""
        text = "HTTPS://THANGS.COM/M/99999"
        result = ThangsAdapter.detect_thangs_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "99999"


class TestDetectPrintablesUrl:
    """Tests for ThangsAdapter.detect_printables_url static method."""

    def test_detect_basic_url(self):
        """Test detecting basic printables.com/model/123 URL."""
        text = "Model at https://www.printables.com/model/12345"
        result = ThangsAdapter.detect_printables_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "12345"
        assert result[0]["url"] == "https://www.printables.com/model/12345"

    def test_detect_url_with_slug(self):
        """Test detecting URL with slug after ID."""
        text = "https://printables.com/model/12345-my-cool-model"
        result = ThangsAdapter.detect_printables_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "12345"

    def test_detect_multiple_urls(self):
        """Test detecting multiple Printables URLs."""
        text = """
        https://printables.com/model/111
        https://printables.com/model/222
        """
        result = ThangsAdapter.detect_printables_url(text)

        assert len(result) == 2

    def test_empty_text_returns_empty(self):
        """Test that empty text returns empty list."""
        assert ThangsAdapter.detect_printables_url("") == []
        assert ThangsAdapter.detect_printables_url(None) == []


class TestDetectThingiverseUrl:
    """Tests for ThangsAdapter.detect_thingiverse_url static method."""

    def test_detect_basic_url(self):
        """Test detecting basic thingiverse.com/thing:123 URL."""
        text = "Thing at https://www.thingiverse.com/thing:12345"
        result = ThangsAdapter.detect_thingiverse_url(text)

        assert len(result) == 1
        assert result[0]["model_id"] == "12345"
        assert result[0]["url"] == "https://www.thingiverse.com/thing:12345"

    def test_detect_multiple_urls(self):
        """Test detecting multiple Thingiverse URLs."""
        text = """
        https://thingiverse.com/thing:111
        https://thingiverse.com/thing:222
        """
        result = ThangsAdapter.detect_thingiverse_url(text)

        assert len(result) == 2

    def test_empty_text_returns_empty(self):
        """Test that empty text returns empty list."""
        assert ThangsAdapter.detect_thingiverse_url("") == []
        assert ThangsAdapter.detect_thingiverse_url(None) == []


class TestDetectAllUrls:
    """Tests for ThangsAdapter.detect_all_urls static method."""

    def test_detects_all_platforms(self):
        """Test detecting URLs from all platforms in same text."""
        text = """
        Thangs: https://thangs.com/m/111
        Printables: https://printables.com/model/222
        Thingiverse: https://thingiverse.com/thing:333
        """
        result = ThangsAdapter.detect_all_urls(text)

        assert len(result["thangs"]) == 1
        assert result["thangs"][0]["model_id"] == "111"

        assert len(result["printables"]) == 1
        assert result["printables"][0]["model_id"] == "222"

        assert len(result["thingiverse"]) == 1
        assert result["thingiverse"][0]["model_id"] == "333"

    def test_returns_empty_dicts_for_missing_platforms(self):
        """Test returns empty lists when platform URLs not found."""
        text = "Just some text with no URLs"
        result = ThangsAdapter.detect_all_urls(text)

        assert result["thangs"] == []
        assert result["printables"] == []
        assert result["thingiverse"] == []


# =============================================================================
# Metadata Fetching Tests (Require Mocking)
# =============================================================================


class TestFetchThangsMetadata:
    """Tests for ThangsAdapter.fetch_thangs_metadata method."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory test database engine."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @pytest.fixture
    async def db_session(self, db_engine):
        """Create a test database session."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_fetch_metadata_success(self, db_session):
        """Test fetching metadata from Thangs API returns correct data."""
        adapter = ThangsAdapter(db_session)

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Cool Model",
            "owner": {"username": "designer123"},
            "tags": ["tag1", "tag2"],
            "images": ["img1.jpg"],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.fetch_thangs_metadata("12345")

        assert result is not None
        assert result["title"] == "Cool Model"
        assert result["designer"] == "designer123"
        assert result["tags"] == ["tag1", "tag2"]

        mock_client.get.assert_called_once_with("https://api.thangs.com/models/12345")
        await adapter.close()

    @pytest.mark.asyncio
    async def test_fetch_metadata_404(self, db_session):
        """Test fetch returns None for 404 response."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.fetch_thangs_metadata("nonexistent")

        assert result is None
        await adapter.close()

    @pytest.mark.asyncio
    async def test_fetch_metadata_server_error(self, db_session):
        """Test fetch returns None for server error."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.fetch_thangs_metadata("12345")

        assert result is None
        await adapter.close()

    @pytest.mark.asyncio
    async def test_extract_designer_from_owner(self, db_session):
        """Test extracting designer from owner field."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Model",
            "owner": {"username": "owner_user"},
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.fetch_thangs_metadata("12345")

        assert result["designer"] == "owner_user"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_extract_designer_from_creator(self, db_session):
        """Test extracting designer from creator field."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Model",
            "creator": {"name": "creator_name"},
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.fetch_thangs_metadata("12345")

        assert result["designer"] == "creator_name"
        await adapter.close()


# =============================================================================
# Process Design URLs Tests (Require DB)
# =============================================================================


class TestProcessDesignUrls:
    """Tests for ThangsAdapter.process_design_urls method."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory test database engine."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @pytest.fixture
    async def db_session(self, db_engine):
        """Create a test database session."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            yield session

    @pytest.fixture
    async def sample_design(self, db_session):
        """Create a sample design for testing."""
        design = Design(
            canonical_title="Test Design",
            canonical_designer="Test Designer",
            status=DesignStatus.DISCOVERED,
            multicolor=MulticolorStatus.UNKNOWN,
        )
        db_session.add(design)
        await db_session.flush()
        return design

    @pytest.mark.asyncio
    async def test_creates_thangs_source(self, db_session, sample_design):
        """Test that Thangs URL creates ExternalMetadataSource record."""
        adapter = ThangsAdapter(db_session)

        caption = "Check out https://thangs.com/m/12345"
        sources = await adapter.process_design_urls(
            sample_design, caption, fetch_metadata=False
        )

        assert len(sources) == 1
        source = sources[0]
        assert source.source_type == ExternalSourceType.THANGS
        assert source.external_id == "12345"
        assert source.external_url == "https://thangs.com/m/12345"
        assert source.confidence_score == 1.0
        assert source.match_method == MatchMethod.LINK
        await adapter.close()

    @pytest.mark.asyncio
    async def test_creates_printables_source(self, db_session, sample_design):
        """Test that Printables URL creates ExternalMetadataSource record."""
        adapter = ThangsAdapter(db_session)

        caption = "Model at https://printables.com/model/67890"
        sources = await adapter.process_design_urls(
            sample_design, caption, fetch_metadata=False
        )

        assert len(sources) == 1
        source = sources[0]
        assert source.source_type == ExternalSourceType.PRINTABLES
        assert source.external_id == "67890"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_creates_thingiverse_source(self, db_session, sample_design):
        """Test that Thingiverse URL creates ExternalMetadataSource record."""
        adapter = ThangsAdapter(db_session)

        caption = "Thing: https://thingiverse.com/thing:11111"
        sources = await adapter.process_design_urls(
            sample_design, caption, fetch_metadata=False
        )

        assert len(sources) == 1
        source = sources[0]
        assert source.source_type == ExternalSourceType.THINGIVERSE
        assert source.external_id == "11111"
        await adapter.close()

    @pytest.mark.asyncio
    async def test_creates_multiple_sources(self, db_session, sample_design):
        """Test that multiple URLs from different platforms all create records."""
        adapter = ThangsAdapter(db_session)

        caption = """
        Thangs: https://thangs.com/m/111
        Printables: https://printables.com/model/222
        Thingiverse: https://thingiverse.com/thing:333
        """
        sources = await adapter.process_design_urls(
            sample_design, caption, fetch_metadata=False
        )

        assert len(sources) == 3
        source_types = {s.source_type for s in sources}
        assert source_types == {
            ExternalSourceType.THANGS,
            ExternalSourceType.PRINTABLES,
            ExternalSourceType.THINGIVERSE,
        }
        await adapter.close()

    @pytest.mark.asyncio
    async def test_updates_existing_source(self, db_session, sample_design):
        """Test that existing source is updated instead of creating duplicate."""
        adapter = ThangsAdapter(db_session)

        # Create first source
        caption1 = "https://thangs.com/m/12345"
        sources1 = await adapter.process_design_urls(
            sample_design, caption1, fetch_metadata=False
        )
        await db_session.flush()

        # Process same URL again
        caption2 = "https://thangs.com/m/12345"
        sources2 = await adapter.process_design_urls(
            sample_design, caption2, fetch_metadata=False
        )

        # Should return the same source (updated)
        assert len(sources1) == 1
        assert len(sources2) == 1
        assert sources1[0].id == sources2[0].id
        await adapter.close()

    @pytest.mark.asyncio
    async def test_no_urls_returns_empty(self, db_session, sample_design):
        """Test that caption with no URLs returns empty list."""
        adapter = ThangsAdapter(db_session)

        caption = "Just some regular text"
        sources = await adapter.process_design_urls(
            sample_design, caption, fetch_metadata=False
        )

        assert sources == []
        await adapter.close()


# =============================================================================
# Search API Tests
# =============================================================================


from app.db import get_db
from app.main import app
from app.services.thangs import (
    ThangsRateLimitError,
    ThangsSearchResponse,
    ThangsSearchResult,
    ThangsUpstreamError,
    _search_cache,
)


class TestThangsSearch:
    """Tests for ThangsAdapter.search method."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory test database engine."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @pytest.fixture
    async def db_session(self, db_engine):
        """Create a test database session."""
        async_session = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            yield session

    @pytest.fixture
    def clear_cache(self):
        """Clear the search cache before and after each test."""
        _search_cache.clear()
        yield
        _search_cache.clear()

    @pytest.mark.asyncio
    async def test_search_success(self, db_session, clear_cache):
        """Test successful search returns results."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "12345",
                    "name": "Cool Batman Model",
                    "owner": {"username": "designer1"},
                    "thumbnail": "https://thangs.com/img/12345.jpg",
                },
                {
                    "id": "67890",
                    "name": "Superman Figure",
                    "owner": {"username": "designer2"},
                },
            ],
            "total": 2,
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.search("batman", limit=10)

        assert isinstance(result, ThangsSearchResponse)
        assert len(result.results) == 2
        assert result.total == 2
        assert result.results[0].model_id == "12345"
        assert result.results[0].title == "Cool Batman Model"
        assert result.results[0].designer == "designer1"
        assert result.results[0].thumbnail_url == "https://thangs.com/img/12345.jpg"
        assert result.results[0].url == "https://thangs.com/m/12345"

        await adapter.close()

    @pytest.mark.asyncio
    async def test_search_query_too_short(self, db_session):
        """Test search with query less than 3 chars raises error."""
        adapter = ThangsAdapter(db_session)

        with pytest.raises(ValueError, match="at least 3 characters"):
            await adapter.search("ab")

        await adapter.close()

    @pytest.mark.asyncio
    async def test_search_caching(self, db_session, clear_cache):
        """Test search results are cached."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": "111", "name": "Test"}],
            "total": 1,
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        # First call - should hit API
        await adapter.search("test", limit=10)
        assert mock_client.get.call_count == 1

        # Second call - should use cache
        await adapter.search("test", limit=10)
        assert mock_client.get.call_count == 1  # Still 1

        await adapter.close()

    @pytest.mark.asyncio
    async def test_search_rate_limit(self, db_session, clear_cache):
        """Test rate limit error handling."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        with pytest.raises(ThangsRateLimitError) as exc_info:
            await adapter.search("test")

        assert exc_info.value.retry_after == 120

        await adapter.close()

    @pytest.mark.asyncio
    async def test_search_upstream_error(self, db_session, clear_cache):
        """Test upstream error handling."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        with pytest.raises(ThangsUpstreamError) as exc_info:
            await adapter.search("test")

        assert exc_info.value.status_code == 500

        await adapter.close()

    @pytest.mark.asyncio
    async def test_search_limit_clamping(self, db_session, clear_cache):
        """Test that limit is clamped to 1-50 range."""
        adapter = ThangsAdapter(db_session)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "total": 0}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        # Test limit > 50 is clamped
        await adapter.search("test", limit=100, use_cache=False)
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["limit"] == 50

        # Test limit < 1 is clamped
        await adapter.search("test", limit=0, use_cache=False)
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["limit"] == 1

        await adapter.close()


class TestThangsSearchAPI:
    """Tests for GET /api/v1/thangs/search endpoint."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory test database engine."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @pytest.fixture
    async def client(self, db_engine):
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

    @pytest.fixture
    def clear_cache(self):
        """Clear the search cache before and after each test."""
        _search_cache.clear()
        yield
        _search_cache.clear()

    @pytest.mark.asyncio
    async def test_search_endpoint_success(self, client, clear_cache):
        """Test search endpoint returns results."""
        with patch("app.api.routes.thangs.ThangsAdapter") as MockAdapter:
            mock_adapter = AsyncMock()
            mock_adapter.search = AsyncMock(
                return_value=ThangsSearchResponse(
                    results=[
                        ThangsSearchResult(
                            model_id="12345",
                            title="Test Model",
                            designer="TestDesigner",
                            thumbnail_url="https://example.com/thumb.jpg",
                            url="https://thangs.com/m/12345",
                        )
                    ],
                    total=1,
                )
            )
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            response = await client.get("/api/v1/thangs/search?q=test")

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["total"] == 1
            assert data["results"][0]["model_id"] == "12345"
            assert data["results"][0]["title"] == "Test Model"

    @pytest.mark.asyncio
    async def test_search_endpoint_query_too_short(self, client):
        """Test search endpoint rejects query < 3 chars."""
        response = await client.get("/api/v1/thangs/search?q=ab")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_search_endpoint_rate_limited(self, client, clear_cache):
        """Test search endpoint returns 429 on rate limit."""
        with patch("app.api.routes.thangs.ThangsAdapter") as MockAdapter:
            mock_adapter = AsyncMock()
            mock_adapter.search = AsyncMock(
                side_effect=ThangsRateLimitError(retry_after=60)
            )
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            response = await client.get("/api/v1/thangs/search?q=test")

            assert response.status_code == 429
            assert "Retry-After" in response.headers
            assert response.headers["Retry-After"] == "60"

    @pytest.mark.asyncio
    async def test_search_endpoint_upstream_error(self, client, clear_cache):
        """Test search endpoint returns 502 on upstream error."""
        with patch("app.api.routes.thangs.ThangsAdapter") as MockAdapter:
            mock_adapter = AsyncMock()
            mock_adapter.search = AsyncMock(
                side_effect=ThangsUpstreamError("API Error", 500)
            )
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            response = await client.get("/api/v1/thangs/search?q=test")

            assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_search_endpoint_custom_limit(self, client, clear_cache):
        """Test search endpoint respects limit parameter."""
        with patch("app.api.routes.thangs.ThangsAdapter") as MockAdapter:
            mock_adapter = AsyncMock()
            mock_adapter.search = AsyncMock(
                return_value=ThangsSearchResponse(results=[], total=0)
            )
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            response = await client.get("/api/v1/thangs/search?q=test&limit=25")

            assert response.status_code == 200
            mock_adapter.search.assert_called_once_with(query="test", limit=25)
