"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.telegram import TelegramService

# Frontend static files directory
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    import asyncio
    from app.services.sync import SyncService
    from app.workers.manager import start_workers, stop_workers

    logger.info(
        "starting_application",
        app_name=settings.app_name,
        version=settings.version,
        host=settings.host,
        port=settings.port,
    )

    # Ensure preview directories exist
    from app.services.preview import PreviewService
    preview_service = PreviewService()
    await preview_service.ensure_directories()
    logger.info("preview_directories_initialized")

    # Seed predefined tags and recover orphaned jobs
    from app.db.session import async_session_maker
    from app.services.job_queue import JobQueueService
    from app.services.tag import TagService

    # Recover orphaned jobs from previous container restart (#163)
    async with async_session_maker() as db:
        job_service = JobQueueService(db)
        recovered = await job_service.recover_orphaned_jobs()
        await db.commit()
        if recovered > 0:
            logger.info("orphaned_jobs_recovered", count=recovered)
    async with async_session_maker() as db:
        tag_service = TagService(db)
        tags_created = await tag_service.seed_predefined_tags()
        await db.commit()
        if tags_created > 0:
            logger.info("predefined_tags_seeded", count=tags_created)

    # Initialize Telegram service if configured
    telegram_service = TelegramService.get_instance()
    telegram_authenticated = False
    if settings.telegram_configured:
        try:
            result = await telegram_service.connect()
            telegram_authenticated = result.get("authenticated", False)
            logger.info(
                "telegram_startup_complete",
                authenticated=telegram_authenticated,
            )
        except Exception as e:
            # Log but don't fail startup - Telegram can be connected later
            logger.warning("telegram_startup_failed", error=str(e))
    else:
        logger.info("telegram_not_configured")

    # Start background workers (download, extract, import)
    worker_task = asyncio.create_task(start_workers())
    logger.info("background_workers_starting")

    # Start sync service for live monitoring (v0.6)
    sync_service = SyncService.get_instance()
    sync_task = None
    if settings.sync_enabled and telegram_authenticated:
        sync_task = asyncio.create_task(sync_service.start())
        # Add exception callback to catch silent failures
        def sync_task_exception_handler(task: asyncio.Task) -> None:
            if task.cancelled():
                return
            exc = task.exception()
            if exc:
                logger.error(
                    "sync_service_crashed",
                    error=str(exc),
                    exc_info=exc,
                )
        sync_task.add_done_callback(sync_task_exception_handler)
        logger.info("sync_service_starting")
    elif not settings.sync_enabled:
        logger.info("sync_service_disabled_by_config")
    else:
        logger.info("sync_service_skipped_not_authenticated")

    # Start cleanup service for data consistency (#237)
    from app.services.cleanup import get_cleanup_service
    cleanup_service = get_cleanup_service()
    await cleanup_service.start()

    yield

    # Stop sync service
    if sync_task:
        logger.info("stopping_sync_service")
        await sync_service.stop()
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

    # Stop background workers
    logger.info("stopping_background_workers")
    await stop_workers()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    # Stop cleanup service
    logger.info("stopping_cleanup_service")
    await cleanup_service.stop()

    # Disconnect Telegram on shutdown
    if telegram_service.is_connected():
        await telegram_service.disconnect()

    logger.info("shutting_down_application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Self-hosted web application for monitoring Telegram channels for 3D-printable designs",
        version=settings.version,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)

    # Mount frontend static files if directory exists
    if FRONTEND_DIR.exists():
        # Mount assets directory for JS, CSS, etc.
        assets_dir = FRONTEND_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve index.html for root
        @app.get("/")
        async def serve_root() -> FileResponse:
            """Serve the frontend application."""
            return FileResponse(FRONTEND_DIR / "index.html")

        # Serve other static files (favicon, etc.)
        @app.get("/{filename:path}")
        async def serve_static(filename: str) -> FileResponse:
            """Serve static files or index.html for SPA routes."""
            # Don't intercept API routes
            if filename.startswith("api/"):
                # This shouldn't happen as API routes should match first,
                # but return 404 if it does
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not found")

            # Check if it's a static file that exists
            file_path = FRONTEND_DIR / filename
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html for client-side routing
            return FileResponse(FRONTEND_DIR / "index.html")

    return app


# Create the application instance
app = create_app()


def main() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
