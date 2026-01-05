"""Duplicate detection and merge service (DEC-041).

Provides deduplication functionality for detecting and merging duplicate designs
using multiple matching signals with confidence scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import (
    Design,
    DesignFile,
    DesignSource,
    DesignStatus,
    DuplicateCandidate,
    DuplicateCandidateStatus,
    DuplicateMatchType,
    ExternalMetadataSource,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Confidence thresholds
AUTO_MERGE_THRESHOLD = 0.9  # Auto-merge when confidence >= 0.9
TITLE_SIMILARITY_THRESHOLD = 80  # 80% similarity for title+designer match

# Confidence scores per match type (DEC-041)
CONFIDENCE_SCORES = {
    DuplicateMatchType.HASH: 1.0,
    DuplicateMatchType.THANGS_ID: 1.0,
    DuplicateMatchType.TITLE_DESIGNER: 0.7,
    DuplicateMatchType.FILENAME_SIZE: 0.5,
}

# File size tolerance for filename+size matching (1%)
FILE_SIZE_TOLERANCE = 0.01


class DuplicateService:
    """Service for detecting and merging duplicate designs.

    Implements the two-stage deduplication strategy from DEC-041:
    - Pre-download: Heuristic matching (title/designer, filename/size)
    - Post-download: SHA-256 hash matching (exact file match)

    Confidence scoring:
    - Hash match: 1.0 (exact file content)
    - Thangs ID: 1.0 (same external source)
    - Title + designer: 0.7 (fuzzy match)
    - Filename + size: 0.5 (weak heuristic)
    """

    def __init__(self, db: AsyncSession):
        """Initialize the duplicate service.

        Args:
            db: AsyncSession for database operations.
        """
        self.db = db

    async def find_duplicates(
        self, design: Design
    ) -> list[DuplicateCandidate]:
        """Find potential duplicates for a design.

        Checks all matching signals and returns candidates with confidence scores.

        Args:
            design: The design to check for duplicates.

        Returns:
            List of DuplicateCandidate records (not yet saved to DB).
        """
        candidates: list[DuplicateCandidate] = []

        # Get design files with hashes
        design_files = await self._get_design_files(design.id)

        # 1. Check hash matches (highest confidence)
        hash_matches = await self._find_hash_matches(design.id, design_files)
        for match_design_id in hash_matches:
            candidates.append(
                DuplicateCandidate(
                    design_id=design.id,
                    candidate_design_id=match_design_id,
                    match_type=DuplicateMatchType.HASH,
                    confidence=CONFIDENCE_SCORES[DuplicateMatchType.HASH],
                )
            )

        # 2. Check Thangs ID matches
        thangs_matches = await self._find_thangs_id_matches(design.id)
        for match_design_id in thangs_matches:
            if not self._already_matched(candidates, match_design_id):
                candidates.append(
                    DuplicateCandidate(
                        design_id=design.id,
                        candidate_design_id=match_design_id,
                        match_type=DuplicateMatchType.THANGS_ID,
                        confidence=CONFIDENCE_SCORES[DuplicateMatchType.THANGS_ID],
                    )
                )

        # 3. Check title + designer matches (fuzzy)
        title_matches = await self._find_title_designer_matches(design)
        for match_design_id in title_matches:
            if not self._already_matched(candidates, match_design_id):
                candidates.append(
                    DuplicateCandidate(
                        design_id=design.id,
                        candidate_design_id=match_design_id,
                        match_type=DuplicateMatchType.TITLE_DESIGNER,
                        confidence=CONFIDENCE_SCORES[DuplicateMatchType.TITLE_DESIGNER],
                    )
                )

        # 4. Check filename + size matches
        filename_matches = await self._find_filename_size_matches(design.id, design_files)
        for match_design_id in filename_matches:
            if not self._already_matched(candidates, match_design_id):
                candidates.append(
                    DuplicateCandidate(
                        design_id=design.id,
                        candidate_design_id=match_design_id,
                        match_type=DuplicateMatchType.FILENAME_SIZE,
                        confidence=CONFIDENCE_SCORES[DuplicateMatchType.FILENAME_SIZE],
                    )
                )

        logger.info(
            "duplicates_found",
            design_id=design.id,
            candidate_count=len(candidates),
        )

        return candidates

    async def process_duplicates(
        self, design: Design
    ) -> tuple[bool, Design | None]:
        """Process duplicates for a design: auto-merge or create candidates.

        Args:
            design: The design to check.

        Returns:
            Tuple of (was_merged, merged_design). merged_design is the surviving
            design if merged, None otherwise.
        """
        candidates = await self.find_duplicates(design)

        if not candidates:
            return False, None

        # Find highest confidence match
        best_candidate = max(candidates, key=lambda c: c.confidence)

        if best_candidate.confidence >= AUTO_MERGE_THRESHOLD:
            # Auto-merge
            target_design = await self.db.get(Design, best_candidate.candidate_design_id)
            if target_design:
                merged = await self.merge_designs(design, target_design)

                # Record the merge
                best_candidate.status = DuplicateCandidateStatus.MERGED
                best_candidate.resolved_at = datetime.now(timezone.utc)
                self.db.add(best_candidate)

                logger.info(
                    "auto_merged_duplicate",
                    source_design_id=design.id,
                    target_design_id=target_design.id,
                    match_type=best_candidate.match_type.value,
                    confidence=best_candidate.confidence,
                )

                return True, merged
        else:
            # Save all candidates for manual review
            for candidate in candidates:
                self.db.add(candidate)

            logger.info(
                "duplicate_candidates_created",
                design_id=design.id,
                count=len(candidates),
            )

        return False, None

    async def merge_designs(
        self, source: Design, target: Design
    ) -> Design:
        """Merge source design into target design.

        Preserves all DesignSource records (no data loss).
        Target design gets "best" metadata.

        Args:
            source: Design to merge from (will be deleted).
            target: Design to merge into (will be preserved).

        Returns:
            The merged target design.
        """
        logger.info(
            "merging_designs",
            source_id=source.id,
            target_id=target.id,
        )

        # 1. Move all DesignSource records to target
        result = await self.db.execute(
            select(DesignSource).where(DesignSource.design_id == source.id)
        )
        sources = result.scalars().all()

        for src in sources:
            src.design_id = target.id

        # 2. Move DesignFile records to target (if not duplicates by hash)
        target_hashes = await self._get_design_file_hashes(target.id)
        source_files = await self._get_design_files(source.id)

        for sf in source_files:
            if sf.sha256 and sf.sha256 in target_hashes:
                # Skip duplicate files
                continue
            sf.design_id = target.id

        # 3. Move ExternalMetadataSource records to target
        result = await self.db.execute(
            select(ExternalMetadataSource).where(
                ExternalMetadataSource.design_id == source.id
            )
        )
        external_sources = result.scalars().all()

        for ext in external_sources:
            ext.design_id = target.id

        # 4. Update target with best metadata
        await self._merge_metadata(source, target)

        # 5. Update total size
        await self._recalculate_size(target)

        # 6. Delete source design
        source.status = DesignStatus.DELETED
        await self.db.delete(source)

        logger.info(
            "designs_merged",
            target_id=target.id,
            sources_moved=len(sources),
        )

        return target

    async def check_pre_download(
        self,
        title: str,
        designer: str,
        files: list[dict],
    ) -> Design | None:
        """Check for duplicates before download using heuristics.

        Used in the pre-download phase to avoid downloading known duplicates.

        Args:
            title: The design title.
            designer: The designer name.
            files: List of file info dicts with 'filename' and 'size'.

        Returns:
            Existing Design if likely duplicate found, None otherwise.
        """
        # Try title + designer match first
        match = await self._find_by_title_designer(title, designer)
        if match:
            logger.info(
                "pre_download_match_title_designer",
                title=title,
                designer=designer,
                match_design_id=match.id,
            )
            return match

        # Try filename + size match
        for file_info in files:
            filename = file_info.get("filename", "")
            size = file_info.get("size", 0)

            if filename and size:
                match = await self._find_by_filename_size(filename, size)
                if match:
                    logger.info(
                        "pre_download_match_filename_size",
                        filename=filename,
                        size=size,
                        match_design_id=match.id,
                    )
                    return match

        return None

    async def get_pending_candidates(
        self, design_id: str | None = None
    ) -> list[DuplicateCandidate]:
        """Get pending duplicate candidates for review.

        Args:
            design_id: Optional design ID to filter by.

        Returns:
            List of pending DuplicateCandidate records.
        """
        query = select(DuplicateCandidate).where(
            DuplicateCandidate.status == DuplicateCandidateStatus.PENDING
        )

        if design_id:
            query = query.where(DuplicateCandidate.design_id == design_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def resolve_candidate(
        self,
        candidate_id: str,
        merge: bool,
    ) -> DuplicateCandidate:
        """Resolve a duplicate candidate (merge or reject).

        Args:
            candidate_id: The DuplicateCandidate ID.
            merge: True to merge, False to reject.

        Returns:
            The updated DuplicateCandidate.
        """
        candidate = await self.db.get(DuplicateCandidate, candidate_id)
        if not candidate:
            raise ValueError(f"Candidate not found: {candidate_id}")

        if merge:
            source = await self.db.get(Design, candidate.design_id)
            target = await self.db.get(Design, candidate.candidate_design_id)

            if source and target:
                await self.merge_designs(source, target)
                candidate.status = DuplicateCandidateStatus.MERGED
        else:
            candidate.status = DuplicateCandidateStatus.REJECTED

        candidate.resolved_at = datetime.now(timezone.utc)

        return candidate

    # ==================== Private Helper Methods ====================

    def _already_matched(
        self, candidates: list[DuplicateCandidate], design_id: str
    ) -> bool:
        """Check if a design is already in the candidate list."""
        return any(c.candidate_design_id == design_id for c in candidates)

    async def _get_design_files(self, design_id: str) -> list[DesignFile]:
        """Get all design files for a design."""
        result = await self.db.execute(
            select(DesignFile).where(DesignFile.design_id == design_id)
        )
        return list(result.scalars().all())

    async def _get_design_file_hashes(self, design_id: str) -> set[str]:
        """Get all file hashes for a design."""
        files = await self._get_design_files(design_id)
        return {f.sha256 for f in files if f.sha256}

    async def _find_hash_matches(
        self, design_id: str, files: list[DesignFile]
    ) -> list[str]:
        """Find designs with matching file hashes."""
        matches: set[str] = set()

        for f in files:
            if not f.sha256:
                continue

            # Find other designs with the same hash
            result = await self.db.execute(
                select(DesignFile.design_id)
                .where(
                    DesignFile.sha256 == f.sha256,
                    DesignFile.design_id != design_id,
                )
                .distinct()
            )

            for (other_design_id,) in result:
                matches.add(other_design_id)

        return list(matches)

    async def _find_thangs_id_matches(self, design_id: str) -> list[str]:
        """Find designs with matching Thangs external IDs."""
        # Get our Thangs IDs
        result = await self.db.execute(
            select(ExternalMetadataSource.external_id)
            .where(
                ExternalMetadataSource.design_id == design_id,
                ExternalMetadataSource.source_type == "THANGS",
            )
        )
        our_thangs_ids = [row[0] for row in result]

        if not our_thangs_ids:
            return []

        # Find other designs with the same Thangs IDs
        result = await self.db.execute(
            select(ExternalMetadataSource.design_id)
            .where(
                ExternalMetadataSource.external_id.in_(our_thangs_ids),
                ExternalMetadataSource.source_type == "THANGS",
                ExternalMetadataSource.design_id != design_id,
            )
            .distinct()
        )

        return [row[0] for row in result]

    async def _find_title_designer_matches(self, design: Design) -> list[str]:
        """Find designs with similar title and designer (fuzzy match)."""
        if not design.canonical_title or not design.canonical_designer:
            return []

        # Get all designs to compare (excluding self)
        result = await self.db.execute(
            select(Design)
            .where(
                Design.id != design.id,
                Design.status != DesignStatus.DELETED,
            )
        )
        all_designs = result.scalars().all()

        matches = []
        for other in all_designs:
            if not other.canonical_title or not other.canonical_designer:
                continue

            # Fuzzy match on title
            title_ratio = fuzz.ratio(
                design.canonical_title.lower(),
                other.canonical_title.lower(),
            )

            # Fuzzy match on designer
            designer_ratio = fuzz.ratio(
                design.canonical_designer.lower(),
                other.canonical_designer.lower(),
            )

            # Both must be similar
            if (
                title_ratio >= TITLE_SIMILARITY_THRESHOLD
                and designer_ratio >= TITLE_SIMILARITY_THRESHOLD
            ):
                matches.append(other.id)
                logger.debug(
                    "title_designer_match",
                    design_id=design.id,
                    other_id=other.id,
                    title_ratio=title_ratio,
                    designer_ratio=designer_ratio,
                )

        return matches

    async def _find_filename_size_matches(
        self, design_id: str, files: list[DesignFile]
    ) -> list[str]:
        """Find designs with matching filename and size."""
        matches: set[str] = set()

        for f in files:
            if not f.filename or not f.size_bytes:
                continue

            # Calculate size tolerance
            min_size = int(f.size_bytes * (1 - FILE_SIZE_TOLERANCE))
            max_size = int(f.size_bytes * (1 + FILE_SIZE_TOLERANCE))

            # Find other designs with similar files
            result = await self.db.execute(
                select(DesignFile.design_id)
                .where(
                    DesignFile.filename == f.filename,
                    DesignFile.size_bytes.between(min_size, max_size),
                    DesignFile.design_id != design_id,
                )
                .distinct()
            )

            for (other_design_id,) in result:
                matches.add(other_design_id)

        return list(matches)

    async def _find_by_title_designer(
        self, title: str, designer: str
    ) -> Design | None:
        """Find a design by exact or fuzzy title+designer match."""
        # Try exact match first
        result = await self.db.execute(
            select(Design)
            .where(
                Design.canonical_title == title,
                Design.canonical_designer == designer,
                Design.status != DesignStatus.DELETED,
            )
        )
        exact_match = result.scalar_one_or_none()

        if exact_match:
            return exact_match

        # Try fuzzy match
        result = await self.db.execute(
            select(Design)
            .where(Design.status != DesignStatus.DELETED)
        )
        all_designs = result.scalars().all()

        for design in all_designs:
            if not design.canonical_title or not design.canonical_designer:
                continue

            title_ratio = fuzz.ratio(title.lower(), design.canonical_title.lower())
            designer_ratio = fuzz.ratio(
                designer.lower(), design.canonical_designer.lower()
            )

            if (
                title_ratio >= TITLE_SIMILARITY_THRESHOLD
                and designer_ratio >= TITLE_SIMILARITY_THRESHOLD
            ):
                return design

        return None

    async def _find_by_filename_size(
        self, filename: str, size: int
    ) -> Design | None:
        """Find a design by filename and size match."""
        min_size = int(size * (1 - FILE_SIZE_TOLERANCE))
        max_size = int(size * (1 + FILE_SIZE_TOLERANCE))

        result = await self.db.execute(
            select(Design)
            .join(DesignFile)
            .where(
                DesignFile.filename == filename,
                DesignFile.size_bytes.between(min_size, max_size),
                Design.status != DesignStatus.DELETED,
            )
        )

        return result.scalar_one_or_none()

    async def _merge_metadata(self, source: Design, target: Design) -> None:
        """Merge metadata from source into target, preferring best quality."""
        # Use source metadata if target is missing it
        if not target.canonical_title and source.canonical_title:
            target.canonical_title = source.canonical_title

        if not target.canonical_designer and source.canonical_designer:
            target.canonical_designer = source.canonical_designer

        if not target.description and source.description:
            target.description = source.description

        # Prefer downloaded status over discovered
        if source.status == DesignStatus.ORGANIZED and target.status in (
            DesignStatus.NEW,
            DesignStatus.DISCOVERED,
        ):
            target.status = source.status

    async def _recalculate_size(self, design: Design) -> None:
        """Recalculate total size of design files."""
        result = await self.db.execute(
            select(DesignFile).where(DesignFile.design_id == design.id)
        )
        files = result.scalars().all()

        total = sum(f.size_bytes or 0 for f in files)
        design.total_size_bytes = total
