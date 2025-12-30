"""Telegram authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.telegram import (
    AuthLogoutResponse,
    AuthStartRequest,
    AuthStartResponse,
    AuthStatusResponse,
    AuthVerifyRequest,
    AuthVerifyResponse,
    ChannelInfo,
    ChannelResolveRequest,
    ChannelResolveResponse,
    Message,
    MessageAttachment,
    MessagesResponse,
    MessageSender,
    TelegramErrorResponse,
    TelegramUser,
)
from app.telegram import (
    TelegramAccessDeniedError,
    TelegramChannelNotFoundError,
    TelegramCodeExpiredError,
    TelegramCodeInvalidError,
    TelegramError,
    TelegramInvalidLinkError,
    TelegramNotAuthenticatedError,
    TelegramNotConfiguredError,
    TelegramNotConnectedError,
    TelegramPasswordInvalidError,
    TelegramPasswordRequiredError,
    TelegramPhoneInvalidError,
    TelegramRateLimitError,
    TelegramService,
    get_telegram_service,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])
auth_router = APIRouter(prefix="/auth", tags=["telegram-auth"])


def telegram_error_response(exc: TelegramError) -> JSONResponse:
    """Create a JSON error response from a TelegramError."""
    content = TelegramErrorResponse(
        error=exc.code,
        message=exc.message,
        retry_after=getattr(exc, "retry_after", None),
    )

    # Determine appropriate status code
    status_code = 400
    if isinstance(exc, TelegramNotConfiguredError):
        status_code = 503  # Service Unavailable
    elif isinstance(exc, TelegramNotConnectedError):
        status_code = 503
    elif isinstance(exc, TelegramNotAuthenticatedError):
        status_code = 401  # Unauthorized
    elif isinstance(exc, TelegramRateLimitError):
        status_code = 429  # Too Many Requests
    elif isinstance(exc, TelegramAccessDeniedError):
        status_code = 403  # Forbidden
    elif isinstance(exc, TelegramChannelNotFoundError):
        status_code = 404  # Not Found

    return JSONResponse(status_code=status_code, content=content.model_dump())


@auth_router.get(
    "/status",
    response_model=AuthStatusResponse,
    responses={503: {"model": TelegramErrorResponse}},
)
async def get_auth_status(
    telegram: TelegramService = Depends(get_telegram_service),
) -> AuthStatusResponse:
    """Get current Telegram authentication status.

    Returns whether the Telegram session is authenticated and user info if available.
    """
    configured = settings.telegram_configured
    connected = telegram.is_connected()
    authenticated = False
    user_info = None

    if connected:
        try:
            authenticated = await telegram.is_authenticated()
            if authenticated:
                user = await telegram.get_current_user()
                if user:
                    user_info = TelegramUser(
                        id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        phone=user.phone,
                    )
        except Exception as e:
            logger.warning("auth_status_error", error=str(e))

    return AuthStatusResponse(
        authenticated=authenticated,
        configured=configured,
        connected=connected,
        user=user_info,
    )


@auth_router.post(
    "/start",
    response_model=AuthStartResponse,
    responses={
        400: {"model": TelegramErrorResponse},
        429: {"model": TelegramErrorResponse},
        503: {"model": TelegramErrorResponse},
    },
)
async def start_auth(
    request: AuthStartRequest,
    telegram: TelegramService = Depends(get_telegram_service),
) -> AuthStartResponse:
    """Start Telegram authentication by sending a verification code.

    This sends a verification code to the provided phone number via SMS or Telegram.
    Use the returned phone_code_hash in the verify endpoint.
    """
    # Ensure connected
    if not telegram.is_connected():
        if not settings.telegram_configured:
            raise HTTPException(
                status_code=503,
                detail="Telegram API credentials not configured",
            )
        try:
            await telegram.connect()
        except TelegramError as e:
            return telegram_error_response(e)

    try:
        result = await telegram.start_auth(request.phone)
        return AuthStartResponse(
            status=result["status"],
            phone_code_hash=result["phone_code_hash"],
        )
    except TelegramPhoneInvalidError as e:
        return telegram_error_response(e)
    except TelegramRateLimitError as e:
        return telegram_error_response(e)
    except TelegramError as e:
        return telegram_error_response(e)


@auth_router.post(
    "/verify",
    response_model=AuthVerifyResponse,
    responses={
        400: {"model": TelegramErrorResponse},
        429: {"model": TelegramErrorResponse},
        503: {"model": TelegramErrorResponse},
    },
)
async def verify_auth(
    request: AuthVerifyRequest,
    telegram: TelegramService = Depends(get_telegram_service),
) -> AuthVerifyResponse:
    """Verify the authentication code.

    If 2FA is enabled, you'll receive a '2fa_required' status.
    In that case, call this endpoint again with the password field set.
    """
    if not telegram.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Telegram client is not connected",
        )

    try:
        result = await telegram.complete_auth(
            phone=request.phone,
            code=request.code,
            phone_code_hash=request.phone_code_hash,
            password=request.password,
        )
        return AuthVerifyResponse(status=result["status"])

    except TelegramPasswordRequiredError:
        # Return 2fa_required status instead of error
        return AuthVerifyResponse(status="2fa_required")

    except TelegramCodeInvalidError as e:
        return telegram_error_response(e)
    except TelegramCodeExpiredError as e:
        return telegram_error_response(e)
    except TelegramPasswordInvalidError as e:
        return telegram_error_response(e)
    except TelegramRateLimitError as e:
        return telegram_error_response(e)
    except TelegramError as e:
        return telegram_error_response(e)


@auth_router.post(
    "/logout",
    response_model=AuthLogoutResponse,
    responses={503: {"model": TelegramErrorResponse}},
)
async def logout(
    telegram: TelegramService = Depends(get_telegram_service),
) -> AuthLogoutResponse:
    """Log out of Telegram and clear the session.

    This will disconnect from Telegram and remove the stored session.
    You will need to re-authenticate to use Telegram features.
    """
    try:
        await telegram.logout()
        return AuthLogoutResponse(status="logged_out")
    except TelegramError as e:
        return telegram_error_response(e)


# === Channel Routes ===

channels_router = APIRouter(prefix="/channels", tags=["telegram-channels"])


@channels_router.post(
    "/resolve",
    response_model=ChannelResolveResponse,
    responses={
        400: {"model": TelegramErrorResponse},
        401: {"model": TelegramErrorResponse},
        403: {"model": TelegramErrorResponse},
        404: {"model": TelegramErrorResponse},
        429: {"model": TelegramErrorResponse},
        503: {"model": TelegramErrorResponse},
    },
)
async def resolve_channel(
    request: ChannelResolveRequest,
    telegram: TelegramService = Depends(get_telegram_service),
) -> ChannelResolveResponse:
    """Resolve a Telegram channel link to channel information.

    Supports various link formats:
    - https://t.me/channelname
    - t.me/channelname
    - @channelname
    - https://t.me/+abcdef (private invite links)
    - https://t.me/joinchat/abcdef (old invite format)

    Returns channel metadata that can be used to add the channel to Printarr.
    """
    if not telegram.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Telegram client is not connected",
        )

    try:
        result = await telegram.resolve_channel(request.link)
        return ChannelResolveResponse(
            id=result.get("id"),
            title=result["title"],
            username=result.get("username"),
            type=result["type"],
            members_count=result.get("members_count"),
            photo_url=result.get("photo_url"),
            is_invite=result.get("is_invite", False),
            invite_hash=result.get("invite_hash"),
        )

    except TelegramInvalidLinkError as e:
        return telegram_error_response(e)
    except TelegramChannelNotFoundError as e:
        return telegram_error_response(e)
    except TelegramAccessDeniedError as e:
        return telegram_error_response(e)
    except TelegramNotAuthenticatedError as e:
        return telegram_error_response(e)
    except TelegramRateLimitError as e:
        return telegram_error_response(e)
    except TelegramError as e:
        return telegram_error_response(e)


@channels_router.get(
    "/{channel_id}/messages/",
    response_model=MessagesResponse,
    responses={
        401: {"model": TelegramErrorResponse},
        403: {"model": TelegramErrorResponse},
        404: {"model": TelegramErrorResponse},
        429: {"model": TelegramErrorResponse},
        503: {"model": TelegramErrorResponse},
    },
)
async def get_channel_messages(
    channel_id: int,
    limit: int = Query(default=10, ge=1, le=100, description="Number of messages to fetch"),
    telegram: TelegramService = Depends(get_telegram_service),
) -> MessagesResponse:
    """Fetch recent messages from a Telegram channel.

    Returns the most recent messages from the specified channel.
    The channel must be one that the authenticated user has access to.
    """
    if not telegram.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Telegram client is not connected",
        )

    try:
        result = await telegram.get_messages(channel_id, limit=limit)
        return MessagesResponse(
            messages=[
                Message(
                    id=msg["id"],
                    date=msg.get("date"),
                    text=msg.get("text", ""),
                    sender=MessageSender(**msg["sender"]) if msg.get("sender") else None,
                    attachments=[
                        MessageAttachment(**att) for att in msg.get("attachments", [])
                    ],
                    has_media=msg.get("has_media", False),
                    forward_from=msg.get("forward_from"),
                )
                for msg in result["messages"]
            ],
            channel=ChannelInfo(
                id=result["channel"]["id"],
                title=result["channel"]["title"],
            ),
        )

    except TelegramChannelNotFoundError as e:
        return telegram_error_response(e)
    except TelegramAccessDeniedError as e:
        return telegram_error_response(e)
    except TelegramNotAuthenticatedError as e:
        return telegram_error_response(e)
    except TelegramRateLimitError as e:
        return telegram_error_response(e)
    except TelegramError as e:
        return telegram_error_response(e)


# Include sub-routers in main telegram router
router.include_router(auth_router)
router.include_router(channels_router)
