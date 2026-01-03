"""Google Drive integration service for v0.8 Manual Imports.

Provides:
- Public folder access via API key
- OAuth2 authentication for private folders
- File listing with pagination
- File downloading
- Credential encryption and storage
- Rate limiting with exponential backoff

See DEC-034 for design decisions.
"""

from __future__ import annotations

import asyncio
import base64
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import GoogleCredentials

if TYPE_CHECKING:
    pass

T = TypeVar("T")

# Rate limiting configuration
RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_BASE_DELAY = 2.0  # seconds
RATE_LIMIT_MAX_DELAY = 300.0  # 5 minutes
RATE_LIMIT_JITTER = 0.3  # 30% jitter

logger = get_logger(__name__)

# Google Drive API scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Regex for parsing Google Drive URLs
DRIVE_FOLDER_REGEX = re.compile(
    r"(?:https?://)?(?:drive\.google\.com/(?:drive/)?(?:u/\d+/)?folders?/|"
    r"drive\.google\.com/open\?id=)([a-zA-Z0-9_-]+)"
)
DRIVE_FILE_REGEX = re.compile(
    r"(?:https?://)?(?:drive\.google\.com/(?:file/d/|open\?id=))([a-zA-Z0-9_-]+)"
)


class GoogleDriveError(Exception):
    """Base exception for Google Drive errors."""

    pass


class GoogleAuthError(GoogleDriveError):
    """Raised when authentication fails."""

    pass


class GoogleAccessDeniedError(GoogleDriveError):
    """Raised when access is denied to a resource."""

    pass


class GoogleNotFoundError(GoogleDriveError):
    """Raised when a file or folder is not found."""

    pass


class GoogleRateLimitError(GoogleDriveError):
    """Raised when rate limited by Google API."""

    def __init__(self, message: str = "Google API rate limit exceeded", retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # Seconds to wait before retry


async def with_rate_limit_retry(
    func: Callable[[], T],
    max_retries: int = RATE_LIMIT_MAX_RETRIES,
    operation: str = "API call",
) -> T:
    """Execute a function with automatic retry on rate limiting.

    Implements exponential backoff with jitter for Google API rate limits.

    Args:
        func: Async function to execute.
        max_retries: Maximum number of retry attempts.
        operation: Description of the operation for logging.

    Returns:
        Result of the function call.

    Raises:
        GoogleRateLimitError: If max retries exceeded.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await asyncio.to_thread(func)
        except Exception as e:
            # Check if it's a rate limit error
            error_str = str(e).lower()
            is_rate_limit = (
                "429" in error_str
                or "rate limit" in error_str
                or "quota" in error_str
                or "automated queries" in error_str
            )

            if not is_rate_limit:
                raise

            last_error = e

            if attempt >= max_retries:
                logger.error(
                    "rate_limit_max_retries",
                    operation=operation,
                    attempts=attempt + 1,
                    error=str(e),
                )
                raise GoogleRateLimitError(
                    f"Rate limit exceeded after {attempt + 1} attempts: {e}"
                ) from e

            # Calculate delay with exponential backoff and jitter
            delay = min(
                RATE_LIMIT_BASE_DELAY * (2 ** attempt),
                RATE_LIMIT_MAX_DELAY,
            )
            jitter = delay * RATE_LIMIT_JITTER * (2 * random.random() - 1)
            delay += jitter

            logger.warning(
                "rate_limit_retry",
                operation=operation,
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_seconds=round(delay, 1),
                error=str(e),
            )

            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise GoogleRateLimitError(f"Rate limit handling failed: {last_error}")


class FolderInfo(BaseModel):
    """Information about a Google Drive folder."""

    id: str
    name: str
    is_public: bool = False
    file_count: int = 0
    owner_email: str | None = None


class FileInfo(BaseModel):
    """Information about a Google Drive file."""

    id: str
    name: str
    mime_type: str
    size: int = 0
    created_time: datetime | None = None
    modified_time: datetime | None = None
    parent_id: str | None = None
    is_folder: bool = False
    web_view_link: str | None = None


class SyncResult(BaseModel):
    """Result of a folder sync operation."""

    folder_id: str
    files_found: int = 0
    files_new: int = 0
    files_downloaded: int = 0
    errors: list[str] = Field(default_factory=list)
    last_file_id: str | None = None


class VirtualFolder:
    """Represents a folder in the virtual file tree built from Google Drive."""

    def __init__(self, id: str, name: str, parent_id: str | None = None):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.files: list[FileInfo] = []
        self.subfolders: dict[str, "VirtualFolder"] = {}
        self.path: str = ""  # Relative path from root

    def add_file(self, file_info: FileInfo) -> None:
        """Add a file to this folder."""
        self.files.append(file_info)

    def add_subfolder(self, folder: "VirtualFolder") -> None:
        """Add a subfolder to this folder."""
        self.subfolders[folder.id] = folder

    def get_files_at_root(self) -> list[FileInfo]:
        """Get files directly in this folder (not in subfolders)."""
        return self.files

    def get_subfolder_by_name(self, name: str) -> "VirtualFolder | None":
        """Get a subfolder by name (case-insensitive)."""
        name_lower = name.lower()
        for subfolder in self.subfolders.values():
            if subfolder.name.lower() == name_lower:
                return subfolder
        return None

    def get_all_files_recursive(self) -> list[tuple[str, FileInfo]]:
        """Get all files with relative paths."""
        results: list[tuple[str, FileInfo]] = []
        for f in self.files:
            results.append((f.name, f))
        for subfolder in self.subfolders.values():
            for rel_path, f in subfolder.get_all_files_recursive():
                results.append((f"{subfolder.name}/{rel_path}", f))
        return results


class DetectedGoogleDriveDesign(BaseModel):
    """A design detected in a Google Drive folder."""

    folder_id: str
    folder_name: str
    relative_path: str  # Path from root folder
    title: str
    model_files: list[str] = Field(default_factory=list)
    archive_files: list[str] = Field(default_factory=list)
    preview_files: list[str] = Field(default_factory=list)
    total_size: int = 0

    class Config:
        arbitrary_types_allowed = True


class GoogleDriveService:
    """Service for interacting with Google Drive API.

    Supports both public folder access (via API key) and
    authenticated access (via OAuth2).
    """

    def __init__(self, db: AsyncSession):
        """Initialize the Google Drive service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db
        self._encryption_key: bytes | None = None

    # ========== URL Parsing ==========

    @staticmethod
    def parse_folder_url(url: str) -> str | None:
        """Extract folder ID from a Google Drive URL.

        Args:
            url: Google Drive folder URL.

        Returns:
            Folder ID or None if not a valid folder URL.
        """
        match = DRIVE_FOLDER_REGEX.search(url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def parse_file_url(url: str) -> str | None:
        """Extract file ID from a Google Drive URL.

        Args:
            url: Google Drive file URL.

        Returns:
            File ID or None if not a valid file URL.
        """
        match = DRIVE_FILE_REGEX.search(url)
        if match:
            return match.group(1)
        return None

    # ========== Folder Operations ==========

    async def validate_folder_url(self, url: str) -> FolderInfo:
        """Validate a Google Drive folder URL and return folder info.

        Args:
            url: Google Drive folder URL.

        Returns:
            FolderInfo with details about the folder.

        Raises:
            GoogleDriveError: If URL is invalid or folder is inaccessible.
        """
        folder_id = self.parse_folder_url(url)
        if not folder_id:
            raise GoogleDriveError(f"Invalid Google Drive folder URL: {url}")

        return await self.get_folder_info(folder_id)

    async def get_folder_info(
        self, folder_id: str, credentials: GoogleCredentials | None = None
    ) -> FolderInfo:
        """Get information about a folder.

        Args:
            folder_id: Google Drive folder ID.
            credentials: Optional credentials for private folders.

        Returns:
            FolderInfo with details about the folder.

        Raises:
            GoogleNotFoundError: If folder doesn't exist.
            GoogleAccessDeniedError: If access is denied.
            GoogleRateLimitError: If rate limited after max retries.
        """
        # Lazy import to avoid startup errors if google libs not installed
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError as e:
            raise GoogleDriveError(
                "Google API libraries not installed. Run: pip install google-api-python-client"
            ) from e

        service = await self._get_drive_service(credentials)

        async def _execute_with_retry() -> FolderInfo:
            for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
                try:
                    file = service.files().get(
                        fileId=folder_id,
                        fields="id, name, mimeType, owners",
                        supportsAllDrives=True,
                    ).execute()

                    if file.get("mimeType") != "application/vnd.google-apps.folder":
                        raise GoogleDriveError(f"ID {folder_id} is not a folder")

                    # Count files in folder
                    query = f"'{folder_id}' in parents and trashed = false"
                    result = service.files().list(
                        q=query,
                        fields="files(id)",
                        pageSize=1000,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    ).execute()
                    file_count = len(result.get("files", []))

                    owners = file.get("owners", [])
                    owner_email = owners[0].get("emailAddress") if owners else None

                    return FolderInfo(
                        id=file["id"],
                        name=file["name"],
                        is_public=credentials is None,
                        file_count=file_count,
                        owner_email=owner_email,
                    )

                except HttpError as e:
                    if e.resp.status == 404:
                        raise GoogleNotFoundError(f"Folder {folder_id} not found") from e
                    if e.resp.status in (401, 403):
                        raise GoogleAccessDeniedError(
                            f"Access denied to folder {folder_id}. May require authentication."
                        ) from e
                    if e.resp.status == 429:
                        if attempt >= RATE_LIMIT_MAX_RETRIES:
                            raise GoogleRateLimitError(
                                f"Rate limit exceeded after {attempt + 1} attempts"
                            ) from e

                        delay = min(RATE_LIMIT_BASE_DELAY * (2 ** attempt), RATE_LIMIT_MAX_DELAY)
                        jitter = delay * RATE_LIMIT_JITTER * (2 * random.random() - 1)
                        delay += jitter

                        logger.warning(
                            "rate_limit_retry",
                            operation="get_folder_info",
                            folder_id=folder_id,
                            attempt=attempt + 1,
                            delay_seconds=round(delay, 1),
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise GoogleDriveError(f"Google API error: {e}") from e

            raise GoogleRateLimitError("Rate limit handling exhausted")

        return await _execute_with_retry()

    async def list_folder(
        self,
        folder_id: str,
        credentials: GoogleCredentials | None = None,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[FileInfo], str | None]:
        """List files in a folder.

        Args:
            folder_id: Google Drive folder ID.
            credentials: Optional credentials for private folders.
            page_token: Token for pagination.
            page_size: Number of files per page.

        Returns:
            Tuple of (list of FileInfo, next_page_token or None).

        Raises:
            GoogleDriveError: If listing fails.
            GoogleRateLimitError: If rate limited after max retries.
        """
        try:
            from googleapiclient.errors import HttpError
        except ImportError as e:
            raise GoogleDriveError("Google API libraries not installed") from e

        service = await self._get_drive_service(credentials)

        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            try:
                query = f"'{folder_id}' in parents and trashed = false"
                result = service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink)",
                    pageToken=page_token,
                    pageSize=page_size,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    orderBy="name",
                ).execute()

                files = []
                for f in result.get("files", []):
                    files.append(FileInfo(
                        id=f["id"],
                        name=f["name"],
                        mime_type=f["mimeType"],
                        size=int(f.get("size", 0)),
                        created_time=datetime.fromisoformat(f["createdTime"].replace("Z", "+00:00")) if f.get("createdTime") else None,
                        modified_time=datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00")) if f.get("modifiedTime") else None,
                        parent_id=f["parents"][0] if f.get("parents") else None,
                        is_folder=f["mimeType"] == "application/vnd.google-apps.folder",
                        web_view_link=f.get("webViewLink"),
                    ))

                return files, result.get("nextPageToken")

            except HttpError as e:
                if e.resp.status == 404:
                    raise GoogleNotFoundError(f"Folder {folder_id} not found") from e
                if e.resp.status in (401, 403):
                    raise GoogleAccessDeniedError(f"Access denied to folder {folder_id}") from e
                if e.resp.status == 429:
                    if attempt >= RATE_LIMIT_MAX_RETRIES:
                        raise GoogleRateLimitError(
                            f"Rate limit exceeded after {attempt + 1} attempts"
                        ) from e

                    delay = min(RATE_LIMIT_BASE_DELAY * (2 ** attempt), RATE_LIMIT_MAX_DELAY)
                    jitter = delay * RATE_LIMIT_JITTER * (2 * random.random() - 1)
                    delay += jitter

                    logger.warning(
                        "rate_limit_retry",
                        operation="list_folder",
                        folder_id=folder_id,
                        attempt=attempt + 1,
                        delay_seconds=round(delay, 1),
                    )
                    await asyncio.sleep(delay)
                    continue
                raise GoogleDriveError(f"Google API error: {e}") from e

        raise GoogleRateLimitError("Rate limit handling exhausted")

    async def list_folder_recursive(
        self,
        folder_id: str,
        credentials: GoogleCredentials | None = None,
        max_depth: int = 10,
    ) -> list[FileInfo]:
        """List all files in a folder recursively.

        Args:
            folder_id: Google Drive folder ID.
            credentials: Optional credentials for private folders.
            max_depth: Maximum recursion depth.

        Returns:
            List of all FileInfo in folder tree.
        """
        all_files: list[FileInfo] = []
        await self._list_recursive(folder_id, credentials, all_files, 0, max_depth)
        return all_files

    async def _list_recursive(
        self,
        folder_id: str,
        credentials: GoogleCredentials | None,
        accumulator: list[FileInfo],
        current_depth: int,
        max_depth: int,
    ) -> None:
        """Recursive helper for listing folder contents."""
        if current_depth >= max_depth:
            return

        page_token = None
        while True:
            files, next_token = await self.list_folder(
                folder_id, credentials, page_token
            )
            for f in files:
                accumulator.append(f)
                if f.is_folder:
                    await self._list_recursive(
                        f.id, credentials, accumulator, current_depth + 1, max_depth
                    )
            if not next_token:
                break
            page_token = next_token

    # ========== File Download ==========

    async def download_file(
        self,
        file_id: str,
        dest_path: Path,
        credentials: GoogleCredentials | None = None,
    ) -> Path:
        """Download a file from Google Drive.

        Args:
            file_id: Google Drive file ID.
            dest_path: Destination path for the file.
            credentials: Optional credentials for private files.

        Returns:
            Path to the downloaded file.

        Raises:
            GoogleDriveError: If download fails.
            GoogleRateLimitError: If rate limited after max retries.
        """
        try:
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as e:
            raise GoogleDriveError("Google API libraries not installed") from e

        import io

        service = await self._get_drive_service(credentials)

        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            try:
                # Get file metadata first
                file_meta = service.files().get(
                    fileId=file_id,
                    fields="name, size, mimeType",
                    supportsAllDrives=True,
                ).execute()

                # Create parent directories
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Download file
                request = service.files().get_media(
                    fileId=file_id,
                    supportsAllDrives=True,
                )

                with open(dest_path, "wb") as f:
                    downloader = MediaIoBaseDownload(f, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()

                logger.info(
                    "file_downloaded",
                    file_id=file_id,
                    name=file_meta["name"],
                    size=file_meta.get("size", 0),
                    dest=str(dest_path),
                )
                return dest_path

            except HttpError as e:
                if e.resp.status == 404:
                    raise GoogleNotFoundError(f"File {file_id} not found") from e
                if e.resp.status in (401, 403):
                    raise GoogleAccessDeniedError(f"Access denied to file {file_id}") from e
                if e.resp.status == 429:
                    if attempt >= RATE_LIMIT_MAX_RETRIES:
                        raise GoogleRateLimitError(
                            f"Rate limit exceeded after {attempt + 1} attempts"
                        ) from e

                    delay = min(RATE_LIMIT_BASE_DELAY * (2 ** attempt), RATE_LIMIT_MAX_DELAY)
                    jitter = delay * RATE_LIMIT_JITTER * (2 * random.random() - 1)
                    delay += jitter

                    logger.warning(
                        "rate_limit_retry",
                        operation="download_file",
                        file_id=file_id,
                        attempt=attempt + 1,
                        delay_seconds=round(delay, 1),
                    )
                    await asyncio.sleep(delay)
                    continue
                raise GoogleDriveError(f"Download failed: {e}") from e

        raise GoogleRateLimitError("Rate limit handling exhausted")

    # ========== OAuth2 Flow ==========

    def get_oauth_url(self, state: str | None = None) -> str:
        """Get the OAuth2 authorization URL.

        Args:
            state: Optional state parameter for CSRF protection.

        Returns:
            OAuth2 authorization URL.

        Raises:
            GoogleAuthError: If OAuth is not configured.
        """
        if not settings.google_oauth_configured:
            raise GoogleAuthError(
                "Google OAuth not configured. Set PRINTARR_GOOGLE_CLIENT_ID and PRINTARR_GOOGLE_CLIENT_SECRET"
            )

        try:
            from google_auth_oauthlib.flow import Flow
        except ImportError as e:
            raise GoogleAuthError("Google OAuth libraries not installed") from e

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=settings.google_redirect_uri,
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )

        return auth_url

    async def handle_oauth_callback(self, code: str) -> GoogleCredentials:
        """Handle OAuth2 callback and store credentials.

        Args:
            code: Authorization code from callback.

        Returns:
            The stored GoogleCredentials.

        Raises:
            GoogleAuthError: If token exchange fails.
        """
        if not settings.google_oauth_configured:
            raise GoogleAuthError("Google OAuth not configured")

        try:
            from google_auth_oauthlib.flow import Flow
            from googleapiclient.discovery import build
        except ImportError as e:
            raise GoogleAuthError("Google OAuth libraries not installed") from e

        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=SCOPES,
                redirect_uri=settings.google_redirect_uri,
            )

            # Exchange code for tokens
            flow.fetch_token(code=code)
            creds = flow.credentials

            # Get user email
            oauth2 = build("oauth2", "v2", credentials=creds)
            user_info = oauth2.userinfo().get().execute()
            email = user_info.get("email", "unknown")

            # Check if credentials already exist for this email
            existing = await self._get_credentials_by_email(email)
            if existing:
                # Update existing credentials
                existing.access_token_encrypted = self._encrypt(creds.token)
                existing.refresh_token_encrypted = self._encrypt(creds.refresh_token) if creds.refresh_token else existing.refresh_token_encrypted
                existing.expires_at = creds.expiry
                await self.db.flush()
                logger.info("credentials_updated", email=email)
                return existing

            # Create new credentials
            credentials = GoogleCredentials(
                email=email,
                access_token_encrypted=self._encrypt(creds.token),
                refresh_token_encrypted=self._encrypt(creds.refresh_token) if creds.refresh_token else None,
                expires_at=creds.expiry,
            )
            self.db.add(credentials)
            await self.db.flush()

            logger.info("credentials_created", email=email, credentials_id=credentials.id)
            return credentials

        except Exception as e:
            raise GoogleAuthError(f"OAuth callback failed: {e}") from e

    async def revoke_credentials(self, credentials_id: str) -> None:
        """Revoke and delete stored credentials.

        Args:
            credentials_id: ID of credentials to revoke.

        Raises:
            GoogleAuthError: If credentials not found.
        """
        result = await self.db.execute(
            select(GoogleCredentials).where(GoogleCredentials.id == credentials_id)
        )
        credentials = result.scalar_one_or_none()
        if not credentials:
            raise GoogleAuthError(f"Credentials {credentials_id} not found")

        # Try to revoke with Google
        if credentials.access_token_encrypted:
            try:
                import httpx
                token = self._decrypt(credentials.access_token_encrypted)
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "https://oauth2.googleapis.com/revoke",
                        params={"token": token},
                    )
            except Exception as e:
                logger.warning("credential_revoke_failed", error=str(e))

        await self.db.delete(credentials)
        logger.info("credentials_deleted", credentials_id=credentials_id)

    # ========== Credential Management ==========

    async def get_credentials(self, credentials_id: str) -> GoogleCredentials | None:
        """Get stored credentials by ID.

        Args:
            credentials_id: Credentials ID.

        Returns:
            GoogleCredentials or None if not found.
        """
        result = await self.db.execute(
            select(GoogleCredentials).where(GoogleCredentials.id == credentials_id)
        )
        return result.scalar_one_or_none()

    async def list_credentials(self) -> list[GoogleCredentials]:
        """List all stored Google credentials.

        Returns:
            List of GoogleCredentials.
        """
        result = await self.db.execute(
            select(GoogleCredentials).order_by(GoogleCredentials.email)
        )
        return list(result.scalars().all())

    async def _get_credentials_by_email(self, email: str) -> GoogleCredentials | None:
        """Get credentials by email address."""
        result = await self.db.execute(
            select(GoogleCredentials).where(GoogleCredentials.email == email)
        )
        return result.scalar_one_or_none()

    async def _refresh_if_needed(self, credentials: GoogleCredentials) -> None:
        """Refresh OAuth token if expired.

        Args:
            credentials: Credentials to potentially refresh.
        """
        if not credentials.expires_at:
            return

        # Refresh if expiring in next 5 minutes
        if credentials.expires_at > datetime.utcnow() + timedelta(minutes=5):
            return

        if not credentials.refresh_token_encrypted:
            logger.warning("cannot_refresh_no_refresh_token", email=credentials.email)
            return

        try:
            from google.oauth2.credentials import Credentials as OAuthCredentials
            from google.auth.transport.requests import Request
        except ImportError:
            return

        refresh_token = self._decrypt(credentials.refresh_token_encrypted)

        creds = OAuthCredentials(
            token=self._decrypt(credentials.access_token_encrypted) if credentials.access_token_encrypted else None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        creds.refresh(Request())

        credentials.access_token_encrypted = self._encrypt(creds.token)
        credentials.expires_at = creds.expiry
        await self.db.flush()

        logger.info("credentials_refreshed", email=credentials.email)

    # ========== Private Helpers ==========

    async def _get_drive_service(self, credentials: GoogleCredentials | None = None):
        """Get a Google Drive service instance.

        Args:
            credentials: Optional stored credentials for authenticated access.

        Returns:
            Drive API service instance.
        """
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials as OAuthCredentials
        except ImportError as e:
            raise GoogleDriveError("Google API libraries not installed") from e

        if credentials:
            # Refresh if needed
            await self._refresh_if_needed(credentials)

            # Build with OAuth credentials
            access_token = self._decrypt(credentials.access_token_encrypted) if credentials.access_token_encrypted else None
            refresh_token = self._decrypt(credentials.refresh_token_encrypted) if credentials.refresh_token_encrypted else None

            creds = OAuthCredentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
            )
            return build("drive", "v3", credentials=creds)

        elif settings.google_api_key:
            # Use API key for public folders
            return build("drive", "v3", developerKey=settings.google_api_key)

        else:
            raise GoogleAuthError(
                "No credentials available. Either provide OAuth credentials or set PRINTARR_GOOGLE_API_KEY"
            )

    def _get_encryption_key(self) -> bytes:
        """Get or generate the encryption key."""
        if self._encryption_key:
            return self._encryption_key

        if settings.encryption_key:
            self._encryption_key = base64.b64decode(settings.encryption_key)
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

    # ========== Design Detection for Google Drive ==========

    async def scan_for_designs(
        self,
        folder_id: str,
        credentials: GoogleCredentials | None = None,
        config: "ImportProfileConfig | None" = None,
    ) -> list[DetectedGoogleDriveDesign]:
        """Scan a Google Drive folder for designs using an import profile.

        Args:
            folder_id: Root folder ID to scan.
            credentials: Optional credentials for private folders.
            config: Import profile config. Uses default detection if not provided.

        Returns:
            List of detected designs.
        """
        from app.schemas.import_profile import ImportProfileConfig, ProfileDetectionConfig

        if config is None:
            config = ImportProfileConfig()

        # List all files recursively
        all_files = await self.list_folder_recursive(folder_id, credentials)

        logger.info(
            "gdrive_scan_started",
            folder_id=folder_id,
            total_files=len(all_files),
        )

        # Build virtual folder tree
        root_folder = self._build_folder_tree(folder_id, all_files)

        # Detect designs
        designs = self._detect_designs_in_tree(root_folder, config, "")

        logger.info(
            "gdrive_scan_complete",
            folder_id=folder_id,
            designs_found=len(designs),
        )

        return designs

    def _build_folder_tree(
        self, root_id: str, all_files: list[FileInfo]
    ) -> VirtualFolder:
        """Build a virtual folder tree from a flat list of files.

        Args:
            root_id: ID of the root folder.
            all_files: Flat list of all files/folders.

        Returns:
            Root VirtualFolder with nested structure.
        """
        # Create folder lookup
        folders: dict[str, VirtualFolder] = {}
        folders[root_id] = VirtualFolder(root_id, "", None)

        # First pass: create all folder nodes
        for f in all_files:
            if f.is_folder:
                folders[f.id] = VirtualFolder(f.id, f.name, f.parent_id)

        # Second pass: build tree structure and add files
        for f in all_files:
            parent_id = f.parent_id or root_id
            if parent_id not in folders:
                # Parent not in our tree (might be outside scan scope)
                continue

            parent = folders[parent_id]
            if f.is_folder:
                parent.add_subfolder(folders[f.id])
            else:
                parent.add_file(f)

        # Third pass: calculate relative paths
        def set_paths(folder: VirtualFolder, path_prefix: str) -> None:
            folder.path = path_prefix
            for subfolder in folder.subfolders.values():
                subfolder_path = f"{path_prefix}/{subfolder.name}" if path_prefix else subfolder.name
                set_paths(subfolder, subfolder_path)

        set_paths(folders[root_id], "")

        return folders[root_id]

    def _detect_designs_in_tree(
        self,
        folder: VirtualFolder,
        config: "ImportProfileConfig",
        current_path: str,
    ) -> list[DetectedGoogleDriveDesign]:
        """Recursively detect designs in a folder tree.

        Implements the same traversal strategy as local folders:
        - If a folder is a design, add it and don't recurse deeper
        - If not a design, recurse into children

        Args:
            folder: Current folder to check.
            config: Import profile configuration.
            current_path: Current relative path from root.

        Returns:
            List of detected designs.
        """
        import fnmatch

        results: list[DetectedGoogleDriveDesign] = []

        # Skip ignored folders
        if folder.name and self._should_ignore_folder(folder.name, config.ignore):
            return results

        # Check if this folder is a design
        detection = self._is_design_folder_virtual(folder, config)

        if detection is not None:
            # Found a design
            results.append(detection)
            return results

        # Not a design, recurse into subfolders
        for subfolder in folder.subfolders.values():
            subfolder_path = f"{current_path}/{subfolder.name}" if current_path else subfolder.name
            results.extend(self._detect_designs_in_tree(subfolder, config, subfolder_path))

        return results

    def _is_design_folder_virtual(
        self,
        folder: VirtualFolder,
        config: "ImportProfileConfig",
    ) -> DetectedGoogleDriveDesign | None:
        """Check if a virtual folder represents a design.

        Args:
            folder: Virtual folder to check.
            config: Import profile configuration.

        Returns:
            DetectedGoogleDriveDesign if this is a design, None otherwise.
        """
        import fnmatch

        detection = config.detection
        model_extensions = set(ext.lower() for ext in detection.model_extensions)
        archive_extensions = set(ext.lower() for ext in detection.archive_extensions)

        model_files: list[str] = []
        archive_files: list[str] = []
        preview_files: list[str] = []
        total_size = 0

        # Check for model files at root
        for f in folder.files:
            ext = self._get_extension(f.name)
            total_size += f.size
            if ext in model_extensions:
                model_files.append(f.name)
            elif ext in archive_extensions:
                archive_files.append(f.name)

        # Check for model files in subfolders (for nested structure)
        if detection.structure in ("nested", "auto"):
            for subfolder_name in detection.model_subfolders:
                subfolder = folder.get_subfolder_by_name(subfolder_name)
                if subfolder:
                    for rel_path, f in subfolder.get_all_files_recursive():
                        ext = self._get_extension(f.name)
                        total_size += f.size
                        if ext in model_extensions:
                            model_files.append(f"{subfolder.name}/{rel_path}")

        # Find preview files
        preview_extensions = set(ext.lower() for ext in config.preview.extensions)
        has_preview_folder = False  # Track if we found a dedicated preview folder

        # Check root folder for previews
        if config.preview.include_root:
            for f in folder.files:
                ext = self._get_extension(f.name)
                if ext in preview_extensions:
                    preview_files.append(f.name)

        # Check specific preview folders
        for preview_folder_name in config.preview.folders:
            preview_folder = folder.get_subfolder_by_name(preview_folder_name)
            if preview_folder:
                has_preview_folder = True
                for rel_path, f in preview_folder.get_all_files_recursive():
                    ext = self._get_extension(f.name)
                    if ext in preview_extensions:
                        preview_files.append(f"{preview_folder.name}/{rel_path}")

        # Check wildcard preview folders
        for pattern in config.preview.wildcard_folders:
            for subfolder in folder.subfolders.values():
                if fnmatch.fnmatch(subfolder.name, pattern):
                    has_preview_folder = True
                    for rel_path, f in subfolder.get_all_files_recursive():
                        ext = self._get_extension(f.name)
                        if ext in preview_extensions:
                            preview_files.append(f"{subfolder.name}/{rel_path}")

        # Check if require_preview_folder is set and we don't have one
        if detection.require_preview_folder and not has_preview_folder:
            return None

        # Determine if this is a design
        is_design = False
        if len(model_files) >= detection.min_model_files:
            is_design = True
        elif archive_files:
            is_design = True

        if not is_design:
            return None

        # Extract title
        title = self._extract_title_from_name(folder.name, config.title)

        return DetectedGoogleDriveDesign(
            folder_id=folder.id,
            folder_name=folder.name,
            relative_path=folder.path,
            title=title,
            model_files=model_files,
            archive_files=archive_files,
            preview_files=preview_files,
            total_size=total_size,
        )

    def _should_ignore_folder(self, folder_name: str, ignore: "ProfileIgnoreConfig") -> bool:
        """Check if a folder should be ignored."""
        import fnmatch

        if folder_name in ignore.folders:
            return True

        for pattern in ignore.patterns:
            if fnmatch.fnmatch(folder_name, pattern):
                return True

        return False

    def _get_extension(self, filename: str) -> str:
        """Get lowercase file extension."""
        if "." in filename:
            return "." + filename.rsplit(".", 1)[-1].lower()
        return ""

    def _extract_title_from_name(self, folder_name: str, title_config: "ProfileTitleConfig") -> str:
        """Extract title from folder name using title config."""
        title = folder_name

        # Strip patterns
        for pattern in title_config.strip_patterns:
            title = title.replace(pattern, "").strip()

        # Apply case transform
        if title_config.case_transform == "title":
            title = title.title()
        elif title_config.case_transform == "lower":
            title = title.lower()
        elif title_config.case_transform == "upper":
            title = title.upper()

        return title.strip() or folder_name

    # ========== Folder Download for Import ==========

    async def download_folder(
        self,
        folder_id: str,
        dest_dir: Path,
        credentials: GoogleCredentials | None = None,
        progress_callback: "Callable[[int, int], None] | None" = None,
    ) -> list[tuple[Path, int]]:
        """Download all files from a Google Drive folder to a local directory.

        Args:
            folder_id: Google Drive folder ID.
            dest_dir: Local directory to download files to.
            credentials: Optional credentials for private folders.
            progress_callback: Optional callback for progress updates (files_done, total_files).

        Returns:
            List of tuples (local_path, file_size) for each downloaded file.

        Raises:
            GoogleDriveError: If download fails.
        """
        from typing import Callable

        # List all files in folder recursively
        all_files = await self.list_folder_recursive(folder_id, credentials)

        # Filter to only files (not folders)
        files_to_download = [f for f in all_files if not f.is_folder]

        if not files_to_download:
            logger.warning("gdrive_folder_empty", folder_id=folder_id)
            return []

        logger.info(
            "gdrive_download_starting",
            folder_id=folder_id,
            file_count=len(files_to_download),
            dest_dir=str(dest_dir),
        )

        # Build folder lookup for path reconstruction
        folders: dict[str, FileInfo] = {f.id: f for f in all_files if f.is_folder}

        # Download each file
        downloaded: list[tuple[Path, int]] = []
        for i, file_info in enumerate(files_to_download):
            # Build relative path from parent chain
            relative_path = self._build_relative_path(file_info, folders, folder_id)
            dest_path = dest_dir / relative_path

            try:
                await self.download_file(file_info.id, dest_path, credentials)
                downloaded.append((dest_path, file_info.size))

                logger.debug(
                    "gdrive_file_downloaded",
                    file_id=file_info.id,
                    name=file_info.name,
                    relative_path=relative_path,
                )

            except GoogleDriveError as e:
                logger.error(
                    "gdrive_file_download_failed",
                    file_id=file_info.id,
                    name=file_info.name,
                    error=str(e),
                )
                # Continue with other files

            if progress_callback:
                progress_callback(i + 1, len(files_to_download))

        logger.info(
            "gdrive_download_complete",
            folder_id=folder_id,
            files_downloaded=len(downloaded),
            total_size=sum(size for _, size in downloaded),
        )

        return downloaded

    def _build_relative_path(
        self,
        file_info: FileInfo,
        folders: dict[str, FileInfo],
        root_folder_id: str,
    ) -> str:
        """Build the relative path for a file from its parent chain.

        Args:
            file_info: The file to build path for.
            folders: Lookup dict of folder_id -> FileInfo.
            root_folder_id: ID of the root folder to stop at.

        Returns:
            Relative path string.
        """
        path_parts = [file_info.name]

        # Walk up parent chain
        parent_id = file_info.parent_id
        while parent_id and parent_id != root_folder_id:
            parent = folders.get(parent_id)
            if not parent:
                break
            path_parts.insert(0, parent.name)
            parent_id = parent.parent_id

        return "/".join(path_parts)
