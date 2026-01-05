"""Queue API endpoints for managing the job queue."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import Design, DesignSource, ImportSource, Job, JobStatus, JobType
from app.schemas.queue import (
    DesignSummary,
    ImportSourceSummary,
    QueueItemResponse,
    QueueListResponse,
    QueueStatsResponse,
    UpdatePriorityRequest,
)
from app.services.job_queue import JobQueueService

logger = get_logger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/", response_model=QueueListResponse)
async def list_queue(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    job_type: JobType | None = Query(None, description="Filter by job type"),
    status: str | None = Query(None, description="Comma-separated statuses (QUEUED,RUNNING)"),
    db: AsyncSession = Depends(get_db),
) -> QueueListResponse:
    """List queued and running jobs.

    Returns jobs that are currently in the queue (QUEUED or RUNNING status).
    """
    # Parse status filter
    status_list = []
    if status:
        for s in status.split(","):
            s = s.strip().upper()
            if s in ("QUEUED", "RUNNING"):
                status_list.append(JobStatus(s))
    else:
        # Default to queued and running
        status_list = [JobStatus.QUEUED, JobStatus.RUNNING]

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

    # Apply ordering: priority desc, then created_at asc
    query = query.order_by(Job.priority.desc(), Job.created_at.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Collect source IDs from SYNC_IMPORT_SOURCE jobs
    source_ids = set()
    for job in jobs:
        if job.type == JobType.SYNC_IMPORT_SOURCE and job.payload_json:
            try:
                payload = json.loads(job.payload_json)
                if source_id := payload.get("source_id"):
                    source_ids.add(source_id)
            except (json.JSONDecodeError, TypeError):
                pass

    # Load import sources in bulk
    source_map: dict[str, ImportSource] = {}
    if source_ids:
        source_result = await db.execute(
            select(ImportSource).where(ImportSource.id.in_(source_ids))
        )
        for source in source_result.scalars().all():
            source_map[source.id] = source

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

        # Get import source for SYNC_IMPORT_SOURCE jobs
        import_source_summary = None
        if job.type == JobType.SYNC_IMPORT_SOURCE and job.payload_json:
            try:
                payload = json.loads(job.payload_json)
                if source_id := payload.get("source_id"):
                    if source := source_map.get(source_id):
                        import_source_summary = ImportSourceSummary(
                            id=source.id,
                            name=source.name,
                            source_type=source.source_type.value,
                        )
            except (json.JSONDecodeError, TypeError):
                pass

        items.append(
            QueueItemResponse(
                id=job.id,
                job_type=job.type,
                status=job.status,
                priority=job.priority,
                display_name=job.display_name,
                progress=job.progress_percent,
                progress_message=_get_progress_message(job),
                design=design_summary,
                import_source=import_source_summary,
                created_at=job.created_at,
                started_at=job.started_at,
                last_error=job.last_error,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
            )
        )

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return QueueListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    db: AsyncSession = Depends(get_db),
) -> QueueStatsResponse:
    """Get queue statistics.

    Returns counts of jobs by status and type for active jobs.
    """
    queue = JobQueueService(db)
    stats = await queue.get_queue_stats()

    # Calculate specific counts
    by_status = stats.get("by_status", {})
    by_type = stats.get("by_type", {})

    queued = by_status.get("QUEUED", 0)
    running = by_status.get("RUNNING", 0)

    # Count by job type (only running jobs for these stats)
    downloading = by_type.get("DOWNLOAD_DESIGN", 0)
    extracting = by_type.get("EXTRACT_ARCHIVE", 0)
    importing = by_type.get("IMPORT_TO_LIBRARY", 0)

    return QueueStatsResponse(
        queued=queued,
        downloading=downloading,
        extracting=extracting,
        importing=importing,
        total_active=queued + running,
        by_status=by_status,
        by_type=by_type,
    )


@router.patch("/{job_id}", response_model=QueueItemResponse)
async def update_job_priority(
    job_id: str,
    request: UpdatePriorityRequest,
    db: AsyncSession = Depends(get_db),
) -> QueueItemResponse:
    """Update job priority.

    Only works for QUEUED jobs.
    """
    # Get job with design
    query = (
        select(Job)
        .options(
            selectinload(Job.design).selectinload(Design.sources).selectinload(DesignSource.channel)
        )
        .where(Job.id == job_id)
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.QUEUED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update priority for job with status {job.status.value}",
        )

    job.priority = request.priority
    await db.commit()

    logger.info(
        "job_priority_updated",
        job_id=job_id,
        priority=request.priority,
    )

    # Build response
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

    return QueueItemResponse(
        id=job.id,
        job_type=job.type,
        status=job.status,
        priority=job.priority,
        display_name=job.display_name,
        progress=job.progress_percent,
        progress_message=_get_progress_message(job),
        design=design_summary,
        created_at=job.created_at,
        started_at=job.started_at,
        last_error=job.last_error,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
    )


@router.delete("/{job_id}", status_code=204)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a job.

    Only works for QUEUED or RUNNING jobs.
    """
    queue = JobQueueService(db)
    job = await queue.cancel(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found or not cancellable",
        )

    await db.commit()

    logger.info("job_cancelled", job_id=job_id)


def _format_bytes(size: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _get_progress_message(job: Job) -> str | None:
    """Get a human-readable progress message for a job (#161).

    Shows file-level progress when available:
    - "Downloading file.stl (2.5MB / 10MB) [3/5]"
    """
    if job.status == JobStatus.QUEUED:
        return "Waiting..."
    elif job.status == JobStatus.RUNNING:
        # Parse extended progress from payload
        progress_info = {}
        if job.payload_json:
            try:
                payload = json.loads(job.payload_json)
                progress_info = payload.get("progress", {})
            except (json.JSONDecodeError, TypeError):
                pass

        current_file = progress_info.get("current_file")
        current_file_bytes = progress_info.get("current_file_bytes")
        current_file_total = progress_info.get("current_file_total")

        if job.type == JobType.DOWNLOAD_DESIGN:
            # Build detailed message
            parts = ["Downloading"]

            if current_file:
                # Truncate long filenames
                display_name = current_file[:30] + "..." if len(current_file) > 30 else current_file
                parts.append(f" {display_name}")

            # Show byte progress for current file
            if current_file_bytes is not None and current_file_total:
                parts.append(f" ({_format_bytes(current_file_bytes)} / {_format_bytes(current_file_total)})")
            elif current_file_bytes is not None:
                parts.append(f" ({_format_bytes(current_file_bytes)})")

            # Show file count progress
            if job.progress_current is not None and job.progress_total:
                parts.append(f" [{job.progress_current}/{job.progress_total}]")

            return "".join(parts)

        elif job.type == JobType.EXTRACT_ARCHIVE:
            if current_file:
                display_name = current_file[:30] + "..." if len(current_file) > 30 else current_file
                if job.progress_current is not None and job.progress_total:
                    return f"Extracting {display_name} [{job.progress_current}/{job.progress_total}]"
                return f"Extracting {display_name}..."
            return "Extracting archives..."

        elif job.type == JobType.IMPORT_TO_LIBRARY:
            if current_file:
                display_name = current_file[:30] + "..." if len(current_file) > 30 else current_file
                if job.progress_current is not None and job.progress_total:
                    return f"Organizing {display_name} [{job.progress_current}/{job.progress_total}]"
                return f"Organizing {display_name}..."
            return "Organizing files..."

        elif job.type == JobType.SYNC_IMPORT_SOURCE:
            if current_file:
                display_name = current_file[:30] + "..." if len(current_file) > 30 else current_file
                if job.progress_current is not None and job.progress_total:
                    return f"Syncing {display_name} [{job.progress_current}/{job.progress_total}]"
                return f"Syncing {display_name}..."
            if job.progress_percent is not None:
                return f"Syncing... {job.progress_percent:.0f}%"
            return "Syncing..."

        elif job.type == JobType.DOWNLOAD_IMPORT_RECORD:
            # DEC-040: Per-design download jobs
            # Use display_name if available, otherwise generic message
            if job.display_name:
                # Extract just the design name from "Download: Dragon Bust from Wicked STL"
                parts = []
                if current_file:
                    display_file = current_file[:30] + "..." if len(current_file) > 30 else current_file
                    parts.append(f"Downloading {display_file}")
                else:
                    parts.append(job.display_name.split(" from ")[0])  # "Download: Dragon Bust"

                # Show byte progress for current file
                if current_file_bytes is not None and current_file_total:
                    parts.append(f" ({_format_bytes(current_file_bytes)} / {_format_bytes(current_file_total)})")

                # Show file count progress
                if job.progress_current is not None and job.progress_total:
                    parts.append(f" [{job.progress_current}/{job.progress_total}]")

                return "".join(parts)
            return "Downloading..."

        else:
            return "Processing..."
    return None
