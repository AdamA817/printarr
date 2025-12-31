"""Tests for PreviewService - preview management and auto-selection."""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Design
from app.db.models.enums import PreviewKind, PreviewSource
from app.db.models.preview_asset import PreviewAsset
from app.services.preview import SOURCE_PRIORITY, PreviewService


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
def mock_session_maker(db_engine):
    """Create a mock session maker that uses the test database."""
    test_session_maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    @asynccontextmanager
    async def mock_maker():
        async with test_session_maker() as session:
            yield session

    return mock_maker


@pytest.fixture
async def sample_design(db_session):
    """Create a sample design for testing."""
    design = Design(
        canonical_title="Test Design",
        canonical_designer="Test Designer",
    )
    db_session.add(design)
    await db_session.commit()
    await db_session.refresh(design)
    return design


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# Tests for SOURCE_PRIORITY
# =============================================================================


class TestSourcePriority:
    """Tests for source priority ordering."""

    def test_priority_order(self):
        """Test that priority order matches DEC-032."""
        # Lower number = higher priority
        assert SOURCE_PRIORITY[PreviewSource.RENDERED] < SOURCE_PRIORITY[PreviewSource.EMBEDDED_3MF]
        assert SOURCE_PRIORITY[PreviewSource.EMBEDDED_3MF] < SOURCE_PRIORITY[PreviewSource.ARCHIVE]
        assert SOURCE_PRIORITY[PreviewSource.ARCHIVE] < SOURCE_PRIORITY[PreviewSource.THANGS]
        assert SOURCE_PRIORITY[PreviewSource.THANGS] < SOURCE_PRIORITY[PreviewSource.TELEGRAM]

    def test_all_sources_have_priority(self):
        """Test that all preview sources have a priority defined."""
        for source in PreviewSource:
            assert source in SOURCE_PRIORITY


# =============================================================================
# Tests for auto_select_primary
# =============================================================================


class TestAutoSelectPrimary:
    """Tests for auto-selecting primary preview."""

    async def test_no_previews_returns_none(self, db_session, sample_design):
        """Test that no previews returns None."""
        service = PreviewService(db_session)
        result = await service.auto_select_primary(sample_design.id)
        assert result is None

    async def test_single_preview_becomes_primary(self, db_session, sample_design):
        """Test that a single preview becomes primary."""
        preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/test.jpg",
            is_primary=False,
        )
        db_session.add(preview)
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.auto_select_primary(sample_design.id)
        await db_session.commit()

        assert result == preview.id
        # Expire and refresh to see DB changes
        db_session.expire(preview)
        await db_session.refresh(preview)
        assert preview.is_primary is True

    async def test_selects_highest_priority_source(self, db_session, sample_design):
        """Test that highest priority source is selected."""
        # Create previews with different sources
        telegram_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/test.jpg",
            is_primary=False,
        )
        rendered_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.RENDERED,
            kind=PreviewKind.THUMBNAIL,
            file_path="rendered/test.png",
            is_primary=False,
        )
        archive_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.ARCHIVE,
            kind=PreviewKind.THUMBNAIL,
            file_path="archive/test.png",
            is_primary=False,
        )
        db_session.add_all([telegram_preview, rendered_preview, archive_preview])
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.auto_select_primary(sample_design.id)
        await db_session.commit()

        # RENDERED has highest priority
        assert result == rendered_preview.id
        db_session.expire(rendered_preview)
        await db_session.refresh(rendered_preview)
        assert rendered_preview.is_primary is True

        # Others should not be primary
        db_session.expire(telegram_preview)
        db_session.expire(archive_preview)
        await db_session.refresh(telegram_preview)
        await db_session.refresh(archive_preview)
        assert telegram_preview.is_primary is False
        assert archive_preview.is_primary is False

    async def test_unsets_previous_primary(self, db_session, sample_design):
        """Test that previous primary is unset when new one is selected."""
        # Create a primary preview
        old_primary = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/old.jpg",
            is_primary=True,
        )
        # Create a higher priority preview
        new_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.RENDERED,
            kind=PreviewKind.THUMBNAIL,
            file_path="rendered/new.png",
            is_primary=False,
        )
        db_session.add_all([old_primary, new_preview])
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.auto_select_primary(sample_design.id)
        await db_session.commit()

        # New preview should be primary
        assert result == new_preview.id
        db_session.expire(new_preview)
        await db_session.refresh(new_preview)
        assert new_preview.is_primary is True

        # Old preview should no longer be primary
        db_session.expire(old_primary)
        await db_session.refresh(old_primary)
        assert old_primary.is_primary is False

    async def test_embedded_3mf_beats_archive(self, db_session, sample_design):
        """Test that EMBEDDED_3MF has higher priority than ARCHIVE."""
        archive_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.ARCHIVE,
            kind=PreviewKind.THUMBNAIL,
            file_path="archive/test.png",
            is_primary=False,
        )
        embedded_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.EMBEDDED_3MF,
            kind=PreviewKind.THUMBNAIL,
            file_path="3mf/thumbnail.png",
            is_primary=False,
        )
        db_session.add_all([archive_preview, embedded_preview])
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.auto_select_primary(sample_design.id)
        await db_session.commit()

        assert result == embedded_preview.id
        db_session.expire(embedded_preview)
        await db_session.refresh(embedded_preview)
        assert embedded_preview.is_primary is True

    async def test_thangs_beats_telegram(self, db_session, sample_design):
        """Test that THANGS has higher priority than TELEGRAM."""
        telegram_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/test.jpg",
            is_primary=False,
        )
        thangs_preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.THANGS,
            kind=PreviewKind.THUMBNAIL,
            file_path="thangs/test.jpg",
            is_primary=False,
        )
        db_session.add_all([telegram_preview, thangs_preview])
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.auto_select_primary(sample_design.id)
        await db_session.commit()

        assert result == thangs_preview.id
        db_session.expire(thangs_preview)
        await db_session.refresh(thangs_preview)
        assert thangs_preview.is_primary is True


# =============================================================================
# Tests for set_primary
# =============================================================================


class TestSetPrimary:
    """Tests for manually setting primary preview."""

    async def test_set_primary_success(self, db_session, sample_design):
        """Test setting a preview as primary."""
        preview1 = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/test1.jpg",
            is_primary=True,
        )
        preview2 = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/test2.jpg",
            is_primary=False,
        )
        db_session.add_all([preview1, preview2])
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.set_primary(preview2.id)

        assert result is True
        await db_session.refresh(preview1)
        await db_session.refresh(preview2)
        assert preview1.is_primary is False
        assert preview2.is_primary is True

    async def test_set_primary_not_found(self, db_session):
        """Test setting primary for non-existent preview."""
        service = PreviewService(db_session)
        result = await service.set_primary("non-existent-id")
        assert result is False


# =============================================================================
# Tests for update_sort_order
# =============================================================================


class TestUpdateSortOrder:
    """Tests for updating preview sort order."""

    async def test_update_sort_order_success(self, db_session, sample_design):
        """Test updating sort order."""
        preview = PreviewAsset(
            design_id=sample_design.id,
            source=PreviewSource.TELEGRAM,
            kind=PreviewKind.THUMBNAIL,
            file_path="telegram/test.jpg",
            sort_order=0,
        )
        db_session.add(preview)
        await db_session.commit()

        service = PreviewService(db_session)
        result = await service.update_sort_order(preview.id, 5)
        await db_session.commit()

        assert result is True
        db_session.expire(preview)
        await db_session.refresh(preview)
        assert preview.sort_order == 5

    async def test_update_sort_order_not_found(self, db_session):
        """Test updating sort order for non-existent preview."""
        service = PreviewService(db_session)
        result = await service.update_sort_order("non-existent-id", 5)
        assert result is False
