"""Worker for generating preview renders from model files.

Supports:
- STL rendering via stl-thumb CLI tool
- 3MF embedded thumbnail extraction

Both sources are processed when available to maximize preview options.
"""

from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DesignFile, Job
from app.db.models.enums import FileKind, JobType, PreviewKind, PreviewSource
from app.db.session import async_session_maker
from app.services.preview import PreviewService
from app.workers.base import BaseWorker
from sqlalchemy import select

logger = get_logger(__name__)

# Known thumbnail paths inside 3MF archives (in priority order)
THREEMF_THUMBNAIL_PATHS = [
    "Metadata/thumbnail.png",
    "Metadata/plate_1.png",
    "thumbnail.png",
    ".thumbnails/thumbnail.png",
]

# Configuration
DEFAULT_RENDER_SIZE = 400
MAX_STL_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
RENDER_TIMEOUT_SECONDS = 30


class RenderWorker(BaseWorker):
    """Worker that generates preview renders for STL files.

    Uses stl-thumb CLI tool to render preview images for designs
    that don't have other preview sources.
    """

    job_types = [JobType.GENERATE_RENDER]

    async def process(self, job: Job, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        """Process a GENERATE_RENDER job.

        Args:
            job: The job to process.
            payload: Job payload with design_id.

        Returns:
            Result dict with render status.
        """
        if not payload:
            return {"error": "No payload provided"}

        design_id = payload.get("design_id")
        if not design_id:
            return {"error": "No design_id in payload"}

        # Check if stl-thumb is available (for STL rendering)
        stl_thumb_available = await self._check_stl_thumb()
        if not stl_thumb_available:
            logger.debug(
                "stl_thumb_not_available",
                design_id=design_id,
            )

        # Find model files for this design
        async with async_session_maker() as db:
            result = await db.execute(
                select(DesignFile)
                .where(DesignFile.design_id == design_id)
                .where(DesignFile.file_kind == FileKind.MODEL)
            )
            design_files = list(result.scalars().all())

        if not design_files:
            logger.debug("no_model_files", design_id=design_id)
            return {"design_id": design_id, "renders": 0, "message": "No model files found"}

        # Track what we generate
        stl_rendered = False
        threemf_extracted = False
        stl_filename = None
        threemf_filename = None

        # Try to render STL file
        stl_file = self._select_stl_for_render(design_files)
        if stl_file and stl_thumb_available:
            stl_path = settings.library_path / design_id / stl_file.relative_path
            if stl_path.exists():
                file_size = stl_path.stat().st_size
                if file_size <= MAX_STL_SIZE_BYTES:
                    stl_rendered = await self._render_stl(design_id, stl_path)
                    if stl_rendered:
                        stl_filename = stl_file.filename
                else:
                    logger.warning(
                        "stl_too_large",
                        design_id=design_id,
                        size_mb=file_size / (1024 * 1024),
                        max_mb=MAX_STL_SIZE_BYTES / (1024 * 1024),
                    )
            else:
                logger.warning(
                    "stl_file_not_found",
                    design_id=design_id,
                    path=str(stl_path),
                )

        # Try to extract 3MF thumbnail
        threemf_file = self._select_3mf_for_extraction(design_files)
        if threemf_file:
            threemf_path = settings.library_path / design_id / threemf_file.relative_path
            if threemf_path.exists():
                threemf_extracted = await self._extract_3mf_thumbnail(design_id, threemf_path)
                if threemf_extracted:
                    threemf_filename = threemf_file.filename
            else:
                logger.warning(
                    "3mf_file_not_found",
                    design_id=design_id,
                    path=str(threemf_path),
                )

        # Count total renders
        total_renders = (1 if stl_rendered else 0) + (1 if threemf_extracted else 0)

        if total_renders > 0:
            # Auto-select primary preview
            async with async_session_maker() as db:
                preview_service = PreviewService(db)
                await preview_service.auto_select_primary(design_id)
                await db.commit()

        # Build result
        result: dict[str, Any] = {
            "design_id": design_id,
            "renders": total_renders,
        }
        if stl_rendered:
            result["stl_file"] = stl_filename
        if threemf_extracted:
            result["threemf_file"] = threemf_filename
        if total_renders == 0:
            result["message"] = "No previews generated"

        return result

    async def _check_stl_thumb(self) -> bool:
        """Check if stl-thumb is available on the system."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "stl-thumb", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False

    def _select_stl_for_render(self, design_files: list[DesignFile]) -> DesignFile | None:
        """Select the best STL file to render.

        Prefers the largest file, filtered to only .stl extension.
        """
        stl_files = [
            f for f in design_files
            if f.filename.lower().endswith(".stl")
        ]

        if not stl_files:
            return None

        # Return the largest by size_bytes (or first if no sizes)
        with_sizes = [f for f in stl_files if f.size_bytes]
        if with_sizes:
            return max(with_sizes, key=lambda f: f.size_bytes or 0)
        return stl_files[0]

    def _select_3mf_for_extraction(self, design_files: list[DesignFile]) -> DesignFile | None:
        """Select a 3MF file for thumbnail extraction.

        Prefers the largest file, filtered to only .3mf extension.
        """
        threemf_files = [
            f for f in design_files
            if f.filename.lower().endswith(".3mf")
        ]

        if not threemf_files:
            return None

        # Return the largest by size_bytes (or first if no sizes)
        with_sizes = [f for f in threemf_files if f.size_bytes]
        if with_sizes:
            return max(with_sizes, key=lambda f: f.size_bytes or 0)
        return threemf_files[0]

    async def _extract_3mf_thumbnail(self, design_id: str, threemf_path: Path) -> bool:
        """Extract embedded thumbnail from a 3MF file.

        Args:
            design_id: The design ID.
            threemf_path: Path to the 3MF file.

        Returns:
            True if thumbnail extracted and saved, False otherwise.
        """
        try:
            with zipfile.ZipFile(threemf_path, "r") as zf:
                namelist = zf.namelist()

                # Try each known thumbnail path
                for thumb_path in THREEMF_THUMBNAIL_PATHS:
                    if thumb_path in namelist:
                        image_data = zf.read(thumb_path)

                        if len(image_data) == 0:
                            continue

                        # Save via PreviewService
                        async with async_session_maker() as db:
                            preview_service = PreviewService(db)
                            await preview_service.save_preview(
                                design_id=design_id,
                                source=PreviewSource.EMBEDDED_3MF,
                                image_data=image_data,
                                filename=f"3mf_thumbnail.png",
                                kind=PreviewKind.THUMBNAIL,
                            )
                            await db.commit()

                        logger.info(
                            "3mf_thumbnail_extracted",
                            design_id=design_id,
                            threemf_file=threemf_path.name,
                            thumbnail_path=thumb_path,
                        )
                        return True

                logger.debug(
                    "3mf_no_thumbnail_found",
                    design_id=design_id,
                    threemf_file=threemf_path.name,
                    checked_paths=THREEMF_THUMBNAIL_PATHS,
                )
                return False

        except zipfile.BadZipFile:
            logger.warning(
                "3mf_invalid_archive",
                design_id=design_id,
                threemf_file=str(threemf_path),
            )
            return False
        except Exception as e:
            logger.error(
                "3mf_extraction_error",
                design_id=design_id,
                threemf_file=str(threemf_path),
                error=str(e),
                exc_info=True,
            )
            return False

    async def _render_stl(self, design_id: str, stl_path: Path) -> bool:
        """Render an STL file using stl-thumb.

        Args:
            design_id: The design ID.
            stl_path: Path to the STL file.

        Returns:
            True if render succeeded, False otherwise.
        """
        # Create temp output file
        output_dir = settings.cache_path / "previews" / "rendered" / design_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{stl_path.stem}_preview.png"

        try:
            # Run stl-thumb
            proc = await asyncio.create_subprocess_exec(
                "stl-thumb",
                "-s", str(DEFAULT_RENDER_SIZE),
                str(stl_path),
                str(output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=RENDER_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                proc.kill()
                logger.warning(
                    "stl_thumb_timeout",
                    design_id=design_id,
                    stl_file=str(stl_path),
                    timeout=RENDER_TIMEOUT_SECONDS,
                )
                return False

            if proc.returncode != 0:
                logger.warning(
                    "stl_thumb_failed",
                    design_id=design_id,
                    stl_file=str(stl_path),
                    returncode=proc.returncode,
                    stderr=stderr.decode("utf-8", errors="replace")[:500],
                )
                return False

            # Verify output exists and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                logger.warning(
                    "stl_thumb_no_output",
                    design_id=design_id,
                    output_path=str(output_path),
                )
                return False

            # Read the rendered image and save via PreviewService
            image_data = output_path.read_bytes()

            async with async_session_maker() as db:
                preview_service = PreviewService(db)
                await preview_service.save_preview(
                    design_id=design_id,
                    source=PreviewSource.RENDERED,
                    image_data=image_data,
                    filename=output_path.name,
                    kind=PreviewKind.THUMBNAIL,
                )
                await db.commit()

            # Clean up temp file (preview service saved its own copy)
            output_path.unlink(missing_ok=True)
            try:
                output_dir.rmdir()  # Only removes if empty
            except OSError:
                pass

            logger.info(
                "stl_rendered",
                design_id=design_id,
                stl_file=stl_path.name,
            )
            return True

        except Exception as e:
            logger.error(
                "stl_render_error",
                design_id=design_id,
                stl_file=str(stl_path),
                error=str(e),
                exc_info=True,
            )
            return False
