"""Database models for Printarr."""

from app.db.models.app_setting import AppSetting
from app.db.models.attachment import Attachment
from app.db.models.channel import Channel
from app.db.models.design import Design
from app.db.models.design_file import DesignFile
from app.db.models.design_source import DesignSource
from app.db.models.design_tag import DesignTag
from app.db.models.discovered_channel import DiscoveredChannel
from app.db.models.duplicate_candidate import DuplicateCandidate
from app.db.models.enums import (
    AttachmentDownloadStatus,
    BackfillMode,
    ConflictResolution,
    DedupeEvidenceType,
    DesignerSource,
    DesignStatus,
    DiscoverySourceType,
    DownloadMode,
    DuplicateCandidateStatus,
    DuplicateMatchType,
    ExternalSourceType,
    FileKind,
    ImportRecordStatus,
    ImportSourceStatus,
    ImportSourceType,
    JobStatus,
    JobType,
    MatchMethod,
    MediaType,
    MetadataAuthority,
    ModelKind,
    MulticolorSource,
    MulticolorStatus,
    PreviewKind,
    PreviewSource,
    TagSource,
    TitleSource,
)
from app.db.models.external_metadata_source import ExternalMetadataSource
from app.db.models.google_credentials import GoogleCredentials
from app.db.models.import_profile import ImportProfile
from app.db.models.phpbb_credentials import PhpbbCredentials
from app.db.models.import_record import ImportRecord
from app.db.models.import_source import ImportSource
from app.db.models.import_source_folder import ImportSourceFolder
from app.db.models.job import Job
from app.db.models.preview_asset import PreviewAsset
from app.db.models.tag import Tag
from app.db.models.telegram_message import TelegramMessage

__all__ = [
    # Models
    "AppSetting",
    "Attachment",
    "Channel",
    "Design",
    "DesignFile",
    "DesignSource",
    "DesignTag",
    "DiscoveredChannel",
    "DuplicateCandidate",
    "ExternalMetadataSource",
    "GoogleCredentials",
    "ImportProfile",
    "PhpbbCredentials",
    "ImportRecord",
    "ImportSource",
    "ImportSourceFolder",
    "Job",
    "PreviewAsset",
    "Tag",
    "TelegramMessage",
    # Enums
    "AttachmentDownloadStatus",
    "BackfillMode",
    "ConflictResolution",
    "DedupeEvidenceType",
    "DesignerSource",
    "DesignStatus",
    "DiscoverySourceType",
    "DownloadMode",
    "DuplicateCandidateStatus",
    "DuplicateMatchType",
    "ExternalSourceType",
    "FileKind",
    "ImportRecordStatus",
    "ImportSourceStatus",
    "ImportSourceType",
    "JobStatus",
    "JobType",
    "MatchMethod",
    "MediaType",
    "MetadataAuthority",
    "ModelKind",
    "MulticolorSource",
    "MulticolorStatus",
    "PreviewKind",
    "PreviewSource",
    "TagSource",
    "TitleSource",
]
