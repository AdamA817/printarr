#!/usr/bin/env python3
"""One-time import script for SuperCrazyPrints collection.

This script handles the mixed folder structure:
- Design folders containing STL/3MF files
- Loose STL/3MF files at various levels

Usage:
    # Dry run to preview what will be imported
    python scripts/import_supercrazyprints.py /library/SuperCrazyPrints --dry-run

    # Live import (source must be inside library path)
    python scripts/import_supercrazyprints.py /library/SuperCrazyPrints

The script will:
1. Scan for design folders (folders containing model files)
2. Detect orphan model files (not inside a design folder)
3. Create Design records with DesignFile entries
4. Queue preview render jobs for each design
5. Queue AI analysis jobs (if AI is enabled)

IMPORTANT: The source_path must be a subdirectory of Printarr's library path.
Mount your SuperCrazyPrints folder under /library in Docker, e.g.:
    volumes:
      - /mnt/user/SuperCrazyPrints:/library/SuperCrazyPrints:ro
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Model file extensions
MODEL_EXTENSIONS = {".stl", ".3mf", ".obj", ".step"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}

# Folders to ignore
IGNORE_FOLDERS = {"Community 3mfs", ".git", "__MACOSX", ".DS_Store", "Missing file"}

# Format subfolders (these should be merged with parent, not separate designs)
FORMAT_SUBFOLDERS = {
    "STL", "STLs", "stl", "stls", "3MF", "3mf",
    "Supported", "Unsupported", "Pre-Supported", "Un-Supported",
    "Models", "Files",
}


def is_format_subfolder(folder_name: str) -> bool:
    """Check if a folder name is a format/organization subfolder."""
    return folder_name in FORMAT_SUBFOLDERS


def is_short_filename(name: str) -> bool:
    """Check if this looks like a Windows 8.3 short filename."""
    # Pattern: 6 chars + ~ + digit(s)
    if "~" in name and len(name) <= 12:
        parts = name.split("~")
        if len(parts) == 2 and parts[1].isdigit():
            return True
    return False


class ImportStats:
    """Track import statistics."""

    def __init__(self):
        self.folders_scanned = 0
        self.design_folders_found = 0
        self.orphan_files_found = 0
        self.designs_created = 0
        self.designs_skipped = 0
        self.files_registered = 0
        self.render_jobs_queued = 0
        self.ai_jobs_queued = 0
        self.errors = []


def is_model_file(path: Path) -> bool:
    """Check if a file is a model file."""
    return path.suffix.lower() in MODEL_EXTENSIONS


def is_archive_file(path: Path) -> bool:
    """Check if a file is an archive."""
    return path.suffix.lower() in ARCHIVE_EXTENSIONS


def should_ignore(path: Path) -> bool:
    """Check if a path should be ignored."""
    return path.name in IGNORE_FOLDERS or path.name.startswith(".")


def get_all_model_files(folder: Path) -> list[Path]:
    """Get all model files in a folder and its subfolders."""
    model_files = []
    try:
        for f in folder.rglob("*"):
            if f.is_file() and (is_model_file(f) or is_archive_file(f)):
                if not should_ignore(f) and not any(should_ignore(p) for p in f.parents):
                    model_files.append(f)
    except PermissionError:
        pass
    return model_files


def find_designs(root_path: Path) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    """Find all designs in the folder structure.

    Algorithm:
    1. Find all "leaf" design folders (folders with model files but NO subfolders with model files)
    2. Find orphan files (model files in folders that have design subfolders)

    This handles mixed structures like Welcome Pack where a folder has both
    design subfolders AND loose model files.

    Returns:
        Tuple of (design_folders, orphan_files)
        Each item is (path, relative_path_for_tags)
    """
    design_folders: list[tuple[Path, str]] = []
    orphan_files: list[tuple[Path, str]] = []

    # First pass: find all folders that contain model files directly
    folders_with_models: dict[Path, list[Path]] = {}  # folder -> list of model files

    for folder in root_path.rglob("*"):
        if not folder.is_dir():
            continue
        if should_ignore(folder):
            continue

        try:
            model_files = [f for f in folder.iterdir() if f.is_file() and (is_model_file(f) or is_archive_file(f))]
        except PermissionError:
            continue

        if model_files:
            folders_with_models[folder] = model_files

    # Second pass: determine which folders are "leaf" designs vs "container" folders
    # A container folder has model files AND has child folders that also have model files
    container_folders: set[Path] = set()

    for folder in folders_with_models:
        # Check if any child folder also has model files
        for child in folder.iterdir():
            if child.is_dir() and not should_ignore(child):
                # Check if this child (or any descendant) has model files
                if child in folders_with_models:
                    container_folders.add(folder)
                    break
                # Also check deeper descendants
                for descendant in child.rglob("*"):
                    if descendant.is_dir() and descendant in folders_with_models:
                        container_folders.add(folder)
                        break

    # Third pass: collect leaf design folders (not containers)
    # Also merge format subfolders with their parents
    processed_parents: set[Path] = set()

    for folder, model_files in folders_with_models.items():
        if folder in container_folders:
            # This is a container - its model files become orphans
            for model_file in model_files:
                relative = model_file.relative_to(root_path)
                parent_rel = str(relative.parent) if relative.parent != Path(".") else ""
                orphan_files.append((model_file, parent_rel))
        else:
            # Skip Windows 8.3 short filenames
            if is_short_filename(folder.name):
                continue

            # Check if this is a format subfolder (STL, 3MF, etc.)
            if is_format_subfolder(folder.name):
                # Use parent folder as the design name instead
                parent = folder.parent
                if parent not in processed_parents and parent != root_path:
                    relative = parent.relative_to(root_path)
                    design_folders.append((parent, str(relative)))
                    processed_parents.add(parent)
                continue

            relative = folder.relative_to(root_path)
            design_folders.append((folder, str(relative)))

    return design_folders, orphan_files


def extract_tags_from_path(relative_path: str) -> list[str]:
    """Extract tags from the folder path."""
    tags = []
    parts = relative_path.split("/") if relative_path else []

    for part in parts:
        if not part or should_ignore(Path(part)):
            continue
        tag = part.strip()
        # Skip year folders
        if tag.isdigit() and len(tag) == 4:
            continue
        # Skip "Welcome Pack 60 Models" type generic folders
        if "welcome pack" in tag.lower():
            continue
        tags.append(tag)

    return tags


def get_design_title(path: Path, is_folder: bool) -> str:
    """Extract design title from path."""
    if is_folder:
        return path.name
    else:
        # For single files, use filename without extension
        # Clean up common suffixes
        name = path.stem
        for suffix in [" STL", "_STL", "-STL", "_3MF", " 3MF"]:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name.replace("_", " ").replace("-", " ").strip()


def count_model_files(folder: Path) -> int:
    """Count model files in a folder (recursive)."""
    return len(get_all_model_files(folder))


def get_file_kind(ext: str):
    """Get FileKind enum for a file extension."""
    # Import here to avoid import errors in dry-run mode
    from app.db.models.enums import FileKind
    ext_lower = ext.lower()
    if ext_lower in MODEL_EXTENSIONS:
        return FileKind.MODEL
    elif ext_lower in ARCHIVE_EXTENSIONS:
        return FileKind.ARCHIVE
    return FileKind.OTHER


def get_model_kind(ext: str):
    """Get ModelKind enum for a file extension."""
    from app.db.models.enums import ModelKind
    ext_lower = ext.lower()
    mapping = {
        ".stl": ModelKind.STL,
        ".3mf": ModelKind.THREE_MF,
        ".obj": ModelKind.OBJ,
        ".step": ModelKind.STEP,
    }
    return mapping.get(ext_lower, ModelKind.UNKNOWN)


async def run_import(
    source_path: Path,
    library_path: Path | None = None,
    designer: str = "SuperCrazyPrints",
    dry_run: bool = False,
    queue_renders: bool = True,
    queue_ai: bool = True,
) -> ImportStats:
    """Run the import process."""
    stats = ImportStats()

    print(f"\n{'=' * 60}")
    print("SuperCrazyPrints Import Script")
    print(f"{'=' * 60}")
    print(f"Source: {source_path}")
    print(f"Designer: {designer}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Queue Renders: {queue_renders}")
    print(f"Queue AI: {queue_ai}")
    print(f"{'=' * 60}\n")

    # Verify source exists
    if not source_path.exists():
        print(f"ERROR: Source path does not exist: {source_path}")
        return stats

    # Find all designs
    print("Scanning for designs...")
    design_folders, orphan_files = find_designs(source_path)

    stats.design_folders_found = len(design_folders)
    stats.orphan_files_found = len(orphan_files)

    print(f"  Found {len(design_folders)} design folders")
    print(f"  Found {len(orphan_files)} orphan model files")
    print()

    if dry_run:
        print("DRY RUN - Showing what would be imported:\n")

        print("Design Folders:")
        print("-" * 50)
        for path, rel_path in design_folders[:30]:
            title = get_design_title(path, is_folder=True)
            tags = extract_tags_from_path(rel_path)
            model_count = count_model_files(path)
            print(f"  [{model_count:2d} files] {title}")
            if tags:
                print(f"             Tags: {', '.join(tags[:3])}")
        if len(design_folders) > 30:
            print(f"  ... and {len(design_folders) - 30} more folders")

        print("\nOrphan Files (single-file designs):")
        print("-" * 50)
        for path, rel_path in orphan_files[:30]:
            title = get_design_title(path, is_folder=False)
            tags = extract_tags_from_path(rel_path)
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [{size_mb:5.1f}MB] {title}")
            if tags:
                print(f"             Tags: {', '.join(tags[:3])}")
        if len(orphan_files) > 30:
            print(f"  ... and {len(orphan_files) - 30} more files")

        total = len(design_folders) + len(orphan_files)
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Design folders: {len(design_folders)}")
        print(f"  Orphan files:   {len(orphan_files)}")
        print(f"  TOTAL DESIGNS:  {total}")
        print(f"\nTo actually import, run without --dry-run")
        return stats

    # LIVE MODE - Import to database
    print("Connecting to database...")

    # Now import the database modules (only when needed)
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.db.models import Design, DesignFile, DesignStatus, MetadataAuthority
    from app.db.models.enums import JobType
    from app.services.job_queue import JobQueueService

    # Use provided library path or default from settings
    if library_path is None:
        library_path = settings.library_path

    # Verify source is inside library
    try:
        source_path.relative_to(library_path)
    except ValueError:
        print("ERROR: Source path must be inside the library path!")
        print(f"  Source:  {source_path}")
        print(f"  Library: {library_path}")
        print(f"\nMount your SuperCrazyPrints folder under the library, e.g.:")
        print("  volumes:")
        print(f"    - /mnt/user/SuperCrazyPrints:{library_path}/SuperCrazyPrints:ro")
        return stats

    print(f"Library path: {library_path}")

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Check if AI is enabled
    ai_enabled = queue_ai and settings.ai_configured
    if queue_ai and not ai_enabled:
        print("NOTE: AI analysis disabled (AI not configured in settings)")

    async with async_session() as db:
        job_queue = JobQueueService(db)

        # Helper to check for existing design
        async def check_existing(title: str) -> bool:
            result = await db.execute(
                select(Design).where(
                    Design.canonical_title == title,
                    Design.canonical_designer == designer,
                )
            )
            return result.scalar_one_or_none() is not None

        # Helper to create design files
        async def create_design_files(design_id: str, model_files: list[Path]) -> int:
            """Create DesignFile records for model files."""
            count = 0
            for model_file in model_files:
                try:
                    rel_path = str(model_file.relative_to(library_path))
                    ext = model_file.suffix.lower()
                    size = model_file.stat().st_size

                    design_file = DesignFile(
                        design_id=design_id,
                        relative_path=rel_path,
                        filename=model_file.name,
                        ext=ext,
                        size_bytes=size,
                        file_kind=get_file_kind(ext),
                        model_kind=get_model_kind(ext),
                        is_primary=(count == 0),  # First file is primary
                    )
                    db.add(design_file)
                    count += 1
                except Exception as e:
                    stats.errors.append(f"File {model_file.name}: {e}")
            return count

        # Helper to queue jobs
        async def queue_jobs_for_design(design_id: str) -> tuple[bool, bool]:
            """Queue render and AI jobs. Returns (render_queued, ai_queued)."""
            render_queued = False
            ai_queued = False

            if queue_renders:
                try:
                    await job_queue.enqueue(
                        job_type=JobType.GENERATE_RENDER,
                        design_id=design_id,
                        priority=-1,  # Background priority
                        payload={"auto_queued": True, "design_id": design_id},
                        max_attempts=2,
                    )
                    render_queued = True
                except Exception as e:
                    stats.errors.append(f"Render job queue failed: {e}")

            if ai_enabled:
                try:
                    await job_queue.enqueue(
                        job_type=JobType.AI_ANALYZE_DESIGN,
                        design_id=design_id,
                        priority=-2,  # Lower than render
                        payload={"design_id": design_id},
                        display_name="AI Analysis (import)",
                    )
                    ai_queued = True
                except Exception as e:
                    stats.errors.append(f"AI job queue failed: {e}")

            return render_queued, ai_queued

        # Import design folders
        print("\nImporting design folders...")
        for i, (path, rel_path) in enumerate(design_folders):
            title = get_design_title(path, is_folder=True)

            if await check_existing(title):
                stats.designs_skipped += 1
                continue

            try:
                design = Design(
                    canonical_title=title,
                    canonical_designer=designer,
                    status=DesignStatus.ORGANIZED,  # Already in library
                    metadata_authority=MetadataAuthority.USER,
                )
                db.add(design)
                await db.flush()  # Get the design ID

                # Create DesignFile records for all model files in this folder
                model_files = get_all_model_files(path)
                files_created = await create_design_files(design.id, model_files)
                stats.files_registered += files_created

                # Queue jobs
                render_q, ai_q = await queue_jobs_for_design(design.id)
                if render_q:
                    stats.render_jobs_queued += 1
                if ai_q:
                    stats.ai_jobs_queued += 1

                stats.designs_created += 1

                if (i + 1) % 50 == 0:
                    print(f"  Progress: {i + 1}/{len(design_folders)} folders")
                    await db.commit()
            except Exception as e:
                stats.errors.append(f"Folder {path.name}: {e}")

        await db.commit()

        # Import orphan files
        print("Importing orphan files...")
        for i, (path, rel_path) in enumerate(orphan_files):
            title = get_design_title(path, is_folder=False)

            if await check_existing(title):
                stats.designs_skipped += 1
                continue

            try:
                design = Design(
                    canonical_title=title,
                    canonical_designer=designer,
                    status=DesignStatus.ORGANIZED,
                    metadata_authority=MetadataAuthority.USER,
                )
                db.add(design)
                await db.flush()

                # Create single DesignFile record
                files_created = await create_design_files(design.id, [path])
                stats.files_registered += files_created

                # Queue jobs
                render_q, ai_q = await queue_jobs_for_design(design.id)
                if render_q:
                    stats.render_jobs_queued += 1
                if ai_q:
                    stats.ai_jobs_queued += 1

                stats.designs_created += 1

                if (i + 1) % 50 == 0:
                    print(f"  Progress: {i + 1}/{len(orphan_files)} files")
                    await db.commit()
            except Exception as e:
                stats.errors.append(f"File {path.name}: {e}")

        await db.commit()

    await engine.dispose()
    print("Done!")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Import SuperCrazyPrints collection into Printarr"
    )
    parser.add_argument(
        "source_path",
        type=Path,
        help="Path to SuperCrazyPrints folder (must be inside library path)",
    )
    parser.add_argument(
        "--library-path",
        type=Path,
        default=None,
        help="Override library path (default: from PRINTARR_LIBRARY_PATH)",
    )
    parser.add_argument(
        "--designer",
        default="SuperCrazyPrints",
        help="Designer name (default: SuperCrazyPrints)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without making changes",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Don't queue render jobs",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Don't queue AI analysis jobs",
    )

    args = parser.parse_args()

    stats = asyncio.run(run_import(
        source_path=args.source_path,
        library_path=args.library_path,
        designer=args.designer,
        dry_run=args.dry_run,
        queue_renders=not args.no_render,
        queue_ai=not args.no_ai,
    ))

    print(f"\n{'=' * 60}")
    print("Import Summary")
    print(f"{'=' * 60}")
    print(f"  Design folders found: {stats.design_folders_found}")
    print(f"  Orphan files found: {stats.orphan_files_found}")
    print(f"  Designs created: {stats.designs_created}")
    print(f"  Designs skipped (duplicates): {stats.designs_skipped}")
    print(f"  Files registered: {stats.files_registered}")
    print(f"  Render jobs queued: {stats.render_jobs_queued}")
    print(f"  AI jobs queued: {stats.ai_jobs_queued}")
    print(f"  Errors: {len(stats.errors)}")

    if stats.errors:
        print("\nErrors:")
        for error in stats.errors[:10]:
            print(f"  - {error}")
        if len(stats.errors) > 10:
            print(f"  ... and {len(stats.errors) - 10} more")

    print()


if __name__ == "__main__":
    main()
