"""Tag service for managing design tags with hybrid taxonomy."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Design, DesignTag, Tag
from app.db.models.enums import TagSource

logger = get_logger(__name__)

# Maximum tags allowed per design
MAX_TAGS_PER_DESIGN = 20

# Predefined tag categories per DEC-028
TAG_CATEGORIES = {
    "Type": ["Figure", "Bust", "Diorama", "Miniature", "Cosplay", "Prop", "Tool", "Art"],
    "Theme": ["Sci-Fi", "Fantasy", "Horror", "Anime", "Gaming", "Movie", "Comic"],
    "Scale": ["28mm", "32mm", "75mm", "1:6", "1:10", "Life Size"],
    "Complexity": ["Simple", "Moderate", "Complex", "Expert"],
    "Print Type": ["FDM", "Resin", "Both"],
}


class TagError(Exception):
    """Error during tag operations."""
    pass


class TagService:
    """Service for managing tags and design-tag associations.

    Implements hybrid taxonomy with predefined categories and free-form tags.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the tag service.

        Args:
            db: The database session.
        """
        self.db = db

    async def get_or_create_tag(
        self,
        name: str,
        category: str | None = None,
        is_predefined: bool = False,
    ) -> Tag:
        """Get an existing tag or create a new one.

        Args:
            name: The tag name (will be normalized to lowercase).
            category: Optional category for the tag.
            is_predefined: Whether this is a predefined tag.

        Returns:
            The existing or newly created Tag.
        """
        normalized_name = self._normalize_name(name)

        # Try to find existing tag
        result = await self.db.execute(
            select(Tag).where(Tag.name == normalized_name)
        )
        tag = result.scalar_one_or_none()

        if tag:
            return tag

        # Create new tag
        tag = Tag(
            name=normalized_name,
            category=category,
            is_predefined=is_predefined,
            usage_count=0,
        )
        self.db.add(tag)
        await self.db.flush()

        logger.info(
            "tag_created",
            name=normalized_name,
            category=category,
            is_predefined=is_predefined,
        )

        return tag

    async def add_tag_to_design(
        self,
        design_id: str,
        tag_id: str,
        source: TagSource = TagSource.USER,
    ) -> DesignTag:
        """Add a tag to a design.

        Args:
            design_id: The design ID.
            tag_id: The tag ID to add.
            source: Source of the tag assignment.

        Returns:
            The DesignTag association.

        Raises:
            TagError: If max tags exceeded or tag already exists.
        """
        # Check if design already has this tag
        result = await self.db.execute(
            select(DesignTag).where(
                DesignTag.design_id == design_id,
                DesignTag.tag_id == tag_id,
            )
        )
        if result.scalar_one_or_none():
            raise TagError(f"Tag already assigned to design")

        # Check tag count (DesignTag has composite PK, count design_id)
        count_result = await self.db.execute(
            select(func.count(DesignTag.design_id)).where(
                DesignTag.design_id == design_id
            )
        )
        current_count = count_result.scalar() or 0

        if current_count >= MAX_TAGS_PER_DESIGN:
            raise TagError(f"Design already has maximum {MAX_TAGS_PER_DESIGN} tags")

        # Create association
        design_tag = DesignTag(
            design_id=design_id,
            tag_id=tag_id,
            source=source,
        )
        self.db.add(design_tag)

        # Increment usage count
        await self.db.execute(
            update(Tag)
            .where(Tag.id == tag_id)
            .values(usage_count=Tag.usage_count + 1)
        )

        await self.db.flush()

        logger.debug(
            "tag_added_to_design",
            design_id=design_id,
            tag_id=tag_id,
            source=source.value,
        )

        return design_tag

    async def remove_tag_from_design(self, design_id: str, tag_id: str) -> bool:
        """Remove a tag from a design.

        Args:
            design_id: The design ID.
            tag_id: The tag ID to remove.

        Returns:
            True if removed, False if not found.
        """
        # Find the association
        result = await self.db.execute(
            select(DesignTag).where(
                DesignTag.design_id == design_id,
                DesignTag.tag_id == tag_id,
            )
        )
        design_tag = result.scalar_one_or_none()

        if not design_tag:
            return False

        # Delete the association
        await self.db.delete(design_tag)

        # Decrement usage count (using case() for SQLite compatibility)
        await self.db.execute(
            update(Tag)
            .where(Tag.id == tag_id)
            .values(
                usage_count=case(
                    (Tag.usage_count > 0, Tag.usage_count - 1),
                    else_=0
                )
            )
        )

        await self.db.flush()

        logger.debug(
            "tag_removed_from_design",
            design_id=design_id,
            tag_id=tag_id,
        )

        return True

    async def get_design_tags(self, design_id: str) -> list[dict[str, Any]]:
        """Get all tags for a design.

        Args:
            design_id: The design ID.

        Returns:
            List of tag dictionaries with tag info and assignment source.
        """
        result = await self.db.execute(
            select(DesignTag, Tag)
            .join(Tag, DesignTag.tag_id == Tag.id)
            .where(DesignTag.design_id == design_id)
            .order_by(Tag.category.nullsfirst(), Tag.name)
        )
        rows = result.all()

        return [
            {
                "id": tag.id,
                "name": tag.name,
                "category": tag.category,
                "is_predefined": tag.is_predefined,
                "source": design_tag.source.value,
                "assigned_at": design_tag.created_at.isoformat() if design_tag.created_at else None,
            }
            for design_tag, tag in rows
        ]

    async def get_all_tags(
        self,
        category: str | None = None,
        include_zero_usage: bool = True,
    ) -> list[dict[str, Any]]:
        """Get all tags with usage counts.

        Args:
            category: Optional filter by category.
            include_zero_usage: Include tags with no usage.

        Returns:
            List of tag dictionaries.
        """
        query = select(Tag)

        if category:
            query = query.where(Tag.category == category)

        if not include_zero_usage:
            query = query.where(Tag.usage_count > 0)

        query = query.order_by(Tag.category.nullsfirst(), Tag.name)

        result = await self.db.execute(query)
        tags = result.scalars().all()

        return [
            {
                "id": tag.id,
                "name": tag.name,
                "category": tag.category,
                "is_predefined": tag.is_predefined,
                "usage_count": tag.usage_count,
            }
            for tag in tags
        ]

    async def get_tags_by_category(self) -> dict[str, list[dict[str, Any]]]:
        """Get all tags grouped by category.

        Returns:
            Dictionary of category -> list of tags.
        """
        result = await self.db.execute(
            select(Tag).order_by(Tag.category.nullsfirst(), Tag.name)
        )
        tags = result.scalars().all()

        categories: dict[str, list[dict[str, Any]]] = {}

        for tag in tags:
            cat_key = tag.category or "Uncategorized"
            if cat_key not in categories:
                categories[cat_key] = []

            categories[cat_key].append({
                "id": tag.id,
                "name": tag.name,
                "is_predefined": tag.is_predefined,
                "usage_count": tag.usage_count,
            })

        return categories

    async def search_tags(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search tags for autocomplete.

        Args:
            query: Search query string.
            limit: Maximum results to return.

        Returns:
            List of matching tag dictionaries.
        """
        normalized_query = self._normalize_name(query)

        result = await self.db.execute(
            select(Tag)
            .where(Tag.name.contains(normalized_query))
            .order_by(Tag.usage_count.desc(), Tag.name)
            .limit(limit)
        )
        tags = result.scalars().all()

        return [
            {
                "id": tag.id,
                "name": tag.name,
                "category": tag.category,
                "is_predefined": tag.is_predefined,
                "usage_count": tag.usage_count,
            }
            for tag in tags
        ]

    async def seed_predefined_tags(self) -> int:
        """Seed the database with predefined tags.

        Returns:
            Number of tags created.
        """
        created_count = 0

        for category, tag_names in TAG_CATEGORIES.items():
            for name in tag_names:
                normalized_name = self._normalize_name(name)

                # Check if already exists
                result = await self.db.execute(
                    select(Tag).where(Tag.name == normalized_name)
                )
                if result.scalar_one_or_none():
                    continue

                tag = Tag(
                    name=normalized_name,
                    category=category,
                    is_predefined=True,
                    usage_count=0,
                )
                self.db.add(tag)
                created_count += 1

        await self.db.flush()

        if created_count > 0:
            logger.info(
                "predefined_tags_seeded",
                count=created_count,
            )

        return created_count

    def _normalize_name(self, name: str) -> str:
        """Normalize a tag name to lowercase.

        Args:
            name: The tag name.

        Returns:
            Normalized lowercase name.
        """
        return name.strip().lower()
