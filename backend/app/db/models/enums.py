"""Enum types for database models."""

from __future__ import annotations

import enum


class BackfillMode(str, enum.Enum):
    """Channel backfill mode options."""

    ALL_HISTORY = "ALL_HISTORY"
    LAST_N_MESSAGES = "LAST_N_MESSAGES"
    LAST_N_DAYS = "LAST_N_DAYS"


class DownloadMode(str, enum.Enum):
    """Channel download mode options."""

    DOWNLOAD_ALL = "DOWNLOAD_ALL"
    DOWNLOAD_ALL_NEW = "DOWNLOAD_ALL_NEW"
    MANUAL = "MANUAL"


class TitleSource(str, enum.Enum):
    """Source for design title."""

    CAPTION = "CAPTION"
    FILENAME = "FILENAME"
    MANUAL = "MANUAL"


class DesignerSource(str, enum.Enum):
    """Source for designer name."""

    CAPTION = "CAPTION"
    CHANNEL = "CHANNEL"
    MANUAL = "MANUAL"


class MediaType(str, enum.Enum):
    """Telegram attachment media type."""

    DOCUMENT = "DOCUMENT"
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    OTHER = "OTHER"


class AttachmentDownloadStatus(str, enum.Enum):
    """Download status for attachments."""

    NOT_DOWNLOADED = "NOT_DOWNLOADED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    FAILED = "FAILED"


class MulticolorStatus(str, enum.Enum):
    """Multicolor classification for designs."""

    UNKNOWN = "UNKNOWN"
    SINGLE = "SINGLE"
    MULTI = "MULTI"


class DesignStatus(str, enum.Enum):
    """Design workflow status."""

    DISCOVERED = "DISCOVERED"
    WANTED = "WANTED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    IMPORTING = "IMPORTING"
    ORGANIZED = "ORGANIZED"
    FAILED = "FAILED"  # Final failure after all retries exhausted


class FileKind(str, enum.Enum):
    """Kind of file in a design."""

    MODEL = "MODEL"
    ARCHIVE = "ARCHIVE"
    IMAGE = "IMAGE"
    OTHER = "OTHER"


class ModelKind(str, enum.Enum):
    """Type of 3D model file."""

    STL = "STL"
    THREE_MF = "THREE_MF"
    OBJ = "OBJ"
    STEP = "STEP"
    UNKNOWN = "UNKNOWN"


class TagSource(str, enum.Enum):
    """Source of a tag assignment."""

    AUTO_CAPTION = "AUTO_CAPTION"  # Extracted from message caption
    AUTO_FILENAME = "AUTO_FILENAME"  # Extracted from filename
    AUTO_THANGS = "AUTO_THANGS"  # Imported from Thangs metadata
    USER = "USER"  # Manually added by user


class PreviewSource(str, enum.Enum):
    """Source of a preview image."""

    TELEGRAM = "TELEGRAM"  # Downloaded from Telegram post
    THANGS = "THANGS"  # Cached from Thangs
    EMBEDDED_3MF = "EMBEDDED_3MF"  # Extracted from 3MF file
    RENDERED = "RENDERED"  # Generated via stl-thumb
    ARCHIVE = "ARCHIVE"  # Extracted from archive (preview.jpg, etc.)


class PreviewKind(str, enum.Enum):
    """Kind of preview asset."""

    THUMBNAIL = "THUMBNAIL"  # Small preview for cards (max 400px)
    FULL = "FULL"  # Full-size preview for detail view
    GALLERY = "GALLERY"  # Additional gallery image


class MulticolorSource(str, enum.Enum):
    """Source of multicolor classification."""

    HEURISTIC = "HEURISTIC"  # Detected from caption/filename keywords
    THREE_MF_ANALYSIS = "3MF_ANALYSIS"  # Parsed from 3MF file
    USER_OVERRIDE = "USER_OVERRIDE"  # Manually set by user


class JobType(str, enum.Enum):
    """Types of background jobs."""

    BACKFILL_CHANNEL = "BACKFILL_CHANNEL"
    SYNC_CHANNEL_LIVE = "SYNC_CHANNEL_LIVE"
    DOWNLOAD_DESIGN = "DOWNLOAD_DESIGN"
    DOWNLOAD_TELEGRAM_IMAGES = "DOWNLOAD_TELEGRAM_IMAGES"  # v0.7: Preview images
    EXTRACT_ARCHIVE = "EXTRACT_ARCHIVE"
    ANALYZE_3MF = "ANALYZE_3MF"
    GENERATE_RENDER = "GENERATE_RENDER"
    IMPORT_TO_LIBRARY = "IMPORT_TO_LIBRARY"
    DEDUPE_RECONCILE = "DEDUPE_RECONCILE"


class JobStatus(str, enum.Enum):
    """Status of a background job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class DedupeEvidenceType(str, enum.Enum):
    """Type of deduplication evidence."""

    HASH_MATCH = "HASH_MATCH"
    FILENAME_SIZE_MATCH = "FILENAME_SIZE_MATCH"
    CAPTION_SIMILARITY = "CAPTION_SIMILARITY"
    MANUAL_MERGE = "MANUAL_MERGE"


class MetadataAuthority(str, enum.Enum):
    """Source of truth for design metadata."""

    TELEGRAM = "TELEGRAM"
    THANGS = "THANGS"
    PRINTABLES = "PRINTABLES"
    USER = "USER"


class ExternalSourceType(str, enum.Enum):
    """Type of external metadata source."""

    THANGS = "THANGS"
    PRINTABLES = "PRINTABLES"
    THINGIVERSE = "THINGIVERSE"


class MatchMethod(str, enum.Enum):
    """How a design was matched to an external source."""

    LINK = "LINK"
    TEXT = "TEXT"
    GEOMETRY = "GEOMETRY"
    MANUAL = "MANUAL"


class DiscoverySourceType(str, enum.Enum):
    """How a channel was discovered from monitored content."""

    FORWARD = "FORWARD"  # Message was forwarded from this channel
    MENTION = "MENTION"  # @username mentioned in caption/text
    CAPTION_LINK = "CAPTION_LINK"  # t.me link in caption
    TEXT_LINK = "TEXT_LINK"  # t.me link in message entities
