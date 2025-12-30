"""API router that aggregates all routes."""

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter(prefix="/api")

# Include route modules
api_router.include_router(health.router)
