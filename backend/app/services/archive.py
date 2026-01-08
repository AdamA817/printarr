"""Archive extraction service for unpacking design archives.

NOTE: This service uses the "session-per-operation" pattern to avoid
holding database locks during long I/O operations. See DEC-019.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import tarfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    Design,
    DesignFile,
    DesignStatus,
    FileKind,
    JobType,
    ModelKind,
)
from app.db.models.enums import PreviewKind, PreviewSource
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService
from app.utils import compute_file_hash

logger = get_logger(__name__)

# Supported archive formats
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar"}

# Multi-part RAR pattern: .part1.rar, .part01.rar, .part001.rar, etc.
MULTIPART_RAR_PATTERN = re.compile(r"\.part0*1\.rar$", re.IGNORECASE)
# Secondary parts: .part2.rar, .part02.rar, .part10.rar, .part100.rar, etc.
MULTIPART_RAR_SECONDARY = re.compile(r"\.part(0*[2-9]\d*|[1-9]\d+)\.rar$", re.IGNORECASE)

# Model file extensions for classification
MODEL_EXTENSIONS = {
    ".stl": ModelKind.STL,
    ".3mf": ModelKind.THREE_MF,
    ".obj": ModelKind.OBJ,
    ".step": ModelKind.STEP,
    ".stp": ModelKind.STEP,
}

# Image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# Preview extraction patterns (v0.7 - per DEC-031)
# Priority 1: Explicit preview files (highest priority)
EXPLICIT_PREVIEW_PATTERNS = [
    re.compile(r"^preview\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
    re.compile(r"^thumbnail\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
    re.compile(r"^cover\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
    re.compile(r"^render\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
]
# Priority 2: Images in preview folders
FOLDER_PREVIEW_PATTERNS = [
    re.compile(r"^images?/[^/]+\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
    re.compile(r"^previews?/[^/]+\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
    re.compile(r"^renders?/[^/]+\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
    re.compile(r"^photos?/[^/]+\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE),
]
# Priority 3: Root-level images (lowest priority)
ROOT_IMAGE_PATTERN = re.compile(r"^[^/]+\.(jpg|jpeg|png|gif|webp)$", re.IGNORECASE)

# Preview extraction limits
MAX_PREVIEW_IMAGES = 10
MIN_PREVIEW_SIZE_BYTES = 10 * 1024  # 10KB - skip tiny icons
MAX_PREVIEW_SIZE_BYTES = 10 * 1024 * 1024  # 10MB - skip huge renders


class ArchiveError(Exception):
    """Error during archive extraction."""

    pass


class PasswordProtectedError(ArchiveError):
    """Archive is password protected."""

    pass


class CorruptedArchiveError(ArchiveError):
    """Archive is corrupted."""

    pass


class MissingPartError(ArchiveError):
    """Missing part in multi-part archive."""

    pass


@dataclass
class ExtractedFileInfo:
    """Info about an extracted file for creating DesignFile records."""

    file_path: Path
    relative_path: str
    filename: str
    ext: str
    size_bytes: int
    sha256: str
    file_kind: FileKind
    model_kind: ModelKind


@dataclass
class PreviewCandidate:
    """Info about a potential preview image found in an archive."""

    file_path: Path
    relative_path: str
    filename: str
    size_bytes: int
    priority: int  # 1=explicit, 2=folder, 3=root


@dataclass
class ExtractResult:
    """Result of archive extraction for upload flow."""

    files_extracted: int
    model_files: int
    nested_archives: int


class ArchiveExtractor:
    """Service for extracting archive files.

    This service uses the "session-per-operation" pattern:
    - Database sessions are only held during brief read/write operations
    - Long I/O operations (extraction) happen outside any session
    - This prevents SQLite locking issues during large archive extraction
    """

    def __init__(self, db: AsyncSession | None = None):
        """Initialize the archive extractor.

        Args:
            db: Optional session for queue_import method.
                For extract_design_archives, sessions are managed internally.
        """
        self.db = db

    async def extract_design_archives(
        self,
        design_id: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Extract all archives for a design.

        Uses session-per-operation pattern to avoid holding locks during extraction.
        """
        staging_dir = self._get_staging_dir(design_id)

        # PHASE 1: Validate and update status (brief session)
        async with async_session_maker() as db:
            design = await db.get(Design, design_id)
            if not design:
                raise ArchiveError(f"Design not found: {design_id}")

            if not staging_dir.exists():
                raise ArchiveError(f"Staging directory not found: {staging_dir}")

            # Find all archives
            archives = self._find_archives(staging_dir)
            if not archives:
                logger.info("no_archives_found", design_id=design_id)
                return {
                    "design_id": design_id,
                    "archives_extracted": 0,
                    "files_created": 0,
                    "nested_archives": 0,
                }

            design.status = DesignStatus.EXTRACTING
            await db.commit()

        # PHASE 2: Extract archives (NO database session held)
        total_archives = len(archives)
        all_extracted_files: list[ExtractedFileInfo] = []
        nested_count = 0

        for i, archive_path in enumerate(archives):
            logger.info(
                "extracting_archive",
                design_id=design_id,
                archive=archive_path.name,
                index=i + 1,
                total=total_archives,
            )

            # Extract the archive (no DB)
            extracted_paths = await self._extract_archive(archive_path, staging_dir)

            # Process extracted files and compute hashes (no DB)
            for file_path in extracted_paths:
                file_info = await self._prepare_file_info(file_path, staging_dir)
                all_extracted_files.append(file_info)

            # Check for nested archives
            nested_archives = [
                f for f in extracted_paths
                if f.suffix.lower() in ARCHIVE_EXTENSIONS
                or str(f).lower().endswith((".tar.gz", ".tgz"))
            ]

            for nested in nested_archives:
                logger.info(
                    "extracting_nested_archive",
                    design_id=design_id,
                    archive=nested.name,
                )
                nested_paths = await self._extract_archive(nested, staging_dir)
                nested_count += 1

                for file_path in nested_paths:
                    file_info = await self._prepare_file_info(file_path, staging_dir)
                    all_extracted_files.append(file_info)

                # Delete nested archive after extraction
                await self._delete_file(nested)

            # Delete original archive after successful extraction
            await self._delete_archive_and_parts(archive_path)

            if progress_callback:
                progress_callback(i + 1, total_archives)

        # PHASE 3: Create DesignFile records (brief session)
        async with async_session_maker() as db:
            for file_info in all_extracted_files:
                design_file = DesignFile(
                    design_id=design_id,
                    relative_path=file_info.relative_path,
                    filename=file_info.filename,
                    ext=file_info.ext,
                    size_bytes=file_info.size_bytes,
                    sha256=file_info.sha256,
                    file_kind=file_info.file_kind,
                    model_kind=file_info.model_kind,
                    is_from_archive=True,
                )
                db.add(design_file)

            await db.commit()

        # PHASE 3.5: Extract preview images (v0.7 - per DEC-031)
        previews_saved = await self._extract_preview_images(
            design_id=design_id,
            extracted_files=all_extracted_files,
        )

        # PHASE 4: Update design status (brief session)
        async with async_session_maker() as db:
            design = await db.get(Design, design_id)
            if design:
                design.status = DesignStatus.EXTRACTED
                await db.commit()

        logger.info(
            "extraction_complete",
            design_id=design_id,
            archives_extracted=total_archives,
            files_created=len(all_extracted_files),
            nested_archives=nested_count,
            previews_extracted=previews_saved,
        )

        return {
            "design_id": design_id,
            "archives_extracted": total_archives,
            "files_created": len(all_extracted_files),
            "nested_archives": nested_count,
            "previews_extracted": previews_saved,
        }

    async def queue_import(self, design_id: str) -> str:
        """Queue an import job for the design."""
        if self.db is None:
            raise ArchiveError("Database session required for queue_import")

        queue = JobQueueService(self.db)
        job = await queue.enqueue(
            JobType.IMPORT_TO_LIBRARY,
            design_id=design_id,
            priority=5,
        )
        return job.id

    async def extract(
        self,
        archive_path: Path,
        output_dir: Path,
    ) -> ExtractResult:
        """Extract an archive to a target directory.

        Simple extraction method for upload flow (no design ID required).

        Args:
            archive_path: Path to the archive file.
            output_dir: Directory to extract to.

        Returns:
            ExtractResult with extraction details.
        """
        import aiofiles.os

        await aiofiles.os.makedirs(output_dir, exist_ok=True)

        try:
            extracted_paths = await self._extract_archive(archive_path, output_dir)

            # Check for nested archives and extract them
            nested_count = 0
            nested_archives = [
                f for f in extracted_paths
                if f.suffix.lower() in ARCHIVE_EXTENSIONS
                or str(f).lower().endswith((".tar.gz", ".tgz"))
            ]

            for nested in nested_archives:
                logger.info(
                    "extracting_nested_archive",
                    archive=nested.name,
                )
                nested_paths = await self._extract_archive(nested, output_dir)
                extracted_paths.extend(nested_paths)
                nested_count += 1

                # Delete nested archive after extraction
                await self._delete_file(nested)
                # Remove from extracted_paths since it's deleted
                if nested in extracted_paths:
                    extracted_paths.remove(nested)

            # Count model files
            model_count = sum(
                1 for p in extracted_paths
                if p.suffix.lower() in MODEL_EXTENSIONS
            )

            return ExtractResult(
                files_extracted=len(extracted_paths),
                model_files=model_count,
                nested_archives=nested_count,
            )

        except (PasswordProtectedError, CorruptedArchiveError, MissingPartError):
            raise
        except Exception as e:
            raise ArchiveError(f"Failed to extract {archive_path.name}: {e}")

    async def _prepare_file_info(
        self, file_path: Path, staging_dir: Path
    ) -> ExtractedFileInfo:
        """Prepare file info for creating DesignFile record later."""
        relative_path = str(file_path.relative_to(staging_dir))
        ext = file_path.suffix.lower()
        file_kind = self._classify_file(ext)
        model_kind = MODEL_EXTENSIONS.get(ext, ModelKind.UNKNOWN)

        size_bytes = file_path.stat().st_size
        sha256 = await self._compute_file_hash(file_path)

        return ExtractedFileInfo(
            file_path=file_path,
            relative_path=relative_path,
            filename=file_path.name,
            ext=ext,
            size_bytes=size_bytes,
            sha256=sha256,
            file_kind=file_kind,
            model_kind=model_kind,
        )

    def _get_staging_dir(self, design_id: str) -> Path:
        """Get the staging directory for a design."""
        return settings.staging_path / design_id

    def _find_archives(self, directory: Path) -> list[Path]:
        """Find all archives in a directory, skipping secondary multi-part files."""
        archives = []

        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue

            name_lower = file_path.name.lower()

            # Skip secondary parts of multi-part RAR
            if MULTIPART_RAR_SECONDARY.search(name_lower):
                continue

            # Check for archive extensions
            if file_path.suffix.lower() in ARCHIVE_EXTENSIONS:
                archives.append(file_path)
            elif name_lower.endswith((".tar.gz", ".tgz")):
                archives.append(file_path)

        return sorted(archives, key=lambda p: p.name)

    async def _extract_archive(self, archive_path: Path, output_dir: Path) -> list[Path]:
        """Extract an archive to the output directory."""
        suffix = archive_path.suffix.lower()
        name_lower = archive_path.name.lower()

        try:
            if suffix == ".zip":
                return await self._extract_zip(archive_path, output_dir)
            elif suffix == ".rar" or MULTIPART_RAR_PATTERN.search(name_lower):
                return await self._extract_rar(archive_path, output_dir)
            elif suffix == ".7z":
                return await self._extract_7z(archive_path, output_dir)
            elif suffix in (".tar", ".tgz") or name_lower.endswith(".tar.gz"):
                return await self._extract_tar(archive_path, output_dir)
            else:
                raise ArchiveError(f"Unsupported archive format: {suffix}")
        except (PasswordProtectedError, CorruptedArchiveError, MissingPartError):
            raise
        except Exception as e:
            raise ArchiveError(f"Failed to extract {archive_path.name}: {e}")

    async def _extract_zip(self, archive_path: Path, output_dir: Path) -> list[Path]:
        """Extract a ZIP archive."""
        def _do_extract() -> list[Path]:
            extracted = []
            with zipfile.ZipFile(archive_path, "r") as zf:
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        raise PasswordProtectedError(f"Archive is password protected: {archive_path.name}")

                for member in zf.namelist():
                    if member.endswith("/") or member.startswith("__MACOSX"):
                        continue

                    target = output_dir / member
                    target.parent.mkdir(parents=True, exist_ok=True)

                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)

                    extracted.append(target)

            return extracted

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_extract)

    async def _extract_rar(self, archive_path: Path, output_dir: Path) -> list[Path]:
        """Extract a RAR archive (including multi-part)."""
        try:
            import rarfile
        except ImportError:
            raise ArchiveError("rarfile library not installed")

        def _do_extract() -> list[Path]:
            extracted = []
            try:
                with rarfile.RarFile(archive_path, "r") as rf:
                    if rf.needs_password():
                        raise PasswordProtectedError(f"Archive is password protected: {archive_path.name}")

                    for member in rf.namelist():
                        if member.endswith("/"):
                            continue

                        target = output_dir / member
                        target.parent.mkdir(parents=True, exist_ok=True)

                        with rf.open(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                        extracted.append(target)

            except rarfile.NeedFirstVolume:
                raise MissingPartError(f"Missing first part of multi-part RAR: {archive_path.name}")
            except rarfile.BadRarFile:
                raise CorruptedArchiveError(f"Corrupted RAR archive: {archive_path.name}")

            return extracted

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_extract)

    async def _extract_7z(self, archive_path: Path, output_dir: Path) -> list[Path]:
        """Extract a 7z archive."""
        try:
            import py7zr
        except ImportError:
            raise ArchiveError("py7zr library not installed")

        def _do_extract() -> list[Path]:
            extracted = []
            try:
                with py7zr.SevenZipFile(archive_path, "r") as sz:
                    if sz.needs_password():
                        raise PasswordProtectedError(f"Archive is password protected: {archive_path.name}")

                    sz.extractall(path=output_dir)

                    for member in sz.getnames():
                        target = output_dir / member
                        if target.is_file():
                            extracted.append(target)

            except py7zr.exceptions.Bad7zFile:
                raise CorruptedArchiveError(f"Corrupted 7z archive: {archive_path.name}")
            except py7zr.exceptions.PasswordRequired:
                raise PasswordProtectedError(f"Archive is password protected: {archive_path.name}")

            return extracted

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_extract)

    async def _extract_tar(self, archive_path: Path, output_dir: Path) -> list[Path]:
        """Extract a tar archive (.tar, .tar.gz, .tgz)."""
        def _do_extract() -> list[Path]:
            extracted = []
            mode = "r:gz" if archive_path.name.lower().endswith((".tar.gz", ".tgz")) else "r"

            try:
                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        if not member.isfile():
                            continue

                        if member.name.startswith("/") or ".." in member.name:
                            continue

                        target = output_dir / member.name
                        target.parent.mkdir(parents=True, exist_ok=True)

                        with tf.extractfile(member) as src, open(target, "wb") as dst:
                            if src:
                                shutil.copyfileobj(src, dst)

                        extracted.append(target)

            except tarfile.ReadError:
                raise CorruptedArchiveError(f"Corrupted tar archive: {archive_path.name}")

            return extracted

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do_extract)

    def _classify_file(self, ext: str) -> FileKind:
        """Classify a file by extension."""
        if ext in MODEL_EXTENSIONS:
            return FileKind.MODEL
        elif ext in ARCHIVE_EXTENSIONS:
            return FileKind.ARCHIVE
        elif ext in IMAGE_EXTENSIONS:
            return FileKind.IMAGE
        else:
            return FileKind.OTHER

    async def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        return await compute_file_hash(file_path)

    async def _delete_file(self, file_path: Path) -> None:
        """Delete a file asynchronously."""
        def _delete() -> None:
            if file_path.exists():
                file_path.unlink()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _delete)

    async def _delete_archive_and_parts(self, archive_path: Path) -> None:
        """Delete an archive and any multi-part RAR files."""
        def _delete() -> None:
            if archive_path.exists():
                archive_path.unlink()
                logger.debug("deleted_archive", path=str(archive_path))

            if MULTIPART_RAR_PATTERN.search(archive_path.name.lower()):
                parent = archive_path.parent
                base_pattern = re.sub(
                    r"\.part0*1\.rar$",
                    ".part",
                    archive_path.name,
                    flags=re.IGNORECASE,
                )

                for part_file in parent.glob(f"{base_pattern}*.rar"):
                    if part_file.exists():
                        part_file.unlink()
                        logger.debug("deleted_archive_part", path=str(part_file))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _delete)

    async def _extract_preview_images(
        self,
        design_id: str,
        extracted_files: list[ExtractedFileInfo],
    ) -> int:
        """Extract preview images from extracted files.

        Per DEC-031, scans for preview images using priority patterns:
        1. Explicit files: preview.*, thumbnail.*, cover.*, render.*
        2. Preview folders: images/, previews/, renders/, photos/
        3. Root-level images

        Args:
            design_id: The design ID.
            extracted_files: List of extracted file info.

        Returns:
            Number of preview images saved.
        """
        # Find preview candidates
        candidates = self._find_preview_candidates(extracted_files)

        if not candidates:
            return 0

        # Sort by priority (lower = higher priority)
        candidates.sort(key=lambda c: (c.priority, c.filename))

        # Take top N candidates
        selected = candidates[:MAX_PREVIEW_IMAGES]

        # Save previews using PreviewService
        from app.services.preview import PreviewService

        saved_count = 0
        async with async_session_maker() as db:
            preview_service = PreviewService(db)

            for candidate in selected:
                try:
                    # Read image data
                    image_data = await self._read_file(candidate.file_path)

                    # Save as preview
                    await preview_service.save_preview(
                        design_id=design_id,
                        source=PreviewSource.ARCHIVE,
                        image_data=image_data,
                        filename=candidate.filename,
                        kind=PreviewKind.THUMBNAIL,
                    )
                    saved_count += 1

                    logger.debug(
                        "preview_extracted",
                        design_id=design_id,
                        filename=candidate.filename,
                        priority=candidate.priority,
                    )

                except Exception as e:
                    logger.warning(
                        "preview_extraction_failed",
                        design_id=design_id,
                        filename=candidate.filename,
                        error=str(e),
                    )
                    continue

            # Auto-select primary if we saved any
            if saved_count > 0:
                await preview_service.auto_select_primary(design_id)

            await db.commit()

        logger.info(
            "previews_extracted",
            design_id=design_id,
            candidates_found=len(candidates),
            saved=saved_count,
        )

        return saved_count

    def _find_preview_candidates(
        self, extracted_files: list[ExtractedFileInfo]
    ) -> list[PreviewCandidate]:
        """Find preview image candidates from extracted files.

        Returns candidates sorted by priority:
        1. Explicit preview files (preview.*, thumbnail.*, etc.)
        2. Images in preview folders (images/, previews/, etc.)
        3. Root-level images

        Args:
            extracted_files: List of extracted file info.

        Returns:
            List of preview candidates with priority assigned.
        """
        candidates = []

        for file_info in extracted_files:
            # Skip non-image files
            if file_info.ext.lower() not in IMAGE_EXTENSIONS:
                continue

            # Skip tiny files (likely icons)
            if file_info.size_bytes < MIN_PREVIEW_SIZE_BYTES:
                continue

            # Skip huge files (likely source renders)
            if file_info.size_bytes > MAX_PREVIEW_SIZE_BYTES:
                continue

            # Determine priority based on path pattern
            relative = file_info.relative_path
            priority = self._get_preview_priority(relative)

            if priority > 0:  # 0 = not a preview candidate
                candidates.append(
                    PreviewCandidate(
                        file_path=file_info.file_path,
                        relative_path=relative,
                        filename=file_info.filename,
                        size_bytes=file_info.size_bytes,
                        priority=priority,
                    )
                )

        return candidates

    def _get_preview_priority(self, relative_path: str) -> int:
        """Get preview priority for a file path.

        Returns:
            Priority level (1=highest, 3=lowest, 0=not a preview)
        """
        # Normalize path separators
        normalized = relative_path.replace("\\", "/")

        # Priority 1: Explicit preview files
        for pattern in EXPLICIT_PREVIEW_PATTERNS:
            if pattern.match(normalized):
                return 1

        # Priority 2: Images in preview folders
        for pattern in FOLDER_PREVIEW_PATTERNS:
            if pattern.match(normalized):
                return 2

        # Priority 3: Root-level images
        if ROOT_IMAGE_PATTERN.match(normalized):
            return 3

        return 0  # Not a preview candidate

    async def _read_file(self, file_path: Path) -> bytes:
        """Read file contents asynchronously."""
        def _read() -> bytes:
            with open(file_path, "rb") as f:
                return f.read()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read)
