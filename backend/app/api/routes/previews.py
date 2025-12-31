"""Preview API endpoints for managing design preview images."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.db.models import PreviewAsset
from app.db.models.enums import PreviewKind, PreviewSource
from app.services.preview import PreviewService

logger = get_logger(__name__)

router = APIRouter(prefix="/previews", tags=["previews"])


# =============================================================================
# Response Schemas
# =============================================================================


class PreviewResponse(BaseModel):
    """Preview asset response."""

    model_config = {"from_attributes": True}

    id: str
    design_id: str
    source: PreviewSource
    kind: PreviewKind
    file_path: str
    file_size: int | None
    original_filename: str | None
    width: int | None
    height: int | None
    telegram_file_id: str | None
    is_primary: bool
    sort_order: int
    created_at: datetime


class PreviewListResponse(BaseModel):
    """List of previews response."""

    items: list[PreviewResponse]
    total: int


class UpdatePreviewRequest(BaseModel):
    """Request body for updating a preview."""

    is_primary: bool | None = None
    sort_order: int | None = None


class UpdatePreviewResponse(BaseModel):
    """Response for preview update."""

    id: str
    is_primary: bool
    sort_order: int
    message: str


class DeletePreviewResponse(BaseModel):
    """Response for preview deletion."""

    id: str
    message: str


class AutoSelectPrimaryResponse(BaseModel):
    """Response for auto-select primary."""

    design_id: str
    selected_preview_id: str | None
    message: str


# =============================================================================
# Static File Serving
# =============================================================================


@router.get("/files/{path:path}")
async def serve_preview_file(path: str) -> FileResponse:
    """Serve a preview image file.

    Security: Validates path to prevent directory traversal.
    Returns appropriate Content-Type header based on file extension.
    """
    service = PreviewService()
    file_path = service.get_static_path(path)

    if not file_path:
        raise HTTPException(status_code=404, detail="Preview file not found")

    # Determine content type
    ext = file_path.suffix.lower()
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
        },
    )


# =============================================================================
# Preview CRUD Operations
# =============================================================================


@router.get("/{preview_id}", response_model=PreviewResponse)
async def get_preview(
    preview_id: str,
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    """Get a single preview by ID."""
    preview = await db.get(PreviewAsset, preview_id)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found")

    return PreviewResponse(
        id=preview.id,
        design_id=preview.design_id,
        source=preview.source,
        kind=preview.kind,
        file_path=preview.file_path,
        file_size=preview.file_size,
        original_filename=preview.original_filename,
        width=preview.width,
        height=preview.height,
        telegram_file_id=preview.telegram_file_id,
        is_primary=preview.is_primary,
        sort_order=preview.sort_order,
        created_at=preview.created_at,
    )


@router.patch("/{preview_id}", response_model=UpdatePreviewResponse)
async def update_preview(
    preview_id: str,
    request: UpdatePreviewRequest,
    db: AsyncSession = Depends(get_db),
) -> UpdatePreviewResponse:
    """Update preview properties (set primary, sort order)."""
    service = PreviewService(db)

    preview = await db.get(PreviewAsset, preview_id)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found")

    changes = []

    if request.is_primary is not None and request.is_primary:
        await service.set_primary(preview_id)
        changes.append("set as primary")

    if request.sort_order is not None:
        preview.sort_order = request.sort_order
        changes.append(f"sort_order={request.sort_order}")

    await db.commit()
    await db.refresh(preview)

    message = f"Updated: {', '.join(changes)}" if changes else "No changes"

    logger.info(
        "preview_updated",
        preview_id=preview_id,
        changes=changes,
    )

    return UpdatePreviewResponse(
        id=preview.id,
        is_primary=preview.is_primary,
        sort_order=preview.sort_order,
        message=message,
    )


@router.delete("/{preview_id}", response_model=DeletePreviewResponse)
async def delete_preview(
    preview_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeletePreviewResponse:
    """Delete a preview and its file."""
    service = PreviewService(db)

    success = await service.delete_preview(preview_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preview not found")

    await db.commit()

    return DeletePreviewResponse(
        id=preview_id,
        message="Preview deleted",
    )


# =============================================================================
# Design Preview Endpoints
# =============================================================================


@router.get("/design/{design_id}/", response_model=PreviewListResponse)
async def list_design_previews(
    design_id: str,
    source: PreviewSource | None = Query(None, description="Filter by source"),
    kind: PreviewKind | None = Query(None, description="Filter by kind"),
    db: AsyncSession = Depends(get_db),
) -> PreviewListResponse:
    """List all previews for a design."""
    query = select(PreviewAsset).where(PreviewAsset.design_id == design_id)

    if source:
        query = query.where(PreviewAsset.source == source)
    if kind:
        query = query.where(PreviewAsset.kind == kind)

    query = query.order_by(
        PreviewAsset.is_primary.desc(),
        PreviewAsset.sort_order.asc(),
        PreviewAsset.created_at.asc(),
    )

    result = await db.execute(query)
    previews = list(result.scalars().all())

    items = [
        PreviewResponse(
            id=p.id,
            design_id=p.design_id,
            source=p.source,
            kind=p.kind,
            file_path=p.file_path,
            file_size=p.file_size,
            original_filename=p.original_filename,
            width=p.width,
            height=p.height,
            telegram_file_id=p.telegram_file_id,
            is_primary=p.is_primary,
            sort_order=p.sort_order,
            created_at=p.created_at,
        )
        for p in previews
    ]

    return PreviewListResponse(
        items=items,
        total=len(items),
    )


@router.post("/design/{design_id}/auto-select-primary", response_model=AutoSelectPrimaryResponse)
async def auto_select_primary(
    design_id: str,
    db: AsyncSession = Depends(get_db),
) -> AutoSelectPrimaryResponse:
    """Auto-select the best preview as primary based on source priority.

    Per DEC-032, priority order:
    1. RENDERED (we generated it)
    2. EMBEDDED_3MF (designer's intended preview)
    3. ARCHIVE (designer included it)
    4. THANGS (authoritative external source)
    5. TELEGRAM (channel post image)
    """
    service = PreviewService(db)
    selected_id = await service.auto_select_primary(design_id)

    await db.commit()

    if selected_id:
        return AutoSelectPrimaryResponse(
            design_id=design_id,
            selected_preview_id=selected_id,
            message="Primary preview auto-selected",
        )
    else:
        return AutoSelectPrimaryResponse(
            design_id=design_id,
            selected_preview_id=None,
            message="No previews available for this design",
        )
