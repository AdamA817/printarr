"""Google Drive integration service for v0.8 Manual Imports.

Provides:
- Public folder access via API key
- OAuth2 authentication for private folders
- File listing with pagination
- File downloading
- Credential encryption and storage

See DEC-034 for design decisions.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import GoogleCredentials

if TYPE_CHECKING:
    pass

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

    pass


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
        """
        # Lazy import to avoid startup errors if google libs not installed
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError as e:
            raise GoogleDriveError(
                "Google API libraries not installed. Run: pip install google-api-python-client"
            ) from e

        try:
            service = await self._get_drive_service(credentials)
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
                raise GoogleRateLimitError("Google API rate limit exceeded") from e
            raise GoogleDriveError(f"Google API error: {e}") from e

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
        """
        try:
            from googleapiclient.errors import HttpError
        except ImportError as e:
            raise GoogleDriveError("Google API libraries not installed") from e

        try:
            service = await self._get_drive_service(credentials)

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
                raise GoogleRateLimitError("Google API rate limit exceeded") from e
            raise GoogleDriveError(f"Google API error: {e}") from e

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
        """
        try:
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as e:
            raise GoogleDriveError("Google API libraries not installed") from e

        import io

        try:
            service = await self._get_drive_service(credentials)

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
                raise GoogleRateLimitError("Google API rate limit exceeded") from e
            raise GoogleDriveError(f"Download failed: {e}") from e

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
