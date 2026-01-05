"""Event broadcast service for real-time updates (#217).

Provides Server-Sent Events (SSE) support for pushing updates to clients.
Events are broadcast for:
- Job status changes (QUEUED -> RUNNING -> SUCCESS/FAILED)
- Job progress updates
- Design status changes
- Queue changes
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator

from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Types of events that can be broadcast."""

    # Job events
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELED = "job_canceled"

    # Design events
    DESIGN_STATUS_CHANGED = "design_status_changed"
    DESIGN_CREATED = "design_created"
    DESIGN_UPDATED = "design_updated"
    DESIGN_DELETED = "design_deleted"

    # Queue events
    QUEUE_UPDATED = "queue_updated"

    # System events
    HEARTBEAT = "heartbeat"
    SYNC_STATUS = "sync_status"


class Event(BaseModel):
    """Event payload for SSE."""

    type: EventType
    payload: dict[str, Any]
    timestamp: datetime = None

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)

    def to_sse(self) -> str:
        """Format event for SSE transmission."""
        data = {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }
        return f"data: {json.dumps(data)}\n\n"


class EventBroadcaster:
    """Manages SSE connections and broadcasts events.

    This is a singleton that maintains a list of connected clients
    and broadcasts events to all of them.
    """

    _instance: "EventBroadcaster | None" = None

    def __new__(cls) -> "EventBroadcaster":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._clients: list[asyncio.Queue[Event]] = []
        self._lock = asyncio.Lock()
        logger.info("event_broadcaster_initialized")

    @asynccontextmanager
    async def subscribe(self) -> AsyncGenerator[asyncio.Queue[Event], None]:
        """Subscribe to events.

        Returns an async queue that will receive events.
        The subscription is automatically cleaned up when the context exits.

        Usage:
            async with broadcaster.subscribe() as queue:
                while True:
                    event = await queue.get()
                    yield event.to_sse()
        """
        queue: asyncio.Queue[Event] = asyncio.Queue()
        async with self._lock:
            self._clients.append(queue)
            client_count = len(self._clients)

        logger.info("sse_client_connected", client_count=client_count)

        try:
            yield queue
        finally:
            async with self._lock:
                self._clients.remove(queue)
                client_count = len(self._clients)
            logger.info("sse_client_disconnected", client_count=client_count)

    async def broadcast(self, event: Event) -> None:
        """Broadcast an event to all connected clients.

        Args:
            event: The event to broadcast.
        """
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        # Put event in all client queues
        for queue in clients:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Client queue is full, skip
                logger.warning("sse_client_queue_full")

        logger.debug(
            "event_broadcast",
            event_type=event.type.value,
            client_count=len(clients),
        )

    async def broadcast_job_created(
        self,
        job_id: str,
        job_type: str,
        design_id: str | None = None,
        display_name: str | None = None,
        priority: int = 0,
    ) -> None:
        """Broadcast job created event."""
        await self.broadcast(Event(
            type=EventType.JOB_CREATED,
            payload={
                "job_id": job_id,
                "job_type": job_type,
                "design_id": design_id,
                "display_name": display_name,
                "priority": priority,
            },
        ))

    async def broadcast_job_started(
        self,
        job_id: str,
        job_type: str,
        design_id: str | None = None,
    ) -> None:
        """Broadcast job started event."""
        await self.broadcast(Event(
            type=EventType.JOB_STARTED,
            payload={
                "job_id": job_id,
                "job_type": job_type,
                "design_id": design_id,
            },
        ))

    async def broadcast_job_progress(
        self,
        job_id: str,
        progress: int | None,
        progress_message: str | None = None,
        current_file: str | None = None,
        current_file_bytes: int | None = None,
        current_file_total: int | None = None,
    ) -> None:
        """Broadcast job progress event."""
        await self.broadcast(Event(
            type=EventType.JOB_PROGRESS,
            payload={
                "job_id": job_id,
                "progress": progress,
                "progress_message": progress_message,
                "current_file": current_file,
                "current_file_bytes": current_file_bytes,
                "current_file_total": current_file_total,
            },
        ))

    async def broadcast_job_completed(
        self,
        job_id: str,
        job_type: str,
        design_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast job completed event."""
        await self.broadcast(Event(
            type=EventType.JOB_COMPLETED,
            payload={
                "job_id": job_id,
                "job_type": job_type,
                "design_id": design_id,
                "result": result,
            },
        ))

    async def broadcast_job_failed(
        self,
        job_id: str,
        job_type: str,
        design_id: str | None = None,
        error: str | None = None,
        will_retry: bool = False,
    ) -> None:
        """Broadcast job failed event."""
        await self.broadcast(Event(
            type=EventType.JOB_FAILED,
            payload={
                "job_id": job_id,
                "job_type": job_type,
                "design_id": design_id,
                "error": error,
                "will_retry": will_retry,
            },
        ))

    async def broadcast_job_canceled(
        self,
        job_id: str,
        job_type: str,
        design_id: str | None = None,
    ) -> None:
        """Broadcast job canceled event."""
        await self.broadcast(Event(
            type=EventType.JOB_CANCELED,
            payload={
                "job_id": job_id,
                "job_type": job_type,
                "design_id": design_id,
            },
        ))

    async def broadcast_design_status_changed(
        self,
        design_id: str,
        old_status: str | None,
        new_status: str,
        title: str | None = None,
    ) -> None:
        """Broadcast design status change event."""
        await self.broadcast(Event(
            type=EventType.DESIGN_STATUS_CHANGED,
            payload={
                "design_id": design_id,
                "old_status": old_status,
                "new_status": new_status,
                "title": title,
            },
        ))

    async def broadcast_design_created(
        self,
        design_id: str,
        title: str,
        designer: str | None = None,
    ) -> None:
        """Broadcast design created event."""
        await self.broadcast(Event(
            type=EventType.DESIGN_CREATED,
            payload={
                "design_id": design_id,
                "title": title,
                "designer": designer,
            },
        ))

    async def broadcast_queue_updated(self) -> None:
        """Broadcast queue updated event (for re-ordering, etc.)."""
        await self.broadcast(Event(
            type=EventType.QUEUE_UPDATED,
            payload={},
        ))

    async def broadcast_sync_status(
        self,
        channel_id: str | None = None,
        channel_title: str | None = None,
        status: str = "syncing",
        new_designs: int = 0,
    ) -> None:
        """Broadcast sync status update."""
        await self.broadcast(Event(
            type=EventType.SYNC_STATUS,
            payload={
                "channel_id": channel_id,
                "channel_title": channel_title,
                "status": status,
                "new_designs": new_designs,
            },
        ))

    @property
    def client_count(self) -> int:
        """Get the number of connected clients."""
        return len(self._clients)


# Global singleton instance
event_broadcaster = EventBroadcaster()


def get_event_broadcaster() -> EventBroadcaster:
    """Get the global event broadcaster instance."""
    return event_broadcaster
