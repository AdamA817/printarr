"""Server-Sent Events (SSE) endpoint for real-time updates (#217).

Provides a streaming endpoint for clients to receive real-time updates
about job progress, design changes, and queue status.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger
from app.services.events import Event, EventType, get_event_broadcaster

logger = get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/")
async def sse_events():
    """Subscribe to Server-Sent Events stream.

    Returns a streaming response that sends events as they occur.
    The connection stays open until the client disconnects.

    Events are JSON-formatted with the following structure:
    ```json
    {
        "type": "job_progress",
        "payload": {
            "job_id": "uuid",
            "progress": 45,
            "progress_message": "Downloading file 2/5..."
        },
        "timestamp": "2024-01-05T12:00:00Z"
    }
    ```

    Event types:
    - job_created: New job added to queue
    - job_started: Job started processing
    - job_progress: Job progress update
    - job_completed: Job finished successfully
    - job_failed: Job failed (may retry)
    - job_canceled: Job was canceled
    - design_status_changed: Design status changed
    - design_created: New design discovered
    - queue_updated: Queue was reordered
    - heartbeat: Keep-alive ping (every 30s)
    - sync_status: Channel sync status update
    """
    broadcaster = get_event_broadcaster()

    async def event_generator():
        """Generate SSE events from the broadcaster queue."""
        async with broadcaster.subscribe() as queue:
            # Send initial connection event
            yield Event(
                type=EventType.HEARTBEAT,
                payload={"message": "connected", "client_count": broadcaster.client_count},
            ).to_sse()

            # Set up heartbeat task
            heartbeat_interval = 30  # seconds

            while True:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=heartbeat_interval,
                    )
                    yield event.to_sse()

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield Event(
                        type=EventType.HEARTBEAT,
                        payload={"message": "ping"},
                    ).to_sse()

                except asyncio.CancelledError:
                    # Client disconnected
                    logger.info("sse_client_cancelled")
                    break

                except Exception as e:
                    logger.error("sse_event_error", error=str(e))
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/status")
async def get_events_status():
    """Get status of the event broadcaster.

    Returns the number of connected clients and broadcaster status.
    """
    broadcaster = get_event_broadcaster()
    return {
        "connected_clients": broadcaster.client_count,
        "status": "active",
    }
