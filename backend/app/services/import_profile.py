"""Import Profile service for managing folder structure parsing (v0.8).

Provides:
- CRUD operations for import profiles
- Built-in preset profiles
- Design detection algorithm (DEC-036)
- Title extraction from folder names
- Preview folder detection
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ImportProfile
from app.schemas.import_profile import (
    DesignDetectionResult,
    ImportProfileConfig,
    ImportProfileCreate,
    ImportProfileUpdate,
    ProfileAutoTagConfig,
    ProfileDetectionConfig,
    ProfileIgnoreConfig,
    ProfilePreviewConfig,
    ProfileTitleConfig,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ImportProfileError(Exception):
    """Base exception for import profile errors."""

    pass


class ProfileNotFoundError(ImportProfileError):
    """Raised when a profile is not found."""

    pass


class ProfileValidationError(ImportProfileError):
    """Raised when a profile configuration is invalid."""

    pass


class BuiltinProfileModificationError(ImportProfileError):
    """Raised when trying to modify a built-in profile."""

    pass


# Built-in profile definitions
BUILTIN_PROFILES: dict[str, dict] = {
    "standard": {
        "name": "Standard",
        "description": "Default profile for most creators. Handles flat and nested structures with common folder names.",
        "config": ImportProfileConfig(
            detection=ProfileDetectionConfig(
                model_extensions=[".stl", ".3mf", ".obj", ".step"],
                archive_extensions=[".zip", ".rar", ".7z"],
                min_model_files=1,
                structure="auto",
                model_subfolders=["STLs", "stls", "Models", "Supported", "Unsupported"],
            ),
            title=ProfileTitleConfig(
                source="folder_name",
                strip_patterns=["(Supported)", "(Unsupported)", "(STLs)", "(Models)"],
                case_transform="none",
            ),
            preview=ProfilePreviewConfig(
                folders=["Renders", "Images", "Preview", "Photos", "Pictures"],
                wildcard_folders=["*Renders", "*Preview"],
                extensions=[".jpg", ".jpeg", ".png", ".webp"],
                include_root=True,
            ),
            ignore=ProfileIgnoreConfig(
                folders=["Lychee", "Chitubox", "Project Files", "Source", ".git"],
                extensions=[".lys", ".ctb", ".gcode", ".blend"],
                patterns=[".DS_Store", "Thumbs.db"],
            ),
            auto_tags=ProfileAutoTagConfig(
                from_subfolders=True,
                from_filename=False,
                subfolder_levels=2,
            ),
        ),
    },
    "yosh-studios": {
        "name": "Yosh Studios",
        "description": "Profile for Yosh Studios folder structure with tier-based organization. "
        "Uses depth-based detection: Root -> Tier folders -> Design folders.",
        "config": ImportProfileConfig(
            detection=ProfileDetectionConfig(
                model_extensions=[".stl", ".3mf"],
                archive_extensions=[".zip", ".rar", ".7z"],
                min_model_files=1,
                structure="nested",
                model_subfolders=["STL", "STLs", "stl", "stls", "Supported", "Unsupported", "Pre-Supported", "Un-Supported", "Models"],
                require_preview_folder=False,  # Not needed with design_depth
                design_depth=2,  # Root (0) -> Tier folders (1) -> Design (2)
            ),
            title=ProfileTitleConfig(
                source="folder_name",
                strip_patterns=["(STLs)", "(Pre-Supported)", "(Un-Supported)"],
                case_transform="title",
            ),
            preview=ProfilePreviewConfig(
                folders=["Renders", "4K Renders", "Preview Renders", "Images"],
                wildcard_folders=["*Renders", "*Preview"],
                extensions=[".jpg", ".jpeg", ".png", ".webp"],
                include_root=True,
            ),
            ignore=ProfileIgnoreConfig(
                folders=["Lychee", "Chitubox", "Project Files", "Source", "Lychee 4K"],
                extensions=[".lys", ".ctb", ".gcode", ".blend", ".zcode"],
                patterns=[".DS_Store", "Thumbs.db", "*.lys"],
            ),
            auto_tags=ProfileAutoTagConfig(
                from_subfolders=True,
                from_filename=False,
                subfolder_levels=2,
                strip_patterns=["Tier$", "^\\d{4}-\\d{2}", "Yosher"],
            ),
        ),
    },
    "flat-archive": {
        "name": "Flat Archive",
        "description": "Simple profile for flat folders or archives with all files at root level.",
        "config": ImportProfileConfig(
            detection=ProfileDetectionConfig(
                model_extensions=[".stl", ".3mf", ".obj", ".step"],
                archive_extensions=[".zip", ".rar", ".7z"],
                min_model_files=1,
                structure="flat",
                model_subfolders=[],
            ),
            title=ProfileTitleConfig(
                source="folder_name",
                strip_patterns=[],
                case_transform="none",
            ),
            preview=ProfilePreviewConfig(
                folders=[],
                wildcard_folders=[],
                extensions=[".jpg", ".jpeg", ".png", ".webp"],
                include_root=True,
            ),
            ignore=ProfileIgnoreConfig(
                folders=[".git"],
                extensions=[".gcode"],
                patterns=[".DS_Store", "Thumbs.db"],
            ),
            auto_tags=ProfileAutoTagConfig(
                from_subfolders=False,
                from_filename=True,
            ),
        ),
    },
    "supported-unsupported": {
        "name": "Supported/Unsupported",
        "description": "Profile for creators who split models into Supported and Unsupported subfolders.",
        "config": ImportProfileConfig(
            detection=ProfileDetectionConfig(
                model_extensions=[".stl", ".3mf"],
                archive_extensions=[".zip", ".rar", ".7z"],
                min_model_files=1,
                structure="nested",
                model_subfolders=["Supported", "Unsupported", "Pre-Supported", "Un-Supported", "Presupported"],
            ),
            title=ProfileTitleConfig(
                source="folder_name",
                strip_patterns=["- Supported", "- Unsupported", "(Supported)", "(Unsupported)"],
                case_transform="none",
            ),
            preview=ProfilePreviewConfig(
                folders=["Renders", "Images", "Preview"],
                wildcard_folders=["*Renders"],
                extensions=[".jpg", ".jpeg", ".png", ".webp"],
                include_root=True,
            ),
            ignore=ProfileIgnoreConfig(
                folders=["Lychee", "Chitubox", "Project Files"],
                extensions=[".lys", ".ctb", ".gcode"],
                patterns=[".DS_Store", "Thumbs.db"],
            ),
            auto_tags=ProfileAutoTagConfig(
                from_subfolders=True,
                from_filename=False,
                subfolder_levels=1,
            ),
        ),
    },
}


class ImportProfileService:
    """Service for managing import profiles and detecting designs.

    Provides CRUD operations for profiles, built-in presets,
    and the design detection algorithm per DEC-036.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the import profile service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db

    # ========== CRUD Operations ==========

    async def list_profiles(self, include_builtin: bool = True) -> list[ImportProfile]:
        """List all import profiles.

        Args:
            include_builtin: Whether to include built-in profiles.

        Returns:
            List of ImportProfile models.
        """
        query = select(ImportProfile)
        if not include_builtin:
            query = query.where(ImportProfile.is_builtin == False)  # noqa: E712
        query = query.order_by(ImportProfile.is_builtin.desc(), ImportProfile.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_profile(self, profile_id: str) -> ImportProfile:
        """Get a profile by ID.

        Args:
            profile_id: The profile ID.

        Returns:
            The ImportProfile model.

        Raises:
            ProfileNotFoundError: If profile not found.
        """
        result = await self.db.execute(
            select(ImportProfile).where(ImportProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ProfileNotFoundError(f"Profile {profile_id} not found")
        return profile

    async def get_profile_by_name(self, name: str) -> ImportProfile | None:
        """Get a profile by name.

        Args:
            name: The profile name.

        Returns:
            The ImportProfile model or None if not found.
        """
        result = await self.db.execute(
            select(ImportProfile).where(ImportProfile.name == name)
        )
        return result.scalar_one_or_none()

    async def create_profile(self, data: ImportProfileCreate) -> ImportProfile:
        """Create a new import profile.

        Args:
            data: Profile creation data.

        Returns:
            The created ImportProfile model.

        Raises:
            ProfileValidationError: If profile with same name exists.
        """
        existing = await self.get_profile_by_name(data.name)
        if existing:
            raise ProfileValidationError(f"Profile with name '{data.name}' already exists")

        profile = ImportProfile(
            name=data.name,
            description=data.description,
            is_builtin=False,
            config_json=data.config.model_dump_json(),
        )
        self.db.add(profile)
        await self.db.flush()

        logger.info("profile_created", profile_id=profile.id, name=data.name)
        return profile

    async def update_profile(
        self, profile_id: str, data: ImportProfileUpdate
    ) -> ImportProfile:
        """Update an import profile.

        Args:
            profile_id: The profile ID to update.
            data: Profile update data.

        Returns:
            The updated ImportProfile model.

        Raises:
            ProfileNotFoundError: If profile not found.
            BuiltinProfileModificationError: If trying to modify builtin profile.
        """
        profile = await self.get_profile(profile_id)

        if profile.is_builtin:
            raise BuiltinProfileModificationError(
                f"Cannot modify built-in profile '{profile.name}'"
            )

        if data.name is not None:
            existing = await self.get_profile_by_name(data.name)
            if existing and existing.id != profile_id:
                raise ProfileValidationError(
                    f"Profile with name '{data.name}' already exists"
                )
            profile.name = data.name

        if data.description is not None:
            profile.description = data.description

        if data.config is not None:
            profile.config_json = data.config.model_dump_json()

        await self.db.flush()
        logger.info("profile_updated", profile_id=profile_id)
        return profile

    async def delete_profile(self, profile_id: str) -> None:
        """Delete an import profile.

        Args:
            profile_id: The profile ID to delete.

        Raises:
            ProfileNotFoundError: If profile not found.
            BuiltinProfileModificationError: If trying to delete builtin profile.
        """
        profile = await self.get_profile(profile_id)

        if profile.is_builtin:
            raise BuiltinProfileModificationError(
                f"Cannot delete built-in profile '{profile.name}'"
            )

        await self.db.delete(profile)
        logger.info("profile_deleted", profile_id=profile_id)

    async def get_profile_config(self, profile_id: str | None) -> ImportProfileConfig:
        """Get the configuration for a profile, or the default if none specified.

        Args:
            profile_id: Optional profile ID. Uses 'standard' profile if None.

        Returns:
            The parsed ImportProfileConfig.
        """
        if profile_id is None:
            # Use standard profile
            return BUILTIN_PROFILES["standard"]["config"]

        profile = await self.get_profile(profile_id)
        if profile.config_json:
            return ImportProfileConfig.model_validate_json(profile.config_json)
        return BUILTIN_PROFILES["standard"]["config"]

    # ========== Built-in Profile Seeding ==========

    async def ensure_builtin_profiles(self) -> int:
        """Ensure all built-in profiles exist in the database with current configs.

        Creates any missing built-in profiles and updates existing ones if
        the configuration has changed. Called on startup.

        Returns:
            Number of profiles created or updated.
        """
        changed = 0
        for key, profile_def in BUILTIN_PROFILES.items():
            existing = await self.get_profile_by_name(profile_def["name"])
            new_config_json = profile_def["config"].model_dump_json()

            if existing is None:
                # Create new built-in profile
                profile = ImportProfile(
                    name=profile_def["name"],
                    description=profile_def["description"],
                    is_builtin=True,
                    config_json=new_config_json,
                )
                self.db.add(profile)
                changed += 1
                logger.info("builtin_profile_created", name=profile_def["name"])
            elif existing.is_builtin and existing.config_json != new_config_json:
                # Update existing built-in profile with new config
                existing.config_json = new_config_json
                existing.description = profile_def["description"]
                changed += 1
                logger.info("builtin_profile_updated", name=profile_def["name"])

        if changed > 0:
            await self.db.flush()

        return changed

    # ========== Design Detection (DEC-036) ==========

    def is_design_folder(
        self, folder_path: Path, config: ImportProfileConfig
    ) -> DesignDetectionResult:
        """Detect if a folder represents a single design.

        Implements the design detection algorithm from DEC-036.

        Args:
            folder_path: Path to the folder to check.
            config: Import profile configuration.

        Returns:
            DesignDetectionResult with detection details.
        """
        detection = config.detection
        model_extensions = set(ext.lower() for ext in detection.model_extensions)
        archive_extensions = set(ext.lower() for ext in detection.archive_extensions)

        result = DesignDetectionResult(is_design=False)
        model_files: list[str] = []
        archive_files: list[str] = []
        preview_files: list[str] = []

        # Check for ignored folders
        if self._should_ignore_folder(folder_path.name, config.ignore):
            return result

        # Get root files
        try:
            root_files = [f for f in folder_path.iterdir() if f.is_file()]
        except PermissionError:
            logger.warning("permission_denied", path=str(folder_path))
            return result

        # Check for model files at root
        for f in root_files:
            ext = f.suffix.lower()
            if ext in model_extensions:
                model_files.append(str(f.relative_to(folder_path)))
            elif ext in archive_extensions:
                archive_files.append(str(f.relative_to(folder_path)))

        # Check for model files in subfolders
        if detection.structure in ("nested", "auto"):
            for subfolder_name in detection.model_subfolders:
                subfolder_path = folder_path / subfolder_name
                if subfolder_path.exists() and subfolder_path.is_dir():
                    for f in subfolder_path.rglob("*"):
                        if f.is_file():
                            ext = f.suffix.lower()
                            if ext in model_extensions:
                                model_files.append(str(f.relative_to(folder_path)))

        # Find preview files and check for preview folder
        preview_files, has_preview_folder = self._find_preview_files_with_folder_check(folder_path, config.preview)

        # Check if require_preview_folder is set and we don't have one
        if detection.require_preview_folder and not has_preview_folder:
            return result

        # Determine if this is a design
        if len(model_files) >= detection.min_model_files:
            result.is_design = True
            result.detection_reason = f"Found {len(model_files)} model file(s) at root or in subfolders"
        elif archive_files:
            result.is_design = True
            result.detection_reason = f"Found {len(archive_files)} archive file(s) (assumed to contain models)"

        if result.is_design:
            result.model_files = model_files
            result.archive_files = archive_files
            result.preview_files = preview_files
            result.title = self._extract_title(folder_path, config.title)

        return result

    def _should_ignore_folder(self, folder_name: str, ignore: ProfileIgnoreConfig) -> bool:
        """Check if a folder should be ignored.

        Args:
            folder_name: Name of the folder.
            ignore: Ignore configuration.

        Returns:
            True if folder should be ignored.
        """
        if folder_name in ignore.folders:
            return True

        for pattern in ignore.patterns:
            if fnmatch.fnmatch(folder_name, pattern):
                return True

        return False

    def _should_ignore_file(self, filename: str, ignore: ProfileIgnoreConfig) -> bool:
        """Check if a file should be ignored.

        Args:
            filename: Name of the file.
            ignore: Ignore configuration.

        Returns:
            True if file should be ignored.
        """
        ext = Path(filename).suffix.lower()
        if ext in ignore.extensions:
            return True

        for pattern in ignore.patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False

    def _find_preview_files(
        self, folder_path: Path, preview: ProfilePreviewConfig
    ) -> list[str]:
        """Find preview image files in a folder.

        Args:
            folder_path: Path to the design folder.
            preview: Preview configuration.

        Returns:
            List of relative paths to preview files.
        """
        files, _ = self._find_preview_files_with_folder_check(folder_path, preview)
        return files

    def _find_preview_files_with_folder_check(
        self, folder_path: Path, preview: ProfilePreviewConfig
    ) -> tuple[list[str], bool]:
        """Find preview image files in a folder and check for preview folders.

        Args:
            folder_path: Path to the design folder.
            preview: Preview configuration.

        Returns:
            Tuple of (list of relative paths to preview files, has_preview_folder).
        """
        preview_files: list[str] = []
        preview_extensions = set(ext.lower() for ext in preview.extensions)
        has_preview_folder = False

        # Check root folder
        if preview.include_root:
            try:
                for f in folder_path.iterdir():
                    if f.is_file() and f.suffix.lower() in preview_extensions:
                        preview_files.append(str(f.relative_to(folder_path)))
            except PermissionError:
                pass

        # Check specific folders
        for folder_name in preview.folders:
            preview_path = folder_path / folder_name
            if preview_path.exists() and preview_path.is_dir():
                has_preview_folder = True
                try:
                    for f in preview_path.rglob("*"):
                        if f.is_file() and f.suffix.lower() in preview_extensions:
                            preview_files.append(str(f.relative_to(folder_path)))
                except PermissionError:
                    pass

        # Check wildcard folders (case-insensitive matching)
        for pattern in preview.wildcard_folders:
            try:
                for subfolder in folder_path.iterdir():
                    if subfolder.is_dir() and fnmatch.fnmatch(subfolder.name.lower(), pattern.lower()):
                        has_preview_folder = True
                        for f in subfolder.rglob("*"):
                            if f.is_file() and f.suffix.lower() in preview_extensions:
                                preview_files.append(str(f.relative_to(folder_path)))
            except PermissionError:
                pass

        return preview_files, has_preview_folder

    def _extract_title(self, folder_path: Path, title_config: ProfileTitleConfig) -> str:
        """Extract design title from folder.

        Args:
            folder_path: Path to the design folder.
            title_config: Title extraction configuration.

        Returns:
            Extracted title string.
        """
        if title_config.source == "folder_name":
            title = folder_path.name
        elif title_config.source == "parent_folder":
            title = folder_path.parent.name
        else:  # filename - use first model file
            title = folder_path.name  # Fallback

        # Strip patterns
        for pattern in title_config.strip_patterns:
            title = title.replace(pattern, "").strip()

        # Apply case transform
        if title_config.case_transform == "title":
            title = title.title()
        elif title_config.case_transform == "lower":
            title = title.lower()
        elif title_config.case_transform == "upper":
            title = title.upper()

        return title.strip()

    def extract_auto_tags(
        self, folder_path: Path, config: ProfileAutoTagConfig
    ) -> list[str]:
        """Extract automatic tags from folder hierarchy.

        Args:
            folder_path: Path to the design folder.
            config: Auto-tag configuration.

        Returns:
            List of extracted tags.
        """
        tags: list[str] = []

        if config.from_subfolders:
            # Walk up the folder hierarchy
            current = folder_path.parent
            for _ in range(config.subfolder_levels):
                if current == current.parent:
                    break
                folder_name = current.name
                # Apply strip patterns
                tag = folder_name
                for pattern in config.strip_patterns:
                    tag = re.sub(pattern, "", tag).strip()
                if tag and tag not in tags:
                    tags.append(tag)
                current = current.parent

        if config.from_filename:
            # Extract keywords from folder name
            words = re.findall(r"[A-Za-z]+", folder_path.name)
            for word in words:
                if len(word) > 2 and word.lower() not in ("the", "and", "for"):
                    if word not in tags:
                        tags.append(word)

        return tags

    # ========== Folder Traversal ==========

    def traverse_for_designs(
        self, root_path: Path, config: ImportProfileConfig
    ) -> list[tuple[Path, DesignDetectionResult]]:
        """Traverse a folder structure and detect all designs.

        Implements the traversal strategy from DEC-036:
        - For each subfolder, check if it's a design
        - If yes: add to results, don't recurse deeper
        - If no: recurse into children
        - Skip ignored folders

        Args:
            root_path: Root path to start traversal.
            config: Import profile configuration.

        Returns:
            List of (path, detection_result) tuples for all detected designs.
        """
        designs: list[tuple[Path, DesignDetectionResult]] = []
        self._traverse_recursive(root_path, config, designs, current_depth=0)
        return designs

    def _traverse_recursive(
        self,
        folder_path: Path,
        config: ImportProfileConfig,
        results: list[tuple[Path, DesignDetectionResult]],
        current_depth: int = 0,
    ) -> None:
        """Recursive helper for folder traversal.

        Args:
            folder_path: Current folder to check.
            config: Import profile configuration.
            results: Accumulator for detected designs.
            current_depth: Current depth in the tree (0 = root).
        """
        # Skip ignored folders
        if self._should_ignore_folder(folder_path.name, config.ignore):
            return

        # Check if we're using depth-based detection
        design_depth = config.detection.design_depth
        if design_depth is not None:
            if current_depth == design_depth:
                # At target depth - treat this folder as a design
                detection = self._create_design_from_folder(folder_path, config)
                if detection.is_design:
                    results.append((folder_path, detection))
                return
            elif current_depth < design_depth:
                # Not deep enough yet, recurse into children
                try:
                    for child in folder_path.iterdir():
                        if child.is_dir():
                            self._traverse_recursive(child, config, results, current_depth + 1)
                except PermissionError:
                    logger.warning("permission_denied_traversal", path=str(folder_path))
                return
            else:
                # Deeper than target, skip
                return

        # Normal detection logic (design_depth not set)
        detection = self.is_design_folder(folder_path, config)

        if detection.is_design:
            # Add to results and don't recurse deeper
            results.append((folder_path, detection))
            return

        # Not a design, recurse into children
        try:
            for child in folder_path.iterdir():
                if child.is_dir():
                    self._traverse_recursive(child, config, results, current_depth + 1)
        except PermissionError:
            logger.warning("permission_denied_traversal", path=str(folder_path))

    def _create_design_from_folder(
        self,
        folder_path: Path,
        config: ImportProfileConfig,
    ) -> DesignDetectionResult:
        """Create a design from a folder without complex detection logic.

        Used when design_depth is set - treats the folder as a design and
        scans for all model/preview files within it.

        Args:
            folder_path: Folder to treat as a design.
            config: Import profile configuration.

        Returns:
            DesignDetectionResult with all files found.
        """
        detection = config.detection
        model_extensions = set(ext.lower() for ext in detection.model_extensions)
        archive_extensions = set(ext.lower() for ext in detection.archive_extensions)
        preview_extensions = set(ext.lower() for ext in config.preview.extensions)

        model_files: list[str] = []
        archive_files: list[str] = []
        preview_files: list[str] = []

        # Scan all files recursively
        try:
            for f in folder_path.rglob("*"):
                if f.is_file():
                    ext = f.suffix.lower()
                    rel_path = str(f.relative_to(folder_path))

                    if ext in model_extensions:
                        model_files.append(rel_path)
                    elif ext in archive_extensions:
                        archive_files.append(rel_path)
                    elif ext in preview_extensions:
                        preview_files.append(rel_path)
        except PermissionError:
            pass

        # Must have at least one model or archive file
        if not model_files and not archive_files:
            return DesignDetectionResult(is_design=False)

        title = self._extract_title(folder_path, config.title)

        return DesignDetectionResult(
            is_design=True,
            title=title,
            model_files=model_files,
            archive_files=archive_files,
            preview_files=preview_files,
            detection_reason=f"Depth-based detection at level {config.detection.design_depth}",
        )
