"""phpBB Forum integration service for v1.0 Manual Imports.

Provides:
- Session authentication (username/password login)
- Forum topic listing with pagination
- Attachment extraction from topics
- File downloading with session cookies
- Credential encryption and storage
- Rate limiting with configurable delays

See issue #239 for design decisions.

Example phpBB sites:
- hex3dpatreon.com (Hex3D Patreon)
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import PhpbbCredentials

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Rate limiting
REQUEST_DELAY = settings.phpbb_request_delay
MAX_CONCURRENT_DOWNLOADS = settings.phpbb_max_concurrent_downloads
SESSION_TIMEOUT_HOURS = settings.phpbb_session_timeout_hours


class PhpbbError(Exception):
    """Base exception for phpBB errors."""

    pass


class PhpbbAuthError(PhpbbError):
    """Raised when authentication fails."""

    pass


class PhpbbSessionExpiredError(PhpbbError):
    """Raised when session cookies have expired."""

    pass


class PhpbbNotFoundError(PhpbbError):
    """Raised when a forum/topic/file is not found."""

    pass


class PhpbbAccessDeniedError(PhpbbError):
    """Raised when access is denied to a resource."""

    pass


class PhpbbRateLimitError(PhpbbError):
    """Raised when rate limited by the forum."""

    pass


class TopicInfo(BaseModel):
    """Information about a forum topic."""

    topic_id: int
    forum_id: int
    title: str
    author: str | None = None
    post_count: int = 0
    last_post_date: datetime | None = None
    url: str


class AttachmentInfo(BaseModel):
    """Information about a file attachment in a topic."""

    file_id: int
    filename: str
    size_bytes: int = 0
    size_display: str = ""  # e.g., "35.68 MiB"
    download_url: str
    post_id: int | None = None


class ForumInfo(BaseModel):
    """Information about a phpBB forum."""

    forum_id: int
    name: str
    url: str
    topic_count: int = 0
    post_count: int = 0


class ImageInfo(BaseModel):
    """Information about an image in a forum post."""

    url: str
    alt_text: str | None = None
    is_inline: bool = False  # True if embedded in post content
    is_attachment: bool = False  # True if it's an attached image


class DetectedPhpbbDesign(BaseModel):
    """A design detected in a phpBB forum topic."""

    topic_id: int
    forum_id: int
    topic_title: str
    relative_path: str  # forum_id/topic_id
    title: str  # Cleaned topic title
    attachments: list[AttachmentInfo] = Field(default_factory=list)
    images: list[ImageInfo] = Field(default_factory=list)  # Preview images from post
    total_size: int = 0
    author: str | None = None
    last_post_date: datetime | None = None


class PhpbbService:
    """Service for interacting with phpBB forums.

    Handles authentication, forum/topic scraping, and file downloads.
    Uses BeautifulSoup for HTML parsing.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the phpBB service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db
        self._encryption_key: bytes | None = None
        self._last_request_time: datetime | None = None

    # ========== Rate Limiting ==========

    async def _rate_limit(self) -> None:
        """Wait to respect rate limiting between requests."""
        if self._last_request_time:
            elapsed = (datetime.now(timezone.utc) - self._last_request_time).total_seconds()
            if elapsed < REQUEST_DELAY:
                await asyncio.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = datetime.now(timezone.utc)

    # ========== Authentication ==========

    async def login(
        self,
        base_url: str,
        username: str,
        password: str,
    ) -> dict[str, str]:
        """Login to a phpBB forum and return session cookies.

        Args:
            base_url: Base URL of the phpBB forum (e.g., https://hex3dpatreon.com)
            username: Forum username
            password: Forum password

        Returns:
            Dict of session cookies.

        Raises:
            PhpbbAuthError: If login fails.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise PhpbbError(
                "BeautifulSoup not installed. Run: pip install beautifulsoup4 lxml"
            ) from e

        # Normalize base URL
        base_url = base_url.rstrip("/")

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            await self._rate_limit()

            # Get login page to extract CSRF tokens
            login_url = f"{base_url}/ucp.php?mode=login"
            login_page = await client.get(login_url)

            if login_page.status_code != 200:
                raise PhpbbAuthError(f"Failed to load login page: {login_page.status_code}")

            # Parse the login form
            soup = BeautifulSoup(login_page.text, "lxml")
            login_form = soup.find("form", {"id": "login"})

            if not login_form:
                # Try alternate form selector
                login_form = soup.find("form", action=re.compile(r"ucp\.php.*mode=login"))

            if not login_form:
                raise PhpbbAuthError("Could not find login form on page")

            # Extract form tokens
            form_data = {
                "username": username,
                "password": password,
                "login": "Login",
                "redirect": "./index.php",
            }

            # Get hidden form fields (CSRF tokens, etc.)
            for hidden in login_form.find_all("input", {"type": "hidden"}):
                name = hidden.get("name")
                value = hidden.get("value", "")
                if name:
                    form_data[name] = value

            # Check for creation_time and form_token (phpBB CSRF protection)
            creation_time = login_form.find("input", {"name": "creation_time"})
            form_token = login_form.find("input", {"name": "form_token"})

            if creation_time:
                form_data["creation_time"] = creation_time.get("value", "")
            if form_token:
                form_data["form_token"] = form_token.get("value", "")

            # Also get sid from cookies or hidden field
            sid_input = login_form.find("input", {"name": "sid"})
            if sid_input:
                form_data["sid"] = sid_input.get("value", "")

            await self._rate_limit()

            # Submit login form (don't follow redirects so we can check the response)
            post_url = f"{base_url}/ucp.php?mode=login"

            # Use a client that doesn't follow redirects for the login POST
            async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as login_client:
                # Copy cookies from the first client
                login_client.cookies = client.cookies

                response = await login_client.post(
                    post_url,
                    data=form_data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": login_url,
                    },
                )

                # Check for successful login
                # phpBB returns 302 redirect on successful login
                if response.status_code == 302:
                    # Redirect means success - extract cookies
                    cookies = {c.name: c.value for c in login_client.cookies.jar}

                    # Verify we got session cookies
                    has_session = any(
                        "_sid" in name or "_u" in name
                        for name in cookies.keys()
                    )

                    if has_session or len(cookies) > 0:
                        logger.info(
                            "phpbb_login_success",
                            base_url=base_url,
                            username=username,
                            cookies_count=len(cookies),
                        )
                        return cookies

                # If we didn't get a redirect, check for error messages
                # Only check for errors in the actual response (not redirected page)
                response_lower = response.text.lower()

                # Look for specific phpBB error patterns
                if "login_error_attempts" in response_lower:
                    raise PhpbbAuthError("Too many login attempts. Please try again later.")

                if "login_error_password" in response_lower or "incorrect password" in response_lower:
                    raise PhpbbAuthError("Invalid password")

                if "login_error_username" in response_lower or "incorrect username" in response_lower:
                    raise PhpbbAuthError("Invalid username")

                # Check for generic error div
                soup = BeautifulSoup(response.text, "lxml")
                error_div = soup.find("div", class_="error")
                if error_div:
                    error_text = error_div.get_text(strip=True)
                    if error_text:
                        raise PhpbbAuthError(f"Login failed: {error_text}")

                # If we got here with a 200, it might still have worked
                # Check for session cookies
                cookies = {c.name: c.value for c in login_client.cookies.jar}
                if cookies:
                    logger.info(
                        "phpbb_login_success_no_redirect",
                        base_url=base_url,
                        username=username,
                        cookies_count=len(cookies),
                    )
                    return cookies

                # No redirect and no cookies - something went wrong
                raise PhpbbAuthError("Login failed: No session cookies received")

    async def validate_session(
        self,
        base_url: str,
        cookies: dict[str, str],
    ) -> bool:
        """Validate that session cookies are still valid.

        Args:
            base_url: Base URL of the phpBB forum.
            cookies: Session cookies to validate.

        Returns:
            True if session is valid, False otherwise.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return False

        base_url = base_url.rstrip("/")

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, cookies=cookies
        ) as client:
            await self._rate_limit()

            # Check the user control panel - if logged in, it shows username
            response = await client.get(f"{base_url}/ucp.php")

            if response.status_code != 200:
                return False

            soup = BeautifulSoup(response.text, "lxml")

            # Check for logout link (indicates logged in)
            logout_link = soup.find("a", href=re.compile(r"ucp\.php.*mode=logout"))
            if logout_link:
                return True

            # Check for login link (indicates not logged in)
            login_link = soup.find("a", href=re.compile(r"ucp\.php.*mode=login"))
            if login_link:
                return False

            return False

    # ========== Forum Scraping ==========

    async def get_forum_info(
        self,
        base_url: str,
        forum_url: str,
        cookies: dict[str, str],
    ) -> ForumInfo:
        """Get information about a forum.

        Args:
            base_url: Base URL of the phpBB forum.
            forum_url: URL of the specific forum (viewforum.php?f=X)
            cookies: Session cookies.

        Returns:
            ForumInfo with forum details.

        Raises:
            PhpbbNotFoundError: If forum doesn't exist.
            PhpbbAccessDeniedError: If access is denied.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise PhpbbError("BeautifulSoup not installed") from e

        base_url = base_url.rstrip("/")

        # Extract forum ID from URL
        parsed = urlparse(forum_url)
        params = parse_qs(parsed.query)
        forum_id = int(params.get("f", [0])[0])

        if not forum_id:
            raise PhpbbError(f"Could not extract forum ID from URL: {forum_url}")

        full_url = urljoin(base_url + "/", forum_url)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, cookies=cookies
        ) as client:
            await self._rate_limit()

            response = await client.get(full_url)

            if response.status_code == 404:
                raise PhpbbNotFoundError(f"Forum {forum_id} not found")

            if response.status_code == 403:
                raise PhpbbAccessDeniedError(f"Access denied to forum {forum_id}")

            if response.status_code != 200:
                raise PhpbbError(f"Failed to load forum: {response.status_code}")

            soup = BeautifulSoup(response.text, "lxml")

            # Get forum name from header
            forum_title = soup.find("h2", class_="forum-title")
            if not forum_title:
                # Try alternate selectors
                forum_title = soup.find("a", class_="forumtitle")
            if not forum_title:
                forum_title = soup.find("h1")

            name = forum_title.get_text(strip=True) if forum_title else f"Forum {forum_id}"

            # Get topic count from pagination or stats
            topic_count = 0
            post_count = 0

            # Look for pagination info
            pagination = soup.find("div", class_="pagination")
            if pagination:
                # Try to extract total from "X topics" text
                stats_text = pagination.get_text()
                topic_match = re.search(r"(\d+)\s+topics?", stats_text, re.IGNORECASE)
                if topic_match:
                    topic_count = int(topic_match.group(1))

            return ForumInfo(
                forum_id=forum_id,
                name=name,
                url=forum_url,
                topic_count=topic_count,
                post_count=post_count,
            )

    async def list_topics(
        self,
        base_url: str,
        forum_url: str,
        cookies: dict[str, str],
        start: int = 0,
    ) -> tuple[list[TopicInfo], int | None]:
        """List topics in a forum with pagination.

        Args:
            base_url: Base URL of the phpBB forum.
            forum_url: URL of the forum (viewforum.php?f=X)
            cookies: Session cookies.
            start: Offset for pagination (default 0).

        Returns:
            Tuple of (list of TopicInfo, next_start or None if last page).

        Raises:
            PhpbbError: If scraping fails.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise PhpbbError("BeautifulSoup not installed") from e

        base_url = base_url.rstrip("/")

        # Extract forum ID
        parsed = urlparse(forum_url)
        params = parse_qs(parsed.query)
        forum_id = int(params.get("f", [0])[0])

        # Build URL with pagination
        paginated_url = f"{base_url}/viewforum.php?f={forum_id}"
        if start > 0:
            paginated_url += f"&start={start}"

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, cookies=cookies
        ) as client:
            await self._rate_limit()

            response = await client.get(paginated_url)

            if response.status_code != 200:
                raise PhpbbError(f"Failed to load forum: {response.status_code}")

            soup = BeautifulSoup(response.text, "lxml")

            topics: list[TopicInfo] = []

            # Find topic rows - phpBB uses various class names
            topic_rows = soup.find_all("li", class_=re.compile(r"row|topic"))
            if not topic_rows:
                # Try alternate selector for topic list
                topic_rows = soup.find_all("tr", class_=re.compile(r"topic"))
            if not topic_rows:
                # Try finding topic links directly
                topic_links = soup.find_all("a", class_="topictitle")
                for link in topic_links:
                    href = link.get("href", "")
                    topic_match = re.search(r"t=(\d+)", href)
                    if topic_match:
                        topic_id = int(topic_match.group(1))
                        topics.append(TopicInfo(
                            topic_id=topic_id,
                            forum_id=forum_id,
                            title=link.get_text(strip=True),
                            url=href,
                        ))
            else:
                for row in topic_rows:
                    # Skip announcements and stickies if marked
                    if "announce" in row.get("class", []) or "global" in row.get("class", []):
                        continue

                    # Find topic link
                    topic_link = row.find("a", class_="topictitle")
                    if not topic_link:
                        topic_link = row.find("a", href=re.compile(r"viewtopic\.php"))

                    if not topic_link:
                        continue

                    href = topic_link.get("href", "")
                    title = topic_link.get_text(strip=True)

                    # Extract topic ID
                    topic_match = re.search(r"t=(\d+)", href)
                    if not topic_match:
                        continue

                    topic_id = int(topic_match.group(1))

                    # Try to get author
                    author = None
                    author_link = row.find("a", class_=re.compile(r"username|author"))
                    if author_link:
                        author = author_link.get_text(strip=True)

                    # Try to get post count
                    post_count = 0
                    posts_elem = row.find("dd", class_="posts")
                    if posts_elem:
                        try:
                            post_count = int(posts_elem.get_text(strip=True))
                        except ValueError:
                            pass

                    topics.append(TopicInfo(
                        topic_id=topic_id,
                        forum_id=forum_id,
                        title=title,
                        author=author,
                        post_count=post_count,
                        url=href,
                    ))

            # Check for next page
            next_start = None
            pagination = soup.find("div", class_="pagination")
            if pagination:
                # Look for "next" link
                next_link = pagination.find("a", class_="arrow", string=re.compile(r"next|»"))
                if not next_link:
                    next_link = pagination.find("a", href=re.compile(rf"start=\d+"))
                    # Find the highest start value that's greater than current
                    all_page_links = pagination.find_all("a", href=re.compile(r"start=(\d+)"))
                    for link in all_page_links:
                        href = link.get("href", "")
                        start_match = re.search(r"start=(\d+)", href)
                        if start_match:
                            page_start = int(start_match.group(1))
                            if page_start > start:
                                next_start = page_start
                                break

            logger.debug(
                "phpbb_topics_listed",
                forum_id=forum_id,
                start=start,
                topics_found=len(topics),
                has_next=next_start is not None,
            )

            return topics, next_start

    async def list_all_topics(
        self,
        base_url: str,
        forum_url: str,
        cookies: dict[str, str],
        max_topics: int | None = None,
    ) -> list[TopicInfo]:
        """List all topics in a forum (handling pagination).

        Args:
            base_url: Base URL of the phpBB forum.
            forum_url: URL of the forum.
            cookies: Session cookies.
            max_topics: Optional limit on topics to fetch.

        Returns:
            List of all TopicInfo in the forum.
        """
        all_topics: list[TopicInfo] = []
        start = 0

        while True:
            topics, next_start = await self.list_topics(
                base_url, forum_url, cookies, start
            )
            all_topics.extend(topics)

            if max_topics and len(all_topics) >= max_topics:
                all_topics = all_topics[:max_topics]
                break

            if next_start is None:
                break

            start = next_start

        return all_topics

    # ========== Topic Scraping ==========

    async def get_topic_attachments(
        self,
        base_url: str,
        topic_url: str,
        cookies: dict[str, str],
    ) -> list[AttachmentInfo]:
        """Get all attachments from a topic.

        Args:
            base_url: Base URL of the phpBB forum.
            topic_url: URL of the topic (viewtopic.php?f=X&t=Y)
            cookies: Session cookies.

        Returns:
            List of AttachmentInfo for files in the topic.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise PhpbbError("BeautifulSoup not installed") from e

        base_url = base_url.rstrip("/")

        # Build full URL
        if not topic_url.startswith("http"):
            full_url = urljoin(base_url + "/", topic_url)
        else:
            full_url = topic_url

        attachments: list[AttachmentInfo] = []

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, cookies=cookies
        ) as client:
            # May need to paginate through topic pages
            current_url = full_url
            page_num = 0
            max_pages = 100  # Safety limit

            while current_url and page_num < max_pages:
                await self._rate_limit()

                response = await client.get(current_url)

                if response.status_code != 200:
                    raise PhpbbError(f"Failed to load topic: {response.status_code}")

                soup = BeautifulSoup(response.text, "lxml")

                # Find attachment sections
                # phpBB typically wraps attachments in a class like "attachbox" or "inline-attachment"
                attachment_divs = soup.find_all("div", class_=re.compile(r"attach|file|download"))

                for div in attachment_divs:
                    # Find download links
                    download_links = div.find_all("a", href=re.compile(r"download/file\.php"))

                    for link in download_links:
                        href = link.get("href", "")

                        # Extract file ID
                        id_match = re.search(r"id=(\d+)", href)
                        if not id_match:
                            continue

                        file_id = int(id_match.group(1))

                        # Skip if already found (same attachment can appear in multiple divs)
                        if any(a.file_id == file_id for a in attachments):
                            continue

                        # Get filename - try multiple sources
                        filename = None

                        # Check link text
                        link_text = link.get_text(strip=True)
                        if link_text and not link_text.lower().startswith(("download", "click")):
                            filename = link_text

                        # Check for title attribute
                        if not filename:
                            filename = link.get("title", "")

                        # Check nearby text
                        if not filename:
                            parent = link.parent
                            if parent:
                                filename_span = parent.find("span", class_="filename")
                                if filename_span:
                                    filename = filename_span.get_text(strip=True)

                        # Default filename
                        if not filename:
                            filename = f"attachment_{file_id}"

                        # Get file size
                        size_display = ""
                        size_bytes = 0
                        size_elem = div.find(string=re.compile(r"[\d.]+\s*[KMGT]?i?B", re.IGNORECASE))
                        if size_elem:
                            size_display = size_elem.strip()
                            size_bytes = self._parse_size(size_display)

                        # Build download URL
                        download_url = urljoin(base_url + "/", href)

                        attachments.append(AttachmentInfo(
                            file_id=file_id,
                            filename=filename,
                            size_bytes=size_bytes,
                            size_display=size_display,
                            download_url=download_url,
                        ))

                # Also check for inline attachments in posts
                post_contents = soup.find_all("div", class_="content")
                for content in post_contents:
                    inline_links = content.find_all("a", href=re.compile(r"download/file\.php"))
                    for link in inline_links:
                        href = link.get("href", "")
                        id_match = re.search(r"id=(\d+)", href)
                        if not id_match:
                            continue

                        file_id = int(id_match.group(1))

                        # Skip if already found
                        if any(a.file_id == file_id for a in attachments):
                            continue

                        filename = link.get_text(strip=True) or f"attachment_{file_id}"
                        download_url = urljoin(base_url + "/", href)

                        attachments.append(AttachmentInfo(
                            file_id=file_id,
                            filename=filename,
                            download_url=download_url,
                        ))

                # Check for next page in topic
                pagination = soup.find("div", class_="pagination")
                next_url = None
                if pagination:
                    next_link = pagination.find("a", class_="arrow", string=re.compile(r"next|»"))
                    if next_link:
                        next_href = next_link.get("href", "")
                        if next_href:
                            next_url = urljoin(base_url + "/", next_href)

                current_url = next_url
                page_num += 1

        logger.debug(
            "phpbb_attachments_found",
            topic_url=topic_url,
            attachment_count=len(attachments),
        )

        return attachments

    async def get_topic_images(
        self,
        base_url: str,
        topic_url: str,
        cookies: dict[str, str],
    ) -> list[ImageInfo]:
        """Get all images from a topic's posts.

        Extracts images that can be used as design previews.

        Args:
            base_url: Base URL of the phpBB forum.
            topic_url: URL of the topic (viewtopic.php?f=X&t=Y)
            cookies: Session cookies.

        Returns:
            List of ImageInfo for images in the topic.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise PhpbbError("BeautifulSoup not installed") from e

        base_url = base_url.rstrip("/")

        # Build full URL
        if not topic_url.startswith("http"):
            full_url = urljoin(base_url + "/", topic_url)
        else:
            full_url = topic_url

        images: list[ImageInfo] = []
        seen_urls: set[str] = set()

        # Image extensions to look for
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, cookies=cookies
        ) as client:
            # Only look at first page of topic (where preview images likely are)
            await self._rate_limit()

            response = await client.get(full_url)

            if response.status_code != 200:
                raise PhpbbError(f"Failed to load topic: {response.status_code}")

            soup = BeautifulSoup(response.text, "lxml")

            # Find post content divs
            post_contents = soup.find_all("div", class_="content")

            for content in post_contents:
                # Find inline images in post content
                img_tags = content.find_all("img")

                for img in img_tags:
                    src = img.get("src", "")
                    if not src:
                        continue

                    # Build absolute URL
                    if not src.startswith("http"):
                        img_url = urljoin(base_url + "/", src)
                    else:
                        img_url = src

                    # Skip small icons, smilies, avatars
                    if any(x in img_url.lower() for x in ["smilies", "smiley", "avatar", "icon", "rank"]):
                        continue

                    # Skip if already seen
                    if img_url in seen_urls:
                        continue
                    seen_urls.add(img_url)

                    # Check if it's a real image (by extension or known patterns)
                    parsed_url = urlparse(img_url)
                    path_lower = parsed_url.path.lower()

                    is_image = any(path_lower.endswith(ext) for ext in image_extensions)

                    # phpBB attached images often use download/file.php
                    is_attachment = "download/file.php" in img_url

                    if not is_image and not is_attachment:
                        # Check for image mode parameter (phpBB attachment viewer)
                        if "mode=view" not in img_url:
                            continue

                    alt_text = img.get("alt", "") or img.get("title", "")

                    images.append(ImageInfo(
                        url=img_url,
                        alt_text=alt_text if alt_text else None,
                        is_inline=True,
                        is_attachment=is_attachment,
                    ))

            # Also look for linked images (thumbnails that link to full size)
            for link in soup.find_all("a", href=re.compile(r"download/file\.php.*mode=view")):
                href = link.get("href", "")
                if not href:
                    continue

                img_url = urljoin(base_url + "/", href)

                if img_url in seen_urls:
                    continue
                seen_urls.add(img_url)

                images.append(ImageInfo(
                    url=img_url,
                    alt_text=None,
                    is_inline=False,
                    is_attachment=True,
                ))

            # Look for attached images in attachment boxes
            attachment_divs = soup.find_all("div", class_=re.compile(r"attach|thumbnail"))
            for div in attachment_divs:
                # Find image links
                img_link = div.find("a", href=re.compile(r"download/file\.php"))
                if img_link:
                    href = img_link.get("href", "")
                    img_url = urljoin(base_url + "/", href)

                    # Check if it's an image attachment (has mode=view or filename ends in image ext)
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)

                    # Check filename if available
                    filename_span = div.find("span", class_="filename")
                    if filename_span:
                        filename = filename_span.get_text(strip=True).lower()
                        if any(filename.endswith(ext) for ext in image_extensions):
                            if img_url not in seen_urls:
                                seen_urls.add(img_url)
                                images.append(ImageInfo(
                                    url=img_url,
                                    alt_text=filename_span.get_text(strip=True),
                                    is_inline=False,
                                    is_attachment=True,
                                ))

        logger.debug(
            "phpbb_images_found",
            topic_url=topic_url,
            image_count=len(images),
        )

        return images

    async def get_topic_content(
        self,
        base_url: str,
        topic_url: str,
        cookies: dict[str, str],
        include_images: bool = True,
    ) -> tuple[list[AttachmentInfo], list[ImageInfo]]:
        """Get attachments and images from a topic in a single fetch.

        Optimized version that extracts both attachments and images from
        the same page fetch, reducing HTTP requests by half.

        Args:
            base_url: Base URL of the phpBB forum.
            topic_url: URL of the topic (viewtopic.php?f=X&t=Y)
            cookies: Session cookies.
            include_images: Whether to extract preview images.

        Returns:
            Tuple of (attachments, images).
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError as e:
            raise PhpbbError("BeautifulSoup not installed") from e

        base_url = base_url.rstrip("/")

        # Build full URL
        if not topic_url.startswith("http"):
            full_url = urljoin(base_url + "/", topic_url)
        else:
            full_url = topic_url

        attachments: list[AttachmentInfo] = []
        images: list[ImageInfo] = []
        seen_image_urls: set[str] = set()
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30.0, cookies=cookies
        ) as client:
            current_url = full_url
            page_num = 0
            max_pages = 100

            while current_url and page_num < max_pages:
                await self._rate_limit()

                response = await client.get(current_url)

                if response.status_code != 200:
                    raise PhpbbError(f"Failed to load topic: {response.status_code}")

                soup = BeautifulSoup(response.text, "lxml")

                # ===== Extract Attachments =====
                attachment_divs = soup.find_all("div", class_=re.compile(r"attach|file|download"))

                for div in attachment_divs:
                    download_links = div.find_all("a", href=re.compile(r"download/file\.php"))

                    for link in download_links:
                        href = link.get("href", "")
                        id_match = re.search(r"id=(\d+)", href)
                        if not id_match:
                            continue

                        file_id = int(id_match.group(1))

                        if any(a.file_id == file_id for a in attachments):
                            continue

                        filename = None
                        link_text = link.get_text(strip=True)
                        if link_text and not link_text.lower().startswith(("download", "click")):
                            filename = link_text

                        if not filename:
                            filename = link.get("title", "")

                        if not filename:
                            parent = link.parent
                            if parent:
                                filename_span = parent.find("span", class_="filename")
                                if filename_span:
                                    filename = filename_span.get_text(strip=True)

                        if not filename:
                            filename = f"attachment_{file_id}"

                        size_display = ""
                        size_bytes = 0
                        size_elem = div.find(string=re.compile(r"[\d.]+\s*[KMGT]?i?B", re.IGNORECASE))
                        if size_elem:
                            size_display = size_elem.strip()
                            size_bytes = self._parse_size(size_display)

                        download_url = urljoin(base_url + "/", href)

                        attachments.append(AttachmentInfo(
                            file_id=file_id,
                            filename=filename,
                            size_bytes=size_bytes,
                            size_display=size_display,
                            download_url=download_url,
                        ))

                # Check inline attachments in posts
                post_contents = soup.find_all("div", class_="content")
                for content in post_contents:
                    inline_links = content.find_all("a", href=re.compile(r"download/file\.php"))
                    for link in inline_links:
                        href = link.get("href", "")
                        id_match = re.search(r"id=(\d+)", href)
                        if not id_match:
                            continue

                        file_id = int(id_match.group(1))

                        if any(a.file_id == file_id for a in attachments):
                            continue

                        filename = link.get_text(strip=True) or f"attachment_{file_id}"
                        download_url = urljoin(base_url + "/", href)

                        attachments.append(AttachmentInfo(
                            file_id=file_id,
                            filename=filename,
                            download_url=download_url,
                        ))

                # ===== Extract Images (first page only) =====
                if page_num == 0 and include_images:
                    for content in post_contents:
                        img_tags = content.find_all("img")

                        for img in img_tags:
                            src = img.get("src", "")
                            if not src:
                                continue

                            if not src.startswith("http"):
                                img_url = urljoin(base_url + "/", src)
                            else:
                                img_url = src

                            if any(x in img_url.lower() for x in ["smilies", "smiley", "avatar", "icon", "rank"]):
                                continue

                            if img_url in seen_image_urls:
                                continue
                            seen_image_urls.add(img_url)

                            parsed_url = urlparse(img_url)
                            path_lower = parsed_url.path.lower()

                            is_image = any(path_lower.endswith(ext) for ext in image_extensions)
                            is_attachment = "download/file.php" in img_url

                            if not is_image and not is_attachment:
                                if "mode=view" not in img_url:
                                    continue

                            alt_text = img.get("alt", "") or img.get("title", "")

                            images.append(ImageInfo(
                                url=img_url,
                                alt_text=alt_text if alt_text else None,
                                is_inline=True,
                                is_attachment=is_attachment,
                            ))

                    # Linked images (thumbnails -> full size)
                    for link in soup.find_all("a", href=re.compile(r"download/file\.php.*mode=view")):
                        href = link.get("href", "")
                        if not href:
                            continue

                        img_url = urljoin(base_url + "/", href)

                        if img_url in seen_image_urls:
                            continue
                        seen_image_urls.add(img_url)

                        images.append(ImageInfo(
                            url=img_url,
                            alt_text=None,
                            is_inline=False,
                            is_attachment=True,
                        ))

                    # Attached images in attachment boxes
                    for div in soup.find_all("div", class_=re.compile(r"attach|thumbnail")):
                        img_link = div.find("a", href=re.compile(r"download/file\.php"))
                        if img_link:
                            href = img_link.get("href", "")
                            img_url = urljoin(base_url + "/", href)

                            filename_span = div.find("span", class_="filename")
                            if filename_span:
                                filename = filename_span.get_text(strip=True).lower()
                                if any(filename.endswith(ext) for ext in image_extensions):
                                    if img_url not in seen_image_urls:
                                        seen_image_urls.add(img_url)
                                        images.append(ImageInfo(
                                            url=img_url,
                                            alt_text=filename_span.get_text(strip=True),
                                            is_inline=False,
                                            is_attachment=True,
                                        ))

                # Check for next page
                pagination = soup.find("div", class_="pagination")
                next_url = None
                if pagination:
                    next_link = pagination.find("a", class_="arrow", string=re.compile(r"next|»"))
                    if next_link:
                        next_href = next_link.get("href", "")
                        if next_href:
                            next_url = urljoin(base_url + "/", next_href)

                current_url = next_url
                page_num += 1

        logger.debug(
            "phpbb_topic_content_found",
            topic_url=topic_url,
            attachment_count=len(attachments),
            image_count=len(images),
        )

        return attachments, images

    def _parse_size(self, size_str: str) -> int:
        """Parse a human-readable size string to bytes."""
        size_str = size_str.strip().upper()

        # Match patterns like "35.68 MIB", "1.2 GB", "500 KB"
        match = re.match(r"([\d.]+)\s*([KMGT]I?B)?", size_str)
        if not match:
            return 0

        value_str = match.group(1)
        # Handle edge cases like just "." or empty string
        if not value_str or value_str == ".":
            return 0

        try:
            value = float(value_str)
        except ValueError:
            return 0

        unit = match.group(2) or "B"

        multipliers = {
            "B": 1,
            "KB": 1024,
            "KIB": 1024,
            "MB": 1024**2,
            "MIB": 1024**2,
            "GB": 1024**3,
            "GIB": 1024**3,
            "TB": 1024**4,
            "TIB": 1024**4,
        }

        return int(value * multipliers.get(unit, 1))

    # ========== File Download ==========

    async def download_file(
        self,
        download_url: str,
        dest_path: Path,
        cookies: dict[str, str],
        progress_callback=None,
    ) -> Path:
        """Download a file from phpBB.

        Args:
            download_url: Full download URL.
            dest_path: Destination path for the file.
            cookies: Session cookies.
            progress_callback: Optional callback(bytes_downloaded, total_bytes).

        Returns:
            Path to the downloaded file.

        Raises:
            PhpbbError: If download fails.
        """
        await self._rate_limit()

        # Create parent directories
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=600.0, cookies=cookies  # 10 minute timeout
        ) as client:
            async with client.stream("GET", download_url) as response:
                if response.status_code == 404:
                    raise PhpbbNotFoundError(f"File not found: {download_url}")

                if response.status_code == 403:
                    raise PhpbbAccessDeniedError(f"Access denied: {download_url}")

                if response.status_code != 200:
                    raise PhpbbError(f"Download failed: {response.status_code}")

                # Get total size from headers
                total_size = int(response.headers.get("content-length", 0))

                # Check for content-disposition to get filename
                content_disp = response.headers.get("content-disposition", "")
                if "filename=" in content_disp:
                    # Extract filename from header
                    filename_match = re.search(r'filename[*]?=["\']?([^"\';]+)', content_disp)
                    if filename_match:
                        # Use the filename from header if dest_path is a directory
                        if dest_path.is_dir():
                            dest_path = dest_path / filename_match.group(1)

                downloaded = 0
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            await progress_callback(downloaded, total_size)

        logger.info(
            "phpbb_file_downloaded",
            url=download_url,
            dest=str(dest_path),
            size=downloaded,
        )

        return dest_path

    # ========== Design Detection ==========

    async def scan_forum_for_designs(
        self,
        base_url: str,
        forum_url: str,
        cookies: dict[str, str],
        max_topics: int | None = None,
        include_images: bool = True,
    ) -> list[DetectedPhpbbDesign]:
        """Scan a forum for designs (topics with ZIP attachments).

        Args:
            base_url: Base URL of the phpBB forum.
            forum_url: URL of the forum to scan.
            cookies: Session cookies.
            max_topics: Optional limit on topics to scan.
            include_images: Whether to also extract preview images from topics.

        Returns:
            List of detected designs.
        """
        # Get all topics
        topics = await self.list_all_topics(base_url, forum_url, cookies, max_topics)

        designs: list[DetectedPhpbbDesign] = []

        for topic in topics:
            # Get attachments and images in a single fetch
            topic_url = f"viewtopic.php?f={topic.forum_id}&t={topic.topic_id}"
            try:
                attachments, images = await self.get_topic_content(
                    base_url, topic_url, cookies, include_images=include_images
                )
            except PhpbbError as e:
                logger.warning(
                    "phpbb_topic_scan_failed",
                    topic_id=topic.topic_id,
                    error=str(e),
                )
                continue

            # Filter to only ZIP/archive files
            archive_extensions = {".zip", ".rar", ".7z", ".tar", ".gz", ".tar.gz"}
            archive_attachments = [
                a for a in attachments
                if any(a.filename.lower().endswith(ext) for ext in archive_extensions)
            ]

            if not archive_attachments:
                continue

            # Create design from topic
            total_size = sum(a.size_bytes for a in archive_attachments)

            # Clean up title (remove common prefixes/suffixes)
            title = self._clean_title(topic.title)

            designs.append(DetectedPhpbbDesign(
                topic_id=topic.topic_id,
                forum_id=topic.forum_id,
                topic_title=topic.title,
                relative_path=f"{topic.forum_id}/{topic.topic_id}",
                title=title,
                attachments=archive_attachments,
                images=images,
                total_size=total_size,
                author=topic.author,
                last_post_date=topic.last_post_date,
            ))

        logger.info(
            "phpbb_forum_scanned",
            forum_url=forum_url,
            topics_scanned=len(topics),
            designs_found=len(designs),
        )

        return designs

    def _clean_title(self, title: str) -> str:
        """Clean up a topic title to use as a design title."""
        # Remove common prefixes
        prefixes_to_remove = [
            r"^\[.*?\]\s*",  # [TAG] prefix
            r"^RE:\s*",  # RE: prefix
            r"^FW:\s*",  # FW: prefix
        ]

        cleaned = title
        for pattern in prefixes_to_remove:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Clean up whitespace
        cleaned = " ".join(cleaned.split())

        return cleaned.strip() or title

    # ========== Credential Management ==========

    async def get_credentials(self, credentials_id: str) -> PhpbbCredentials | None:
        """Get stored credentials by ID.

        Args:
            credentials_id: Credentials ID.

        Returns:
            PhpbbCredentials or None if not found.
        """
        result = await self.db.execute(
            select(PhpbbCredentials).where(PhpbbCredentials.id == credentials_id)
        )
        return result.scalar_one_or_none()

    async def list_credentials(self) -> list[PhpbbCredentials]:
        """List all stored phpBB credentials.

        Returns:
            List of PhpbbCredentials.
        """
        result = await self.db.execute(
            select(PhpbbCredentials).order_by(PhpbbCredentials.base_url)
        )
        return list(result.scalars().all())

    async def create_credentials(
        self,
        base_url: str,
        username: str,
        password: str,
        test_login: bool = True,
    ) -> PhpbbCredentials:
        """Create and store new phpBB credentials.

        Args:
            base_url: Base URL of the phpBB forum.
            username: Forum username.
            password: Forum password.
            test_login: Whether to test login before storing.

        Returns:
            The created PhpbbCredentials.

        Raises:
            PhpbbAuthError: If test_login is True and login fails.
        """
        base_url = base_url.rstrip("/")

        # Test login if requested
        session_cookies = None
        if test_login:
            cookies = await self.login(base_url, username, password)
            session_cookies = json.dumps(cookies)

        # Create credentials
        credentials = PhpbbCredentials(
            base_url=base_url,
            username_encrypted=self._encrypt(username),
            password_encrypted=self._encrypt(password),
            session_cookies_encrypted=self._encrypt(session_cookies) if session_cookies else None,
            session_expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_TIMEOUT_HOURS) if session_cookies else None,
            last_login_at=datetime.now(timezone.utc) if test_login else None,
        )
        self.db.add(credentials)
        await self.db.flush()

        logger.info(
            "phpbb_credentials_created",
            credentials_id=credentials.id,
            base_url=base_url,
            username=username,
        )

        return credentials

    async def get_session_cookies(
        self,
        credentials: PhpbbCredentials,
        force_refresh: bool = False,
    ) -> dict[str, str]:
        """Get valid session cookies, refreshing if needed.

        Args:
            credentials: The credentials to use.
            force_refresh: Force a new login even if session is valid.

        Returns:
            Dict of session cookies.

        Raises:
            PhpbbAuthError: If login fails.
        """
        # Check if we have a valid cached session
        if not force_refresh and credentials.session_cookies_encrypted:
            if credentials.session_expires_at and credentials.session_expires_at > datetime.now(timezone.utc):
                try:
                    cookies_json = self._decrypt(credentials.session_cookies_encrypted)
                    cookies = json.loads(cookies_json)

                    # Validate the session is still active
                    if await self.validate_session(credentials.base_url, cookies):
                        return cookies
                except Exception:
                    pass  # Session invalid, need to refresh

        # Need to login fresh
        username = self._decrypt(credentials.username_encrypted)
        password = self._decrypt(credentials.password_encrypted)

        cookies = await self.login(credentials.base_url, username, password)

        # Update stored session
        credentials.session_cookies_encrypted = self._encrypt(json.dumps(cookies))
        credentials.session_expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TIMEOUT_HOURS)
        credentials.last_login_at = datetime.now(timezone.utc)
        credentials.last_login_error = None
        await self.db.flush()

        return cookies

    async def delete_credentials(self, credentials_id: str) -> None:
        """Delete stored credentials.

        Args:
            credentials_id: ID of credentials to delete.

        Raises:
            PhpbbError: If credentials not found.
        """
        credentials = await self.get_credentials(credentials_id)
        if not credentials:
            raise PhpbbError(f"Credentials {credentials_id} not found")

        await self.db.delete(credentials)

        logger.info("phpbb_credentials_deleted", credentials_id=credentials_id)

    # ========== Encryption Helpers ==========

    def _get_encryption_key(self) -> bytes:
        """Get or generate the encryption key."""
        if self._encryption_key:
            return self._encryption_key

        if settings.encryption_key:
            # Fernet expects the key as base64-encoded bytes (not decoded)
            self._encryption_key = settings.encryption_key.encode()
        else:
            # Generate a new key if not set (will only persist in memory)
            from cryptography.fernet import Fernet
            self._encryption_key = Fernet.generate_key()
            logger.warning(
                "encryption_key_generated",
                message="Using auto-generated encryption key. Set PRINTARR_ENCRYPTION_KEY for persistence.",
            )

        return self._encryption_key

    def _encrypt(self, data: str) -> str:
        """Encrypt a string using Fernet."""
        from cryptography.fernet import Fernet

        key = self._get_encryption_key()
        f = Fernet(key)
        return f.encrypt(data.encode()).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        """Decrypt a Fernet-encrypted string."""
        from cryptography.fernet import Fernet

        key = self._get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted_data.encode()).decode()
