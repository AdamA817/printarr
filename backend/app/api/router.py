"""API router that aggregates all routes."""

from fastapi import APIRouter

from app.api.routes import activity, channels, designs, discovered_channels, health, import_profiles, import_sources, previews, queue, settings, stats, system, tags, telegram, thangs

api_router = APIRouter(prefix="/api")

# Include route modules
api_router.include_router(health.router)

# V1 API routes
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(activity.router)
v1_router.include_router(channels.router)
v1_router.include_router(designs.router)
v1_router.include_router(discovered_channels.router)
v1_router.include_router(import_profiles.router)
v1_router.include_router(import_sources.router)
v1_router.include_router(previews.router)
v1_router.include_router(queue.router)
v1_router.include_router(settings.router)
v1_router.include_router(stats.router)
v1_router.include_router(system.router)
v1_router.include_router(tags.router)
v1_router.include_router(telegram.router)
v1_router.include_router(thangs.router)

api_router.include_router(v1_router)
