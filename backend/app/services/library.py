"""Library import service for organizing design files.

NOTE: This service uses the "session-per-operation" pattern to avoid
holding database locks during file I/O operations. See DEC-019.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
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
from app.db.models.enums import JobType, PreviewKind, PreviewSource
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService
from app.services.preview import PreviewService

logger = get_logger(__name__)

# Invalid characters for folder/file names across platforms
INVALID_CHARS = re.compile(r'[/\\:*?"<>|]')

# Default template if none configured
DEFAULT_TEMPLATE = "{designer}/{channel}/{title}"

# Common thumbnail paths inside 3MF files (in priority order)
THREEMF_THUMBNAIL_PATHS = [
    "Metadata/thumbnail.png",
    "thumbnail.png",
    "3D/Metadata/thumbnail.png",
    "Metadata/thumbnail.jpg",
    "thumbnail.jpg",
]


class LibraryError(Exception):
    """Error during library import."""

    pass


@dataclass
class DesignInfo:
    """Design info needed for import (no ORM objects)."""

    id: str
    display_title: str | None
    display_designer: str | None
    channel_title: str
    channel_template_override: str | None


@dataclass
class FileToMove:
    """Info about a file to move."""

    design_file_id: str
    relative_path: str
    filename: str
    size_bytes: int | None
    source_path: Path


class LibraryImportService:
    """Service for importing files from staging to the library.

    This service uses the "session-per-operation" pattern:
    - Database sessions are only held during brief read/write operations
    - File I/O operations (moves) happen outside any session
    - This prevents SQLite locking issues during slow file operations
    """

    def __init__(self, db: AsyncSession | None = None):
        """Initialize the library import service.

        Args:
            db: Optional session (not used by import_design which manages its own).
        """
        self.db = db

    async def import_design(
        self,
        design_id: str,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Import a design's files from staging to the library.

        Uses session-per-operation pattern to avoid holding locks during file moves.
        """
        staging_dir = self._get_staging_dir(design_id)

        # PHASE 1: Gather design info and file list (brief session)
        async with async_session_maker() as db:
            design = await self._get_design_with_files(db, design_id)
            if not design:
                raise LibraryError(f"Design not found: {design_id}")

            if not staging_dir.exists():
                raise LibraryError(f"Staging directory not found: {staging_dir}")

            # Gather design info as plain data
            design_info = await self._collect_design_info(db, design)

            # Get files to move
            files_to_move = await self._collect_files_to_move(db, design_id, staging_dir)

            if not files_to_move:
                logger.info("no_files_to_import", design_id=design_id)
                return {
                    "design_id": design_id,
                    "files_imported": 0,
                    "library_path": "",
                }

            # Update status
            design.status = DesignStatus.IMPORTING
            await db.commit()

        # Get template and build library path
        template = design_info.channel_template_override or settings.library_template_global
        library_path = self._build_library_path(design_info, template)

        # PHASE 2: Move files (NO database session held)
        library_path.mkdir(parents=True, exist_ok=True)
        total_files = len(files_to_move)
        files_imported = 0
        total_bytes = 0
        moved_files: list[tuple[str, str, str]] = []  # (design_file_id, new_relative_path, new_filename)

        for i, file_info in enumerate(files_to_move):
            if not file_info.source_path.exists():
                logger.warning(
                    "file_not_found_in_staging",
                    design_id=design_id,
                    relative_path=file_info.relative_path,
                )
                continue

            # Handle filename collision
            target_filename = self._resolve_collision(
                library_path, file_info.filename
            )
            target_path = library_path / target_filename

            # Move file (no DB)
            await self._move_file(file_info.source_path, target_path)

            # Record the move for DB update
            new_relative_path = str(target_path.relative_to(settings.library_path))
            moved_files.append((file_info.design_file_id, new_relative_path, target_filename))

            files_imported += 1
            total_bytes += file_info.size_bytes or 0

            if progress_callback:
                progress_callback(i + 1, total_files)

        # Clean up staging (no DB)
        await self._cleanup_staging(staging_dir)

        # PHASE 3: Update DesignFile records (brief session)
        async with async_session_maker() as db:
            for design_file_id, new_relative_path, new_filename in moved_files:
                design_file = await db.get(DesignFile, design_file_id)
                if design_file:
                    design_file.relative_path = new_relative_path
                    design_file.filename = new_filename

            await db.commit()

        # PHASE 4: Update design status (brief session)
        async with async_session_maker() as db:
            design = await db.get(Design, design_id)
            if design:
                design.status = DesignStatus.ORGANIZED
                await db.commit()

        # PHASE 5: Extract 3MF thumbnails (NO database session held during I/O)
        threemf_thumbnails = await self._extract_3mf_thumbnails(design_id, library_path)

        # PHASE 6: Auto-select primary preview if we extracted any thumbnails
        if threemf_thumbnails > 0:
            async with async_session_maker() as db:
                preview_service = PreviewService(db)
                await preview_service.auto_select_primary(design_id)
                await db.commit()

        # PHASE 7: Queue render job for STL preview generation
        async with async_session_maker() as db:
            queue = JobQueueService(db)
            await queue.enqueue(
                job_type=JobType.GENERATE_RENDER,
                design_id=design_id,
                payload={"design_id": design_id},
            )
            await db.commit()
            logger.debug("render_job_queued", design_id=design_id)

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

    async def _get_design_with_files(
        self, db: AsyncSession, design_id: str
    ) -> Design | None:
        """Get design with sources loaded for template resolution."""
        result = await db.execute(
            select(Design)
            .options(
                selectinload(Design.sources)
                .selectinload(DesignSource.message)
                .selectinload(TelegramMessage.channel)
            )
            .where(Design.id == design_id)
        )
        return result.scalar_one_or_none()

    async def _collect_design_info(
        self, db: AsyncSession, design: Design
    ) -> DesignInfo:
        """Collect design info as plain data."""
        channel_title = "Unknown Channel"
        channel_template_override = None

        if design.sources:
            for source in design.sources:
                if source.message and source.message.channel:
                    channel_title = source.message.channel.title
                    channel_template_override = source.message.channel.library_template_override
                    break

        return DesignInfo(
            id=design.id,
            display_title=design.display_title,
            display_designer=design.display_designer,
            channel_title=channel_title,
            channel_template_override=channel_template_override,
        )

    async def _collect_files_to_move(
        self, db: AsyncSession, design_id: str, staging_dir: Path
    ) -> list[FileToMove]:
        """Collect file info as plain data."""
        result = await db.execute(
            select(DesignFile).where(DesignFile.design_id == design_id)
        )
        design_files = result.scalars().all()

        files_to_move = []
        for df in design_files:
            source_path = staging_dir / df.relative_path
            files_to_move.append(
                FileToMove(
                    design_file_id=df.id,
                    relative_path=df.relative_path,
                    filename=df.filename,
                    size_bytes=df.size_bytes,
                    source_path=source_path,
                )
            )

        return files_to_move

    def _build_library_path(self, design_info: DesignInfo, template: str) -> Path:
        """Build the library path from template and design data."""
        now = datetime.utcnow()

        variables = {
            "designer": self._sanitize_name(design_info.display_designer or "Unknown"),
            "title": self._sanitize_name(design_info.display_title or "Untitled"),
            "date": now.strftime("%Y-%m-%d"),
            "year": str(now.year),
            "month": now.strftime("%m"),
            "channel": self._sanitize_name(design_info.channel_title),
        }

        path_str = template
        for key, value in variables.items():
            path_str = path_str.replace(f"{{{key}}}", value)

        return settings.library_path / path_str

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use in file/folder paths."""
        sanitized = INVALID_CHARS.sub("_", name)
        sanitized = re.sub(r"[_\s]+", "_", sanitized)
        sanitized = sanitized.strip("_ ")

        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        if not sanitized:
            sanitized = "Unknown"

        return sanitized

    def _resolve_collision(self, directory: Path, filename: str) -> str:
        """Resolve filename collision by appending numeric suffix."""
        if not (directory / filename).exists():
            return filename

        path = Path(filename)
        base = path.stem
        ext = path.suffix

        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            if not (directory / new_name).exists():
                return new_name
            counter += 1
            if counter > 9999:
                raise LibraryError(f"Too many filename collisions: {filename}")

    async def _move_file(self, source: Path, target: Path) -> None:
        """Move a file from source to target."""
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
        """Remove the staging directory if empty."""
        def _do_cleanup() -> None:
            try:
                if staging_dir.exists():
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
        """Recursively remove empty directories."""
        if not path.is_dir():
            return False

        for child in list(path.iterdir()):
            if child.is_dir():
                self._remove_empty_dirs(child)

        try:
            path.rmdir()
            logger.debug("removed_empty_dir", path=str(path))
            return True
        except OSError:
            return False

    def _get_staging_dir(self, design_id: str) -> Path:
        """Get the staging directory for a design."""
        return settings.staging_path / design_id

    async def _extract_3mf_thumbnails(self, design_id: str, library_path: Path) -> int:
        """Extract thumbnails from 3MF files in the library folder.

        Args:
            design_id: The design ID.
            library_path: Path to the design's library folder.

        Returns:
            Number of thumbnails extracted.
        """
        threemf_files = self._find_3mf_files(library_path)
        if not threemf_files:
            return 0

        extracted_count = 0

        for threemf_path in threemf_files:
            thumbnail_data = await self._extract_thumbnail_from_3mf(threemf_path)
            if not thumbnail_data:
                continue

            image_data, original_filename = thumbnail_data

            # Save thumbnail using PreviewService
            async with async_session_maker() as db:
                preview_service = PreviewService(db)
                await preview_service.save_preview(
                    design_id=design_id,
                    image_data=image_data,
                    source=PreviewSource.EMBEDDED_3MF,
                    kind=PreviewKind.THUMBNAIL,
                    original_filename=original_filename or f"{threemf_path.stem}_thumbnail.png",
                )
                await db.commit()

            extracted_count += 1
            logger.debug(
                "extracted_3mf_thumbnail",
                design_id=design_id,
                threemf_file=threemf_path.name,
            )

        if extracted_count > 0:
            logger.info(
                "3mf_thumbnails_extracted",
                design_id=design_id,
                count=extracted_count,
            )

        return extracted_count

    def _find_3mf_files(self, directory: Path) -> list[Path]:
        """Find all 3MF files in a directory (non-recursive).

        Args:
            directory: Directory to search.

        Returns:
            List of paths to 3MF files.
        """
        if not directory.exists():
            return []

        return list(directory.glob("*.3mf"))

    async def _extract_thumbnail_from_3mf(
        self, threemf_path: Path
    ) -> tuple[bytes, str | None] | None:
        """Extract embedded thumbnail from a 3MF file.

        3MF files are ZIP archives that may contain thumbnail images
        at standard locations.

        Args:
            threemf_path: Path to the 3MF file.

        Returns:
            Tuple of (image_data, original_filename) or None if no thumbnail.
        """
        def _do_extract() -> tuple[bytes, str | None] | None:
            try:
                with zipfile.ZipFile(threemf_path, "r") as zf:
                    # Get list of files in archive
                    namelist = zf.namelist()

                    # Try each known thumbnail path
                    for thumb_path in THREEMF_THUMBNAIL_PATHS:
                        if thumb_path in namelist:
                            data = zf.read(thumb_path)
                            if len(data) > 0:
                                return (data, thumb_path.split("/")[-1])

                    # Also check for any image in Metadata folder
                    for name in namelist:
                        if name.startswith("Metadata/") and name.lower().endswith(
                            (".png", ".jpg", ".jpeg")
                        ):
                            data = zf.read(name)
                            if len(data) > 0:
                                return (data, name.split("/")[-1])

                return None

            except (zipfile.BadZipFile, Exception) as e:
                logger.warning(
                    "3mf_thumbnail_extraction_failed",
                    file=str(threemf_path),
                    error=str(e),
                )
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_extract)
