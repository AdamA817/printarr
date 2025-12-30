"""Thangs adapter for URL detection and metadata fetching."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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

    # Thangs API base URL (on main domain, not api subdomain)
    API_BASE = "https://thangs.com/api"

    def __init__(self, db: AsyncSession):
        """Initialize the Thangs adapter.

        Args:
            db: Async database session.
        """
        self.db = db
        self._client: httpx.AsyncClient | None = None
        self._flaresolverr_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for direct requests."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
        return self._client

    async def _get_flaresolverr_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for FlareSolverr requests."""
        if self._flaresolverr_client is None:
            self._flaresolverr_client = httpx.AsyncClient(
                timeout=90.0,  # FlareSolverr can take time to solve challenges
                headers={"Content-Type": "application/json"},
            )
        return self._flaresolverr_client

    async def close(self) -> None:
        """Close the HTTP clients."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._flaresolverr_client:
            await self._flaresolverr_client.aclose()
            self._flaresolverr_client = None

    def _is_flaresolverr_configured(self) -> bool:
        """Check if FlareSolverr is configured."""
        return settings.flaresolverr_url is not None

    async def _request_via_flaresolverr(
        self,
        url: str,
        retries: int = MAX_RETRIES,
    ) -> dict:
        """Make a request through FlareSolverr.

        Args:
            url: The URL to fetch.
            retries: Number of retries remaining.

        Returns:
            Parsed JSON response.

        Raises:
            FlareSolverrError: If FlareSolverr fails.
            ThangsUpstreamError: If the target returns an error.
        """
        if not settings.flaresolverr_url:
            raise FlareSolverrError("FlareSolverr not configured")

        client = await self._get_flaresolverr_client()

        for attempt in range(retries):
            try:
                logger.debug(
                    "flaresolverr_request",
                    url=url,
                    attempt=attempt + 1,
                    max_retries=retries,
                )

                response = await client.post(
                    settings.flaresolverr_url,
                    json={
                        "cmd": "request.get",
                        "url": url,
                        "maxTimeout": FLARESOLVERR_TIMEOUT,
                    },
                )

                if response.status_code != 200:
                    logger.warning(
                        "flaresolverr_http_error",
                        status_code=response.status_code,
                    )
                    if attempt < retries - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    raise FlareSolverrError(f"HTTP {response.status_code}")

                data = response.json()

                if data.get("status") != "ok":
                    error_msg = data.get("message", "Unknown error")
                    logger.warning("flaresolverr_error", message=error_msg)
                    if attempt < retries - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    raise FlareSolverrError(error_msg)

                # Extract response from solution
                solution = data.get("solution", {})
                response_body = solution.get("response", "")

                logger.debug(
                    "flaresolverr_success",
                    url=url,
                    response_length=len(response_body),
                )

                # FlareSolverr returns HTML with JSON in the body
                return self._extract_json_from_response(response_body)

            except httpx.HTTPError as e:
                logger.warning(
                    "flaresolverr_connection_error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < retries - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                raise FlareSolverrError(f"Connection error: {e}")

        raise FlareSolverrError("Max retries exceeded")

    def _extract_json_from_response(self, response_body: str) -> dict:
        """Extract JSON from FlareSolverr response.

        FlareSolverr may return:
        - Direct JSON string
        - HTML page with JSON in <pre> tags
        - HTML page with JSON in body

        Args:
            response_body: The response body from FlareSolverr.

        Returns:
            Parsed JSON dict.

        Raises:
            ThangsUpstreamError: If JSON cannot be extracted.
        """
        # Try direct JSON parse first
        try:
            return json.loads(response_body)
        except json.JSONDecodeError:
            pass

        # Try to extract from <pre> tags (common Thangs API response format)
        pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", response_body, re.DOTALL)
        if pre_match:
            try:
                return json.loads(pre_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in the response
        json_match = re.search(r"\{[\s\S]*\}", response_body)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(
            "json_extraction_failed",
            response_preview=response_body[:500],
        )
        raise ThangsUpstreamError("Failed to extract JSON from response")

    async def _make_thangs_request(self, url: str) -> dict:
        """Make a request to Thangs API with fallback logic.

        Uses FlareSolverr if configured, falls back to direct request.

        Args:
            url: The Thangs API URL.

        Returns:
            Parsed JSON response.
        """
        # Try FlareSolverr first if configured
        if self._is_flaresolverr_configured():
            try:
                logger.info("thangs_request_via_flaresolverr", url=url)
                return await self._request_via_flaresolverr(url)
            except FlareSolverrError as e:
                logger.warning(
                    "flaresolverr_failed_fallback_direct",
                    error=str(e),
                    url=url,
                )
                # Fall through to direct request

        # Direct request (may fail due to Cloudflare)
        logger.debug("thangs_direct_request", url=url)
        client = await self._get_client()

        try:
            response = await client.get(url)

            if response.status_code == 403:
                logger.warning(
                    "thangs_cloudflare_blocked",
                    status_code=response.status_code,
                    hint="Configure FlareSolverr to bypass Cloudflare",
                )
                raise ThangsUpstreamError(
                    "Blocked by Cloudflare. Configure FlareSolverr.",
                    status_code=403,
                )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                raise ThangsRateLimitError(retry_after=retry_after)

            if response.status_code >= 400:
                raise ThangsUpstreamError(
                    f"Thangs API returned {response.status_code}",
                    status_code=response.status_code,
                )

            return response.json()

        except httpx.HTTPError as e:
            logger.error("thangs_http_error", error=str(e))
            raise ThangsUpstreamError(f"HTTP error: {e}")

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
            # Use the correct Thangs API endpoint
            url = f"{self.API_BASE}/models/{model_id}"
            data = await self._make_thangs_request(url)

            return {
                "title": data.get("name") or data.get("title"),
                "designer": self._extract_designer(data),
                "tags": data.get("tags", []),
                "images": data.get("images", []),
            }

        except ThangsRateLimitError:
            raise
        except ThangsUpstreamError as e:
            if e.status_code == 404:
                logger.warning("thangs_model_not_found", model_id=model_id)
            else:
                logger.warning(
                    "thangs_api_error",
                    model_id=model_id,
                    status=e.status_code,
                )
            return None
        except Exception as e:
            logger.error("thangs_metadata_error", model_id=model_id, error=str(e))
            return None

    def _extract_designer(self, data: dict) -> str | None:
        """Extract designer name from Thangs API response."""
        # Try various possible fields (in order of preference)
        # Search results use ownerUsername at top level
        if "ownerUsername" in data:
            return data["ownerUsername"]
        # Model detail responses may use nested owner/creator
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

        # Build correct search URL
        url = f"{self.API_BASE}/models/v3/search-by-text?searchTerm={query}&pageSize={limit}&page=0"

        try:
            logger.debug("thangs_search_request", query=query, limit=limit)
            data = await self._make_thangs_request(url)

            results = []

            # Parse results - adapt to actual Thangs API response structure
            items = data.get("results", data.get("models", data.get("items", [])))
            total = data.get("total", data.get("count", len(items)))

            for item in items[:limit]:
                # Thangs API uses different field names:
                # - externalId: numeric model ID for linking (preferred)
                # - id: internal UUID (fallback)
                # - modelId: alternative field name
                model_id = str(
                    item.get("externalId")
                    or item.get("id")
                    or item.get("modelId", "")
                )
                if not model_id:
                    continue

                # Extract title - Thangs search uses modelTitle
                title = (
                    item.get("modelTitle")
                    or item.get("name")
                    or item.get("title")
                    or "Unknown"
                )

                # Extract thumbnail URL
                thumbnail_url = None
                if "thumbnail" in item:
                    thumbnail_url = item["thumbnail"]
                elif "thumbnailUrl" in item:
                    thumbnail_url = item["thumbnailUrl"]
                elif "images" in item and item["images"]:
                    first_img = item["images"][0]
                    thumbnail_url = first_img if isinstance(first_img, str) else first_img.get("url")

                results.append(
                    ThangsSearchResult(
                        model_id=model_id,
                        title=title,
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

        except ThangsRateLimitError:
            raise
        except ThangsUpstreamError:
            raise
        except Exception as e:
            logger.error("thangs_search_error", query=query, error=str(e))
            raise ThangsUpstreamError(f"Search error: {e}")

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
