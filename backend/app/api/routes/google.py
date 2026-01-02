"""Google OAuth API endpoints for v0.8 Manual Imports."""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db import get_db
from app.services.google_drive import GoogleAuthError, GoogleDriveService

logger = get_logger(__name__)

router = APIRouter(prefix="/google", tags=["google"])


# =============================================================================
# Schemas
# =============================================================================


class GoogleOAuthStatus(BaseModel):
    """OAuth status response."""

    configured: bool
    authenticated: bool
    email: str | None = None
    expires_at: datetime | None = None


class GoogleOAuthInitResponse(BaseModel):
    """OAuth authorization URL response."""

    auth_url: str
    state: str


class GoogleOAuthCallbackParams(BaseModel):
    """OAuth callback parameters."""

    code: str
    state: str | None = None


class GoogleOAuthCallbackResponse(BaseModel):
    """OAuth callback result."""

    success: bool
    email: str | None = None
    credentials_id: str | None = None


class GoogleCredentialsResponse(BaseModel):
    """Google credentials response."""

    id: str
    email: str
    expires_at: datetime | None = None
    created_at: datetime | None = None


class GoogleCredentialsList(BaseModel):
    """List of Google credentials."""

    items: list[GoogleCredentialsResponse]
    total: int


# =============================================================================
# OAuth Flow Endpoints
# =============================================================================


@router.get("/oauth/status", response_model=GoogleOAuthStatus)
async def get_oauth_status(
    db: AsyncSession = Depends(get_db),
) -> GoogleOAuthStatus:
    """Get Google OAuth configuration and authentication status.

    Returns whether OAuth is configured and if there are valid credentials.
    """
    service = GoogleDriveService(db)

    # Check if OAuth is configured
    if not settings.google_oauth_configured:
        return GoogleOAuthStatus(
            configured=False,
            authenticated=False,
        )

    # Check for existing credentials
    credentials_list = await service.list_credentials()

    if not credentials_list:
        return GoogleOAuthStatus(
            configured=True,
            authenticated=False,
        )

    # Return info about the first (primary) credential
    cred = credentials_list[0]
    return GoogleOAuthStatus(
        configured=True,
        authenticated=True,
        email=cred.email,
        expires_at=cred.expires_at,
    )


@router.post("/oauth/authorize", response_model=GoogleOAuthInitResponse)
async def initiate_oauth(
    db: AsyncSession = Depends(get_db),
) -> GoogleOAuthInitResponse:
    """Start the OAuth authorization flow.

    Returns a URL to redirect the user to for Google authentication.
    """
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth is not configured. Set PRINTARR_GOOGLE_CLIENT_ID and PRINTARR_GOOGLE_CLIENT_SECRET.",
        )

    service = GoogleDriveService(db)

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    try:
        auth_url = service.get_oauth_url(state=state)
        logger.info("oauth_initiated", state=state[:8])
        return GoogleOAuthInitResponse(auth_url=auth_url, state=state)
    except GoogleAuthError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/oauth/callback", response_model=GoogleOAuthCallbackResponse)
async def handle_oauth_callback(
    params: GoogleOAuthCallbackParams,
    db: AsyncSession = Depends(get_db),
) -> GoogleOAuthCallbackResponse:
    """Handle the OAuth callback from Google.

    Exchanges the authorization code for tokens and stores credentials.
    """
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth is not configured.",
        )

    service = GoogleDriveService(db)

    try:
        credentials = await service.handle_oauth_callback(params.code)
        await db.commit()

        logger.info(
            "oauth_callback_success",
            email=credentials.email,
            credentials_id=credentials.id,
        )

        return GoogleOAuthCallbackResponse(
            success=True,
            email=credentials.email,
            credentials_id=credentials.id,
        )

    except GoogleAuthError as e:
        logger.error("oauth_callback_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Credentials Management Endpoints
# =============================================================================


@router.get("/credentials/", response_model=GoogleCredentialsList)
async def list_credentials(
    db: AsyncSession = Depends(get_db),
) -> GoogleCredentialsList:
    """List all stored Google credentials."""
    service = GoogleDriveService(db)
    credentials_list = await service.list_credentials()

    items = [
        GoogleCredentialsResponse(
            id=c.id,
            email=c.email,
            expires_at=c.expires_at,
            created_at=c.created_at,
        )
        for c in credentials_list
    ]

    return GoogleCredentialsList(items=items, total=len(items))


@router.get("/credentials/{credentials_id}", response_model=GoogleCredentialsResponse)
async def get_credentials(
    credentials_id: str,
    db: AsyncSession = Depends(get_db),
) -> GoogleCredentialsResponse:
    """Get specific Google credentials by ID."""
    service = GoogleDriveService(db)
    credentials = await service.get_credentials(credentials_id)

    if not credentials:
        raise HTTPException(status_code=404, detail="Credentials not found")

    return GoogleCredentialsResponse(
        id=credentials.id,
        email=credentials.email,
        expires_at=credentials.expires_at,
        created_at=credentials.created_at,
    )


@router.delete("/credentials/{credentials_id}", status_code=204)
async def revoke_credentials(
    credentials_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke and delete Google credentials.

    This will revoke the OAuth tokens with Google and remove them from storage.
    """
    service = GoogleDriveService(db)

    try:
        await service.revoke_credentials(credentials_id)
        await db.commit()
        logger.info("credentials_revoked", credentials_id=credentials_id)
    except GoogleAuthError as e:
        raise HTTPException(status_code=404, detail=str(e))
