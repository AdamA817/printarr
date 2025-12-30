"""API router that aggregates all routes."""

from fastapi import APIRouter

from app.api.routes import activity, channels, designs, health, queue, stats, telegram, thangs

api_router = APIRouter(prefix="/api")

# Include route modules
api_router.include_router(health.router)

# V1 API routes
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(activity.router)
v1_router.include_router(channels.router)
v1_router.include_router(designs.router)
v1_router.include_router(queue.router)
v1_router.include_router(stats.router)
v1_router.include_router(telegram.router)
v1_router.include_router(thangs.router)

api_router.include_router(v1_router)
