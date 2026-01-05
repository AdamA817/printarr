"""File upload API endpoints for direct file uploads (v0.8).

Provides endpoints for:
- Single and batch file uploads via multipart/form-data
- Upload status checking
- Upload processing (trigger import)
- Upload deletion/cleanup

See DEC-033 for Import Source design decisions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.schemas.upload import (
    BatchUploadResponse,
    ProcessUploadRequest,
    ProcessUploadResponse,
    UploadInfo,
    UploadResponse,
    UploadStatusResponse,
)
from app.services.upload import (
    UploadError,
    UploadNotFoundError,
    UploadProcessingError,
    UploadService,
    UploadValidationError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/files", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Upload a single file.

    Accepts multipart/form-data with a single file. The file is saved to
    staging and must be processed separately via POST /upload/{upload_id}/process.

    Supported file types: .zip, .rar, .7z, .stl, .3mf, .obj, .step, .stp
    Maximum file size: 500MB (configurable)
    """
    service = UploadService(db)
    await service.ensure_staging_dir()

    try:
        # Read file content
        content = await file.read()

        response = await service.create_upload(
            filename=file.filename or "unnamed_file",
            file_content=content,
            content_type=file.content_type,
        )

        await db.commit()

        logger.info(
            "file_uploaded",
            upload_id=response.upload_id,
            filename=response.filename,
            size=response.size,
        )

        return response

    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UploadError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/batch", response_model=BatchUploadResponse)
async def upload_files_batch(
    files: list[UploadFile] = File(..., description="Files to upload"),
    db: AsyncSession = Depends(get_db),
) -> BatchUploadResponse:
    """Upload multiple files in a single request.

    Accepts multipart/form-data with multiple files. Each file is saved
    separately and must be processed individually.

    Maximum 10 files per batch.
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files per batch upload",
        )

    service = UploadService(db)
    await service.ensure_staging_dir()

    uploads: list[UploadResponse] = []
    total_size = 0
    errors: list[str] = []

    for file in files:
        try:
            content = await file.read()
            response = await service.create_upload(
                filename=file.filename or "unnamed_file",
                file_content=content,
                content_type=file.content_type,
            )
            uploads.append(response)
            total_size += response.size

        except UploadValidationError as e:
            errors.append(f"{file.filename}: {str(e)}")
        except UploadError as e:
            errors.append(f"{file.filename}: {str(e)}")

    await db.commit()

    if not uploads and errors:
        raise HTTPException(
            status_code=400,
            detail=f"All uploads failed: {'; '.join(errors)}",
        )

    # Generate batch ID from first upload
    import uuid
    batch_id = str(uuid.uuid4())

    logger.info(
        "batch_uploaded",
        batch_id=batch_id,
        file_count=len(uploads),
        total_size=total_size,
        errors=len(errors),
    )

    return BatchUploadResponse(
        batch_id=batch_id,
        uploads=uploads,
        total_size=total_size,
    )


@router.get("/", response_model=list[UploadInfo])
async def list_uploads(
    include_expired: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[UploadInfo]:
    """List all uploads in staging.

    Returns uploads sorted by creation time (newest first).
    """
    service = UploadService(db)
    return await service.list_uploads(include_expired=include_expired)


@router.get("/{upload_id}", response_model=UploadInfo)
async def get_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
) -> UploadInfo:
    """Get information about a specific upload."""
    service = UploadService(db)

    try:
        return await service.get_upload(upload_id)
    except UploadNotFoundError:
        raise HTTPException(status_code=404, detail="Upload not found")


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
) -> UploadStatusResponse:
    """Get processing status of an upload.

    This endpoint is optimized for polling during processing.
    """
    service = UploadService(db)

    try:
        info = await service.get_upload(upload_id)
        return UploadStatusResponse(
            upload_id=info.id,
            filename=info.filename,
            status=info.status,
            error_message=info.error_message,
            design_id=info.design_id,
            progress=100 if info.design_id else 0,
        )
    except UploadNotFoundError:
        raise HTTPException(status_code=404, detail="Upload not found")


@router.post("/{upload_id}/process", response_model=ProcessUploadResponse)
async def process_upload(
    upload_id: str,
    request: ProcessUploadRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> ProcessUploadResponse:
    """Process an uploaded file and create a design.

    Extracts archives, detects design files, and creates a catalog entry.
    """
    service = UploadService(db)

    request = request or ProcessUploadRequest()

    try:
        response = await service.process_upload(
            upload_id=upload_id,
            import_profile_id=request.import_profile_id,
            designer=request.designer,
            tags=request.tags,
            title=request.title,
        )

        await db.commit()

        return response

    except UploadNotFoundError:
        raise HTTPException(status_code=404, detail="Upload not found")
    except UploadProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{upload_id}", status_code=204)
async def delete_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an upload and its files.

    Removes the upload from staging. Cannot delete completed uploads
    that have already been imported.
    """
    service = UploadService(db)

    try:
        info = await service.get_upload(upload_id)
        if info.design_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete processed upload. Delete the design instead.",
            )

        await service.delete_upload(upload_id)

    except UploadNotFoundError:
        raise HTTPException(status_code=404, detail="Upload not found")


@router.post("/cleanup", response_model=dict)
async def cleanup_expired_uploads(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clean up expired uploads.

    Removes uploads that exceed the retention period and haven't been processed.
    This is typically called by a scheduled task.
    """
    service = UploadService(db)
    cleaned = await service.cleanup_expired()

    return {"cleaned": cleaned}
