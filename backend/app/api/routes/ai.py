"""AI Analysis API endpoints (DEC-043).

Provides endpoints for triggering AI analysis on designs and managing AI settings.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Design
from app.db.models.enums import JobType
from app.services.job_queue import JobQueueService

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class AnalyzeRequest(BaseModel):
    """Request to analyze a design."""

    force: bool = Field(
        default=False,
        description="Re-analyze even if already analyzed",
    )


class AnalyzeResponse(BaseModel):
    """Response after queuing analysis."""

    job_id: str
    design_id: str
    status: str = "queued"


class BulkAnalyzeRequest(BaseModel):
    """Request to analyze multiple designs."""

    design_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Design IDs to analyze",
    )
    force: bool = Field(
        default=False,
        description="Re-analyze even if already analyzed",
    )


class BulkAnalyzeResponse(BaseModel):
    """Response after queuing bulk analysis."""

    jobs: list[AnalyzeResponse]
    total_queued: int


class AiStatusResponse(BaseModel):
    """AI service status."""

    enabled: bool
    configured: bool
    model: str


class AiSettingsResponse(BaseModel):
    """AI settings for settings page."""

    enabled: bool
    model: str
    api_key_configured: bool
    auto_analyze_on_import: bool
    select_best_preview: bool
    rate_limit_rpm: int
    max_tags_per_design: int


class AiSettingsUpdate(BaseModel):
    """Request to update AI settings."""

    enabled: bool | None = None
    model: str | None = None
    api_key: str | None = Field(
        default=None,
        description="New API key (or empty string to clear)",
    )
    auto_analyze_on_import: bool | None = None
    select_best_preview: bool | None = None
    rate_limit_rpm: int | None = Field(default=None, ge=5, le=60)
    max_tags_per_design: int | None = Field(default=None, ge=1, le=30)


# =============================================================================
# Helper Functions
# =============================================================================


def _check_ai_enabled() -> None:
    """Check if AI is enabled and raise 503 if not."""
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis is disabled. Enable it in settings.",
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=AiStatusResponse)
async def get_ai_status() -> AiStatusResponse:
    """Get AI service status."""
    return AiStatusResponse(
        enabled=settings.ai_enabled,
        configured=settings.ai_configured,
        model=settings.ai_model,
    )


@router.get("/settings", response_model=AiSettingsResponse)
async def get_ai_settings(
    db: AsyncSession = Depends(get_db),
) -> AiSettingsResponse:
    """Get AI settings for settings page.

    Reads from database first, falling back to environment variables.
    """
    from app.services.settings import SettingsService

    settings_service = SettingsService(db)

    return AiSettingsResponse(
        enabled=await settings_service.get("ai_enabled", settings.ai_enabled),
        model=await settings_service.get("ai_model", settings.ai_model),
        api_key_configured=settings.ai_api_key is not None,
        auto_analyze_on_import=await settings_service.get(
            "ai_auto_analyze_on_import", settings.ai_auto_analyze_on_import
        ),
        select_best_preview=await settings_service.get(
            "ai_select_best_preview", settings.ai_select_best_preview
        ),
        rate_limit_rpm=await settings_service.get(
            "ai_rate_limit_rpm", settings.ai_rate_limit_rpm
        ),
        max_tags_per_design=await settings_service.get(
            "ai_max_tags_per_design", settings.ai_max_tags_per_design
        ),
    )


@router.put("/settings", response_model=AiSettingsResponse)
async def update_ai_settings(
    request: AiSettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> AiSettingsResponse:
    """Update AI settings.

    Note: AI settings (especially api_key) must be configured via environment
    variables for security. This endpoint updates the runtime-configurable
    settings only.
    """
    from app.services.settings import SettingsService

    settings_service = SettingsService(db)
    updated_keys: list[str] = []

    # Only allow updating non-sensitive settings via API
    if request.enabled is not None:
        await settings_service.set("ai_enabled", request.enabled)
        updated_keys.append("ai_enabled")

    if request.model is not None:
        await settings_service.set("ai_model", request.model)
        updated_keys.append("ai_model")

    if request.auto_analyze_on_import is not None:
        await settings_service.set("ai_auto_analyze_on_import", request.auto_analyze_on_import)
        updated_keys.append("ai_auto_analyze_on_import")

    if request.select_best_preview is not None:
        await settings_service.set("ai_select_best_preview", request.select_best_preview)
        updated_keys.append("ai_select_best_preview")

    if request.rate_limit_rpm is not None:
        await settings_service.set("ai_rate_limit_rpm", request.rate_limit_rpm)
        updated_keys.append("ai_rate_limit_rpm")

    if request.max_tags_per_design is not None:
        await settings_service.set("ai_max_tags_per_design", request.max_tags_per_design)
        updated_keys.append("ai_max_tags_per_design")

    # API key must be set via environment variable
    if request.api_key is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key must be configured via PRINTARR_AI_API_KEY environment variable",
        )

    if updated_keys:
        await db.commit()
        logger.info("ai_settings_updated", updates=updated_keys)

    # Return current settings (from env + db)
    return await get_ai_settings(db=db)


# NOTE: /analyze/bulk MUST come before /analyze/{design_id} to avoid route conflicts
@router.post("/analyze/bulk", response_model=BulkAnalyzeResponse)
async def bulk_analyze_designs(
    request: BulkAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> BulkAnalyzeResponse:
    """Queue AI analysis for multiple designs.

    Returns 503 if AI is disabled.
    Skips designs that don't exist (doesn't fail the whole request).
    """
    _check_ai_enabled()

    queue = JobQueueService(db)
    jobs: list[AnalyzeResponse] = []

    for design_id in request.design_ids:
        # Verify design exists
        design = await db.get(Design, design_id)
        if not design:
            logger.warning("bulk_analyze_design_not_found", design_id=design_id)
            continue

        # Queue the job
        job = await queue.enqueue(
            job_type=JobType.AI_ANALYZE_DESIGN,
            design_id=design_id,
            payload={
                "design_id": design_id,
                "force": request.force,
            },
            priority=-1,  # Lower priority for bulk operations
            display_name=f"AI: {design.canonical_title[:30]}..." if len(design.canonical_title) > 30 else f"AI: {design.canonical_title}",
        )

        jobs.append(AnalyzeResponse(
            job_id=job.id,
            design_id=design_id,
            status="queued",
        ))

    await db.commit()

    logger.info(
        "bulk_ai_analysis_queued",
        requested=len(request.design_ids),
        queued=len(jobs),
        force=request.force,
    )

    return BulkAnalyzeResponse(
        jobs=jobs,
        total_queued=len(jobs),
    )


@router.post("/analyze/{design_id}", response_model=AnalyzeResponse)
async def analyze_design(
    design_id: str,
    request: AnalyzeRequest = AnalyzeRequest(),
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Queue AI analysis for a single design.

    Returns 503 if AI is disabled.
    """
    _check_ai_enabled()

    # Verify design exists
    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Design {design_id} not found",
        )

    # Queue the job
    queue = JobQueueService(db)
    job = await queue.enqueue(
        job_type=JobType.AI_ANALYZE_DESIGN,
        design_id=design_id,
        payload={
            "design_id": design_id,
            "force": request.force,
        },
        display_name=f"AI: {design.canonical_title[:30]}..." if len(design.canonical_title) > 30 else f"AI: {design.canonical_title}",
    )
    await db.commit()

    logger.info(
        "ai_analysis_queued",
        design_id=design_id,
        job_id=job.id,
        force=request.force,
    )

    return AnalyzeResponse(
        job_id=job.id,
        design_id=design_id,
        status="queued",
    )
