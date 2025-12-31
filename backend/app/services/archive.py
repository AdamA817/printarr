"""Archive extraction service for unpacking design archives.

NOTE: This service uses the "session-per-operation" pattern to avoid
holding database locks during long I/O operations. See DEC-019.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
from app.db.session import async_session_maker
from app.services.job_queue import JobQueueService

logger = get_logger(__name__)

# Supported archive formats
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar"}

# Multi-part RAR pattern: .part1.rar, .part01.rar, .part001.rar, etc.
MULTIPART_RAR_PATTERN = re.compile(r"\.part0*1\.rar$", re.IGNORECASE)
MULTIPART_RAR_SECONDARY = re.compile(r"\.part0*[2-9]\d*\.rar$", re.IGNORECASE)

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
        )

        return {
            "design_id": design_id,
            "archives_extracted": total_archives,
            "files_created": len(all_extracted_files),
            "nested_archives": nested_count,
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
        def _hash() -> str:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _hash)

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
