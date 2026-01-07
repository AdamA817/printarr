"""AI Analysis service for design tagging using Google Gemini (DEC-043).

This service provides AI-powered analysis of design preview images to:
1. Generate relevant tags for designs
2. Select the most representative preview image

Uses Google's Gemini API with rate limiting to respect API quotas.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Design, DesignSource, DesignTag, PreviewAsset, Tag
from app.db.models.enums import PreviewSource, TagSource
from app.db.session import async_session_maker
from app.services.tag import TagService

logger = get_logger(__name__)

# Preview source priority for AI analysis (lower = better)
# Creator-provided images are more useful than auto-generated ones
PREVIEW_PRIORITY = {
    PreviewSource.TELEGRAM: 1,      # Creator's actual images - best
    PreviewSource.THANGS: 2,        # Professional renders
    PreviewSource.ARCHIVE: 3,       # Images from zip
    PreviewSource.EMBEDDED_3MF: 4,  # Slicer thumbnails
    PreviewSource.RENDERED: 5,      # Our stl-thumb output - least useful
}


class AiRateLimitError(Exception):
    """Error when AI rate limit is exceeded."""

    def __init__(self, retry_after: int, message: str = "Rate limit exceeded"):
        self.retry_after = retry_after
        self.message = message
        super().__init__(message)


class AiRateLimiter:
    """Rate limiter for AI API calls using token bucket algorithm.

    Features:
    - Configurable requests per minute (RPM)
    - Thread-safe for concurrent workers
    - Backoff support when Gemini returns rate limit errors
    - Simple token bucket without per-channel tracking (unlike Telegram)

    Usage:
        rate_limiter = await AiRateLimiter.get_instance()
        await rate_limiter.acquire()
        # make AI API call
    """

    _instance: AiRateLimiter | None = None
    _lock: asyncio.Lock | None = None

    def __init__(self, rpm: int | None = None):
        """Initialize the rate limiter.

        Args:
            rpm: Requests per minute limit (default from settings).
        """
        self.rpm = rpm or settings.ai_rate_limit_rpm

        # Token bucket state
        self.tokens = float(self.rpm)
        self.max_tokens = float(self.rpm)
        self.last_refill = time.monotonic()
        self._token_lock = asyncio.Lock()

        # Backoff state (when Gemini returns rate limit)
        self._backoff_until: float = 0.0
        self._rate_limit_count = 0

        # Metrics
        self._requests_total = 0
        self._throttled_count = 0

        logger.info("ai_rate_limiter_initialized", rpm=self.rpm)

    @classmethod
    async def get_instance(cls) -> AiRateLimiter:
        """Get the singleton rate limiter instance."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._instance is None:
                cls._instance = AiRateLimiter()
            return cls._instance

    async def acquire(self) -> None:
        """Acquire permission to make an AI API call.

        Blocks until a token is available and backoff period has passed.

        Raises:
            AiRateLimitError: If in backoff and wait would be too long (>60s).
        """
        # Check if we're in backoff from a previous rate limit response
        now = time.monotonic()
        if self._backoff_until > now:
            wait_time = self._backoff_until - now
            if wait_time > 60:
                # Don't wait more than 60s - let the job retry later
                raise AiRateLimitError(
                    retry_after=int(wait_time),
                    message=f"AI rate limited, retry in {int(wait_time)}s",
                )
            logger.info(
                "ai_rate_limiter_backoff_wait",
                wait_seconds=wait_time,
            )
            await asyncio.sleep(wait_time)

        await self._wait_for_token()
        self._requests_total += 1

    def handle_rate_limit(self, retry_after: int | None = None) -> None:
        """Handle a rate limit response from Gemini.

        Sets backoff period and reduces effective RPM temporarily.

        Args:
            retry_after: Seconds to wait (from Gemini's response), or None for default.
        """
        self._rate_limit_count += 1

        # Default to 60 seconds if not specified
        wait_seconds = retry_after or 60

        # Set backoff until time
        self._backoff_until = time.monotonic() + wait_seconds

        # Drain tokens to slow down after backoff
        self.tokens = 0

        logger.warning(
            "ai_rate_limit_received",
            retry_after=wait_seconds,
            total_rate_limits=self._rate_limit_count,
        )

    async def _wait_for_token(self) -> None:
        """Wait until a token is available (token bucket algorithm)."""
        async with self._token_lock:
            # Refill tokens based on time elapsed
            now = time.monotonic()
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * (self.rpm / 60.0)  # Tokens per second
            self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
            self.last_refill = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60.0 / self.rpm)
                self._throttled_count += 1
                logger.debug(
                    "ai_rate_limiter_throttling",
                    wait_time=wait_time,
                    tokens=self.tokens,
                )
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        now = time.monotonic()
        in_backoff = self._backoff_until > now
        backoff_remaining = max(0, self._backoff_until - now) if in_backoff else 0

        return {
            "rpm_limit": self.rpm,
            "tokens_available": self.tokens,
            "requests_total": self._requests_total,
            "throttled_count": self._throttled_count,
            "rate_limit_count": self._rate_limit_count,
            "in_backoff": in_backoff,
            "backoff_remaining_seconds": int(backoff_remaining),
        }


class AiAnalysisResult:
    """Result of AI analysis for a design."""

    def __init__(
        self,
        tags: list[str],
        best_preview_index: int | None = None,
        raw_response: str | None = None,
    ):
        self.tags = tags
        self.best_preview_index = best_preview_index
        self.raw_response = raw_response

    def to_dict(self) -> dict[str, Any]:
        return {
            "tags": self.tags,
            "best_preview_index": self.best_preview_index,
        }


class AiService:
    """Service for AI-powered design analysis.

    Uses Google Gemini REST API to analyze preview images and generate tags.
    Uses httpx for HTTP requests to avoid SDK dependency conflicts.
    """

    # Gemini API base URL
    GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

    # Class-level httpx client for connection pooling
    _http_client: httpx.AsyncClient | None = None

    def __init__(self, db: AsyncSession | None = None):
        """Initialize the AI service.

        Args:
            db: Optional database session. If not provided, creates sessions as needed.
        """
        self.db = db

    @classmethod
    def _get_http_client(cls) -> httpx.AsyncClient:
        """Get or create the httpx client for API calls."""
        if cls._http_client is None:
            cls._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0),  # 2 minute timeout for AI responses
                headers={"Content-Type": "application/json"},
            )
        return cls._http_client

    async def analyze_design(
        self,
        design_id: str,
        force: bool = False,
    ) -> AiAnalysisResult | None:
        """Analyze a design using AI to generate tags and select best preview.

        Args:
            design_id: The design to analyze.
            force: Re-analyze even if already done.

        Returns:
            AiAnalysisResult with tags and best preview index, or None if skipped.
        """
        if not settings.ai_configured:
            logger.warning("ai_not_configured", design_id=design_id)
            return None

        if self.db:
            db = self.db
        else:
            db = async_session_maker()

        try:
            # Get design with eager-loaded relationships (needed for sync _build_prompt)
            from sqlalchemy.orm import selectinload

            result = await db.execute(
                select(Design)
                .where(Design.id == design_id)
                .options(
                    selectinload(Design.sources).selectinload(DesignSource.channel)
                )
            )
            design = result.scalar_one_or_none()
            if not design:
                logger.warning("design_not_found", design_id=design_id)
                return None

            # Check if already analyzed (has AUTO_AI tags)
            if not force:
                existing_ai_tags = await db.execute(
                    select(DesignTag).where(
                        DesignTag.design_id == design_id,
                        DesignTag.source == TagSource.AUTO_AI,
                    )
                )
                if existing_ai_tags.scalars().first():
                    logger.debug("design_already_analyzed", design_id=design_id)
                    return None

            # Get previews for analysis
            previews = await self._get_previews_for_analysis(db, design_id)
            if not previews:
                logger.debug("no_previews_for_analysis", design_id=design_id)
                return None

            # Get existing tags for context (to prefer existing tag names)
            existing_tags = await self._get_existing_tags(db)

            # Build prompt
            prompt = self._build_prompt(design, previews, existing_tags)

            # Read preview images
            image_data_list = await self._read_preview_images(previews)

            # Call AI API with rate limiting
            rate_limiter = await AiRateLimiter.get_instance()
            await rate_limiter.acquire()

            result = await self._call_gemini(prompt, image_data_list)

            if result:
                # Apply tags to design
                await self._apply_tags(db, design_id, result.tags)

                # Update primary preview if AI selected one
                if (
                    settings.ai_select_best_preview
                    and result.best_preview_index is not None
                    and 0 <= result.best_preview_index < len(previews)
                ):
                    await self._set_primary_preview(
                        db, design_id, previews[result.best_preview_index].id
                    )

                if not self.db:
                    await db.commit()

                logger.info(
                    "design_analyzed",
                    design_id=design_id,
                    tags_count=len(result.tags),
                    best_preview_index=result.best_preview_index,
                )

            return result

        except Exception as e:
            logger.error(
                "ai_analysis_error",
                design_id=design_id,
                error=str(e),
                exc_info=True,
            )
            raise

        finally:
            if not self.db:
                await db.close()

    async def _get_previews_for_analysis(
        self,
        db: AsyncSession,
        design_id: str,
        max_images: int = 4,
    ) -> list[PreviewAsset]:
        """Select best preview images for AI analysis.

        Prioritizes by source quality, preferring creator-provided images.

        Args:
            db: Database session.
            design_id: The design ID.
            max_images: Maximum images to select.

        Returns:
            List of selected PreviewAssets.
        """
        result = await db.execute(
            select(PreviewAsset).where(PreviewAsset.design_id == design_id)
        )
        all_previews = list(result.scalars().all())

        if not all_previews:
            return []

        # Sort by priority
        sorted_previews = sorted(
            all_previews,
            key=lambda p: PREVIEW_PRIORITY.get(p.source, 99),
        )

        # Select top images
        selected = sorted_previews[:max_images]

        # Skip RENDERED if we have better options (unless it's all we have)
        if len(selected) > 1:
            better = [p for p in selected if p.source != PreviewSource.RENDERED]
            if better:
                selected = better[:max_images]

        return selected

    async def _get_existing_tags(
        self,
        db: AsyncSession,
        limit: int = 300,
    ) -> list[str]:
        """Get top existing tags by usage for context.

        Args:
            db: Database session.
            limit: Maximum tags to return.

        Returns:
            List of tag names sorted by usage.
        """
        result = await db.execute(
            select(Tag.name)
            .where(Tag.usage_count > 0)
            .order_by(Tag.usage_count.desc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    def _build_prompt(
        self,
        design: Design,
        previews: list[PreviewAsset],
        existing_tags: list[str],
    ) -> str:
        """Build the AI analysis prompt.

        Args:
            design: The design to analyze.
            previews: Selected preview images.
            existing_tags: Existing tags for context.

        Returns:
            Formatted prompt string.
        """
        # Get design info
        title = design.canonical_title or "Unknown"
        designer = design.canonical_designer or "Unknown"

        # Get channel name from first source if available
        channel_name = "Unknown"
        if design.sources and len(design.sources) > 0:
            first_source = design.sources[0]
            if first_source.channel:
                channel_name = first_source.channel.title or first_source.channel.username or "Unknown"

        # Get caption text
        caption_text = ""
        if design.sources and len(design.sources) > 0:
            first_source = design.sources[0]
            if first_source.original_caption:
                caption_text = first_source.original_caption[:1000]  # Limit length

        # Format image sources
        image_sources = ", ".join(
            p.source.value for p in previews
        )

        # Format existing tags (limit to reasonable size)
        existing_tags_list = ", ".join(existing_tags[:200])

        max_tags = settings.ai_max_tags_per_design

        prompt = f"""Analyze this 3D printable design.

## Design Information
- **Title**: {title}
- **Designer**: {designer}
- **Source**: {channel_name}
- **Caption**:
{caption_text}

## Images
{len(previews)} preview image(s) attached (numbered 0-{len(previews) - 1}).
Sources: {image_sources}

## Existing Tags
Prefer these existing tags when the meaning matches:
{existing_tags_list}

## Tasks

### 1. Tags
Generate up to {max_tags} tags for this design.
- **Prefer existing tags** when meaning matches (use "helmet" not "helmets")
- Lowercase, no special characters
- Include: what it is, theme/franchise, style, use case
- Be specific when warranted ("nightmare before christmas" not just "christmas")
- Skip: "3d print", "stl", "model", "file"
- **Do NOT include print-type tags** like "multicolor", "resin", "fdm", "presupported", "single color" - these require technical knowledge that cannot be determined from images

### 2. Best Preview (if multiple images)
Select which image (0-indexed) best represents this design.
- Shows the complete model clearly
- Good lighting/angle
- Prefer creator photos over gray STL renders

## Response
JSON only:
{{"tags": ["tag1", "tag2"], "best_preview_index": 0}}"""

        return prompt

    async def _read_preview_images(
        self,
        previews: list[PreviewAsset],
    ) -> list[tuple[bytes, str]]:
        """Read preview image files.

        Args:
            previews: List of preview assets.

        Returns:
            List of (image_bytes, mime_type) tuples.
        """
        cache_path = settings.cache_path / "previews"
        result = []

        for preview in previews:
            try:
                file_path = cache_path / preview.file_path
                if not file_path.exists():
                    logger.warning(
                        "preview_file_missing",
                        preview_id=preview.id,
                        path=str(file_path),
                    )
                    continue

                # Read file
                def _read_file():
                    return file_path.read_bytes()

                loop = asyncio.get_event_loop()
                image_data = await loop.run_in_executor(None, _read_file)

                # Determine mime type
                ext = file_path.suffix.lower()
                mime_types = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }
                mime_type = mime_types.get(ext, "image/jpeg")

                result.append((image_data, mime_type))

            except Exception as e:
                logger.warning(
                    "preview_read_error",
                    preview_id=preview.id,
                    error=str(e),
                )

        return result

    async def _call_gemini(
        self,
        prompt: str,
        images: list[tuple[bytes, str]],
    ) -> AiAnalysisResult | None:
        """Call the Gemini API with the prompt and images.

        Uses the REST API directly with httpx to avoid SDK dependency conflicts.

        Args:
            prompt: The analysis prompt.
            images: List of (image_bytes, mime_type) tuples.

        Returns:
            AiAnalysisResult or None if failed.

        Raises:
            AiRateLimitError: If Gemini returns a rate limit error.
        """
        try:
            if not settings.ai_configured:
                raise RuntimeError("AI is not configured")

            client = self._get_http_client()

            # Build content parts for REST API
            parts = []

            # Add images as inline_data
            for image_data, mime_type in images:
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(image_data).decode("utf-8"),
                    }
                })

            # Add text prompt
            parts.append({"text": prompt})

            # Build request payload
            payload = {
                "contents": [{"parts": parts}],
            }

            # Make API request
            url = f"{self.GEMINI_API_BASE}/models/{settings.ai_model}:generateContent"
            response = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": settings.ai_api_key},
            )

            # Check for HTTP errors
            if response.status_code == 429:
                # Rate limit - extract retry-after if available
                retry_after = int(response.headers.get("Retry-After", 60))
                raise AiRateLimitError(
                    retry_after=retry_after,
                    message="Gemini rate limit exceeded",
                )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", response.text)
                raise RuntimeError(f"Gemini API error ({response.status_code}): {error_msg}")

            # Parse response
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning("gemini_no_candidates", response=data)
                return None

            # Extract text from first candidate
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                logger.warning("gemini_no_parts", response=data)
                return None

            response_text = parts[0].get("text", "")
            if not response_text:
                logger.warning("gemini_empty_response", response=data)
                return None

            # Parse the JSON response
            return self._parse_response(response_text)

        except AiRateLimitError:
            # Re-raise rate limit errors (already logged inline)
            raise

        except httpx.HTTPStatusError as e:
            # HTTP errors from httpx
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str:
                retry_after = self._extract_retry_after(str(e))
                rate_limiter = await AiRateLimiter.get_instance()
                rate_limiter.handle_rate_limit(retry_after)
                raise AiRateLimitError(
                    retry_after=retry_after or 60,
                    message=f"Gemini rate limit: {e}",
                )
            logger.error("gemini_http_error", error=str(e), exc_info=True)
            raise

        except Exception as e:
            # Other errors - check for rate limit indicators
            error_str = str(e).lower()
            if "quota" in error_str or "rate limit" in error_str:
                retry_after = self._extract_retry_after(str(e))
                rate_limiter = await AiRateLimiter.get_instance()
                rate_limiter.handle_rate_limit(retry_after)
                raise AiRateLimitError(
                    retry_after=retry_after or 60,
                    message=f"Gemini rate limit: {e}",
                )

            logger.error(
                "gemini_api_error",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise

    def _extract_retry_after(self, error_message: str) -> int | None:
        """Extract retry-after seconds from an error message.

        Args:
            error_message: The error message string.

        Returns:
            Seconds to wait, or None if not found.
        """
        import re

        # Look for patterns like "retry after 60 seconds" or "wait 30s"
        patterns = [
            r"retry.{0,10}?(\d+)\s*(?:second|sec|s\b)",
            r"wait.{0,10}?(\d+)\s*(?:second|sec|s\b)",
            r"(\d+)\s*(?:second|sec|s\b).{0,10}?(?:retry|wait)",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_message.lower())
            if match:
                return int(match.group(1))

        return None

    def _parse_response(self, response_text: str) -> AiAnalysisResult | None:
        """Parse the AI response JSON.

        Args:
            response_text: Raw response from Gemini.

        Returns:
            AiAnalysisResult or None if parsing failed.
        """
        try:
            # Try to extract JSON from response
            # Sometimes the model wraps it in markdown code blocks
            text = response_text.strip()

            # Remove markdown code block if present
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            # Parse JSON
            data = json.loads(text)

            tags = data.get("tags", [])
            # Normalize tags: lowercase, strip whitespace
            tags = [tag.strip().lower() for tag in tags if isinstance(tag, str) and tag.strip()]
            # Remove duplicates while preserving order
            seen = set()
            unique_tags = []
            for tag in tags:
                if tag not in seen:
                    seen.add(tag)
                    unique_tags.append(tag)
            tags = unique_tags[:settings.ai_max_tags_per_design]

            best_preview_index = data.get("best_preview_index")
            if best_preview_index is not None:
                best_preview_index = int(best_preview_index)

            return AiAnalysisResult(
                tags=tags,
                best_preview_index=best_preview_index,
                raw_response=response_text,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(
                "ai_response_parse_error",
                error=str(e),
                response=response_text[:500],
            )
            return None

    async def _apply_tags(
        self,
        db: AsyncSession,
        design_id: str,
        tag_names: list[str],
    ) -> None:
        """Apply AI-generated tags to a design.

        Args:
            db: Database session.
            design_id: The design ID.
            tag_names: List of tag names to apply.
        """
        tag_service = TagService(db)

        for tag_name in tag_names:
            try:
                # Get or create tag
                tag = await tag_service.get_or_create_tag(tag_name)

                # Add to design (will skip if already exists)
                try:
                    await tag_service.add_tag_to_design(
                        design_id=design_id,
                        tag_id=tag.id,
                        source=TagSource.AUTO_AI,
                    )
                except Exception:
                    # Tag might already exist on design
                    pass

            except Exception as e:
                logger.warning(
                    "tag_apply_error",
                    design_id=design_id,
                    tag_name=tag_name,
                    error=str(e),
                )

    async def _set_primary_preview(
        self,
        db: AsyncSession,
        design_id: str,
        preview_id: str,
    ) -> None:
        """Set a preview as primary for a design.

        Args:
            db: Database session.
            design_id: The design ID.
            preview_id: The preview ID to set as primary.
        """
        from app.services.preview import PreviewService

        preview_service = PreviewService(db)
        await preview_service.set_primary(preview_id)
