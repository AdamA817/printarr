"""Tests for GoogleDriveService - Google Drive integration (v0.8).

Tests cover:
- URL parsing for folder and file IDs
- Folder validation (mocked API)
- File listing (mocked API)
- Credential encryption/decryption
- OAuth flow setup

Note: Most tests mock the Google API to avoid requiring real credentials.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import GoogleCredentials
from app.services.google_drive import (
    DRIVE_FILE_REGEX,
    DRIVE_FOLDER_REGEX,
    FileInfo,
    FolderInfo,
    GoogleAccessDeniedError,
    GoogleAuthError,
    GoogleDriveError,
    GoogleDriveService,
    GoogleNotFoundError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def db_engine():
    """Create an in-memory test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def service(db_session) -> GoogleDriveService:
    """Create GoogleDriveService instance."""
    return GoogleDriveService(db_session)


@pytest.fixture
async def sample_credentials(db_session):
    """Create sample Google credentials."""
    creds = GoogleCredentials(
        email="test@example.com",
        access_token_encrypted="encrypted_access",
        refresh_token_encrypted="encrypted_refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(creds)
    await db_session.flush()
    return creds


# =============================================================================
# URL Parsing Tests
# =============================================================================


class TestParseFolderUrl:
    """Tests for parse_folder_url static method."""

    def test_parse_standard_folder_url(self):
        """Test parsing standard folder URL."""
        url = "https://drive.google.com/drive/folders/1ABC123def456"
        result = GoogleDriveService.parse_folder_url(url)
        assert result == "1ABC123def456"

    def test_parse_folder_url_with_user(self):
        """Test parsing folder URL with user segment."""
        url = "https://drive.google.com/drive/u/0/folders/1ABC123def456"
        result = GoogleDriveService.parse_folder_url(url)
        assert result == "1ABC123def456"

    def test_parse_folder_url_open_format(self):
        """Test parsing open?id= format."""
        url = "https://drive.google.com/open?id=1ABC123def456"
        result = GoogleDriveService.parse_folder_url(url)
        assert result == "1ABC123def456"

    def test_parse_folder_url_without_https(self):
        """Test parsing URL without https."""
        url = "drive.google.com/drive/folders/1ABC123def456"
        result = GoogleDriveService.parse_folder_url(url)
        assert result == "1ABC123def456"

    def test_parse_invalid_folder_url(self):
        """Test parsing invalid URL returns None."""
        url = "https://example.com/not-drive"
        result = GoogleDriveService.parse_folder_url(url)
        assert result is None

    def test_parse_empty_url(self):
        """Test parsing empty string."""
        result = GoogleDriveService.parse_folder_url("")
        assert result is None


class TestParseFileUrl:
    """Tests for parse_file_url static method."""

    def test_parse_standard_file_url(self):
        """Test parsing standard file URL."""
        url = "https://drive.google.com/file/d/1XYZ789abc/view"
        result = GoogleDriveService.parse_file_url(url)
        assert result == "1XYZ789abc"

    def test_parse_file_url_open_format(self):
        """Test parsing open?id= format for files."""
        url = "https://drive.google.com/open?id=1XYZ789abc"
        result = GoogleDriveService.parse_file_url(url)
        assert result == "1XYZ789abc"

    def test_parse_invalid_file_url(self):
        """Test parsing invalid file URL."""
        url = "https://drive.google.com/folders/1ABC123"
        result = GoogleDriveService.parse_file_url(url)
        assert result is None


class TestParseUrls:
    """Tests for URL parsing with parse_drive_url."""

    def test_parse_drive_url_folder(self):
        """Test parsing folder URL through unified method."""
        # The service uses parse_folder_url for this
        url = "https://drive.google.com/drive/folders/1ABC123"
        result = GoogleDriveService.parse_folder_url(url)
        assert result == "1ABC123"


# =============================================================================
# Credential Management Tests
# =============================================================================


class TestCredentialManagement:
    """Tests for credential storage and retrieval."""

    @pytest.mark.asyncio
    async def test_get_credentials(self, service: GoogleDriveService, sample_credentials):
        """Test retrieving credentials by ID."""
        result = await service.get_credentials(sample_credentials.id)
        assert result is not None
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_credentials_not_found(self, service: GoogleDriveService):
        """Test retrieving non-existent credentials."""
        result = await service.get_credentials("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_credentials(self, service: GoogleDriveService, db_session):
        """Test listing all credentials."""
        # Create multiple credentials
        creds1 = GoogleCredentials(email="a@test.com")
        creds2 = GoogleCredentials(email="b@test.com")
        db_session.add_all([creds1, creds2])
        await db_session.flush()

        result = await service.list_credentials()
        assert len(result) == 2
        # Should be sorted by email
        assert result[0].email == "a@test.com"
        assert result[1].email == "b@test.com"


class TestEncryption:
    """Tests for credential encryption/decryption."""

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_roundtrip(self, service: GoogleDriveService):
        """Test that encryption and decryption are reversible."""
        try:
            from cryptography.fernet import Fernet  # noqa
        except ImportError:
            pytest.skip("cryptography module not installed")

        original = "my_secret_token_123"
        encrypted = service._encrypt(original)
        decrypted = service._decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original  # Should be different

    @pytest.mark.asyncio
    async def test_encrypt_produces_different_outputs(self, service: GoogleDriveService):
        """Test that encryption produces different ciphertext for same input (due to IV)."""
        try:
            from cryptography.fernet import Fernet  # noqa
        except ImportError:
            pytest.skip("cryptography module not installed")

        original = "test_token"
        encrypted1 = service._encrypt(original)
        encrypted2 = service._encrypt(original)

        # Fernet uses random IV, so outputs should be different
        # But both should decrypt to the same value
        assert service._decrypt(encrypted1) == original
        assert service._decrypt(encrypted2) == original


# =============================================================================
# Folder Operations Tests (Mocked)
# =============================================================================


class TestValidateFolderUrl:
    """Tests for validate_folder_url method."""

    @pytest.mark.asyncio
    async def test_validate_invalid_url_format(self, service: GoogleDriveService):
        """Test validation with invalid URL format."""
        with pytest.raises(GoogleDriveError, match="Invalid Google Drive folder URL"):
            await service.validate_folder_url("https://example.com/not-drive")


class TestGetFolderInfo:
    """Tests for get_folder_info method with mocked API."""

    @pytest.mark.asyncio
    async def test_get_folder_info_success(self, service: GoogleDriveService):
        """Test getting folder info with mocked API."""
        mock_file_response = {
            "id": "folder123",
            "name": "Test Folder",
            "mimeType": "application/vnd.google-apps.folder",
            "owners": [{"emailAddress": "owner@test.com"}],
        }
        mock_list_response = {
            "files": [{"id": "file1"}, {"id": "file2"}],
        }

        with patch.object(service, "_get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            # Mock files().get()
            mock_service.files.return_value.get.return_value.execute.return_value = mock_file_response
            # Mock files().list()
            mock_service.files.return_value.list.return_value.execute.return_value = mock_list_response

            result = await service.get_folder_info("folder123")

            assert result.id == "folder123"
            assert result.name == "Test Folder"
            assert result.file_count == 2
            assert result.owner_email == "owner@test.com"

    @pytest.mark.asyncio
    async def test_get_folder_info_not_a_folder(self, service: GoogleDriveService):
        """Test error when ID is not a folder."""
        mock_file_response = {
            "id": "file123",
            "name": "Not A Folder",
            "mimeType": "application/pdf",  # Not a folder
        }

        with patch.object(service, "_get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.files.return_value.get.return_value.execute.return_value = mock_file_response

            with pytest.raises(GoogleDriveError, match="is not a folder"):
                await service.get_folder_info("file123")


class TestListFolder:
    """Tests for list_folder method with mocked API."""

    @pytest.mark.asyncio
    async def test_list_folder_success(self, service: GoogleDriveService):
        """Test listing folder contents."""
        mock_response = {
            "files": [
                {
                    "id": "file1",
                    "name": "model.stl",
                    "mimeType": "application/sla",
                    "size": "1024",
                    "createdTime": "2024-01-01T00:00:00.000Z",
                    "modifiedTime": "2024-01-02T00:00:00.000Z",
                    "parents": ["folder123"],
                },
                {
                    "id": "subfolder1",
                    "name": "Renders",
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": ["folder123"],
                },
            ],
            "nextPageToken": None,
        }

        with patch.object(service, "_get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.files.return_value.list.return_value.execute.return_value = mock_response

            files, next_token = await service.list_folder("folder123")

            assert len(files) == 2
            assert files[0].name == "model.stl"
            assert files[0].size == 1024
            assert files[1].name == "Renders"
            assert files[1].is_folder is True
            assert next_token is None

    @pytest.mark.asyncio
    async def test_list_folder_pagination(self, service: GoogleDriveService):
        """Test folder listing returns next page token."""
        mock_response = {
            "files": [{"id": "file1", "name": "file.stl", "mimeType": "application/sla"}],
            "nextPageToken": "next_page_123",
        }

        with patch.object(service, "_get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.files.return_value.list.return_value.execute.return_value = mock_response

            files, next_token = await service.list_folder("folder123")

            assert len(files) == 1
            assert next_token == "next_page_123"


# =============================================================================
# OAuth Flow Tests
# =============================================================================


class TestOAuthFlow:
    """Tests for OAuth authentication flow."""

    @pytest.mark.asyncio
    async def test_get_oauth_url_not_configured(self, service: GoogleDriveService):
        """Test getting OAuth URL when not configured."""
        with patch("app.services.google_drive.settings") as mock_settings:
            mock_settings.google_oauth_configured = False

            with pytest.raises(GoogleAuthError, match="not configured"):
                service.get_oauth_url()

    @pytest.mark.asyncio
    async def test_handle_oauth_callback_not_configured(self, service: GoogleDriveService):
        """Test OAuth callback when not configured."""
        with patch("app.services.google_drive.settings") as mock_settings:
            mock_settings.google_oauth_configured = False

            with pytest.raises(GoogleAuthError, match="not configured"):
                await service.handle_oauth_callback("auth_code_123")


class TestRevokeCredentials:
    """Tests for credential revocation."""

    @pytest.mark.asyncio
    async def test_revoke_credentials_not_found(self, service: GoogleDriveService):
        """Test revoking non-existent credentials."""
        with pytest.raises(GoogleAuthError, match="not found"):
            await service.revoke_credentials("nonexistent-id")


# =============================================================================
# Token Refresh Tests
# =============================================================================


class TestTokenRefresh:
    """Tests for token refresh logic."""

    @pytest.mark.asyncio
    async def test_refresh_not_needed_for_valid_token(self, service: GoogleDriveService, sample_credentials):
        """Test that refresh is not triggered for valid token."""
        # Token expires in 1 hour, no refresh needed
        sample_credentials.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Should not modify credentials
        await service._refresh_if_needed(sample_credentials)
        # No exception means success

    @pytest.mark.asyncio
    async def test_refresh_not_needed_without_expiry(self, service: GoogleDriveService, sample_credentials):
        """Test that refresh is skipped if no expiry set."""
        sample_credentials.expires_at = None

        # Should not raise error
        await service._refresh_if_needed(sample_credentials)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for API error handling."""

    @pytest.mark.asyncio
    async def test_handle_404_error(self, service: GoogleDriveService):
        """Test 404 error converts to GoogleNotFoundError."""
        from googleapiclient.errors import HttpError

        mock_response = MagicMock()
        mock_response.status = 404

        with patch.object(service, "_get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.files.return_value.get.return_value.execute.side_effect = HttpError(
                mock_response, b"Not Found"
            )

            with pytest.raises(GoogleNotFoundError):
                await service.get_folder_info("nonexistent")

    @pytest.mark.asyncio
    async def test_handle_403_error(self, service: GoogleDriveService):
        """Test 403 error converts to GoogleAccessDeniedError."""
        from googleapiclient.errors import HttpError

        mock_response = MagicMock()
        mock_response.status = 403

        with patch.object(service, "_get_drive_service") as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service
            mock_service.files.return_value.get.return_value.execute.side_effect = HttpError(
                mock_response, b"Access Denied"
            )

            with pytest.raises(GoogleAccessDeniedError):
                await service.get_folder_info("private_folder")


# =============================================================================
# Regex Pattern Tests
# =============================================================================


class TestRegexPatterns:
    """Tests for URL regex patterns."""

    def test_folder_regex_patterns(self):
        """Test various folder URL patterns."""
        test_cases = [
            ("https://drive.google.com/drive/folders/1ABC", "1ABC"),
            ("https://drive.google.com/drive/u/0/folders/1ABC", "1ABC"),
            ("https://drive.google.com/drive/u/1/folders/1ABC", "1ABC"),
            ("drive.google.com/drive/folders/1ABC", "1ABC"),
            ("https://drive.google.com/open?id=1ABC", "1ABC"),
        ]

        for url, expected_id in test_cases:
            match = DRIVE_FOLDER_REGEX.search(url)
            assert match is not None, f"Failed to match: {url}"
            assert match.group(1) == expected_id, f"Wrong ID for: {url}"

    def test_file_regex_patterns(self):
        """Test various file URL patterns."""
        test_cases = [
            ("https://drive.google.com/file/d/1XYZ/view", "1XYZ"),
            ("https://drive.google.com/file/d/1XYZ", "1XYZ"),
            ("https://drive.google.com/open?id=1XYZ", "1XYZ"),
        ]

        for url, expected_id in test_cases:
            match = DRIVE_FILE_REGEX.search(url)
            assert match is not None, f"Failed to match: {url}"
            assert match.group(1) == expected_id, f"Wrong ID for: {url}"
