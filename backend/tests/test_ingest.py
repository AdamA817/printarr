"""Tests for IngestService - message ingestion and design detection."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Attachment,
    Channel,
    Design,
    DesignSource,
    DesignStatus,
    MediaType,
    MulticolorStatus,
    TelegramMessage,
)
from app.services.ingest import IngestService, DESIGN_EXTENSIONS


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
async def sample_channel(db_session):
    """Create a sample channel for testing."""
    channel = Channel(
        title="Test Channel",
        telegram_peer_id="test_peer_123",
        is_enabled=True,
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


# =============================================================================
# TelegramMessage Creation Tests
# =============================================================================


class TestIngestMessageCreatesRecord:
    """Tests that ingest_message creates TelegramMessage records correctly."""

    @pytest.mark.asyncio
    async def test_creates_telegram_message(self, db_session, sample_channel):
        """Test that ingest_message creates a TelegramMessage record."""
        service = IngestService(db_session)

        message_data = {
            "id": 123,
            "date": "2024-01-15T10:30:00Z",
            "text": "Hello world",
            "has_media": False,
            "attachments": [],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert message is not None
        assert message.telegram_message_id == 123
        assert message.channel_id == sample_channel.id
        assert message.caption_text == "Hello world"
        assert design_created is False

    @pytest.mark.asyncio
    async def test_parses_iso_date(self, db_session, sample_channel):
        """Test that ISO date string is parsed correctly."""
        service = IngestService(db_session)

        message_data = {
            "id": 124,
            "date": "2024-06-15T14:30:00+00:00",
            "text": "",
            "has_media": False,
            "attachments": [],
        }

        message, _ = await service.ingest_message(sample_channel, message_data)

        assert message.date_posted.year == 2024
        assert message.date_posted.month == 6
        assert message.date_posted.day == 15

    @pytest.mark.asyncio
    async def test_extracts_author_name(self, db_session, sample_channel):
        """Test that author name is extracted from sender."""
        service = IngestService(db_session)

        message_data = {
            "id": 125,
            "date": "2024-01-15T10:30:00Z",
            "text": "Test",
            "has_media": False,
            "attachments": [],
            "sender": {"name": "John Doe"},
        }

        message, _ = await service.ingest_message(sample_channel, message_data)

        assert message.author_name == "John Doe"

    @pytest.mark.asyncio
    async def test_normalizes_caption_text(self, db_session, sample_channel):
        """Test that caption text is normalized for search."""
        service = IngestService(db_session)

        message_data = {
            "id": 126,
            "date": "2024-01-15T10:30:00Z",
            "text": "Check out https://example.com! #3dprinting",
            "has_media": False,
            "attachments": [],
        }

        message, _ = await service.ingest_message(sample_channel, message_data)

        # Normalized text should have URL removed and be lowercase
        assert "example.com" not in message.caption_text_normalized
        assert message.caption_text_normalized.islower()


# =============================================================================
# Idempotency Tests
# =============================================================================


class TestIngestMessageIdempotent:
    """Tests that ingest_message is idempotent (no duplicates)."""

    @pytest.mark.asyncio
    async def test_same_message_twice_no_duplicate(self, db_session, sample_channel):
        """Test that ingesting the same message twice doesn't create duplicate."""
        service = IngestService(db_session)

        message_data = {
            "id": 200,
            "date": "2024-01-15T10:30:00Z",
            "text": "Test message",
            "has_media": False,
            "attachments": [],
        }

        # Ingest first time
        message1, _ = await service.ingest_message(sample_channel, message_data)
        await db_session.flush()

        # Ingest second time
        message2, _ = await service.ingest_message(sample_channel, message_data)

        # Should return existing message
        assert message1.id == message2.id

        # Verify only one message in DB
        result = await db_session.execute(
            select(TelegramMessage).where(
                TelegramMessage.telegram_message_id == 200
            )
        )
        messages = result.scalars().all()
        assert len(messages) == 1

    @pytest.mark.asyncio
    async def test_skips_message_without_id(self, db_session, sample_channel):
        """Test that message without ID is skipped."""
        service = IngestService(db_session)

        message_data = {
            "date": "2024-01-15T10:30:00Z",
            "text": "No ID message",
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert message is None
        assert design_created is False


# =============================================================================
# Attachment Processing Tests
# =============================================================================


class TestIngestMessageAttachments:
    """Tests that ingest_message creates Attachment records correctly."""

    @pytest.mark.asyncio
    async def test_creates_document_attachment(self, db_session, sample_channel):
        """Test that document attachments are created."""
        service = IngestService(db_session)

        message_data = {
            "id": 300,
            "date": "2024-01-15T10:30:00Z",
            "text": "Model file",
            "has_media": True,
            "attachments": [
                {
                    "type": "DOCUMENT",
                    "filename": "model.stl",
                    "mime_type": "application/octet-stream",
                    "size": 1024000,
                }
            ],
        }

        message, _ = await service.ingest_message(sample_channel, message_data)
        await db_session.flush()

        # Query attachments
        result = await db_session.execute(
            select(Attachment).where(Attachment.message_id == message.id)
        )
        attachments = result.scalars().all()

        assert len(attachments) == 1
        assert attachments[0].filename == "model.stl"
        assert attachments[0].ext == ".stl"
        assert attachments[0].media_type == MediaType.DOCUMENT
        assert attachments[0].is_candidate_design_file is True

    @pytest.mark.asyncio
    async def test_creates_photo_attachment(self, db_session, sample_channel):
        """Test that photo attachments are created."""
        service = IngestService(db_session)

        message_data = {
            "id": 301,
            "date": "2024-01-15T10:30:00Z",
            "text": "Photo only",
            "has_media": True,
            "attachments": [
                {
                    "type": "PHOTO",
                    "filename": None,
                    "size": 50000,
                }
            ],
        }

        message, _ = await service.ingest_message(sample_channel, message_data)
        await db_session.flush()

        result = await db_session.execute(
            select(Attachment).where(Attachment.message_id == message.id)
        )
        attachments = result.scalars().all()

        assert len(attachments) == 1
        assert attachments[0].media_type == MediaType.PHOTO
        assert attachments[0].is_candidate_design_file is False


# =============================================================================
# Design Detection Tests
# =============================================================================


class TestDesignDetection:
    """Tests for design file detection."""

    @pytest.mark.asyncio
    async def test_stl_creates_design(self, db_session, sample_channel):
        """Test that STL file creates a Design record."""
        service = IngestService(db_session)

        message_data = {
            "id": 400,
            "date": "2024-01-15T10:30:00Z",
            "text": "Cool Model",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "benchy.stl", "size": 500000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert design_created is True

        # Verify Design was created
        result = await db_session.execute(select(Design))
        designs = result.scalars().all()
        assert len(designs) == 1
        assert designs[0].canonical_title == "Cool Model"
        assert designs[0].status == DesignStatus.DISCOVERED

    @pytest.mark.asyncio
    async def test_3mf_creates_design(self, db_session, sample_channel):
        """Test that 3MF file creates a Design record."""
        service = IngestService(db_session)

        message_data = {
            "id": 401,
            "date": "2024-01-15T10:30:00Z",
            "text": "3MF Model",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "model.3mf", "size": 2000000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert design_created is True

    @pytest.mark.asyncio
    async def test_zip_creates_design(self, db_session, sample_channel):
        """Test that ZIP archive creates a Design record."""
        service = IngestService(db_session)

        message_data = {
            "id": 402,
            "date": "2024-01-15T10:30:00Z",
            "text": "Archive Model",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "models.zip", "size": 10000000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert design_created is True

    @pytest.mark.asyncio
    async def test_rar_creates_design(self, db_session, sample_channel):
        """Test that RAR archive creates a Design record."""
        service = IngestService(db_session)

        message_data = {
            "id": 403,
            "date": "2024-01-15T10:30:00Z",
            "text": "RAR Model",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "models.rar", "size": 8000000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert design_created is True

    @pytest.mark.asyncio
    async def test_7z_creates_design(self, db_session, sample_channel):
        """Test that 7Z archive creates a Design record."""
        service = IngestService(db_session)

        message_data = {
            "id": 404,
            "date": "2024-01-15T10:30:00Z",
            "text": "7Z Model",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "models.7z", "size": 5000000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert design_created is True

    @pytest.mark.asyncio
    async def test_photo_only_no_design(self, db_session, sample_channel):
        """Test that photo-only post does NOT create Design."""
        service = IngestService(db_session)

        message_data = {
            "id": 405,
            "date": "2024-01-15T10:30:00Z",
            "text": "Just a photo",
            "has_media": True,
            "attachments": [
                {"type": "PHOTO", "filename": None, "size": 50000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert message is not None
        assert design_created is False

        # Verify no Design was created
        result = await db_session.execute(select(Design))
        designs = result.scalars().all()
        assert len(designs) == 0

    @pytest.mark.asyncio
    async def test_text_only_no_design(self, db_session, sample_channel):
        """Test that text-only post does NOT create Design."""
        service = IngestService(db_session)

        message_data = {
            "id": 406,
            "date": "2024-01-15T10:30:00Z",
            "text": "Just text, no files",
            "has_media": False,
            "attachments": [],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert message is not None
        assert design_created is False


# =============================================================================
# Title Extraction Tests
# =============================================================================


class TestTitleExtraction:
    """Tests for _extract_title method."""

    @pytest.mark.asyncio
    async def test_title_from_first_line(self, db_session, sample_channel):
        """Test title is extracted from first non-empty caption line."""
        service = IngestService(db_session)

        message_data = {
            "id": 500,
            "date": "2024-01-15T10:30:00Z",
            "text": "My Cool Design\n\nThis is the description.",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "model.stl", "size": 1000}
            ],
        }

        await service.ingest_message(sample_channel, message_data)

        result = await db_session.execute(select(Design))
        design = result.scalar_one()
        assert design.canonical_title == "My Cool Design"

    @pytest.mark.asyncio
    async def test_title_skips_url_lines(self, db_session, sample_channel):
        """Test title extraction skips lines starting with http."""
        service = IngestService(db_session)

        message_data = {
            "id": 501,
            "date": "2024-01-15T10:30:00Z",
            "text": "https://example.com\nActual Title Here",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "model.stl", "size": 1000}
            ],
        }

        await service.ingest_message(sample_channel, message_data)

        result = await db_session.execute(select(Design))
        design = result.scalar_one()
        assert design.canonical_title == "Actual Title Here"

    @pytest.mark.asyncio
    async def test_title_skips_hashtag_only_lines(self, db_session, sample_channel):
        """Test title extraction skips lines that are only hashtags."""
        service = IngestService(db_session)

        message_data = {
            "id": 502,
            "date": "2024-01-15T10:30:00Z",
            "text": "#3dprinting #stl\nReal Title",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "model.stl", "size": 1000}
            ],
        }

        await service.ingest_message(sample_channel, message_data)

        result = await db_session.execute(select(Design))
        design = result.scalar_one()
        assert design.canonical_title == "Real Title"

    @pytest.mark.asyncio
    async def test_title_fallback_to_filename(self, db_session, sample_channel):
        """Test title falls back to filename when caption is empty."""
        service = IngestService(db_session)

        message_data = {
            "id": 503,
            "date": "2024-01-15T10:30:00Z",
            "text": "",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "Flexi Squirrel.stl", "size": 1000}
            ],
        }

        await service.ingest_message(sample_channel, message_data)

        result = await db_session.execute(select(Design))
        design = result.scalar_one()
        assert design.canonical_title == "Flexi Squirrel"

    @pytest.mark.asyncio
    async def test_title_fallback_to_date(self, db_session, sample_channel):
        """Test title falls back to date when no caption or good filename."""
        service = IngestService(db_session)

        message_data = {
            "id": 504,
            "date": "2024-03-20T10:30:00Z",
            "text": "",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "a.stl", "size": 1000}  # Too short
            ],
        }

        await service.ingest_message(sample_channel, message_data)

        result = await db_session.execute(select(Design))
        design = result.scalar_one()
        assert "2024-03-20" in design.canonical_title


# =============================================================================
# DesignSource Creation Tests
# =============================================================================


class TestDesignSourceCreation:
    """Tests that DesignSource is created correctly."""

    @pytest.mark.asyncio
    async def test_creates_design_source(self, db_session, sample_channel):
        """Test that ingesting design creates DesignSource linking to channel."""
        service = IngestService(db_session)

        message_data = {
            "id": 600,
            "date": "2024-01-15T10:30:00Z",
            "text": "Test Design",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "model.stl", "size": 1000}
            ],
        }

        await service.ingest_message(sample_channel, message_data)

        result = await db_session.execute(select(DesignSource))
        sources = result.scalars().all()

        assert len(sources) == 1
        assert sources[0].channel_id == sample_channel.id
        assert sources[0].source_rank == 1
        assert sources[0].is_preferred is True
        assert sources[0].caption_snapshot == "Test Design"


# =============================================================================
# Extension Detection Tests
# =============================================================================


class TestIsCandidateDesignFile:
    """Tests for _is_candidate_design_file method."""

    def test_all_design_extensions_detected(self):
        """Test all extensions in DESIGN_EXTENSIONS are detected."""
        service = IngestService.__new__(IngestService)

        for ext in DESIGN_EXTENSIONS:
            assert service._is_candidate_design_file(ext, f"file{ext}") is True

    def test_non_design_extension_not_detected(self):
        """Test non-design extensions are not detected."""
        service = IngestService.__new__(IngestService)

        assert service._is_candidate_design_file(".txt", "file.txt") is False
        assert service._is_candidate_design_file(".pdf", "file.pdf") is False
        assert service._is_candidate_design_file(".jpg", "file.jpg") is False

    def test_case_insensitive_extension(self):
        """Test extension detection is case insensitive."""
        service = IngestService.__new__(IngestService)

        assert service._is_candidate_design_file(".STL", "file.STL") is True
        assert service._is_candidate_design_file(".Stl", "file.Stl") is True


class TestExtractExtension:
    """Tests for _extract_extension method."""

    def test_extracts_simple_extension(self):
        """Test extracting simple extension."""
        service = IngestService.__new__(IngestService)

        assert service._extract_extension("model.stl") == ".stl"
        assert service._extract_extension("file.ZIP") == ".zip"

    def test_extracts_tar_gz_extension(self):
        """Test extracting .tar.gz double extension."""
        service = IngestService.__new__(IngestService)

        assert service._extract_extension("models.tar.gz") == ".tar.gz"

    def test_extracts_tgz_extension(self):
        """Test extracting .tgz extension."""
        service = IngestService.__new__(IngestService)

        assert service._extract_extension("models.tgz") == ".tgz"

    def test_no_extension_returns_none(self):
        """Test file without extension returns None."""
        service = IngestService.__new__(IngestService)

        assert service._extract_extension("noextension") is None
        assert service._extract_extension("") is None
        assert service._extract_extension(None) is None


# =============================================================================
# Split Archive Detection Tests (Issue #61)
# =============================================================================


class TestSplitArchiveDetection:
    """Tests for split archive pattern detection."""

    def test_detect_part_rar_pattern(self):
        """Test detection of .part1.rar, .part2.rar patterns."""
        service = IngestService.__new__(IngestService)

        result = service.detect_split_archive("Model.part1.rar")
        assert result is not None
        assert result.base_name == "Model"
        assert result.part_number == 1

        result = service.detect_split_archive("Model.part2.rar")
        assert result is not None
        assert result.base_name == "Model"
        assert result.part_number == 2

    def test_detect_part_padded_rar_pattern(self):
        """Test detection of .part01.rar, .part02.rar patterns."""
        service = IngestService.__new__(IngestService)

        result = service.detect_split_archive("Design.part01.rar")
        assert result is not None
        assert result.base_name == "Design"
        assert result.part_number == 1

        result = service.detect_split_archive("Design.part09.rar")
        assert result is not None
        assert result.base_name == "Design"
        assert result.part_number == 9

    def test_detect_7z_split_pattern(self):
        """Test detection of .001, .002 patterns (7z splits)."""
        service = IngestService.__new__(IngestService)

        result = service.detect_split_archive("Archive.7z.001")
        assert result is not None
        assert result.base_name == "Archive.7z"
        assert result.part_number == 1

        result = service.detect_split_archive("Archive.7z.005")
        assert result is not None
        assert result.part_number == 5

    def test_detect_rar_volume_pattern(self):
        """Test detection of .r00, .r01 patterns (RAR volumes)."""
        service = IngestService.__new__(IngestService)

        result = service.detect_split_archive("Model.r00")
        assert result is not None
        assert result.base_name == "Model"
        assert result.part_number == 0

        result = service.detect_split_archive("Model.r05")
        assert result is not None
        assert result.base_name == "Model"
        assert result.part_number == 5

    def test_non_split_archive_returns_none(self):
        """Test that non-split archives return None."""
        service = IngestService.__new__(IngestService)

        assert service.detect_split_archive("Model.rar") is None
        assert service.detect_split_archive("Model.zip") is None
        assert service.detect_split_archive("Model.7z") is None
        assert service.detect_split_archive("Model.stl") is None

    def test_case_insensitive_detection(self):
        """Test that pattern detection is case insensitive."""
        service = IngestService.__new__(IngestService)

        result = service.detect_split_archive("Model.PART1.RAR")
        assert result is not None
        assert result.part_number == 1

        result = service.detect_split_archive("Model.Part2.Rar")
        assert result is not None
        assert result.part_number == 2


class TestSplitArchiveIngestion:
    """Tests for split archive detection during ingestion."""

    @pytest.mark.asyncio
    async def test_split_archive_creates_design_with_metadata(
        self, db_session, sample_channel
    ):
        """Test that split archive creates design with split metadata."""
        service = IngestService(db_session)

        message_data = {
            "id": 700,
            "date": "2024-01-15T10:30:00Z",
            "text": "Batman Model",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "Batman.part1.rar", "size": 10000000}
            ],
        }

        message, design_created = await service.ingest_message(
            sample_channel, message_data
        )

        assert design_created is True

        result = await db_session.execute(select(Design))
        design = result.scalar_one()

        assert design.is_split_archive is True
        assert design.split_archive_base_name == "Batman"
        assert design.detected_parts == 1

    @pytest.mark.asyncio
    async def test_split_archive_merges_into_existing(
        self, db_session, sample_channel
    ):
        """Test that second part merges into existing split archive design."""
        service = IngestService(db_session)

        # Ingest first part
        message_data_1 = {
            "id": 701,
            "date": "2024-01-15T10:30:00Z",
            "text": "Superman Model Part 1",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "Superman.part1.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_1)

        # Ingest second part
        message_data_2 = {
            "id": 702,
            "date": "2024-01-15T10:35:00Z",
            "text": "Superman Model Part 2",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "Superman.part2.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_2)

        # Should only have one design
        result = await db_session.execute(select(Design))
        designs = result.scalars().all()
        assert len(designs) == 1

        design = designs[0]
        assert design.is_split_archive is True
        assert design.detected_parts == 2

        # Should have two sources
        result = await db_session.execute(
            select(DesignSource).where(DesignSource.design_id == design.id)
        )
        sources = result.scalars().all()
        assert len(sources) == 2

    @pytest.mark.asyncio
    async def test_split_archive_different_base_creates_separate(
        self, db_session, sample_channel
    ):
        """Test that different base names create separate designs."""
        service = IngestService(db_session)

        # Ingest first design part 1
        message_data_1 = {
            "id": 703,
            "date": "2024-01-15T10:30:00Z",
            "text": "Design A",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "DesignA.part1.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_1)

        # Ingest different design part 1
        message_data_2 = {
            "id": 704,
            "date": "2024-01-15T10:35:00Z",
            "text": "Design B",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "DesignB.part1.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_2)

        # Should have two separate designs
        result = await db_session.execute(select(Design))
        designs = result.scalars().all()
        assert len(designs) == 2

        base_names = {d.split_archive_base_name for d in designs}
        assert base_names == {"DesignA", "DesignB"}

    @pytest.mark.asyncio
    async def test_non_split_archive_is_not_merged(
        self, db_session, sample_channel
    ):
        """Test that non-split archives are not merged with split archives."""
        service = IngestService(db_session)

        # Ingest split archive
        message_data_1 = {
            "id": 705,
            "date": "2024-01-15T10:30:00Z",
            "text": "Model Part 1",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "Model.part1.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_1)

        # Ingest regular rar with same base name
        message_data_2 = {
            "id": 706,
            "date": "2024-01-15T10:35:00Z",
            "text": "Model Full",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "Model.rar", "size": 20000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_2)

        # Should have two separate designs
        result = await db_session.execute(select(Design))
        designs = result.scalars().all()
        assert len(designs) == 2

    @pytest.mark.asyncio
    async def test_split_archive_parts_out_of_order(
        self, db_session, sample_channel
    ):
        """Test that parts posted out of order are still merged."""
        service = IngestService(db_session)

        # Ingest part 2 first
        message_data_2 = {
            "id": 707,
            "date": "2024-01-15T10:30:00Z",
            "text": "Part 2 First",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "OutOfOrder.part2.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_2)

        # Ingest part 1 second
        message_data_1 = {
            "id": 708,
            "date": "2024-01-15T10:35:00Z",
            "text": "Part 1 Second",
            "has_media": True,
            "attachments": [
                {"type": "DOCUMENT", "filename": "OutOfOrder.part1.rar", "size": 10000000}
            ],
        }
        await service.ingest_message(sample_channel, message_data_1)

        # Should have one design with both sources
        result = await db_session.execute(select(Design))
        designs = result.scalars().all()
        assert len(designs) == 1

        design = designs[0]
        assert design.detected_parts == 2  # Max of 1 and 2

        # Both sources should be linked
        result = await db_session.execute(
            select(DesignSource).where(DesignSource.design_id == design.id)
        )
        sources = result.scalars().all()
        assert len(sources) == 2
