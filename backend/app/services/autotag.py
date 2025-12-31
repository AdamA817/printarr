"""Auto-tagging service for extracting tags from captions and filenames."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.enums import TagSource
from app.services.tag import TagService

logger = get_logger(__name__)

# Stop words to exclude from auto-tagging
STOP_WORDS = {
    # Common words
    "the", "and", "for", "with", "from", "into", "this", "that",
    "all", "any", "are", "was", "were", "been", "being", "have",
    "has", "had", "having", "does", "did", "doing", "will", "would",
    "should", "could", "can", "may", "might", "must", "shall",
    "not", "but", "what", "which", "who", "whom", "how", "when",
    "where", "why", "only", "just", "also", "very", "too",
    # File-related
    "stl", "3mf", "obj", "step", "stp", "zip", "rar", "7z", "tar",
    "file", "files", "part", "parts", "model", "models",
    "print", "printer", "printed", "printing", "printable",
    "download", "free", "new", "version", "update", "updated",
    # Numbers and sizes
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "size", "small", "medium", "large", "big",
    # Common 3D printing terms that aren't useful as tags
    "layer", "layers", "infill", "support", "supports", "base",
    "preview", "thumbnail", "image", "images", "photo", "photos",
}

# Minimum tag length
MIN_TAG_LENGTH = 3

# Maximum tags to extract from a single source
MAX_TAGS_PER_SOURCE = 10


@dataclass
class ExtractedTag:
    """A tag extracted from text."""

    name: str
    source: TagSource


class AutoTagService:
    """Service for automatically extracting tags from captions and filenames."""

    def __init__(self, db: AsyncSession):
        """Initialize the auto-tag service.

        Args:
            db: Async database session.
        """
        self.db = db
        self.tag_service = TagService(db)

    async def auto_tag_design(
        self,
        design_id: str,
        caption: str | None = None,
        filenames: list[str] | None = None,
    ) -> dict[str, Any]:
        """Automatically extract and apply tags to a design.

        Args:
            design_id: The design ID.
            caption: Optional caption text.
            filenames: Optional list of filenames.

        Returns:
            Dict with extraction results.
        """
        extracted_tags: list[ExtractedTag] = []

        # Extract from caption
        if caption:
            caption_tags = self._extract_from_caption(caption)
            extracted_tags.extend(caption_tags)

        # Extract from filenames
        if filenames:
            for filename in filenames:
                filename_tags = self._extract_from_filename(filename)
                extracted_tags.extend(filename_tags)

        if not extracted_tags:
            return {"design_id": design_id, "tags_added": 0}

        # Deduplicate and limit
        seen_names = set()
        unique_tags = []
        for tag in extracted_tags:
            if tag.name not in seen_names:
                seen_names.add(tag.name)
                unique_tags.append(tag)
                if len(unique_tags) >= MAX_TAGS_PER_SOURCE * 2:
                    break

        # Apply tags
        tags_added = 0
        for extracted in unique_tags:
            try:
                # Get or create the tag
                tag = await self.tag_service.get_or_create_tag(extracted.name)

                # Add to design
                await self.tag_service.add_tag_to_design(
                    design_id=design_id,
                    tag_id=tag.id,
                    source=extracted.source,
                )
                tags_added += 1

            except Exception as e:
                # Tag already exists or other error, skip
                logger.debug(
                    "auto_tag_skipped",
                    tag_name=extracted.name,
                    error=str(e),
                )

        if tags_added > 0:
            logger.info(
                "auto_tags_applied",
                design_id=design_id,
                tags_added=tags_added,
            )

        return {
            "design_id": design_id,
            "tags_added": tags_added,
            "extracted": [t.name for t in unique_tags],
        }

    def _extract_from_caption(self, caption: str) -> list[ExtractedTag]:
        """Extract tags from caption text.

        Args:
            caption: Caption text.

        Returns:
            List of extracted tags.
        """
        tags = []

        # Extract hashtags
        hashtags = re.findall(r"#(\w+)", caption, re.UNICODE)
        for hashtag in hashtags[:MAX_TAGS_PER_SOURCE]:
            normalized = self._normalize_tag(hashtag)
            if normalized and normalized not in STOP_WORDS:
                tags.append(ExtractedTag(
                    name=normalized,
                    source=TagSource.AUTO_CAPTION,
                ))

        return tags

    def _extract_from_filename(self, filename: str) -> list[ExtractedTag]:
        """Extract tags from filename.

        Args:
            filename: The filename.

        Returns:
            List of extracted tags.
        """
        tags = []

        # Remove extension
        name_without_ext = re.sub(r"\.[^.]+$", "", filename)

        # Split on common separators
        parts = re.split(r"[_\-\s\.]+", name_without_ext)

        for part in parts[:MAX_TAGS_PER_SOURCE]:
            normalized = self._normalize_tag(part)
            if normalized and normalized not in STOP_WORDS:
                tags.append(ExtractedTag(
                    name=normalized,
                    source=TagSource.AUTO_FILENAME,
                ))

        return tags

    def _normalize_tag(self, tag: str) -> str | None:
        """Normalize a tag name.

        Args:
            tag: The tag to normalize.

        Returns:
            Normalized tag or None if invalid.
        """
        # Lowercase and strip
        normalized = tag.lower().strip()

        # Remove non-alphanumeric (except hyphens)
        normalized = re.sub(r"[^a-z0-9\-]", "", normalized)

        # Check minimum length
        if len(normalized) < MIN_TAG_LENGTH:
            return None

        return normalized
