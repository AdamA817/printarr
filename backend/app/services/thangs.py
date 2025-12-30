"""Thangs adapter for URL detection and metadata fetching."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    Design,
    ExternalMetadataSource,
    ExternalSourceType,
    MatchMethod,
)

if TYPE_CHECKING:
    pass

# Rate limiting: delay between Thangs API calls (in seconds)
THANGS_API_DELAY = 0.5

# Cache TTL for search results (5 minutes)
SEARCH_CACHE_TTL = 300

# FlareSolverr timeout (60 seconds)
FLARESOLVERR_TIMEOUT = 60000

# Max retries for transient failures
MAX_RETRIES = 3
RETRY_DELAY = 2.0


@dataclass
class ThangsSearchResult:
    """A single search result from Thangs API."""

    model_id: str
    title: str
    designer: str | None
    thumbnail_url: str | None
    url: str


@dataclass
class ThangsSearchResponse:
    """Response from Thangs search."""

    results: list[ThangsSearchResult]
    total: int


class ThangsSearchError(Exception):
    """Base exception for Thangs search errors."""

    pass


class ThangsRateLimitError(ThangsSearchError):
    """Raised when Thangs API rate limit is hit."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after} seconds.")


class ThangsUpstreamError(ThangsSearchError):
    """Raised when Thangs API returns an error."""

    def __init__(self, message: str, status_code: int = 502):
        self.status_code = status_code
        super().__init__(message)


class FlareSolverrError(ThangsSearchError):
    """Raised when FlareSolverr returns an error."""

    def __init__(self, message: str):
        super().__init__(f"FlareSolverr error: {message}")


# Simple in-memory cache for search results
_search_cache: dict[str, tuple[float, ThangsSearchResponse]] = {}

logger = get_logger(__name__)

# URL patterns for external model platforms
THANGS_PATTERNS = [
    # thangs.com/designer/model-slug-123456
    re.compile(r"thangs\.com/([^/]+)/([^/\s]+)-(\d+)(?:\?|$|/|\s)", re.IGNORECASE),
    # thangs.com/m/123456
    re.compile(r"thangs\.com/m/(\d+)(?:\?|$|/|\s)", re.IGNORECASE),
    # thangs.com/model/123456
    re.compile(r"thangs\.com/model/(\d+)(?:\?|$|/|\s)", re.IGNORECASE),
]

PRINTABLES_PATTERN = re.compile(
    r"printables\.com/model/(\d+)(?:[/-]|$|\s|\?)", re.IGNORECASE
)

THINGIVERSE_PATTERN = re.compile(
    r"thingiverse\.com/thing:(\d+)(?:\s|$|/|\?)", re.IGNORECASE
)


class ThangsAdapter:
    """Adapter for Thangs API interactions and URL detection."""

    # Thangs API base URL
    API_BASE = "https://api.thangs.com"

    def __init__(self, db: AsyncSession):
        """Initialize the Thangs adapter.

        Args:
            db: Async database session.
        """
        self.db = db
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Printarr/1.0",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def detect_thangs_url(text: str) -> list[dict]:
        """Detect Thangs URLs in text.

        Args:
            text: Text to search for URLs.

        Returns:
            List of dicts with 'url', 'model_id' keys.
        """
        if not text:
            return []

        results = []
        seen_ids = set()

        # Try each pattern
        for pattern in THANGS_PATTERNS:
            for match in pattern.finditer(text):
                groups = match.groups()
                # Different patterns have different group structures
                if len(groups) == 3:
                    # designer/slug-id pattern
                    model_id = groups[2]
                else:
                    # m/id or model/id pattern
                    model_id = groups[0]

                if model_id not in seen_ids:
                    seen_ids.add(model_id)
                    # Reconstruct canonical URL
                    url = f"https://thangs.com/m/{model_id}"
                    results.append({
                        "url": url,
                        "model_id": model_id,
                    })

        return results

    @staticmethod
    def detect_printables_url(text: str) -> list[dict]:
        """Detect Printables URLs in text.

        Args:
            text: Text to search for URLs.

        Returns:
            List of dicts with 'url', 'model_id' keys.
        """
        if not text:
            return []

        results = []
        seen_ids = set()

        for match in PRINTABLES_PATTERN.finditer(text):
            model_id = match.group(1)
            if model_id not in seen_ids:
                seen_ids.add(model_id)
                url = f"https://www.printables.com/model/{model_id}"
                results.append({
                    "url": url,
                    "model_id": model_id,
                })

        return results

    @staticmethod
    def detect_thingiverse_url(text: str) -> list[dict]:
        """Detect Thingiverse URLs in text.

        Args:
            text: Text to search for URLs.

        Returns:
            List of dicts with 'url', 'model_id' keys.
        """
        if not text:
            return []

        results = []
        seen_ids = set()

        for match in THINGIVERSE_PATTERN.finditer(text):
            model_id = match.group(1)
            if model_id not in seen_ids:
                seen_ids.add(model_id)
                url = f"https://www.thingiverse.com/thing:{model_id}"
                results.append({
                    "url": url,
                    "model_id": model_id,
                })

        return results

    @staticmethod
    def detect_all_urls(text: str) -> dict[str, list[dict]]:
        """Detect all external platform URLs in text.

        Args:
            text: Text to search for URLs.

        Returns:
            Dict with keys 'thangs', 'printables', 'thingiverse'.
        """
        return {
            "thangs": ThangsAdapter.detect_thangs_url(text),
            "printables": ThangsAdapter.detect_printables_url(text),
            "thingiverse": ThangsAdapter.detect_thingiverse_url(text),
        }

    async def fetch_thangs_metadata(self, model_id: str) -> dict | None:
        """Fetch metadata from Thangs API.

        Args:
            model_id: Thangs model ID.

        Returns:
            Dict with metadata or None if fetch failed.
        """
        try:
            client = await self._get_client()

            # Try the public model endpoint
            # Note: This may need adjustment based on actual Thangs API
            url = f"{self.API_BASE}/models/{model_id}"

            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("name") or data.get("title"),
                    "designer": self._extract_designer(data),
                    "tags": data.get("tags", []),
                    "images": data.get("images", []),
                }
            elif response.status_code == 404:
                logger.warning("thangs_model_not_found", model_id=model_id)
                return None
            else:
                logger.warning(
                    "thangs_api_error",
                    model_id=model_id,
                    status=response.status_code,
                )
                return None

        except httpx.HTTPError as e:
            logger.error("thangs_http_error", model_id=model_id, error=str(e))
            return None

    def _extract_designer(self, data: dict) -> str | None:
        """Extract designer name from Thangs API response."""
        # Try various possible fields
        if "owner" in data and isinstance(data["owner"], dict):
            return data["owner"].get("username") or data["owner"].get("name")
        if "creator" in data and isinstance(data["creator"], dict):
            return data["creator"].get("username") or data["creator"].get("name")
        if "author" in data:
            return data["author"]
        if "designer" in data:
            return data["designer"]
        return None

    async def process_design_urls(
        self,
        design: Design,
        caption: str,
        *,
        fetch_metadata: bool = True,
    ) -> list[ExternalMetadataSource]:
        """Process a design's caption for external URLs and create links.

        Args:
            design: The Design to link.
            caption: The caption text to scan.
            fetch_metadata: Whether to fetch metadata from APIs.

        Returns:
            List of created ExternalMetadataSource records.
        """
        created = []
        urls = self.detect_all_urls(caption)

        # Process Thangs URLs
        for thangs_url in urls["thangs"]:
            source = await self._create_or_update_source(
                design=design,
                source_type=ExternalSourceType.THANGS,
                external_id=thangs_url["model_id"],
                external_url=thangs_url["url"],
                confidence=1.0,  # Direct link = full confidence
                match_method=MatchMethod.LINK,
                fetch_metadata=fetch_metadata,
            )
            if source:
                created.append(source)

        # Process Printables URLs (don't fetch metadata yet)
        for printables_url in urls["printables"]:
            source = await self._create_or_update_source(
                design=design,
                source_type=ExternalSourceType.PRINTABLES,
                external_id=printables_url["model_id"],
                external_url=printables_url["url"],
                confidence=1.0,
                match_method=MatchMethod.LINK,
                fetch_metadata=False,  # No Printables API integration yet
            )
            if source:
                created.append(source)

        # Process Thingiverse URLs (don't fetch metadata yet)
        for thingiverse_url in urls["thingiverse"]:
            source = await self._create_or_update_source(
                design=design,
                source_type=ExternalSourceType.THINGIVERSE,
                external_id=thingiverse_url["model_id"],
                external_url=thingiverse_url["url"],
                confidence=1.0,
                match_method=MatchMethod.LINK,
                fetch_metadata=False,  # No Thingiverse API integration yet
            )
            if source:
                created.append(source)

        return created

    async def _create_or_update_source(
        self,
        design: Design,
        source_type: ExternalSourceType,
        external_id: str,
        external_url: str,
        confidence: float,
        match_method: MatchMethod,
        fetch_metadata: bool = True,
    ) -> ExternalMetadataSource | None:
        """Create or update an ExternalMetadataSource record."""
        # Check if source already exists
        existing = await self.db.execute(
            select(ExternalMetadataSource).where(
                ExternalMetadataSource.design_id == design.id,
                ExternalMetadataSource.source_type == source_type,
            )
        )
        source = existing.scalar_one_or_none()

        if source:
            # Update existing
            source.external_id = external_id
            source.external_url = external_url
            source.confidence_score = max(source.confidence_score, confidence)
            logger.debug(
                "external_source_updated",
                design_id=design.id,
                source_type=source_type.value,
            )
        else:
            # Create new
            source = ExternalMetadataSource(
                design_id=design.id,
                source_type=source_type,
                external_id=external_id,
                external_url=external_url,
                confidence_score=confidence,
                match_method=match_method,
            )
            self.db.add(source)

        # Fetch metadata if requested and this is Thangs
        if fetch_metadata and source_type == ExternalSourceType.THANGS:
            metadata = await self.fetch_thangs_metadata(external_id)
            if metadata:
                source.fetched_title = metadata.get("title")
                source.fetched_designer = metadata.get("designer")
                tags = metadata.get("tags", [])
                source.fetched_tags = ",".join(tags) if tags else None
                source.last_fetched_at = datetime.utcnow()

                logger.info(
                    "thangs_metadata_fetched",
                    design_id=design.id,
                    model_id=external_id,
                    title=source.fetched_title,
                )

        await self.db.flush()
        return source

    async def search(
        self,
        query: str,
        limit: int = 10,
        use_cache: bool = True,
    ) -> ThangsSearchResponse:
        """Search Thangs for 3D models.

        Args:
            query: Search query (min 3 characters).
            limit: Maximum number of results (1-50).
            use_cache: Whether to use cached results.

        Returns:
            ThangsSearchResponse with results and total count.

        Raises:
            ThangsRateLimitError: If rate limited by Thangs.
            ThangsUpstreamError: If Thangs API returns an error.
        """
        if len(query) < 3:
            raise ValueError("Search query must be at least 3 characters")

        limit = max(1, min(50, limit))

        # Check cache
        cache_key = f"{query}:{limit}"
        if use_cache and cache_key in _search_cache:
            cached_time, cached_response = _search_cache[cache_key]
            if time.time() - cached_time < SEARCH_CACHE_TTL:
                logger.debug(
                    "thangs_search_cache_hit",
                    query=query,
                    results_count=len(cached_response.results),
                )
                return cached_response

        try:
            client = await self._get_client()

            # Thangs search API endpoint
            # Note: This is based on the expected Thangs API structure
            url = f"{self.API_BASE}/search"
            params = {
                "q": query,
                "limit": limit,
                "type": "models",
            }

            logger.debug("thangs_search_request", query=query, limit=limit)
            response = await client.get(url, params=params)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                logger.warning("thangs_rate_limited", retry_after=retry_after)
                raise ThangsRateLimitError(retry_after=retry_after)

            if response.status_code >= 500:
                logger.error(
                    "thangs_upstream_error",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
                raise ThangsUpstreamError(
                    f"Thangs API returned {response.status_code}",
                    status_code=response.status_code,
                )

            if response.status_code != 200:
                logger.warning(
                    "thangs_search_error",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
                raise ThangsUpstreamError(
                    f"Thangs API returned {response.status_code}",
                    status_code=response.status_code,
                )

            data = response.json()
            results = []

            # Parse results - adapt to actual Thangs API response structure
            items = data.get("results", data.get("models", data.get("items", [])))
            total = data.get("total", data.get("count", len(items)))

            for item in items[:limit]:
                model_id = str(item.get("id", item.get("modelId", "")))
                if not model_id:
                    continue

                # Extract thumbnail URL
                thumbnail_url = None
                if "thumbnail" in item:
                    thumbnail_url = item["thumbnail"]
                elif "thumbnailUrl" in item:
                    thumbnail_url = item["thumbnailUrl"]
                elif "images" in item and item["images"]:
                    thumbnail_url = item["images"][0] if isinstance(item["images"][0], str) else item["images"][0].get("url")

                results.append(
                    ThangsSearchResult(
                        model_id=model_id,
                        title=item.get("name", item.get("title", "Unknown")),
                        designer=self._extract_designer(item),
                        thumbnail_url=thumbnail_url,
                        url=f"https://thangs.com/m/{model_id}",
                    )
                )

            search_response = ThangsSearchResponse(results=results, total=total)

            # Cache results
            _search_cache[cache_key] = (time.time(), search_response)

            # Clean old cache entries
            self._clean_cache()

            logger.info(
                "thangs_search_complete",
                query=query,
                results_count=len(results),
                total=total,
            )

            return search_response

        except httpx.HTTPError as e:
            logger.error("thangs_search_http_error", query=query, error=str(e))
            raise ThangsUpstreamError(f"HTTP error: {e}", status_code=502)

    def _clean_cache(self) -> None:
        """Remove expired entries from the search cache."""
        now = time.time()
        expired_keys = [
            key for key, (cached_time, _) in _search_cache.items()
            if now - cached_time >= SEARCH_CACHE_TTL
        ]
        for key in expired_keys:
            del _search_cache[key]

    async def fetch_unfetched_metadata(
        self,
        design_ids: list[str] | None = None,
        limit: int = 100,
    ) -> dict:
        """Fetch metadata for unfetched Thangs sources.

        This method queries for ExternalMetadataSource records that haven't
        been fetched yet (last_fetched_at IS NULL) and fetches metadata from
        the Thangs API for each one.

        Args:
            design_ids: Optional list of design IDs to limit the fetch to.
                       If None, fetches all unfetched sources.
            limit: Maximum number of sources to process in one batch.

        Returns:
            Dict with 'fetched', 'failed', 'skipped' counts.
        """
        # Build query for unfetched Thangs sources
        query = (
            select(ExternalMetadataSource)
            .where(
                ExternalMetadataSource.source_type == ExternalSourceType.THANGS,
                ExternalMetadataSource.last_fetched_at.is_(None),
            )
            .limit(limit)
        )

        if design_ids:
            query = query.where(ExternalMetadataSource.design_id.in_(design_ids))

        result = await self.db.execute(query)
        sources = result.scalars().all()

        if not sources:
            logger.debug("no_unfetched_thangs_sources")
            return {"fetched": 0, "failed": 0, "skipped": 0}

        logger.info(
            "fetching_unfetched_metadata",
            count=len(sources),
        )

        # Collect source info before committing current transaction
        sources_to_fetch = [
            {"id": s.id, "external_id": s.external_id}
            for s in sources
        ]

        # Commit current transaction to avoid greenlet conflicts
        await self.db.commit()

        # Fetch metadata outside DB context
        fetched = 0
        failed = 0

        for i, source_info in enumerate(sources_to_fetch):
            # Rate limiting: delay between requests
            if i > 0:
                await asyncio.sleep(THANGS_API_DELAY)

            try:
                metadata = await self.fetch_thangs_metadata(source_info["external_id"])

                if metadata:
                    # Update source with fetched metadata
                    await self.db.execute(
                        update(ExternalMetadataSource)
                        .where(ExternalMetadataSource.id == source_info["id"])
                        .values(
                            fetched_title=metadata.get("title"),
                            fetched_designer=metadata.get("designer"),
                            fetched_tags=",".join(metadata.get("tags", [])) if metadata.get("tags") else None,
                            last_fetched_at=datetime.utcnow(),
                        )
                    )
                    fetched += 1
                    logger.debug(
                        "metadata_fetched",
                        source_id=source_info["id"],
                        title=metadata.get("title"),
                    )
                else:
                    # Mark as fetched but with no data (404 or error)
                    await self.db.execute(
                        update(ExternalMetadataSource)
                        .where(ExternalMetadataSource.id == source_info["id"])
                        .values(last_fetched_at=datetime.utcnow())
                    )
                    failed += 1
                    logger.debug(
                        "metadata_fetch_empty",
                        source_id=source_info["id"],
                    )

            except Exception as e:
                logger.warning(
                    "metadata_fetch_error",
                    source_id=source_info["id"],
                    error=str(e),
                )
                failed += 1

        await self.db.commit()

        logger.info(
            "unfetched_metadata_complete",
            fetched=fetched,
            failed=failed,
        )

        return {
            "fetched": fetched,
            "failed": failed,
            "skipped": 0,
        }
