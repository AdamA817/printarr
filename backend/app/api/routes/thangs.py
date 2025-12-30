"""Thangs API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import get_db
from app.services.thangs import (
    ThangsAdapter,
    ThangsRateLimitError,
    ThangsUpstreamError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/thangs", tags=["thangs"])


class ThangsSearchResultResponse(BaseModel):
    """A single search result from Thangs."""

    model_id: str
    title: str
    designer: str | None = None
    thumbnail_url: str | None = None
    url: str


class ThangsSearchResponse(BaseModel):
    """Response for Thangs search endpoint."""

    results: list[ThangsSearchResultResponse]
    total: int


@router.get("/search", response_model=ThangsSearchResponse)
async def search_thangs(
    q: str = Query(..., min_length=3, description="Search query (min 3 characters)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results (1-50)"),
    db: AsyncSession = Depends(get_db),
) -> ThangsSearchResponse:
    """Search Thangs for 3D models.

    Returns search results from the Thangs API that can be used for manual
    linking of designs.

    - Results are cached for 5 minutes to reduce API calls
    - Rate limiting is handled gracefully (returns 429)
    - Upstream errors return 502
    """
    adapter = ThangsAdapter(db)

    try:
        search_result = await adapter.search(query=q, limit=limit)

        return ThangsSearchResponse(
            results=[
                ThangsSearchResultResponse(
                    model_id=r.model_id,
                    title=r.title,
                    designer=r.designer,
                    thumbnail_url=r.thumbnail_url,
                    url=r.url,
                )
                for r in search_result.results
            ],
            total=search_result.total,
        )

    except ThangsRateLimitError as e:
        logger.warning("thangs_search_rate_limited", retry_after=e.retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Thangs API rate limited. Retry after {e.retry_after} seconds.",
            headers={"Retry-After": str(e.retry_after)},
        )

    except ThangsUpstreamError as e:
        logger.error("thangs_search_upstream_error", error=str(e))
        raise HTTPException(
            status_code=502,
            detail="Thangs API is unavailable. Please try again later.",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        await adapter.close()
