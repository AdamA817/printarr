"""Library import service for organizing design files."""

from __future__ import annotations

import asyncio
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    Design,
    DesignFile,
    DesignSource,
    DesignStatus,
    TelegramMessage,
)

logger = get_logger(__name__)

# Invalid characters for folder/file names across platforms
INVALID_CHARS = re.compile(r'[/\\:*?"<>|]')

# Default template if none configured
DEFAULT_TEMPLATE = "{designer}/{channel}/{title}"


class LibraryError(Exception):
    """Error during library import."""

    pass


class LibraryImportService:
    """Service for importing files from staging to the library."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def import_design(
        self,
        design_id: str,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Import a design's files from staging to the library.

        Args:
            design_id: The design ID.
            progress_callback: Optional callback for progress updates.

        Returns:
            Dictionary with import results.

        Raises:
            LibraryError: If import fails.
        """
        design = await self._get_design_with_files(design_id)
        if not design:
            raise LibraryError(f"Design not found: {design_id}")

        staging_dir = self._get_staging_dir(design_id)
        if not staging_dir.exists():
            raise LibraryError(f"Staging directory not found: {staging_dir}")

        design.status = DesignStatus.IMPORTING
        await self.db.flush()

        # Get template for this design
        template = await self._get_template(design)

        # Build library path from template
        library_path = await self._build_library_path(design, template)
        library_path.mkdir(parents=True, exist_ok=True)

        # Get all files in staging that need to be moved
        files = await self._get_design_files(design_id)
        total_files = len(files)

        if total_files == 0:
            logger.info("no_files_to_import", design_id=design_id)
            return {
                "design_id": design_id,
                "files_imported": 0,
                "library_path": str(library_path),
            }

        files_imported = 0
        total_bytes = 0

        for i, design_file in enumerate(files):
            source_path = staging_dir / design_file.relative_path
            if not source_path.exists():
                logger.warning(
                    "file_not_found_in_staging",
                    design_id=design_id,
                    relative_path=design_file.relative_path,
                )
                continue

            # Handle filename collision
            target_filename = self._resolve_collision(
                library_path, design_file.filename
            )
            target_path = library_path / target_filename

            # Move file
            await self._move_file(source_path, target_path)

            # Update DesignFile record with new location
            new_relative_path = str(target_path.relative_to(settings.library_path))
            design_file.relative_path = new_relative_path
            design_file.filename = target_filename
            await self.db.flush()

            files_imported += 1
            total_bytes += design_file.size_bytes or 0

            if progress_callback:
                progress_callback(i + 1, total_files)

        # Clean up empty staging directory
        await self._cleanup_staging(staging_dir)

        design.status = DesignStatus.ORGANIZED
        await self.db.flush()

        logger.info(
            "import_complete",
            design_id=design_id,
            files_imported=files_imported,
            total_bytes=total_bytes,
            library_path=str(library_path),
        )

        return {
            "design_id": design_id,
            "files_imported": files_imported,
            "total_bytes": total_bytes,
            "library_path": str(library_path),
        }

    async def _get_design_with_files(self, design_id: str) -> Design | None:
        """Get design with sources loaded for template resolution."""
        result = await self.db.execute(
            select(Design)
            .options(
                selectinload(Design.sources)
                .selectinload(DesignSource.message)
                .selectinload(TelegramMessage.channel)
            )
            .where(Design.id == design_id)
        )
        return result.scalar_one_or_none()

    async def _get_design_files(self, design_id: str) -> list[DesignFile]:
        """Get all DesignFile records for a design."""
        result = await self.db.execute(
            select(DesignFile).where(DesignFile.design_id == design_id)
        )
        return list(result.scalars().all())

    async def _get_template(self, design: Design) -> str:
        """Get the library template for a design.

        Order of precedence:
        1. Channel's library_template_override (if set)
        2. Global LIBRARY_TEMPLATE_GLOBAL setting
        3. Default template
        """
        # Check for channel override
        if design.sources:
            for source in design.sources:
                if source.message and source.message.channel:
                    channel = source.message.channel
                    if channel.library_template_override:
                        return channel.library_template_override
                    break

        # Use global setting or default
        return settings.library_template_global

    async def _build_library_path(self, design: Design, template: str) -> Path:
        """Build the library path from template and design data."""
        # Gather template variables
        now = datetime.utcnow()

        variables = {
            "designer": self._sanitize_name(design.display_designer or "Unknown"),
            "title": self._sanitize_name(design.display_title or "Untitled"),
            "date": now.strftime("%Y-%m-%d"),
            "year": str(now.year),
            "month": now.strftime("%m"),
        }

        # Get channel title from sources
        channel_title = "Unknown Channel"
        if design.sources:
            for source in design.sources:
                if source.message and source.message.channel:
                    channel_title = source.message.channel.title
                    break
        variables["channel"] = self._sanitize_name(channel_title)

        # Substitute template variables
        path_str = template
        for key, value in variables.items():
            path_str = path_str.replace(f"{{{key}}}", value)

        return settings.library_path / path_str

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use in file/folder paths.

        Replaces invalid characters with underscore.
        Trims whitespace and limits length.
        """
        # Replace invalid characters
        sanitized = INVALID_CHARS.sub("_", name)

        # Replace multiple underscores/spaces with single underscore
        sanitized = re.sub(r"[_\s]+", "_", sanitized)

        # Trim whitespace and underscores from ends
        sanitized = sanitized.strip("_ ")

        # Limit length (leave room for collision suffix)
        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        # Fallback for empty names
        if not sanitized:
            sanitized = "Unknown"

        return sanitized

    def _resolve_collision(self, directory: Path, filename: str) -> str:
        """Resolve filename collision by appending numeric suffix.

        Returns a filename that doesn't exist in the directory.
        """
        if not (directory / filename).exists():
            return filename

        # Split filename into base and extension
        path = Path(filename)
        base = path.stem
        ext = path.suffix

        # Try incrementing suffixes
        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            if not (directory / new_name).exists():
                return new_name
            counter += 1
            if counter > 9999:
                raise LibraryError(f"Too many filename collisions: {filename}")

    async def _move_file(self, source: Path, target: Path) -> None:
        """Move a file from source to target.

        Uses shutil.move for cross-filesystem support.
        """
        def _do_move() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_move)

        logger.debug(
            "file_moved",
            source=str(source),
            target=str(target),
        )

    async def _cleanup_staging(self, staging_dir: Path) -> None:
        """Remove the staging directory if empty.

        Recursively removes empty parent directories up to staging root.
        """
        def _do_cleanup() -> None:
            try:
                # Remove the design's staging directory
                if staging_dir.exists():
                    # Remove only if empty or only contains empty directories
                    self._remove_empty_dirs(staging_dir)
            except Exception as e:
                logger.warning(
                    "staging_cleanup_failed",
                    staging_dir=str(staging_dir),
                    error=str(e),
                )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_cleanup)

    def _remove_empty_dirs(self, path: Path) -> bool:
        """Recursively remove empty directories.

        Returns True if the directory was removed.
        """
        if not path.is_dir():
            return False

        # First, recursively clean subdirectories
        for child in list(path.iterdir()):
            if child.is_dir():
                self._remove_empty_dirs(child)

        # Then try to remove this directory (will fail if not empty)
        try:
            path.rmdir()
            logger.debug("removed_empty_dir", path=str(path))
            return True
        except OSError:
            return False

    def _get_staging_dir(self, design_id: str) -> Path:
        """Get the staging directory for a design."""
        return settings.staging_path / design_id
