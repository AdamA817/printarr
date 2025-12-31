"""Activity API endpoints for viewing job history."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Design, DesignSource, Job, JobStatus, JobType
from app.schemas.queue import (
    ActivityItemResponse,
    ActivityListResponse,
    DesignSummary,
    JobResultStats,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/", response_model=ActivityListResponse)
async def list_activity(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    job_type: JobType | None = Query(None, description="Filter by job type"),
    status: str | None = Query(None, description="Comma-separated statuses (SUCCESS,FAILED,CANCELED)"),
    db: AsyncSession = Depends(get_db),
) -> ActivityListResponse:
    """List completed jobs (activity history).

    Returns jobs that have finished (SUCCESS, FAILED, or CANCELED status).
    Ordered by finished_at descending (most recent first).
    """
    # Parse status filter
    status_list = []
    if status:
        for s in status.split(","):
            s = s.strip().upper()
            if s in ("SUCCESS", "FAILED", "CANCELED"):
                status_list.append(JobStatus(s))
    else:
        # Default to all completed statuses
        status_list = [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELED]

    # Build query with eager loading
    query = (
        select(Job)
        .options(
            selectinload(Job.design).selectinload(Design.sources).selectinload(DesignSource.channel)
        )
        .where(Job.status.in_(status_list))
    )

    # Apply job type filter
    if job_type:
        query = query.where(Job.type == job_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering: finished_at desc
    query = query.order_by(Job.finished_at.desc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Transform to response
    items = []
    for job in jobs:
        design_summary = None
        if job.design:
            channel_title = None
            if job.design.sources:
                preferred = next((s for s in job.design.sources if s.is_preferred), job.design.sources[0])
                if preferred.channel:
                    channel_title = preferred.channel.title

            design_summary = DesignSummary(
                id=job.design.id,
                canonical_title=job.design.canonical_title,
                canonical_designer=job.design.canonical_designer,
                channel_title=channel_title,
            )

        # Calculate duration
        duration_ms = None
        if job.started_at and job.finished_at:
            delta = job.finished_at - job.started_at
            duration_ms = int(delta.total_seconds() * 1000)

        # Parse result JSON if available
        result_stats = None
        if job.result_json:
            try:
                result_data = json.loads(job.result_json)
                result_stats = JobResultStats(**result_data)
            except (json.JSONDecodeError, TypeError):
                pass

        items.append(
            ActivityItemResponse(
                id=job.id,
                job_type=job.type,
                status=job.status,
                design=design_summary,
                created_at=job.created_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
                duration_ms=duration_ms,
                result=result_stats,
                last_error=job.last_error,
                attempts=job.attempts,
            )
        )

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return ActivityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.delete("/{job_id}", status_code=204)
async def delete_activity_item(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a completed job from activity history.

    Only works for completed jobs (SUCCESS, FAILED, CANCELED).
    """
    # Get the job
    query = select(Job).where(
        Job.id == job_id,
        Job.status.in_([JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELED]),
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Activity item not found or not deletable",
        )

    await db.delete(job)
    await db.commit()

    logger.info("activity_item_deleted", job_id=job_id)
