"""Bulk folder import service for v0.8 Manual Imports.

Provides:
- Local folder scanning with import profiles
- File system monitoring (watchdog + polling fallback)
- Design detection and import tracking
- Duplicate detection via file hash and path

See DEC-036 for design detection algorithm.
See DEC-037 for conflict handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    ConflictResolution,
    Design,
    DesignStatus,
    ImportRecord,
    ImportRecordStatus,
    ImportSource,
    ImportSourceStatus,
    ImportSourceType,
    MetadataAuthority,
)
from app.schemas.import_profile import DesignDetectionResult, ImportProfileConfig
from app.services.auto_render import auto_queue_render_for_design
from app.services.import_profile import ImportProfileService

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Hash chunk size for file hashing
HASH_CHUNK_SIZE = 64 * 1024  # 64KB


class BulkImportError(Exception):
    """Base exception for bulk import errors."""

    pass


class BulkImportSourceNotFoundError(BulkImportError):
    """Raised when an import source is not found."""

    pass


class BulkImportPathError(BulkImportError):
    """Raised when a path is invalid or inaccessible."""

    pass


class DetectedDesign:
    """Represents a design detected during folder scanning."""

    def __init__(
        self,
        path: Path,
        detection: DesignDetectionResult,
        relative_path: str,
    ):
        self.path = path
        self.detection = detection
        self.relative_path = relative_path
        self.file_hash: str | None = None
        self.total_size: int = 0
        self.mtime: datetime | None = None

    @property
    def title(self) -> str:
        """Get the detected title."""
        return self.detection.title or self.path.name

    @property
    def model_count(self) -> int:
        """Get the number of model files."""
        return len(self.detection.model_files)

    @property
    def preview_count(self) -> int:
        """Get the number of preview files."""
        return len(self.detection.preview_files)


class FolderEventHandler(FileSystemEventHandler):
    """Watchdog event handler for folder monitoring."""

    def __init__(self, callback: Callable[[str, Path], None]):
        super().__init__()
        self.callback = callback

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file/folder creation events."""
        if not event.is_directory:
            self.callback("created", Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self.callback("modified", Path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if not event.is_directory:
            self.callback("deleted", Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if hasattr(event, "dest_path"):
            self.callback("moved", Path(event.dest_path))


class BulkImportService:
    """Service for bulk folder import and monitoring.

    Provides folder scanning, file system monitoring, and design import
    for local directory sources.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the bulk import service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db
        self._profile_service = ImportProfileService(db)
        self._observers: dict[str, Observer] = {}  # source_id -> Observer
        self._pending_events: dict[str, list[tuple[str, Path]]] = {}  # source_id -> events

    # ========== Folder Scanning ==========

    async def scan_folder(
        self,
        source: ImportSource,
        config: ImportProfileConfig | None = None,
    ) -> list[DetectedDesign]:
        """Scan a folder and detect designs.

        Args:
            source: The import source with folder path.
            config: Optional import profile config. Uses source profile if not provided.

        Returns:
            List of DetectedDesign objects.

        Raises:
            BulkImportPathError: If path is invalid or inaccessible.
        """
        if source.source_type != ImportSourceType.BULK_FOLDER:
            raise BulkImportError(f"Source {source.id} is not a bulk folder source")

        if not source.folder_path:
            raise BulkImportPathError("Source has no folder path configured")

        folder_path = Path(source.folder_path)
        if not folder_path.exists():
            raise BulkImportPathError(f"Folder does not exist: {folder_path}")
        if not folder_path.is_dir():
            raise BulkImportPathError(f"Path is not a directory: {folder_path}")

        # Get import profile config
        if config is None:
            config = await self._profile_service.get_profile_config(
                source.import_profile_id
            )

        # Traverse and detect designs
        detected = self._profile_service.traverse_for_designs(folder_path, config)

        # Convert to DetectedDesign objects
        designs = []
        for path, detection in detected:
            relative_path = str(path.relative_to(folder_path))
            detected_design = DetectedDesign(path, detection, relative_path)

            # Calculate additional metadata
            detected_design.total_size = self._calculate_folder_size(path)
            detected_design.mtime = self._get_folder_mtime(path)
            detected_design.file_hash = self._calculate_folder_hash(path)

            designs.append(detected_design)

        logger.info(
            "folder_scanned",
            source_id=source.id,
            folder_path=str(folder_path),
            designs_found=len(designs),
        )

        return designs

    async def scan_folder_path(
        self,
        folder_path_str: str,
        profile_id: str | None = None,
    ) -> list[DetectedDesign]:
        """Scan a folder path directly (DEC-038 multi-folder support).

        Args:
            folder_path_str: The folder path to scan.
            profile_id: Optional import profile ID.

        Returns:
            List of DetectedDesign objects.

        Raises:
            BulkImportPathError: If path is invalid or inaccessible.
        """
        folder_path = Path(folder_path_str)
        if not folder_path.exists():
            raise BulkImportPathError(f"Folder does not exist: {folder_path}")
        if not folder_path.is_dir():
            raise BulkImportPathError(f"Path is not a directory: {folder_path}")

        # Get import profile config
        config = await self._profile_service.get_profile_config(profile_id)

        # Traverse and detect designs
        detected = self._profile_service.traverse_for_designs(folder_path, config)

        # Convert to DetectedDesign objects
        designs = []
        for path, detection in detected:
            relative_path = str(path.relative_to(folder_path))
            detected_design = DetectedDesign(path, detection, relative_path)

            # Calculate additional metadata
            detected_design.total_size = self._calculate_folder_size(path)
            detected_design.mtime = self._get_folder_mtime(path)
            detected_design.file_hash = self._calculate_folder_hash(path)

            designs.append(detected_design)

        logger.info(
            "folder_path_scanned",
            folder_path=str(folder_path),
            designs_found=len(designs),
        )

        return designs

    def _calculate_folder_size(self, folder_path: Path) -> int:
        """Calculate total size of files in a folder."""
        total = 0
        try:
            for f in folder_path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except (PermissionError, OSError):
            pass
        return total

    def _get_folder_mtime(self, folder_path: Path) -> datetime | None:
        """Get the most recent modification time in a folder."""
        latest = None
        try:
            for f in folder_path.rglob("*"):
                if f.is_file():
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if latest is None or mtime > latest:
                        latest = mtime
        except (PermissionError, OSError):
            pass
        return latest

    def _calculate_folder_hash(self, folder_path: Path) -> str:
        """Calculate a hash representing the folder contents.

        Uses a combination of file paths and sizes for quick comparison.
        """
        hasher = hashlib.sha256()
        try:
            files = sorted(folder_path.rglob("*"))
            for f in files:
                if f.is_file():
                    rel_path = str(f.relative_to(folder_path))
                    size = f.stat().st_size
                    hasher.update(f"{rel_path}:{size}".encode())
        except (PermissionError, OSError):
            pass
        return hasher.hexdigest()[:32]

    # ========== Import Record Management ==========

    async def create_import_records(
        self,
        source: ImportSource,
        designs: list[DetectedDesign],
    ) -> list[ImportRecord]:
        """Create import records for detected designs.

        Args:
            source: The import source.
            designs: List of detected designs.

        Returns:
            List of created ImportRecord models.
        """
        records = []
        for design in designs:
            # Check for existing record
            existing = await self._get_record_by_path(source.id, design.relative_path)
            if existing:
                # Update if changed
                if existing.file_hash != design.file_hash:
                    existing.file_hash = design.file_hash
                    existing.file_size = design.total_size
                    existing.file_mtime = design.mtime
                    existing.detected_title = design.title
                    existing.model_file_count = design.model_count
                    existing.preview_file_count = design.preview_count
                    if existing.status == ImportRecordStatus.IMPORTED:
                        # Mark for re-import if content changed
                        existing.status = ImportRecordStatus.PENDING
                    logger.debug(
                        "import_record_updated",
                        record_id=existing.id,
                        path=design.relative_path,
                    )
                records.append(existing)
            else:
                # Create new record
                record = ImportRecord(
                    import_source_id=source.id,
                    source_path=design.relative_path,
                    file_hash=design.file_hash,
                    file_size=design.total_size,
                    file_mtime=design.mtime,
                    status=ImportRecordStatus.PENDING,
                    detected_title=design.title,
                    detected_designer=source.default_designer,
                    model_file_count=design.model_count,
                    preview_file_count=design.preview_count,
                )
                self.db.add(record)
                records.append(record)
                logger.debug(
                    "import_record_created",
                    source_id=source.id,
                    path=design.relative_path,
                )

        await self.db.flush()
        return records

    async def _get_record_by_path(
        self, source_id: str, source_path: str
    ) -> ImportRecord | None:
        """Get an import record by source and path."""
        result = await self.db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_id == source_id,
                ImportRecord.source_path == source_path,
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_records(self, source_id: str) -> list[ImportRecord]:
        """Get all pending import records for a source."""
        result = await self.db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_id == source_id,
                ImportRecord.status == ImportRecordStatus.PENDING,
            )
        )
        return list(result.scalars().all())

    # ========== Design Import ==========

    async def import_design(
        self,
        record: ImportRecord,
        source: ImportSource,
        conflict_resolution: ConflictResolution = ConflictResolution.SKIP,
    ) -> Design | None:
        """Import a detected design and create a Design record.

        Args:
            record: The import record to import.
            source: The import source.
            conflict_resolution: How to handle conflicts.

        Returns:
            The created Design, or None if skipped.
        """
        if record.status != ImportRecordStatus.PENDING:
            logger.warning(
                "import_skipped_not_pending",
                record_id=record.id,
                status=record.status.value,
            )
            return None

        # Check for conflicts (same title + designer from same source)
        if conflict_resolution == ConflictResolution.SKIP:
            existing = await self._find_existing_design(record, source)
            if existing:
                record.status = ImportRecordStatus.SKIPPED
                record.design_id = existing.id
                logger.info(
                    "import_skipped_duplicate",
                    record_id=record.id,
                    existing_design_id=existing.id,
                )
                return None

        try:
            record.status = ImportRecordStatus.IMPORTING

            # Get the folder path
            folder_path = Path(source.folder_path) / record.source_path

            # Create design record
            design = Design(
                canonical_title=record.detected_title or folder_path.name,
                canonical_designer=record.detected_designer or source.default_designer or "Unknown",
                status=DesignStatus.DOWNLOADED,
                metadata_authority=MetadataAuthority.USER,
                import_source_id=source.id,
                total_size_bytes=record.file_size,
            )
            self.db.add(design)
            await self.db.flush()

            # Auto-queue render if no previews detected in source
            if record.preview_file_count == 0:
                await auto_queue_render_for_design(self.db, design.id)

            # Update record
            record.status = ImportRecordStatus.IMPORTED
            record.design_id = design.id
            record.imported_at = datetime.now(timezone.utc)

            # Update source stats
            source.items_imported = (source.items_imported or 0) + 1
            source.last_sync_at = datetime.now(timezone.utc)

            logger.info(
                "design_imported",
                design_id=design.id,
                title=design.canonical_title,
                source_path=record.source_path,
            )

            return design

        except Exception as e:
            record.status = ImportRecordStatus.ERROR
            record.error_message = str(e)
            logger.error(
                "import_failed",
                record_id=record.id,
                error=str(e),
            )
            raise

    async def _find_existing_design(
        self, record: ImportRecord, source: ImportSource
    ) -> Design | None:
        """Find an existing design that matches the record."""
        # Check by import record (same source + path)
        result = await self.db.execute(
            select(ImportRecord).where(
                ImportRecord.import_source_id == source.id,
                ImportRecord.source_path == record.source_path,
                ImportRecord.status == ImportRecordStatus.IMPORTED,
                ImportRecord.id != record.id,
            )
        )
        existing_record = result.scalar_one_or_none()
        if existing_record and existing_record.design_id:
            design_result = await self.db.execute(
                select(Design).where(Design.id == existing_record.design_id)
            )
            return design_result.scalar_one_or_none()

        return None

    async def import_all_pending(
        self,
        source: ImportSource,
        conflict_resolution: ConflictResolution = ConflictResolution.SKIP,
    ) -> tuple[int, int]:
        """Import all pending designs from a source.

        Args:
            source: The import source.
            conflict_resolution: How to handle conflicts.

        Returns:
            Tuple of (imported_count, skipped_count).
        """
        # Ensure any pending changes are flushed before querying
        # (autoflush is disabled in session config)
        await self.db.flush()

        records = await self.get_pending_records(source.id)
        logger.debug(
            "import_all_pending_records_found",
            source_id=source.id,
            pending_count=len(records),
        )
        imported = 0
        skipped = 0

        for record in records:
            try:
                design = await self.import_design(record, source, conflict_resolution)
                if design:
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(
                    "import_all_pending_error",
                    record_id=record.id,
                    error=str(e),
                )
                skipped += 1

        logger.info(
            "import_all_pending_complete",
            source_id=source.id,
            imported=imported,
            skipped=skipped,
        )

        return imported, skipped

    # ========== File System Monitoring ==========

    async def start_monitoring(self, source: ImportSource) -> None:
        """Start file system monitoring for a source.

        Uses watchdog for real-time filesystem events.

        Args:
            source: The import source to monitor.
        """
        if source.source_type != ImportSourceType.BULK_FOLDER:
            raise BulkImportError(f"Source {source.id} is not a bulk folder source")

        if not source.folder_path:
            raise BulkImportPathError("Source has no folder path configured")

        folder_path = Path(source.folder_path)
        if not folder_path.exists():
            raise BulkImportPathError(f"Folder does not exist: {folder_path}")

        # Stop existing observer if any
        await self.stop_monitoring(source.id)

        # Create event handler
        def handle_event(event_type: str, path: Path) -> None:
            if source.id not in self._pending_events:
                self._pending_events[source.id] = []
            self._pending_events[source.id].append((event_type, path))
            logger.debug(
                "fs_event",
                source_id=source.id,
                event_type=event_type,
                path=str(path),
            )

        handler = FolderEventHandler(handle_event)
        observer = Observer()
        observer.schedule(handler, str(folder_path), recursive=True)
        observer.start()

        self._observers[source.id] = observer
        logger.info(
            "monitoring_started",
            source_id=source.id,
            folder_path=str(folder_path),
        )

    async def stop_monitoring(self, source_id: str) -> None:
        """Stop file system monitoring for a source.

        Args:
            source_id: The source ID to stop monitoring.
        """
        if source_id in self._observers:
            observer = self._observers[source_id]
            observer.stop()
            observer.join(timeout=5)
            del self._observers[source_id]
            logger.info("monitoring_stopped", source_id=source_id)

        if source_id in self._pending_events:
            del self._pending_events[source_id]

    async def stop_all_monitoring(self) -> None:
        """Stop all file system monitoring."""
        for source_id in list(self._observers.keys()):
            await self.stop_monitoring(source_id)

    def is_monitoring(self, source_id: str) -> bool:
        """Check if a source is being monitored."""
        return source_id in self._observers and self._observers[source_id].is_alive()

    async def process_pending_events(self, source: ImportSource) -> int:
        """Process pending file system events for a source.

        Args:
            source: The import source.

        Returns:
            Number of events processed.
        """
        events = self._pending_events.get(source.id, [])
        if not events:
            return 0

        # Clear events
        self._pending_events[source.id] = []

        # Group events by parent folder to detect designs
        affected_folders: set[Path] = set()
        folder_path = Path(source.folder_path)

        for event_type, path in events:
            if event_type != "deleted":
                # Find the design folder this file belongs to
                parent = path.parent
                while parent != folder_path and parent != parent.parent:
                    affected_folders.add(parent)
                    parent = parent.parent

        # Re-scan affected folders
        if affected_folders:
            config = await self._profile_service.get_profile_config(
                source.import_profile_id
            )
            for folder in affected_folders:
                if folder.exists():
                    detection = self._profile_service.is_design_folder(folder, config)
                    if detection.is_design:
                        relative_path = str(folder.relative_to(folder_path))
                        detected = DetectedDesign(folder, detection, relative_path)
                        detected.total_size = self._calculate_folder_size(folder)
                        detected.mtime = self._get_folder_mtime(folder)
                        detected.file_hash = self._calculate_folder_hash(folder)
                        await self.create_import_records(source, [detected])

        logger.info(
            "events_processed",
            source_id=source.id,
            event_count=len(events),
            folders_affected=len(affected_folders),
        )

        return len(events)

    # ========== Polling Fallback ==========

    async def poll_source(self, source: ImportSource) -> tuple[int, int]:
        """Poll a source for changes (fallback when watchdog unavailable).

        Args:
            source: The import source to poll.

        Returns:
            Tuple of (new_designs, updated_designs).
        """
        designs = await self.scan_folder(source)
        records = await self.create_import_records(source, designs)

        new_count = sum(
            1 for r in records
            if r.status == ImportRecordStatus.PENDING and r.imported_at is None
        )
        updated_count = sum(
            1 for r in records
            if r.status == ImportRecordStatus.PENDING and r.imported_at is not None
        )

        # Update source
        source.last_sync_at = datetime.now(timezone.utc)
        source.status = ImportSourceStatus.ACTIVE

        logger.info(
            "source_polled",
            source_id=source.id,
            new=new_count,
            updated=updated_count,
        )

        return new_count, updated_count

    # ========== Initial Scan ==========

    async def initial_scan(
        self,
        source: ImportSource,
        auto_import: bool = False,
    ) -> tuple[int, int]:
        """Perform initial scan of a source.

        Args:
            source: The import source.
            auto_import: Whether to automatically import detected designs.

        Returns:
            Tuple of (detected_count, imported_count).
        """
        # Scan folder
        designs = await self.scan_folder(source)
        detected = len(designs)

        # Create import records
        await self.create_import_records(source, designs)

        imported = 0
        if auto_import:
            imported, _ = await self.import_all_pending(source)

        # Update source status
        source.status = ImportSourceStatus.ACTIVE
        source.last_sync_at = datetime.now(timezone.utc)

        logger.info(
            "initial_scan_complete",
            source_id=source.id,
            detected=detected,
            imported=imported,
        )

        return detected, imported
