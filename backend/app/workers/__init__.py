"""Background workers for Printarr."""

from app.workers.base import BaseWorker, NonRetryableError, RetryableError, calculate_retry_delay
from app.workers.download import DownloadWorker
from app.workers.extract import ExtractArchiveWorker
from app.workers.manager import (
    WorkerManager,
    get_worker_manager,
    start_workers,
    stop_workers,
)

__all__ = [
    # Base classes
    "BaseWorker",
    "calculate_retry_delay",
    "RetryableError",
    "NonRetryableError",
    # Workers
    "DownloadWorker",
    "ExtractArchiveWorker",
    # Manager
    "WorkerManager",
    "get_worker_manager",
    "start_workers",
    "stop_workers",
]
