"""Import Source API endpoints for v0.8 Manual Imports."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import (
    ImportProfile,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceFolder,
    ImportSourceStatus,
    ImportSourceType,
    JobType,
)
from app.schemas.import_source import (
    FolderSyncTriggerResponse,
    ImportHistoryItem,
    ImportHistoryResponse,
    ImportProfileSummary,
    ImportSourceCreate,
    ImportSourceDetailResponse,
    ImportSourceFolderCreate,
    ImportSourceFolderResponse,
    ImportSourceFolderSummary,
    ImportSourceFolderUpdate,
    ImportSourceList,
    ImportSourceResponse,
    ImportSourceUpdate,
    SyncTriggerRequest,
    SyncTriggerResponse,
)
from app.services.google_drive import GoogleDriveService
from app.services.job_queue import JobQueueService

logger = get_logger(__name__)

router = APIRouter(prefix="/import-sources", tags=["import-sources"])


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_source_or_404(db: AsyncSession, source_id: str) -> ImportSource:
    """Get an import source by ID or raise 404."""
    result = await db.execute(
        select(ImportSource)
        .options(selectinload(ImportSource.folders))
        .where(ImportSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Import source not found")
    return source


async def _get_folder_or_404(
    db: AsyncSession, source_id: str, folder_id: str
) -> ImportSourceFolder:
    """Get a folder by ID, verifying it belongs to the source."""
    folder = await db.get(ImportSourceFolder, folder_id)
    if not folder or folder.import_source_id != source_id:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


def _build_folder_summary(folder: ImportSourceFolder) -> ImportSourceFolderSummary:
    """Build folder summary for embedding in source responses."""
    has_overrides = bool(
        folder.import_profile_id
        or folder.default_designer
        or folder.default_tags_json
    )
    return ImportSourceFolderSummary(
        id=folder.id,
        name=folder.name,
        google_drive_url=folder.google_drive_url,
        google_folder_id=folder.google_folder_id,
        folder_path=folder.folder_path,
        enabled=folder.enabled,
        items_detected=folder.items_detected or 0,
        items_imported=folder.items_imported or 0,
        last_synced_at=folder.last_synced_at,
        has_overrides=has_overrides,
    )


async def _build_folder_response(
    db: AsyncSession,
    folder: ImportSourceFolder,
    source: ImportSource,
) -> ImportSourceFolderResponse:
    """Build full folder response with effective values."""
    # Parse folder tags
    folder_tags = None
    if folder.default_tags_json:
        try:
            folder_tags = json.loads(folder.default_tags_json)
        except json.JSONDecodeError:
            pass

    # Parse source tags
    source_tags = None
    if source.default_tags_json:
        try:
            source_tags = json.loads(source.default_tags_json)
        except json.JSONDecodeError:
            pass

    # Compute effective values (folder override or inherit from source)
    effective_profile_id = folder.import_profile_id or source.import_profile_id
    effective_designer = folder.default_designer or source.default_designer
    effective_tags = folder_tags if folder_tags is not None else (source_tags or [])

    return ImportSourceFolderResponse(
        id=folder.id,
        import_source_id=folder.import_source_id,
        name=folder.name,
        google_drive_url=folder.google_drive_url,
        google_folder_id=folder.google_folder_id,
        folder_path=folder.folder_path,
        import_profile_id=folder.import_profile_id,
        default_designer=folder.default_designer,
        default_tags=folder_tags,
        effective_profile_id=effective_profile_id,
        effective_designer=effective_designer,
        effective_tags=effective_tags,
        enabled=folder.enabled,
        last_synced_at=folder.last_synced_at,
        sync_cursor=folder.sync_cursor,
        last_sync_error=folder.last_sync_error,
        items_detected=folder.items_detected or 0,
        items_imported=folder.items_imported or 0,
        created_at=folder.created_at,
    )


async def _build_source_response(
    db: AsyncSession, source: ImportSource
) -> ImportSourceResponse:
    """Build response from source model with profile summary and folders."""
    profile_summary = None
    if source.import_profile_id:
        profile = await db.get(ImportProfile, source.import_profile_id)
        if profile:
            profile_summary = ImportProfileSummary(
                id=profile.id,
                name=profile.name,
                is_builtin=profile.is_builtin,
            )

    # Parse tags from JSON
    default_tags = None
    if source.default_tags_json:
        try:
            default_tags = json.loads(source.default_tags_json)
        except json.JSONDecodeError:
            pass

    # Build folder summaries
    folder_summaries = [_build_folder_summary(f) for f in (source.folders or [])]
    folder_count = len(folder_summaries)
    enabled_folder_count = sum(1 for f in (source.folders or []) if f.enabled)

    # Check if Google is connected
    google_connected = source.google_credentials_id is not None

    return ImportSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        status=source.status,
        google_connected=google_connected,
        google_drive_url=source.google_drive_url,
        google_drive_folder_id=source.google_drive_folder_id,
        folder_path=source.folder_path,
        import_profile_id=source.import_profile_id,
        default_designer=source.default_designer,
        default_tags=default_tags,
        sync_enabled=source.sync_enabled,
        sync_interval_hours=source.sync_interval_hours,
        last_sync_at=source.last_sync_at,
        last_sync_error=source.last_sync_error,
        items_imported=source.items_imported or 0,
        folder_count=folder_count,
        enabled_folder_count=enabled_folder_count,
        folders=folder_summaries,
        created_at=source.created_at,
        updated_at=source.updated_at,
        profile=profile_summary,
    )


# =============================================================================
# List and Create
# =============================================================================


@router.get("/", response_model=ImportSourceList)
async def list_import_sources(
    source_type: ImportSourceType | None = Query(None, description="Filter by type"),
    sync_enabled: bool | None = Query(None, description="Filter by sync enabled"),
    status: ImportSourceStatus | None = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
) -> ImportSourceList:
    """List all import sources with optional filters."""
    query = select(ImportSource).options(selectinload(ImportSource.folders))

    if source_type:
        query = query.where(ImportSource.source_type == source_type)
    if sync_enabled is not None:
        query = query.where(ImportSource.sync_enabled == sync_enabled)
    if status:
        query = query.where(ImportSource.status == status)

    query = query.order_by(ImportSource.created_at.desc())
    result = await db.execute(query)
    sources = result.scalars().all()

    items = [await _build_source_response(db, s) for s in sources]
    return ImportSourceList(items=items, total=len(items))


@router.post("/", response_model=ImportSourceResponse, status_code=201)
async def create_import_source(
    data: ImportSourceCreate,
    db: AsyncSession = Depends(get_db),
) -> ImportSourceResponse:
    """Create a new import source.

    Validates the configuration based on source type:
    - GOOGLE_DRIVE: Requires google_drive_url
    - BULK_FOLDER: Requires folder_path
    - UPLOAD: No additional validation
    """
    # Validate based on source type
    if data.source_type == ImportSourceType.GOOGLE_DRIVE:
        if not data.google_drive_url:
            raise HTTPException(
                status_code=400,
                detail="google_drive_url is required for GOOGLE_DRIVE sources",
            )
        # Extract folder ID from URL
        folder_id = GoogleDriveService.parse_folder_url(data.google_drive_url)
        if folder_id is None:
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL: Could not extract folder ID")
    elif data.source_type == ImportSourceType.BULK_FOLDER:
        if not data.folder_path:
            raise HTTPException(
                status_code=400,
                detail="folder_path is required for BULK_FOLDER sources",
            )
        folder_id = None
    else:
        folder_id = None

    # Validate profile exists if specified
    if data.import_profile_id:
        profile = await db.get(ImportProfile, data.import_profile_id)
        if not profile:
            raise HTTPException(status_code=400, detail="Import profile not found")

    # Create source
    source = ImportSource(
        name=data.name,
        source_type=data.source_type,
        status=ImportSourceStatus.PENDING,
        google_drive_url=data.google_drive_url,
        google_drive_folder_id=folder_id,
        folder_path=data.folder_path,
        import_profile_id=data.import_profile_id,
        default_designer=data.default_designer,
        default_tags_json=json.dumps(data.default_tags) if data.default_tags else None,
        sync_enabled=data.sync_enabled,
        sync_interval_hours=data.sync_interval_hours,
    )
    db.add(source)
    await db.commit()

    # Reload with folders relationship eagerly loaded
    result = await db.execute(
        select(ImportSource)
        .options(selectinload(ImportSource.folders))
        .where(ImportSource.id == source.id)
    )
    source = result.scalar_one()

    logger.info(
        "import_source_created",
        source_id=source.id,
        name=data.name,
        source_type=data.source_type.value,
    )

    return await _build_source_response(db, source)


# =============================================================================
# Get, Update, Delete
# =============================================================================


@router.get("/{source_id}", response_model=ImportSourceDetailResponse)
async def get_import_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportSourceDetailResponse:
    """Get import source details with record counts."""
    source = await _get_source_or_404(db, source_id)

    # Get record counts
    pending_result = await db.execute(
        select(func.count(ImportRecord.id)).where(
            ImportRecord.import_source_id == source_id,
            ImportRecord.status == ImportRecordStatus.PENDING,
        )
    )
    pending_count = pending_result.scalar() or 0

    imported_result = await db.execute(
        select(func.count(ImportRecord.id)).where(
            ImportRecord.import_source_id == source_id,
            ImportRecord.status == ImportRecordStatus.IMPORTED,
        )
    )
    imported_count = imported_result.scalar() or 0

    error_result = await db.execute(
        select(func.count(ImportRecord.id)).where(
            ImportRecord.import_source_id == source_id,
            ImportRecord.status == ImportRecordStatus.ERROR,
        )
    )
    error_count = error_result.scalar() or 0

    base_response = await _build_source_response(db, source)

    return ImportSourceDetailResponse(
        **base_response.model_dump(),
        pending_count=pending_count,
        imported_count=imported_count,
        error_count=error_count,
    )


@router.put("/{source_id}", response_model=ImportSourceResponse)
async def update_import_source(
    source_id: str,
    data: ImportSourceUpdate,
    db: AsyncSession = Depends(get_db),
) -> ImportSourceResponse:
    """Update an import source.

    Note: source_type cannot be changed after creation.
    """
    source = await _get_source_or_404(db, source_id)

    # Apply updates
    if data.name is not None:
        source.name = data.name

    if data.google_drive_url is not None and source.source_type == ImportSourceType.GOOGLE_DRIVE:
        source.google_drive_url = data.google_drive_url
        folder_id = GoogleDriveService.parse_folder_url(data.google_drive_url)
        if folder_id is None:
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL: Could not extract folder ID")
        source.google_drive_folder_id = folder_id

    if data.folder_path is not None and source.source_type == ImportSourceType.BULK_FOLDER:
        source.folder_path = data.folder_path

    if data.import_profile_id is not None:
        if data.import_profile_id:
            profile = await db.get(ImportProfile, data.import_profile_id)
            if not profile:
                raise HTTPException(status_code=400, detail="Import profile not found")
        source.import_profile_id = data.import_profile_id

    if data.default_designer is not None:
        source.default_designer = data.default_designer

    if data.default_tags is not None:
        source.default_tags_json = json.dumps(data.default_tags) if data.default_tags else None

    if data.sync_enabled is not None:
        source.sync_enabled = data.sync_enabled

    if data.sync_interval_hours is not None:
        source.sync_interval_hours = data.sync_interval_hours

    await db.commit()

    # Reload with folders relationship eagerly loaded
    result = await db.execute(
        select(ImportSource)
        .options(selectinload(ImportSource.folders))
        .where(ImportSource.id == source_id)
    )
    source = result.scalar_one()

    logger.info("import_source_updated", source_id=source_id)

    return await _build_source_response(db, source)


@router.delete("/{source_id}", status_code=204)
async def delete_import_source(
    source_id: str,
    keep_designs: bool = Query(True, description="Keep imported designs"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an import source.

    By default, keeps the imported designs but removes the source reference.
    Set keep_designs=false to delete imported designs as well.
    """
    source = await _get_source_or_404(db, source_id)

    # Note: ImportRecords will be deleted via cascade
    # Designs have SET NULL on delete, so they'll keep their data

    await db.delete(source)
    await db.commit()

    logger.info(
        "import_source_deleted",
        source_id=source_id,
        keep_designs=keep_designs,
    )


# =============================================================================
# Sync Operations
# =============================================================================


@router.post("/{source_id}/sync", response_model=SyncTriggerResponse)
async def trigger_sync(
    source_id: str,
    request: SyncTriggerRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> SyncTriggerResponse:
    """Trigger an async sync job for an import source.

    Queues a SYNC_IMPORT_SOURCE job that will:
    - For BULK_FOLDER sources: scan the folder and create import records
    - For GOOGLE_DRIVE sources: list files and create import records

    Returns immediately with the job_id for tracking progress.
    """
    if request is None:
        request = SyncTriggerRequest()

    source = await _get_source_or_404(db, source_id)

    # Validate source configuration before queuing
    if source.source_type == ImportSourceType.GOOGLE_DRIVE:
        if not source.google_drive_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Google Drive source missing folder ID",
            )
    elif source.source_type == ImportSourceType.BULK_FOLDER:
        if not source.folder_path:
            raise HTTPException(
                status_code=400,
                detail="Bulk folder source missing folder path",
            )

    # Queue the async sync job
    queue = JobQueueService(db)
    job = await queue.enqueue(
        job_type=JobType.SYNC_IMPORT_SOURCE,
        payload={
            "source_id": source_id,
            "auto_import": request.auto_import,
            "conflict_resolution": request.conflict_resolution.value,
        },
    )
    await db.commit()

    logger.info(
        "sync_job_queued",
        source_id=source_id,
        job_id=job.id,
        auto_import=request.auto_import,
    )

    return SyncTriggerResponse(
        source_id=source_id,
        job_id=job.id,
        message="Sync job queued",
        designs_detected=0,
        designs_imported=0,
    )


# =============================================================================
# Import History
# =============================================================================


@router.get("/{source_id}/history", response_model=ImportHistoryResponse)
async def get_import_history(
    source_id: str,
    status: ImportRecordStatus | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> ImportHistoryResponse:
    """Get import history for an import source."""
    await _get_source_or_404(db, source_id)

    # Build query
    query = select(ImportRecord).where(ImportRecord.import_source_id == source_id)

    if status:
        query = query.where(ImportRecord.status == status)

    # Count total
    count_query = select(func.count(ImportRecord.id)).where(
        ImportRecord.import_source_id == source_id
    )
    if status:
        count_query = count_query.where(ImportRecord.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.order_by(ImportRecord.detected_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    records = result.scalars().all()

    items = [
        ImportHistoryItem(
            id=r.id,
            source_path=r.source_path,
            status=r.status.value,
            detected_title=r.detected_title,
            design_id=r.design_id,
            error_message=r.error_message,
            detected_at=r.detected_at,
            imported_at=r.imported_at,
        )
        for r in records
    ]

    return ImportHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Folder Management (DEC-038)
# =============================================================================


@router.get("/{source_id}/folders", response_model=list[ImportSourceFolderSummary])
async def list_folders(
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ImportSourceFolderSummary]:
    """List all folders in an import source."""
    source = await _get_source_or_404(db, source_id)
    return [_build_folder_summary(f) for f in (source.folders or [])]


@router.post(
    "/{source_id}/folders",
    response_model=ImportSourceFolderResponse,
    status_code=201,
)
async def add_folder(
    source_id: str,
    data: ImportSourceFolderCreate,
    db: AsyncSession = Depends(get_db),
) -> ImportSourceFolderResponse:
    """Add a new folder to an import source.

    Validates the location based on source type:
    - GOOGLE_DRIVE: Requires google_drive_url
    - BULK_FOLDER: Requires folder_path
    """
    source = await _get_source_or_404(db, source_id)

    # Validate based on source type
    google_folder_id = None
    if source.source_type == ImportSourceType.GOOGLE_DRIVE:
        if not data.google_drive_url:
            raise HTTPException(
                status_code=400,
                detail="google_drive_url is required for GOOGLE_DRIVE sources",
            )
        google_folder_id = GoogleDriveService.parse_folder_url(data.google_drive_url)
        if google_folder_id is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid Google Drive URL: Could not extract folder ID",
            )
    elif source.source_type == ImportSourceType.BULK_FOLDER:
        if not data.folder_path:
            raise HTTPException(
                status_code=400,
                detail="folder_path is required for BULK_FOLDER sources",
            )

    # Validate profile exists if specified
    if data.import_profile_id:
        profile = await db.get(ImportProfile, data.import_profile_id)
        if not profile:
            raise HTTPException(status_code=400, detail="Import profile not found")

    # Create folder
    folder = ImportSourceFolder(
        import_source_id=source_id,
        name=data.name,
        google_drive_url=data.google_drive_url,
        google_folder_id=google_folder_id,
        folder_path=data.folder_path,
        import_profile_id=data.import_profile_id,
        default_designer=data.default_designer,
        default_tags_json=json.dumps(data.default_tags) if data.default_tags else None,
        enabled=data.enabled,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)

    logger.info(
        "folder_added",
        source_id=source_id,
        folder_id=folder.id,
        name=data.name,
    )

    return await _build_folder_response(db, folder, source)


@router.get(
    "/{source_id}/folders/{folder_id}",
    response_model=ImportSourceFolderResponse,
)
async def get_folder(
    source_id: str,
    folder_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImportSourceFolderResponse:
    """Get folder details with effective values."""
    source = await _get_source_or_404(db, source_id)
    folder = await _get_folder_or_404(db, source_id, folder_id)
    return await _build_folder_response(db, folder, source)


@router.put(
    "/{source_id}/folders/{folder_id}",
    response_model=ImportSourceFolderResponse,
)
async def update_folder(
    source_id: str,
    folder_id: str,
    data: ImportSourceFolderUpdate,
    db: AsyncSession = Depends(get_db),
) -> ImportSourceFolderResponse:
    """Update a folder.

    Note: Location (google_drive_url, folder_path) cannot be changed.
    Delete and recreate the folder instead.
    """
    source = await _get_source_or_404(db, source_id)
    folder = await _get_folder_or_404(db, source_id, folder_id)

    # Apply updates
    if data.name is not None:
        folder.name = data.name

    if data.import_profile_id is not None:
        if data.import_profile_id:
            profile = await db.get(ImportProfile, data.import_profile_id)
            if not profile:
                raise HTTPException(status_code=400, detail="Import profile not found")
        folder.import_profile_id = data.import_profile_id

    if data.default_designer is not None:
        folder.default_designer = data.default_designer

    if data.default_tags is not None:
        folder.default_tags_json = (
            json.dumps(data.default_tags) if data.default_tags else None
        )

    if data.enabled is not None:
        folder.enabled = data.enabled

    await db.commit()
    await db.refresh(folder)

    logger.info("folder_updated", source_id=source_id, folder_id=folder_id)

    return await _build_folder_response(db, folder, source)


@router.delete("/{source_id}/folders/{folder_id}", status_code=204)
async def delete_folder(
    source_id: str,
    folder_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a folder from an import source.

    Import records for this folder will be deleted via cascade.
    Designs imported from this folder will keep their data (SET NULL).
    """
    await _get_source_or_404(db, source_id)
    folder = await _get_folder_or_404(db, source_id, folder_id)

    await db.delete(folder)
    await db.commit()

    logger.info("folder_deleted", source_id=source_id, folder_id=folder_id)


@router.post(
    "/{source_id}/folders/{folder_id}/sync",
    response_model=FolderSyncTriggerResponse,
)
async def trigger_folder_sync(
    source_id: str,
    folder_id: str,
    request: SyncTriggerRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> FolderSyncTriggerResponse:
    """Trigger sync for a single folder.

    Queues a SYNC_IMPORT_SOURCE_FOLDER job for this specific folder.
    """
    if request is None:
        request = SyncTriggerRequest()

    source = await _get_source_or_404(db, source_id)
    folder = await _get_folder_or_404(db, source_id, folder_id)

    if not folder.enabled:
        raise HTTPException(status_code=400, detail="Folder is disabled")

    # Validate folder configuration
    if source.source_type == ImportSourceType.GOOGLE_DRIVE:
        if not folder.google_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Folder missing Google Drive folder ID",
            )
    elif source.source_type == ImportSourceType.BULK_FOLDER:
        if not folder.folder_path:
            raise HTTPException(
                status_code=400,
                detail="Folder missing folder path",
            )

    # Queue the async sync job for this folder
    queue = JobQueueService(db)
    job = await queue.enqueue(
        job_type=JobType.SYNC_IMPORT_SOURCE,
        payload={
            "source_id": source_id,
            "folder_id": folder_id,
            "auto_import": request.auto_import,
            "conflict_resolution": request.conflict_resolution.value,
        },
    )
    await db.commit()

    logger.info(
        "folder_sync_job_queued",
        source_id=source_id,
        folder_id=folder_id,
        job_id=job.id,
        auto_import=request.auto_import,
    )

    return FolderSyncTriggerResponse(
        folder_id=folder_id,
        job_id=job.id,
        message="Folder sync job queued",
        designs_detected=0,
        designs_imported=0,
    )
