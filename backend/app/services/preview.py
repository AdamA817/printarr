"""Preview service for managing design preview images.

Handles storage, retrieval, and management of preview images from various sources:
- Telegram post images
- Archive-extracted previews
- Thangs cached images
- 3MF embedded thumbnails
- Rendered STL previews

Per DEC-027, images are stored in /cache/previews/ with subdirectories by source.
Per DEC-032, primary preview is auto-selected based on source priority.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from PIL import Image
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Design, PreviewAsset
from app.db.models.enums import PreviewKind, PreviewSource
from app.db.session import async_session_maker

logger = get_logger(__name__)

# Source priority for auto-selecting primary preview (per DEC-032)
# Lower number = higher priority
SOURCE_PRIORITY = {
    PreviewSource.RENDERED: 1,
    PreviewSource.EMBEDDED_3MF: 2,
    PreviewSource.ARCHIVE: 3,
    PreviewSource.THANGS: 4,
    PreviewSource.TELEGRAM: 5,
}


class PreviewError(Exception):
    """Error during preview operations."""

    pass


class PreviewService:
    """Service for managing preview images.

    Handles file storage, database records, and cleanup.
    """

    def __init__(self, db: AsyncSession | None = None):
        """Initialize the preview service.

        Args:
            db: Optional database session. If not provided, creates sessions as needed.
        """
        self.db = db
        self._previews_root = settings.cache_path / "previews"

    async def ensure_directories(self) -> None:
        """Ensure preview directory structure exists.

        Creates:
        /cache/previews/
        ├── telegram/
        ├── archive/
        ├── thangs/
        ├── embedded/
        └── rendered/
        """
        subdirs = ["telegram", "archive", "thangs", "embedded", "rendered"]

        def _create_dirs() -> None:
            self._previews_root.mkdir(parents=True, exist_ok=True)
            for subdir in subdirs:
                (self._previews_root / subdir).mkdir(exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_dirs)

        logger.debug("preview_directories_ensured", root=str(self._previews_root))

    def get_source_dir(self, source: PreviewSource) -> Path:
        """Get the directory for a preview source type."""
        source_to_dir = {
            PreviewSource.TELEGRAM: "telegram",
            PreviewSource.ARCHIVE: "archive",
            PreviewSource.THANGS: "thangs",
            PreviewSource.EMBEDDED_3MF: "embedded",
            PreviewSource.RENDERED: "rendered",
        }
        return self._previews_root / source_to_dir[source]

    async def save_preview(
        self,
        design_id: str,
        source: PreviewSource,
        image_data: bytes,
        filename: str | None = None,
        kind: PreviewKind = PreviewKind.THUMBNAIL,
        telegram_file_id: str | None = None,
        source_attachment_id: str | None = None,
    ) -> PreviewAsset:
        """Save a preview image and create a database record.

        Args:
            design_id: The design this preview belongs to
            source: Where the preview came from (TELEGRAM, ARCHIVE, etc.)
            image_data: Raw image bytes
            filename: Original filename (optional)
            kind: Type of preview (THUMBNAIL, FULL, GALLERY)
            telegram_file_id: Telegram file ID for later reference
            source_attachment_id: ID of the source attachment

        Returns:
            The created PreviewAsset record
        """
        # Generate unique filename
        ext = ".jpg"
        if filename:
            ext = Path(filename).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            ext = ".jpg"

        unique_filename = f"{uuid.uuid4()}{ext}"

        # Determine storage path
        source_dir = self.get_source_dir(source) / design_id
        file_path = source_dir / unique_filename
        relative_path = str(file_path.relative_to(self._previews_root))

        # Get image dimensions
        width, height = await self._get_image_dimensions(image_data)

        # Save file
        await self._save_file(file_path, image_data)

        # Create database record
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            preview = PreviewAsset(
                design_id=design_id,
                source=source,
                kind=kind,
                file_path=relative_path,
                file_size=len(image_data),
                original_filename=filename,
                width=width,
                height=height,
                telegram_file_id=telegram_file_id,
                source_attachment_id=source_attachment_id,
                is_primary=False,
                sort_order=0,
            )
            db.add(preview)

            if not self.db:
                await db.commit()
                await db.refresh(preview)

            logger.info(
                "preview_saved",
                design_id=design_id,
                source=source.value,
                path=relative_path,
                size=len(image_data),
            )

            return preview

        finally:
            if not self.db:
                await db.close()

    async def _save_file(self, path: Path, data: bytes) -> None:
        """Save data to a file, creating directories as needed."""

        def _do_save() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_save)

        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def _get_image_dimensions(self, image_data: bytes) -> tuple[int | None, int | None]:
        """Get image dimensions from bytes."""

        def _get_dims() -> tuple[int | None, int | None]:
            try:
                from io import BytesIO

                img = Image.open(BytesIO(image_data))
                return img.width, img.height
            except Exception:
                return None, None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_dims)

    async def get_preview_path(self, preview_id: str) -> Path | None:
        """Get the absolute path to a preview file.

        Args:
            preview_id: The preview asset ID

        Returns:
            Absolute path to the file, or None if not found
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            preview = await db.get(PreviewAsset, preview_id)
            if not preview:
                return None

            abs_path = self._previews_root / preview.file_path
            if abs_path.exists():
                return abs_path
            return None

        finally:
            if not self.db:
                await db.close()

    async def delete_preview(self, preview_id: str) -> bool:
        """Delete a preview and its file.

        Args:
            preview_id: The preview asset ID

        Returns:
            True if deleted, False if not found
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            preview = await db.get(PreviewAsset, preview_id)
            if not preview:
                return False

            # Delete file
            file_path = self._previews_root / preview.file_path
            if file_path.exists():
                await self._delete_file(file_path)

            # Delete record
            await db.delete(preview)

            if not self.db:
                await db.commit()

            logger.info("preview_deleted", preview_id=preview_id)
            return True

        finally:
            if not self.db:
                await db.close()

    async def _delete_file(self, path: Path) -> None:
        """Delete a file."""

        def _do_delete() -> None:
            try:
                path.unlink()
                # Try to remove empty parent directories
                parent = path.parent
                while parent != self._previews_root:
                    if not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                    else:
                        break
            except Exception as e:
                logger.warning("file_delete_failed", path=str(path), error=str(e))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_delete)

    async def get_design_previews(self, design_id: str) -> list[PreviewAsset]:
        """Get all previews for a design, sorted by primary status and sort_order.

        Args:
            design_id: The design ID

        Returns:
            List of preview assets
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            result = await db.execute(
                select(PreviewAsset)
                .where(PreviewAsset.design_id == design_id)
                .order_by(
                    PreviewAsset.is_primary.desc(),
                    PreviewAsset.sort_order.asc(),
                    PreviewAsset.created_at.asc(),
                )
            )
            return list(result.scalars().all())

        finally:
            if not self.db:
                await db.close()

    async def set_primary(self, preview_id: str) -> bool:
        """Set a preview as primary for its design.

        Args:
            preview_id: The preview to set as primary

        Returns:
            True if successful, False if preview not found
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            preview = await db.get(PreviewAsset, preview_id)
            if not preview:
                return False

            # Unset current primary for this design
            await db.execute(
                update(PreviewAsset)
                .where(
                    PreviewAsset.design_id == preview.design_id,
                    PreviewAsset.is_primary == True,
                )
                .values(is_primary=False)
            )

            # Set new primary
            preview.is_primary = True

            if not self.db:
                await db.commit()

            logger.info(
                "preview_set_primary",
                preview_id=preview_id,
                design_id=preview.design_id,
            )
            return True

        finally:
            if not self.db:
                await db.close()

    async def auto_select_primary(self, design_id: str) -> str | None:
        """Auto-select the best preview as primary based on source priority.

        Per DEC-032, priority order:
        1. RENDERED (we generated it)
        2. EMBEDDED_3MF (designer's intended preview)
        3. ARCHIVE (designer included it)
        4. THANGS (authoritative external source)
        5. TELEGRAM (channel post image)

        Args:
            design_id: The design to select primary for

        Returns:
            ID of the selected primary preview, or None if no previews
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            result = await db.execute(
                select(PreviewAsset).where(PreviewAsset.design_id == design_id)
            )
            previews = list(result.scalars().all())

            if not previews:
                return None

            # Sort by priority
            previews.sort(key=lambda p: SOURCE_PRIORITY.get(p.source, 99))

            # Select best
            best = previews[0]

            # Unset current primary
            await db.execute(
                update(PreviewAsset)
                .where(
                    PreviewAsset.design_id == design_id,
                    PreviewAsset.is_primary == True,
                )
                .values(is_primary=False)
            )

            # Set new primary
            best.is_primary = True

            if not self.db:
                await db.commit()

            logger.info(
                "preview_auto_selected",
                design_id=design_id,
                preview_id=best.id,
                source=best.source.value,
            )
            return best.id

        finally:
            if not self.db:
                await db.close()

    async def update_sort_order(self, preview_id: str, sort_order: int) -> bool:
        """Update the sort order for a preview.

        Args:
            preview_id: The preview to update
            sort_order: New sort order value

        Returns:
            True if successful, False if preview not found
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            preview = await db.get(PreviewAsset, preview_id)
            if not preview:
                return False

            preview.sort_order = sort_order

            if not self.db:
                await db.commit()

            return True

        finally:
            if not self.db:
                await db.close()

    async def delete_design_previews(self, design_id: str) -> int:
        """Delete all previews for a design.

        Used when a design is deleted.

        Args:
            design_id: The design ID

        Returns:
            Number of previews deleted
        """
        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            # Get all previews
            result = await db.execute(
                select(PreviewAsset).where(PreviewAsset.design_id == design_id)
            )
            previews = list(result.scalars().all())

            if not previews:
                return 0

            # Delete files
            for preview in previews:
                file_path = self._previews_root / preview.file_path
                if file_path.exists():
                    await self._delete_file(file_path)

            # Delete records
            await db.execute(
                delete(PreviewAsset).where(PreviewAsset.design_id == design_id)
            )

            if not self.db:
                await db.commit()

            logger.info(
                "design_previews_deleted",
                design_id=design_id,
                count=len(previews),
            )
            return len(previews)

        finally:
            if not self.db:
                await db.close()

    def get_static_path(self, relative_path: str) -> Path | None:
        """Get absolute path for static file serving with security validation.

        Args:
            relative_path: Path relative to /cache/previews/

        Returns:
            Absolute path if valid and exists, None otherwise
        """
        # Security: Prevent directory traversal
        try:
            requested_path = (self._previews_root / relative_path).resolve()
            if not str(requested_path).startswith(str(self._previews_root.resolve())):
                logger.warning(
                    "directory_traversal_attempt",
                    requested=relative_path,
                )
                return None

            if requested_path.exists() and requested_path.is_file():
                return requested_path
            return None

        except Exception:
            return None
