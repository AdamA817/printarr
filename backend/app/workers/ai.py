"""Worker for AI-powered design analysis (DEC-043).

Processes AI_ANALYZE_DESIGN jobs to generate tags and select best previews
using Google Gemini.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Job
from app.db.models.enums import JobType
from app.db.session import async_session_maker
from app.services.ai import AiRateLimitError, AiService
from app.workers.base import BaseWorker, RetryableError

logger = get_logger(__name__)


class AiWorker(BaseWorker):
    """Worker that processes AI analysis jobs.

    Uses Google Gemini to analyze design preview images and generate tags.
    Only processes jobs when AI is enabled and configured.

    Handles rate limit errors gracefully by scheduling retries.
    """

    job_types = [JobType.AI_ANALYZE_DESIGN]

    async def process(self, job: Job, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        """Process an AI_ANALYZE_DESIGN job.

        Args:
            job: The job to process.
            payload: Job payload with design_id and optional force flag.

        Returns:
            Result dict with analysis status.
        """
        # Check if AI is configured
        if not settings.ai_configured:
            logger.debug(
                "ai_not_configured",
                job_id=job.id,
            )
            return {
                "skipped": True,
                "reason": "AI not configured",
            }

        if not payload:
            return {"error": "No payload provided"}

        design_id = payload.get("design_id")
        if not design_id:
            return {"error": "No design_id in payload"}

        force = payload.get("force", False)

        # Run analysis
        async with async_session_maker() as db:
            ai_service = AiService(db)

            try:
                result = await ai_service.analyze_design(
                    design_id=design_id,
                    force=force,
                )

                if result is None:
                    return {
                        "design_id": design_id,
                        "skipped": True,
                        "reason": "Already analyzed or no previews",
                    }

                await db.commit()

                return {
                    "design_id": design_id,
                    "tags_count": len(result.tags),
                    "tags": result.tags,
                    "best_preview_index": result.best_preview_index,
                }

            except AiRateLimitError as e:
                # Rate limited by Gemini - retry with appropriate delay
                logger.warning(
                    "ai_analysis_rate_limited",
                    job_id=job.id,
                    design_id=design_id,
                    retry_after=e.retry_after,
                )
                # Raise RetryableError to trigger job retry with backoff
                raise RetryableError(
                    f"Gemini rate limit - retry after {e.retry_after}s"
                )

            except Exception as e:
                logger.error(
                    "ai_analysis_job_error",
                    job_id=job.id,
                    design_id=design_id,
                    error=str(e),
                    exc_info=True,
                )
                raise
