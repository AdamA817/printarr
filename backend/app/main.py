"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Frontend static files directory
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    logger.info(
        "starting_application",
        app_name=settings.app_name,
        version=settings.version,
        host=settings.host,
        port=settings.port,
    )
    yield
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
