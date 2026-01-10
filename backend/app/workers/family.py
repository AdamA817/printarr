"""Worker for family detection via file hash overlap (DEC-044).

Processes DETECT_FAMILY_OVERLAP jobs to find design variants based on
shared file hashes. This runs post-download when file hashes are available.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.db.models import Design, Job
from app.db.models.enums import FamilyDetectionMethod, JobType
from app.db.session import async_session_maker
from app.services.family import FamilyService
from app.workers.base import BaseWorker

logger = get_logger(__name__)


class FamilyWorker(BaseWorker):
    """Worker that processes family overlap detection jobs.

    Runs after design file downloads are complete to detect family
    relationships based on shared file hashes.
    """

    job_types = [JobType.DETECT_FAMILY_OVERLAP]

    async def process(self, job: Job, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        """Process a DETECT_FAMILY_OVERLAP job.

        Args:
            job: The job to process.
            payload: Job payload with design_id.

        Returns:
            Result dict with detection status.
        """
        if not payload:
            return {"error": "No payload provided"}

        design_id = payload.get("design_id")
        if not design_id:
            return {"error": "No design_id in payload"}

        async with async_session_maker() as db:
            # Get design
            design = await db.get(Design, design_id)
            if not design:
                return {"error": f"Design {design_id} not found"}

            # Skip if design already has a family
            if design.family_id:
                logger.debug(
                    "design_already_in_family",
                    job_id=job.id,
                    design_id=design_id,
                    family_id=design.family_id,
                )
                return {
                    "design_id": design_id,
                    "skipped": True,
                    "reason": "Already in a family",
                    "family_id": design.family_id,
                }

            service = FamilyService(db)

            # Try file hash overlap first (most reliable for variants)
            candidates = await service.detect_family_by_file_overlap(design)
            detection_method = FamilyDetectionMethod.FILE_HASH_OVERLAP

            # If no file overlap found, try name-based detection as fallback
            # This handles cases like 3MF vs STL of the same model
            if not candidates:
                name_candidates = await service.find_family_candidates_by_name(design)
                if name_candidates:
                    # Convert name candidates to same format as file overlap
                    # (Design, confidence) - use 0.5 confidence for name matches
                    candidates = [(d, 0.5) for d, _ in name_candidates]
                    detection_method = FamilyDetectionMethod.NAME_PATTERN
                    logger.debug(
                        "name_pattern_candidates_found",
                        job_id=job.id,
                        design_id=design_id,
                        count=len(candidates),
                    )

            if not candidates:
                logger.debug(
                    "no_candidates_found",
                    job_id=job.id,
                    design_id=design_id,
                )
                return {
                    "design_id": design_id,
                    "candidates_found": 0,
                }

            # Check if any candidate already has a family
            existing_family = None
            for candidate, overlap_ratio in candidates:
                if candidate.family_id:
                    existing_family = await service.get_family(candidate.family_id)
                    break

            if existing_family:
                # Add design to existing family
                # Extract variant info from title
                info = service.extract_family_info(design.canonical_title)
                await service.add_to_family(design, existing_family, info.variant_name)

                await db.commit()

                logger.info(
                    "design_added_to_family_via_file_overlap",
                    job_id=job.id,
                    design_id=design_id,
                    family_id=existing_family.id,
                    overlap_candidates=len(candidates),
                )

                return {
                    "design_id": design_id,
                    "family_id": existing_family.id,
                    "family_created": False,
                    "candidates_found": len(candidates),
                }

            # Create new family from candidates
            # Use the design title as base for family name (strip channel prefixes)
            stripped_title = service._strip_channel_prefix(design.canonical_title)
            info = service.extract_family_info(stripped_title)
            family_name = info.base_name if info.variant_name else stripped_title

            # Find average confidence from overlaps
            avg_confidence = sum(ratio for _, ratio in candidates) / len(candidates)

            family = await service.create_family(
                name=family_name,
                designer=design.canonical_designer,
                detection_method=detection_method,
                detection_confidence=avg_confidence,
            )

            # Add this design
            await service.add_to_family(design, family, info.variant_name)

            # Add candidates that aren't in families
            variants_added = 1
            for candidate, overlap_ratio in candidates:
                if not candidate.family_id:
                    candidate_info = service.extract_family_info(candidate.canonical_title)
                    await service.add_to_family(candidate, family, candidate_info.variant_name or "Variant")
                    variants_added += 1

            # Aggregate tags from all variants
            await service.aggregate_tags(family)

            await db.commit()

            logger.info(
                "family_created_via_file_overlap",
                job_id=job.id,
                design_id=design_id,
                family_id=family.id,
                family_name=family_name,
                variants_added=variants_added,
                confidence=avg_confidence,
            )

            return {
                "design_id": design_id,
                "family_id": family.id,
                "family_name": family_name,
                "family_created": True,
                "variants_added": variants_added,
                "confidence": avg_confidence,
            }
