"""Pydantic schemas for Import Profile API and configuration (v0.8)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileDetectionConfig(BaseModel):
    """Configuration for design detection within folders."""

    model_extensions: list[str] = Field(
        default=[".stl", ".3mf", ".obj", ".step"],
        description="File extensions that indicate 3D model files",
    )
    archive_extensions: list[str] = Field(
        default=[".zip", ".rar", ".7z"],
        description="Archive extensions (assumed to contain models)",
    )
    min_model_files: int = Field(
        default=1,
        ge=1,
        description="Minimum model files required to consider folder a design",
    )
    structure: Literal["nested", "flat", "auto"] = Field(
        default="auto",
        description="Expected folder structure: nested (subfolders), flat (files at root), auto (detect)",
    )
    model_subfolders: list[str] = Field(
        default=["STLs", "stls", "Models", "Supported", "Unsupported"],
        description="Subfolder names that may contain model files",
    )
    require_preview_folder: bool = Field(
        default=False,
        description="Require a preview/renders folder to be considered a design",
    )
    design_depth: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="If set, treat ALL folders at this depth as designs (skips detection logic). "
        "Depth 1 = immediate children of root, depth 2 = grandchildren, etc.",
    )


class ProfileTitleConfig(BaseModel):
    """Configuration for extracting design title."""

    source: Literal["folder_name", "parent_folder", "filename"] = Field(
        default="folder_name",
        description="Where to extract the title from",
    )
    strip_patterns: list[str] = Field(
        default=["(Supported)", "(Unsupported)", "(STLs)", "(Models)"],
        description="Patterns to remove from title",
    )
    case_transform: Literal["none", "title", "lower", "upper"] = Field(
        default="none",
        description="Case transformation to apply to title",
    )


class ProfilePreviewConfig(BaseModel):
    """Configuration for finding preview images."""

    folders: list[str] = Field(
        default=["Renders", "Images", "Preview", "Photos", "Pictures"],
        description="Subfolder names that may contain preview images",
    )
    wildcard_folders: list[str] = Field(
        default=["*Renders", "*Preview", "*Images"],
        description="Wildcard patterns for preview folders (e.g., '4K Renders')",
    )
    extensions: list[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".webp", ".gif"],
        description="Image file extensions to look for",
    )
    include_root: bool = Field(
        default=True,
        description="Also look for images at the design root folder",
    )


class ProfileIgnoreConfig(BaseModel):
    """Configuration for files/folders to ignore during import."""

    folders: list[str] = Field(
        default=["Lychee", "Chitubox", "Project Files", "Source", ".git", "__MACOSX"],
        description="Folder names to skip",
    )
    extensions: list[str] = Field(
        default=[".lys", ".ctb", ".gcode", ".blend", ".zcode", ".chitubox"],
        description="File extensions to skip",
    )
    patterns: list[str] = Field(
        default=[".DS_Store", "Thumbs.db", "*.tmp"],
        description="Filename patterns to skip (supports * wildcard)",
    )


class ProfileAutoTagConfig(BaseModel):
    """Configuration for automatic tagging during import."""

    from_subfolders: bool = Field(
        default=True,
        description="Extract tags from subfolder names in path",
    )
    from_filename: bool = Field(
        default=False,
        description="Extract tags from filename keywords",
    )
    subfolder_levels: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Number of parent folder levels to use for tags",
    )
    strip_patterns: list[str] = Field(
        default=["Tier$", "^\\d{4}-\\d{2}"],
        description="Regex patterns to strip from folder names before using as tags",
    )


class ImportProfileConfig(BaseModel):
    """Complete configuration for an import profile.

    This is stored as JSON in the ImportProfile.config_json field.
    """

    detection: ProfileDetectionConfig = Field(default_factory=ProfileDetectionConfig)
    title: ProfileTitleConfig = Field(default_factory=ProfileTitleConfig)
    preview: ProfilePreviewConfig = Field(default_factory=ProfilePreviewConfig)
    ignore: ProfileIgnoreConfig = Field(default_factory=ProfileIgnoreConfig)
    auto_tags: ProfileAutoTagConfig = Field(default_factory=ProfileAutoTagConfig)


class ImportProfileCreate(BaseModel):
    """Schema for creating a new import profile."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1024)
    config: ImportProfileConfig = Field(default_factory=ImportProfileConfig)


class ImportProfileUpdate(BaseModel):
    """Schema for updating an import profile (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1024)
    config: ImportProfileConfig | None = None


class ImportProfileResponse(BaseModel):
    """Schema for import profile response."""

    id: str
    name: str
    description: str | None = None
    is_builtin: bool
    config: ImportProfileConfig
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImportProfileList(BaseModel):
    """Schema for paginated import profile list response."""

    items: list[ImportProfileResponse]
    total: int


class DesignDetectionResult(BaseModel):
    """Result of design detection for a folder."""

    is_design: bool = Field(description="Whether the folder is detected as a design")
    title: str | None = Field(None, description="Extracted title if detected")
    model_files: list[str] = Field(default_factory=list, description="Detected model files")
    archive_files: list[str] = Field(default_factory=list, description="Detected archive files")
    preview_files: list[str] = Field(default_factory=list, description="Detected preview images")
    detection_reason: str | None = Field(None, description="Why this was detected as a design")
