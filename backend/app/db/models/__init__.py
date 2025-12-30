"""Database models for Printarr."""

from app.db.models.attachment import Attachment
from app.db.models.channel import Channel
from app.db.models.design import Design
from app.db.models.design_file import DesignFile
from app.db.models.design_source import DesignSource
from app.db.models.design_tag import DesignTag
from app.db.models.enums import (
    AttachmentDownloadStatus,
    BackfillMode,
    DedupeEvidenceType,
    DesignerSource,
    DesignStatus,
    DownloadMode,
    ExternalSourceType,
    FileKind,
    JobStatus,
    JobType,
    MatchMethod,
    MediaType,
    MetadataAuthority,
    ModelKind,
    MulticolorStatus,
    PreviewKind,
    TagSource,
    TitleSource,
)
from app.db.models.external_metadata_source import ExternalMetadataSource
from app.db.models.job import Job
from app.db.models.preview_asset import PreviewAsset
from app.db.models.tag import Tag
from app.db.models.telegram_message import TelegramMessage

__all__ = [
    # Models
    "Attachment",
    "Channel",
    "Design",
    "DesignFile",
    "DesignSource",
    "DesignTag",
    "ExternalMetadataSource",
    "Job",
    "PreviewAsset",
    "Tag",
    "TelegramMessage",
    # Enums
    "AttachmentDownloadStatus",
    "BackfillMode",
    "DedupeEvidenceType",
    "DesignerSource",
    "DesignStatus",
    "DownloadMode",
    "ExternalSourceType",
    "FileKind",
    "JobStatus",
    "JobType",
    "MatchMethod",
    "MediaType",
    "MetadataAuthority",
    "ModelKind",
    "MulticolorStatus",
    "PreviewKind",
    "TagSource",
    "TitleSource",
]
