"""API router that aggregates all routes."""

from fastapi import APIRouter

from app.api.routes import activity, ai, channels, designs, discovered_channels, events, families, google, health, import_profiles, import_sources, previews, queue, settings, stats, system, tags, telegram, thangs, upload

api_router = APIRouter(prefix="/api")

# Include route modules
api_router.include_router(health.router)

# V1 API routes
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(activity.router)
v1_router.include_router(ai.router)
v1_router.include_router(channels.router)
v1_router.include_router(designs.router)
v1_router.include_router(discovered_channels.router)
v1_router.include_router(events.router)
v1_router.include_router(families.router)
v1_router.include_router(google.router)
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
v1_router.include_router(upload.router)

api_router.include_router(v1_router)
