"""Family service for managing design variant groupings.

Implements DEC-044: Design Families Architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import (
    Design,
    DesignFamily,
    DesignFile,
    DesignTag,
    FamilyDetectionMethod,
    FamilyTag,
    Tag,
    TagSource,
)

logger = get_logger(__name__)


# =============================================================================
# Variant Detection Patterns
# =============================================================================

# Patterns to extract base name and variant suffix from design titles
# Each pattern should have two groups: (base_name, variant_name)
VARIANT_PATTERNS = [
    # Color variants: RoboTortoise_4Color_Multicolor -> ("RoboTortoise", "4Color_Multicolor")
    re.compile(r"^(.+?)_(\d+color.*)$", re.IGNORECASE),
    re.compile(r"^(.+?)_(multicolor|single|dual|mono|filament).*$", re.IGNORECASE),

    # Version variants: Dragon_v2 -> ("Dragon", "v2")
    re.compile(r"^(.+?)_(v\d+|version\s*\d+)$", re.IGNORECASE),
    re.compile(r"^(.+?)_(remix|remixed|modified|mod).*$", re.IGNORECASE),

    # Size variants: Benchy_large -> ("Benchy", "large")
    re.compile(r"^(.+?)_(small|medium|large|xl|xxl|mini|micro|giant)$", re.IGNORECASE),
    re.compile(r"^(.+?)_(\d+mm|\d+cm|\d+%)$", re.IGNORECASE),

    # Support variants: Model_supported -> ("Model", "supported")
    re.compile(r"^(.+?)_(supported|nosupport|presupported|hollowed)$", re.IGNORECASE),

    # Part variants: Assembly_PartA -> ("Assembly", "PartA")
    re.compile(r"^(.+?)_(part\s*\d+|part\s*[a-z])$", re.IGNORECASE),
]


@dataclass
class FamilyInfo:
    """Extracted family information from a design title."""

    base_name: str
    variant_name: str | None


class FamilyError(Exception):
    """Error during family operations."""
    pass


class FamilyService:
    """Service for managing design families (variant groupings).

    Provides methods for:
    - Detecting family relationships from design titles
    - Detecting family relationships from file hash overlap
    - Creating and managing family groupings
    - Aggregating tags from variants to family level
    """

    def __init__(self, db: AsyncSession):
        """Initialize the family service.

        Args:
            db: The database session.
        """
        self.db = db

    # =========================================================================
    # Detection Methods
    # =========================================================================

    def extract_family_info(self, title: str) -> FamilyInfo:
        """Extract family base name and variant name from a design title.

        Attempts to match the title against known variant patterns to extract
        the base design name and the variant-specific suffix.

        Args:
            title: The design title to analyze.

        Returns:
            FamilyInfo with base_name and optional variant_name.
            If no pattern matches, returns the full title as base_name.
        """
        if not title:
            return FamilyInfo(base_name="", variant_name=None)

        # Normalize: strip and remove extra whitespace
        title = title.strip()

        for pattern in VARIANT_PATTERNS:
            match = pattern.match(title)
            if match:
                base_name = match.group(1).strip()
                variant_name = match.group(2).strip()
                return FamilyInfo(base_name=base_name, variant_name=variant_name)

        # No pattern matched - return full title as base name
        return FamilyInfo(base_name=title, variant_name=None)

    async def find_family_candidates_by_name(
        self,
        design: Design,
        exclude_design_ids: list[str] | None = None,
    ) -> list[tuple[Design, str]]:
        """Find designs that might be variants of the same family based on name.

        Extracts the base name from the design title and searches for other
        designs with matching base names and compatible designers.

        Args:
            design: The design to find family candidates for.
            exclude_design_ids: Optional list of design IDs to exclude.

        Returns:
            List of (Design, variant_name) tuples for potential family members.
        """
        info = self.extract_family_info(design.canonical_title)

        if not info.variant_name:
            # No variant pattern detected - not a candidate for family grouping
            return []

        # Search for other designs with matching base name
        query = select(Design).where(
            Design.canonical_title.ilike(f"{info.base_name}%"),
            Design.id != design.id,
        )

        if exclude_design_ids:
            query = query.where(Design.id.notin_(exclude_design_ids))

        result = await self.db.execute(query)
        candidates = result.scalars().all()

        matches = []
        for candidate in candidates:
            # Check designer compatibility
            if not self._designers_match(design.canonical_designer, candidate.canonical_designer):
                continue

            # Extract candidate's variant info
            candidate_info = self.extract_family_info(candidate.canonical_title)

            # Only include if base names match
            if candidate_info.base_name.lower() == info.base_name.lower():
                matches.append((candidate, candidate_info.variant_name or "Original"))

        return matches

    async def detect_family_by_file_overlap(
        self,
        design: Design,
        min_overlap_ratio: float = 0.3,
        max_overlap_ratio: float = 0.9,
    ) -> list[tuple[Design, float]]:
        """Find designs with partial file overlap (variants, not duplicates).

        Compares file hashes between the given design and other designs to find
        those that share 30-90% of files. This range indicates variants rather
        than duplicates (>90%) or unrelated designs (<30%).

        Args:
            design: The design to find variants for.
            min_overlap_ratio: Minimum file overlap ratio (default 0.3 = 30%).
            max_overlap_ratio: Maximum file overlap ratio (default 0.9 = 90%).

        Returns:
            List of (Design, overlap_ratio) tuples sorted by overlap descending.
        """
        # Get file hashes for this design
        result = await self.db.execute(
            select(DesignFile.sha256).where(
                DesignFile.design_id == design.id,
                DesignFile.sha256.isnot(None),
            )
        )
        design_hashes = set(result.scalars().all())

        if not design_hashes:
            return []

        # Find other designs with overlapping hashes
        subquery = (
            select(DesignFile.design_id, func.count(DesignFile.id).label("overlap_count"))
            .where(
                DesignFile.sha256.in_(design_hashes),
                DesignFile.design_id != design.id,
            )
            .group_by(DesignFile.design_id)
        ).subquery()

        result = await self.db.execute(
            select(Design, subquery.c.overlap_count)
            .join(subquery, Design.id == subquery.c.design_id)
            .options(selectinload(Design.files))
        )
        rows = result.all()

        matches = []
        for other_design, overlap_count in rows:
            # Check designer compatibility
            if not self._designers_match(design.canonical_designer, other_design.canonical_designer):
                continue

            # Calculate overlap ratio
            other_hashes = {f.sha256 for f in other_design.files if f.sha256}
            total_unique = len(design_hashes | other_hashes)
            if total_unique == 0:
                continue

            overlap_ratio = overlap_count / total_unique

            if min_overlap_ratio <= overlap_ratio <= max_overlap_ratio:
                matches.append((other_design, overlap_ratio))

        # Sort by overlap ratio descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    async def find_existing_family(
        self,
        base_name: str,
        designer: str,
    ) -> DesignFamily | None:
        """Find an existing family matching the base name and designer.

        Args:
            base_name: The family's canonical name to search for.
            designer: The designer name to match.

        Returns:
            The matching DesignFamily or None if not found.
        """
        result = await self.db.execute(
            select(DesignFamily).where(
                DesignFamily.canonical_name.ilike(base_name),
            )
        )
        families = result.scalars().all()

        for family in families:
            if self._designers_match(designer, family.canonical_designer):
                return family

        return None

    # =========================================================================
    # Family Management Methods
    # =========================================================================

    async def create_family(
        self,
        name: str,
        designer: str = "Unknown",
        designs: list[Design] | None = None,
        detection_method: FamilyDetectionMethod = FamilyDetectionMethod.MANUAL,
        detection_confidence: float | None = None,
    ) -> DesignFamily:
        """Create a new design family.

        Args:
            name: The canonical family name.
            designer: The canonical designer name.
            designs: Optional list of designs to add to the family.
            detection_method: How the family was detected.
            detection_confidence: Confidence score for automated detection.

        Returns:
            The newly created DesignFamily.
        """
        family = DesignFamily(
            canonical_name=name,
            canonical_designer=designer,
            detection_method=detection_method,
            detection_confidence=detection_confidence,
        )
        self.db.add(family)
        await self.db.flush()

        logger.info(
            "family_created",
            family_id=family.id,
            name=name,
            designer=designer,
            detection_method=detection_method.value,
        )

        # Add designs if provided
        if designs:
            for design in designs:
                await self.add_to_family(design, family)

        return family

    async def add_to_family(
        self,
        design: Design,
        family: DesignFamily,
        variant_name: str | None = None,
    ) -> None:
        """Add a design to a family.

        If variant_name is not provided, attempts to extract it from the
        design's title using pattern matching.

        Args:
            design: The design to add.
            family: The family to add the design to.
            variant_name: Optional explicit variant name.
        """
        # Extract variant name if not provided
        if variant_name is None:
            info = self.extract_family_info(design.canonical_title)
            variant_name = info.variant_name

        # Update design
        design.family_id = family.id
        design.variant_name = variant_name

        # Update family's canonical designer if current design has a known designer
        # and family designer is Unknown
        if family.canonical_designer == "Unknown" and design.canonical_designer != "Unknown":
            family.canonical_designer = design.canonical_designer

        await self.db.flush()

        logger.info(
            "design_added_to_family",
            design_id=design.id,
            family_id=family.id,
            variant_name=variant_name,
        )

    async def remove_from_family(self, design: Design) -> None:
        """Remove a design from its family.

        Args:
            design: The design to remove from its family.
        """
        if not design.family_id:
            return

        family_id = design.family_id
        design.family_id = None
        design.variant_name = None

        await self.db.flush()

        logger.info(
            "design_removed_from_family",
            design_id=design.id,
            family_id=family_id,
        )

    async def dissolve_family(self, family: DesignFamily) -> int:
        """Dissolve a family, removing all designs from it.

        Args:
            family: The family to dissolve.

        Returns:
            Number of designs that were removed from the family.
        """
        # Get all designs in family
        result = await self.db.execute(
            select(Design).where(Design.family_id == family.id)
        )
        designs = result.scalars().all()

        count = len(designs)

        # Remove all designs from family
        for design in designs:
            design.family_id = None
            design.variant_name = None

        # Delete the family
        await self.db.delete(family)
        await self.db.flush()

        logger.info(
            "family_dissolved",
            family_id=family.id,
            designs_removed=count,
        )

        return count

    async def group_designs(
        self,
        design_ids: list[str],
        family_name: str | None = None,
        family_id: str | None = None,
    ) -> DesignFamily:
        """Group multiple designs into a family.

        Either creates a new family or adds to an existing one.

        Args:
            design_ids: List of design IDs to group.
            family_name: Optional name for new family (required if family_id not provided).
            family_id: Optional existing family ID to add designs to.

        Returns:
            The family the designs were added to.

        Raises:
            FamilyError: If neither family_name nor family_id is provided,
                         or if designs/family not found.
        """
        if not family_id and not family_name:
            raise FamilyError("Either family_name or family_id must be provided")

        # Get designs
        result = await self.db.execute(
            select(Design).where(Design.id.in_(design_ids))
        )
        designs = result.scalars().all()

        if not designs:
            raise FamilyError("No designs found with the provided IDs")

        if family_id:
            # Add to existing family
            family = await self.db.get(DesignFamily, family_id)
            if not family:
                raise FamilyError(f"Family {family_id} not found")
        else:
            # Create new family
            # Use designer from first design that has a known designer
            designer = "Unknown"
            for design in designs:
                if design.canonical_designer != "Unknown":
                    designer = design.canonical_designer
                    break

            family = await self.create_family(
                name=family_name,
                designer=designer,
                detection_method=FamilyDetectionMethod.MANUAL,
            )

        # Add all designs to family
        for design in designs:
            await self.add_to_family(design, family)

        # Aggregate tags from all designs
        await self.aggregate_tags(family)

        return family

    async def aggregate_tags(self, family: DesignFamily) -> int:
        """Aggregate tags from all variants to the family level.

        Per DEC-044: Collect manual + Telegram tags from all variants.
        AI tags are not inherited - they should be regenerated at family level.

        Args:
            family: The family to aggregate tags for.

        Returns:
            Number of tags added to the family.
        """
        # Get all designs in family
        result = await self.db.execute(
            select(Design.id).where(Design.family_id == family.id)
        )
        design_ids = [row[0] for row in result.all()]

        if not design_ids:
            return 0

        # Get all tags from designs (excluding AI tags)
        result = await self.db.execute(
            select(DesignTag.tag_id, DesignTag.source).where(
                DesignTag.design_id.in_(design_ids),
                DesignTag.source != TagSource.AUTO_AI,
            )
        )
        design_tag_data = result.all()

        # Get existing family tags
        result = await self.db.execute(
            select(FamilyTag.tag_id).where(FamilyTag.family_id == family.id)
        )
        existing_tag_ids = set(row[0] for row in result.all())

        # Add new tags to family
        added_count = 0
        for tag_id, source in design_tag_data:
            if tag_id not in existing_tag_ids:
                family_tag = FamilyTag(
                    family_id=family.id,
                    tag_id=tag_id,
                    source=source,
                )
                self.db.add(family_tag)
                existing_tag_ids.add(tag_id)
                added_count += 1

        await self.db.flush()

        if added_count > 0:
            logger.info(
                "family_tags_aggregated",
                family_id=family.id,
                tags_added=added_count,
            )

        return added_count

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_family(self, family_id: str) -> DesignFamily | None:
        """Get a family by ID with its designs loaded.

        Args:
            family_id: The family ID.

        Returns:
            The DesignFamily with designs loaded, or None if not found.
        """
        result = await self.db.execute(
            select(DesignFamily)
            .where(DesignFamily.id == family_id)
            .options(
                selectinload(DesignFamily.designs),
                selectinload(DesignFamily.family_tags).selectinload(FamilyTag.tag),
            )
        )
        return result.scalar_one_or_none()

    async def list_families(
        self,
        page: int = 1,
        limit: int = 50,
        designer: str | None = None,
    ) -> tuple[list[DesignFamily], int]:
        """List families with pagination.

        Args:
            page: Page number (1-indexed).
            limit: Items per page.
            designer: Optional filter by designer.

        Returns:
            Tuple of (families list, total count).
        """
        # Build base query
        query = select(DesignFamily).options(
            selectinload(DesignFamily.designs),
        )

        if designer:
            query = query.where(DesignFamily.canonical_designer.ilike(f"%{designer}%"))

        # Get total count
        count_query = select(func.count(DesignFamily.id))
        if designer:
            count_query = count_query.where(DesignFamily.canonical_designer.ilike(f"%{designer}%"))

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get page
        offset = (page - 1) * limit
        query = query.order_by(DesignFamily.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        families = result.scalars().all()

        return list(families), total

    async def get_family_tags(self, family_id: str) -> list[dict[str, Any]]:
        """Get all tags for a family.

        Args:
            family_id: The family ID.

        Returns:
            List of tag dictionaries with tag info and source.
        """
        result = await self.db.execute(
            select(FamilyTag, Tag)
            .join(Tag, FamilyTag.tag_id == Tag.id)
            .where(FamilyTag.family_id == family_id)
            .order_by(Tag.category.nullsfirst(), Tag.name)
        )
        rows = result.all()

        return [
            {
                "id": tag.id,
                "name": tag.name,
                "category": tag.category,
                "is_predefined": tag.is_predefined,
                "source": family_tag.source.value,
                "assigned_at": family_tag.created_at.isoformat() if family_tag.created_at else None,
            }
            for family_tag, tag in rows
        ]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _designers_match(self, designer_a: str, designer_b: str) -> bool:
        """Check if two designers match for family grouping.

        Per DEC-044: Designers must match, with one exception:
        "Unknown" can match with any known designer.

        Args:
            designer_a: First designer name.
            designer_b: Second designer name.

        Returns:
            True if designers are compatible for family grouping.
        """
        if designer_a == designer_b:
            return True
        if designer_a == "Unknown" or designer_b == "Unknown":
            return True
        return False
