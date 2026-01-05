"""Worker for generating STL preview renders using stl-thumb."""

from __future__ import annotations

import asyncio
import os
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

        # Check if stl-thumb is available
        if not await self._check_stl_thumb():
            logger.warning(
                "stl_thumb_not_available",
                design_id=design_id,
            )
            return {"error": "stl-thumb not installed", "skipped": True}

        # Find STL files for this design
        async with async_session_maker() as db:
            result = await db.execute(
                select(DesignFile)
                .where(DesignFile.design_id == design_id)
                .where(DesignFile.file_kind == FileKind.MODEL)
            )
            design_files = list(result.scalars().all())

        if not design_files:
            logger.debug("no_stl_files", design_id=design_id)
            return {"design_id": design_id, "renders": 0, "message": "No model files found"}

        # Find largest STL file (or first one)
        stl_file = self._select_stl_for_render(design_files)
        if not stl_file:
            return {"design_id": design_id, "renders": 0, "message": "No renderable STL files"}

        # Check file size
        stl_path = settings.library_path / stl_file.relative_path
        if not stl_path.exists():
            logger.warning(
                "stl_file_not_found",
                design_id=design_id,
                path=str(stl_path),
            )
            return {"error": f"STL file not found: {stl_path}"}

        file_size = stl_path.stat().st_size
        if file_size > MAX_STL_SIZE_BYTES:
            logger.warning(
                "stl_too_large",
                design_id=design_id,
                size_mb=file_size / (1024 * 1024),
                max_mb=MAX_STL_SIZE_BYTES / (1024 * 1024),
            )
            return {
                "design_id": design_id,
                "renders": 0,
                "skipped": True,
                "message": f"STL too large: {file_size / (1024 * 1024):.1f}MB > 100MB limit",
            }

        # Render the preview
        rendered = await self._render_stl(design_id, stl_path)

        if rendered:
            # Auto-select primary preview
            async with async_session_maker() as db:
                preview_service = PreviewService(db)
                await preview_service.auto_select_primary(design_id)
                await db.commit()

            return {
                "design_id": design_id,
                "renders": 1,
                "stl_file": stl_file.filename,
            }
        else:
            return {
                "design_id": design_id,
                "renders": 0,
                "message": "Render failed",
            }

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
                    image_data=image_data,
                    source=PreviewSource.RENDERED,
                    kind=PreviewKind.THUMBNAIL,
                    original_filename=output_path.name,
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
