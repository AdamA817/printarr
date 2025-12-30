"""Thangs adapter for URL detection and metadata fetching."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select
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
