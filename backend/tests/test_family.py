"""Tests for FamilyService - design variant grouping (DEC-044)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Design,
    DesignFamily,
    DesignFile,
    DesignStatus,
    DesignTag,
    FamilyDetectionMethod,
    FamilyTag,
    Tag,
    TagSource,
)
from app.services.family import FamilyInfo, FamilyService


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
async def sample_design(db_session):
    """Create a sample design for testing."""
    design = Design(
        canonical_title="Test Design",
        canonical_designer="Test Designer",
        status=DesignStatus.DISCOVERED,
    )
    db_session.add(design)
    await db_session.flush()
    return design


@pytest.fixture
async def sample_tag(db_session):
    """Create a sample tag for testing."""
    tag = Tag(
        name="test_tag",
        category="Type",
        is_predefined=True,
        usage_count=0,
    )
    db_session.add(tag)
    await db_session.flush()
    return tag


# =============================================================================
# FamilyInfo Extraction Tests
# =============================================================================


class TestExtractFamilyInfo:
    """Tests for extract_family_info method."""

    def test_extracts_color_variant(self, db_session):
        """Test extraction of color variants like _4Color."""
        service = FamilyService(db_session)

        result = service.extract_family_info("RoboTortoise_4Color")
        assert result.base_name == "RoboTortoise"
        assert result.variant_name == "4Color"

    def test_extracts_multicolor_variant(self, db_session):
        """Test extraction of multicolor variants."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Dragon_multicolor")
        assert result.base_name == "Dragon"
        assert result.variant_name == "multicolor"

    def test_extracts_version_variant(self, db_session):
        """Test extraction of version variants like _v2."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Benchy_v2")
        assert result.base_name == "Benchy"
        assert result.variant_name == "v2"

    def test_extracts_remix_variant(self, db_session):
        """Test extraction of remix variants."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Model_remix")
        assert result.base_name == "Model"
        assert result.variant_name == "remix"

    def test_extracts_size_variant(self, db_session):
        """Test extraction of size variants."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Figurine_large")
        assert result.base_name == "Figurine"
        assert result.variant_name == "large"

    def test_extracts_support_variant(self, db_session):
        """Test extraction of support variants."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Model_supported")
        assert result.base_name == "Model"
        assert result.variant_name == "supported"

    def test_extracts_part_variant(self, db_session):
        """Test extraction of part variants."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Assembly_Part1")
        assert result.base_name == "Assembly"
        assert result.variant_name == "Part1"

    def test_no_variant_pattern(self, db_session):
        """Test that non-variant titles return None for variant_name."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Simple Model Name")
        assert result.base_name == "Simple Model Name"
        assert result.variant_name is None

    def test_empty_title(self, db_session):
        """Test that empty titles are handled."""
        service = FamilyService(db_session)

        result = service.extract_family_info("")
        assert result.base_name == ""
        assert result.variant_name is None

    def test_case_insensitive_patterns(self, db_session):
        """Test that patterns match case-insensitively."""
        service = FamilyService(db_session)

        result = service.extract_family_info("Model_MULTICOLOR")
        assert result.base_name == "Model"
        assert result.variant_name == "MULTICOLOR"

        result = service.extract_family_info("Model_V2")
        assert result.base_name == "Model"
        assert result.variant_name == "V2"


# =============================================================================
# Designer Matching Tests
# =============================================================================


class TestDesignerMatching:
    """Tests for _designers_match helper method."""

    def test_exact_match(self, db_session):
        """Test that identical designers match."""
        service = FamilyService(db_session)

        assert service._designers_match("John Doe", "John Doe") is True

    def test_unknown_matches_any(self, db_session):
        """Test that Unknown matches any designer."""
        service = FamilyService(db_session)

        assert service._designers_match("Unknown", "John Doe") is True
        assert service._designers_match("John Doe", "Unknown") is True

    def test_different_designers_no_match(self, db_session):
        """Test that different designers don't match."""
        service = FamilyService(db_session)

        assert service._designers_match("John Doe", "Jane Doe") is False


# =============================================================================
# Family Creation Tests
# =============================================================================


class TestCreateFamily:
    """Tests for create_family method."""

    @pytest.mark.asyncio
    async def test_creates_family_with_name(self, db_session):
        """Test creating a family with a name."""
        service = FamilyService(db_session)

        family = await service.create_family(
            name="Test Family",
            designer="Test Designer",
        )

        assert family is not None
        assert family.canonical_name == "Test Family"
        assert family.canonical_designer == "Test Designer"
        assert family.detection_method == FamilyDetectionMethod.MANUAL

    @pytest.mark.asyncio
    async def test_creates_family_with_detection_method(self, db_session):
        """Test creating a family with a specific detection method."""
        service = FamilyService(db_session)

        family = await service.create_family(
            name="Test Family",
            detection_method=FamilyDetectionMethod.NAME_PATTERN,
            detection_confidence=0.8,
        )

        assert family.detection_method == FamilyDetectionMethod.NAME_PATTERN
        assert family.detection_confidence == 0.8

    @pytest.mark.asyncio
    async def test_creates_family_with_designs(self, db_session, sample_design):
        """Test creating a family with designs."""
        service = FamilyService(db_session)

        family = await service.create_family(
            name="Test Family",
            designs=[sample_design],
        )

        assert len(family.designs) == 1
        assert sample_design.family_id == family.id


# =============================================================================
# Add/Remove Design Tests
# =============================================================================


class TestAddToFamily:
    """Tests for add_to_family method."""

    @pytest.mark.asyncio
    async def test_adds_design_to_family(self, db_session, sample_design):
        """Test adding a design to a family."""
        service = FamilyService(db_session)

        family = await service.create_family(name="Test Family")
        await service.add_to_family(sample_design, family, "v2")

        assert sample_design.family_id == family.id
        assert sample_design.variant_name == "v2"

    @pytest.mark.asyncio
    async def test_extracts_variant_from_title(self, db_session):
        """Test that variant name is extracted from title if not provided."""
        service = FamilyService(db_session)

        design = Design(
            canonical_title="Model_multicolor",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add(design)
        await db_session.flush()

        family = await service.create_family(name="Model")
        await service.add_to_family(design, family)

        assert design.variant_name == "multicolor"

    @pytest.mark.asyncio
    async def test_updates_family_designer_from_design(self, db_session):
        """Test that adding design updates Unknown family designer."""
        service = FamilyService(db_session)

        design = Design(
            canonical_title="Model",
            canonical_designer="Known Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add(design)
        await db_session.flush()

        family = await service.create_family(name="Model", designer="Unknown")
        await service.add_to_family(design, family)

        assert family.canonical_designer == "Known Designer"


class TestRemoveFromFamily:
    """Tests for remove_from_family method."""

    @pytest.mark.asyncio
    async def test_removes_design_from_family(self, db_session, sample_design):
        """Test removing a design from a family."""
        service = FamilyService(db_session)

        family = await service.create_family(name="Test Family")
        await service.add_to_family(sample_design, family, "v1")
        assert sample_design.family_id == family.id

        await service.remove_from_family(sample_design)

        assert sample_design.family_id is None
        assert sample_design.variant_name is None

    @pytest.mark.asyncio
    async def test_remove_from_no_family(self, db_session, sample_design):
        """Test that removing design without family is a no-op."""
        service = FamilyService(db_session)

        assert sample_design.family_id is None
        await service.remove_from_family(sample_design)
        assert sample_design.family_id is None


# =============================================================================
# Dissolve Family Tests
# =============================================================================


class TestDissolveFamily:
    """Tests for dissolve_family method."""

    @pytest.mark.asyncio
    async def test_dissolves_family_removes_designs(self, db_session):
        """Test that dissolving family removes all designs from it."""
        service = FamilyService(db_session)

        # Create designs
        design1 = Design(
            canonical_title="Design 1",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        design2 = Design(
            canonical_title="Design 2",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add_all([design1, design2])
        await db_session.flush()

        # Create family with designs
        family = await service.create_family(name="Family", designs=[design1, design2])
        family_id = family.id

        # Dissolve
        count = await service.dissolve_family(family)

        assert count == 2
        assert design1.family_id is None
        assert design2.family_id is None

        # Family should be deleted
        result = await db_session.execute(
            select(DesignFamily).where(DesignFamily.id == family_id)
        )
        assert result.scalar_one_or_none() is None


# =============================================================================
# Group Designs Tests
# =============================================================================


class TestGroupDesigns:
    """Tests for group_designs method."""

    @pytest.mark.asyncio
    async def test_groups_designs_into_new_family(self, db_session):
        """Test grouping designs into a new family."""
        service = FamilyService(db_session)

        # Create designs
        design1 = Design(
            canonical_title="Design 1",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        design2 = Design(
            canonical_title="Design 2",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add_all([design1, design2])
        await db_session.flush()

        # Group
        family = await service.group_designs(
            design_ids=[design1.id, design2.id],
            family_name="New Family",
        )

        assert family.canonical_name == "New Family"
        assert design1.family_id == family.id
        assert design2.family_id == family.id

    @pytest.mark.asyncio
    async def test_groups_designs_into_existing_family(self, db_session):
        """Test grouping designs into an existing family."""
        service = FamilyService(db_session)

        # Create family
        family = await service.create_family(name="Existing Family")

        # Create design
        design = Design(
            canonical_title="Design",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add(design)
        await db_session.flush()

        # Group into existing
        result = await service.group_designs(
            design_ids=[design.id],
            family_id=family.id,
        )

        assert result.id == family.id
        assert design.family_id == family.id


# =============================================================================
# Tag Aggregation Tests
# =============================================================================


class TestAggregateTagS:
    """Tests for aggregate_tags method."""

    @pytest.mark.asyncio
    async def test_aggregates_tags_from_designs(self, db_session, sample_tag):
        """Test that tags are aggregated from designs to family."""
        service = FamilyService(db_session)

        # Create design with tag
        design = Design(
            canonical_title="Design",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add(design)
        await db_session.flush()

        # Add tag to design
        design_tag = DesignTag(
            design_id=design.id,
            tag_id=sample_tag.id,
            source=TagSource.USER,
        )
        db_session.add(design_tag)
        await db_session.flush()

        # Create family with design
        family = await service.create_family(name="Family", designs=[design])

        # Aggregate tags
        count = await service.aggregate_tags(family)

        assert count == 1

        # Verify family tag exists
        result = await db_session.execute(
            select(FamilyTag).where(FamilyTag.family_id == family.id)
        )
        family_tags = result.scalars().all()
        assert len(family_tags) == 1
        assert family_tags[0].tag_id == sample_tag.id

    @pytest.mark.asyncio
    async def test_skips_ai_tags(self, db_session):
        """Test that AI tags are not aggregated to family."""
        service = FamilyService(db_session)

        # Create tags
        user_tag = Tag(name="user_tag", usage_count=0)
        ai_tag = Tag(name="ai_tag", usage_count=0)
        db_session.add_all([user_tag, ai_tag])
        await db_session.flush()

        # Create design with both tags
        design = Design(
            canonical_title="Design",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add(design)
        await db_session.flush()

        db_session.add(DesignTag(design_id=design.id, tag_id=user_tag.id, source=TagSource.USER))
        db_session.add(DesignTag(design_id=design.id, tag_id=ai_tag.id, source=TagSource.AUTO_AI))
        await db_session.flush()

        # Create family
        family = await service.create_family(name="Family", designs=[design])

        # Aggregate
        count = await service.aggregate_tags(family)

        # Only user tag should be aggregated
        assert count == 1

        result = await db_session.execute(
            select(FamilyTag).where(FamilyTag.family_id == family.id)
        )
        family_tags = result.scalars().all()
        assert len(family_tags) == 1
        assert family_tags[0].tag_id == user_tag.id


# =============================================================================
# Find Family Candidates Tests
# =============================================================================


class TestFindFamilyCandidates:
    """Tests for find_family_candidates_by_name method."""

    @pytest.mark.asyncio
    async def test_finds_candidates_by_base_name(self, db_session):
        """Test finding candidates with matching base name."""
        service = FamilyService(db_session)

        # Create designs with matching base name
        design1 = Design(
            canonical_title="Dragon_v1",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        design2 = Design(
            canonical_title="Dragon_v2",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        design3 = Design(
            canonical_title="Unrelated",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add_all([design1, design2, design3])
        await db_session.flush()

        # Find candidates for design1
        candidates = await service.find_family_candidates_by_name(design1)

        # Should find design2 but not design3
        assert len(candidates) == 1
        assert candidates[0][0].id == design2.id
        assert candidates[0][1] == "v2"

    @pytest.mark.asyncio
    async def test_no_candidates_for_non_variant(self, db_session):
        """Test that non-variant designs return no candidates."""
        service = FamilyService(db_session)

        design = Design(
            canonical_title="Simple Model",
            canonical_designer="Designer",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add(design)
        await db_session.flush()

        candidates = await service.find_family_candidates_by_name(design)
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_respects_designer_match(self, db_session):
        """Test that candidates must have matching designer."""
        service = FamilyService(db_session)

        design1 = Design(
            canonical_title="Model_v1",
            canonical_designer="Designer A",
            status=DesignStatus.DISCOVERED,
        )
        design2 = Design(
            canonical_title="Model_v2",
            canonical_designer="Designer B",
            status=DesignStatus.DISCOVERED,
        )
        db_session.add_all([design1, design2])
        await db_session.flush()

        candidates = await service.find_family_candidates_by_name(design1)

        # Should not find design2 due to different designer
        assert len(candidates) == 0


# =============================================================================
# File Hash Overlap Tests
# =============================================================================


class TestDetectFamilyByFileOverlap:
    """Tests for detect_family_by_file_overlap method."""

    @pytest.mark.asyncio
    async def test_finds_overlapping_designs(self, db_session):
        """Test finding designs with overlapping file hashes."""
        service = FamilyService(db_session)

        # Create two designs
        design1 = Design(
            canonical_title="Design 1",
            canonical_designer="Designer",
            status=DesignStatus.DOWNLOADED,
        )
        design2 = Design(
            canonical_title="Design 2",
            canonical_designer="Designer",
            status=DesignStatus.DOWNLOADED,
        )
        db_session.add_all([design1, design2])
        await db_session.flush()

        # Add files with overlapping hashes
        # Design 1 has files A, B, C
        file1a = DesignFile(design_id=design1.id, relative_path="a.stl", sha256="hash_a")
        file1b = DesignFile(design_id=design1.id, relative_path="b.stl", sha256="hash_b")
        file1c = DesignFile(design_id=design1.id, relative_path="c.stl", sha256="hash_c")
        # Design 2 has files A, B, D (2/4 = 50% overlap)
        file2a = DesignFile(design_id=design2.id, relative_path="a.stl", sha256="hash_a")
        file2b = DesignFile(design_id=design2.id, relative_path="b.stl", sha256="hash_b")
        file2d = DesignFile(design_id=design2.id, relative_path="d.stl", sha256="hash_d")

        db_session.add_all([file1a, file1b, file1c, file2a, file2b, file2d])
        await db_session.flush()

        # Find overlaps for design1
        candidates = await service.detect_family_by_file_overlap(design1)

        assert len(candidates) == 1
        assert candidates[0][0].id == design2.id
        # Overlap ratio: 2 shared / 4 total unique = 0.5
        assert 0.4 <= candidates[0][1] <= 0.6

    @pytest.mark.asyncio
    async def test_excludes_high_overlap(self, db_session):
        """Test that very high overlap (>90%) is excluded (duplicates)."""
        service = FamilyService(db_session)

        design1 = Design(
            canonical_title="Design 1",
            canonical_designer="Designer",
            status=DesignStatus.DOWNLOADED,
        )
        design2 = Design(
            canonical_title="Design 2",
            canonical_designer="Designer",
            status=DesignStatus.DOWNLOADED,
        )
        db_session.add_all([design1, design2])
        await db_session.flush()

        # Same files = 100% overlap (duplicate)
        file1 = DesignFile(design_id=design1.id, relative_path="a.stl", sha256="hash_a")
        file2 = DesignFile(design_id=design2.id, relative_path="a.stl", sha256="hash_a")
        db_session.add_all([file1, file2])
        await db_session.flush()

        candidates = await service.detect_family_by_file_overlap(design1)

        # Should be excluded as it's a duplicate
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_excludes_low_overlap(self, db_session):
        """Test that very low overlap (<30%) is excluded."""
        service = FamilyService(db_session)

        design1 = Design(
            canonical_title="Design 1",
            canonical_designer="Designer",
            status=DesignStatus.DOWNLOADED,
        )
        design2 = Design(
            canonical_title="Design 2",
            canonical_designer="Designer",
            status=DesignStatus.DOWNLOADED,
        )
        db_session.add_all([design1, design2])
        await db_session.flush()

        # 1 shared out of 10 unique = 10% overlap
        for i in range(5):
            db_session.add(DesignFile(design_id=design1.id, relative_path=f"f{i}.stl", sha256=f"hash_{i}"))
        for i in range(5, 10):
            db_session.add(DesignFile(design_id=design2.id, relative_path=f"f{i}.stl", sha256=f"hash_{i}"))
        # One shared
        db_session.add(DesignFile(design_id=design2.id, relative_path="shared.stl", sha256="hash_0"))
        await db_session.flush()

        candidates = await service.detect_family_by_file_overlap(design1)

        # Should be excluded due to low overlap
        assert len(candidates) == 0


# =============================================================================
# List Families Tests
# =============================================================================


class TestListFamilies:
    """Tests for list_families method."""

    @pytest.mark.asyncio
    async def test_lists_families_with_pagination(self, db_session):
        """Test listing families with pagination."""
        service = FamilyService(db_session)

        # Create families
        for i in range(5):
            await service.create_family(name=f"Family {i}")

        families, total = await service.list_families(page=1, limit=3)

        assert len(families) == 3
        assert total == 5

    @pytest.mark.asyncio
    async def test_filters_by_designer(self, db_session):
        """Test filtering families by designer."""
        service = FamilyService(db_session)

        await service.create_family(name="Family A", designer="Designer A")
        await service.create_family(name="Family B", designer="Designer B")
        await service.create_family(name="Family C", designer="Designer A")

        families, total = await service.list_families(designer="Designer A")

        assert len(families) == 2
        assert total == 2


# =============================================================================
# Get Family Tests
# =============================================================================


class TestGetFamily:
    """Tests for get_family method."""

    @pytest.mark.asyncio
    async def test_gets_family_with_designs(self, db_session, sample_design):
        """Test getting a family with its designs loaded."""
        service = FamilyService(db_session)

        family = await service.create_family(name="Test Family", designs=[sample_design])

        result = await service.get_family(family.id)

        assert result is not None
        assert result.id == family.id
        assert len(result.designs) == 1

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent(self, db_session):
        """Test that nonexistent family returns None."""
        service = FamilyService(db_session)

        result = await service.get_family("nonexistent-id")

        assert result is None
