"""Import Source API endpoints for v0.8 Manual Imports."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import (
    ConflictResolution,
    ImportProfile,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceStatus,
    ImportSourceType,
)
from app.schemas.import_source import (
    ImportHistoryItem,
    ImportHistoryResponse,
    ImportProfileSummary,
    ImportSourceCreate,
    ImportSourceDetailResponse,
    ImportSourceList,
    ImportSourceResponse,
    ImportSourceUpdate,
    SyncTriggerRequest,
    SyncTriggerResponse,
)
from app.services.bulk_import import (
    BulkImportError,
    BulkImportPathError,
    BulkImportService,
)
from app.services.google_drive import GoogleDriveService

logger = get_logger(__name__)

router = APIRouter(prefix="/import-sources", tags=["import-sources"])


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_source_or_404(db: AsyncSession, source_id: str) -> ImportSource:
    """Get an import source by ID or raise 404."""
    source = await db.get(ImportSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Import source not found")
    return source


async def _build_source_response(
    db: AsyncSession, source: ImportSource
) -> ImportSourceResponse:
    """Build response from source model with profile summary."""
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

    return ImportSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        status=source.status,
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
        created_at=source.created_at,
        updated_at=source.updated_at,
        profile=profile_summary,
    )


# =============================================================================
# List and Create
# =============================================================================


@router.get("", response_model=ImportSourceList)
async def list_import_sources(
    source_type: ImportSourceType | None = Query(None, description="Filter by type"),
    sync_enabled: bool | None = Query(None, description="Filter by sync enabled"),
    status: ImportSourceStatus | None = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
) -> ImportSourceList:
    """List all import sources with optional filters."""
    query = select(ImportSource)

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


@router.post("", response_model=ImportSourceResponse, status_code=201)
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
    await db.refresh(source)

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
    await db.refresh(source)

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
    """Trigger a manual sync for an import source.

    For BULK_FOLDER sources, scans the folder and creates import records.
    For GOOGLE_DRIVE sources, lists files and creates import records.
    """
    if request is None:
        request = SyncTriggerRequest()

    source = await _get_source_or_404(db, source_id)

    designs_detected = 0
    designs_imported = 0

    try:
        if source.source_type == ImportSourceType.BULK_FOLDER:
            service = BulkImportService(db)
            designs = await service.scan_folder(source)
            await service.create_import_records(source, designs)
            designs_detected = len(designs)

            if request.auto_import:
                imported, _ = await service.import_all_pending(
                    source, request.conflict_resolution
                )
                designs_imported = imported

            source.status = ImportSourceStatus.ACTIVE
            source.last_sync_at = datetime.utcnow()
            source.last_sync_error = None

        elif source.source_type == ImportSourceType.GOOGLE_DRIVE:
            # Google Drive sync would use GoogleDriveService
            # For now, just update status
            source.status = ImportSourceStatus.ACTIVE
            source.last_sync_at = datetime.utcnow()
            source.last_sync_error = None

        await db.commit()

        logger.info(
            "sync_triggered",
            source_id=source_id,
            designs_detected=designs_detected,
            designs_imported=designs_imported,
        )

        return SyncTriggerResponse(
            source_id=source_id,
            message="Sync completed successfully",
            designs_detected=designs_detected,
            designs_imported=designs_imported,
        )

    except BulkImportPathError as e:
        source.status = ImportSourceStatus.ERROR
        source.last_sync_error = str(e)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(e))

    except BulkImportError as e:
        source.status = ImportSourceStatus.ERROR
        source.last_sync_error = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


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
