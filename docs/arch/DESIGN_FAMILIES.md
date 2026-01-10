# Design Families Architecture

**Status**: Draft
**Date**: 2026-01-09
**Author**: Architect Agent

## Overview

This document proposes adding a "Design Families" feature to group related design variants under a common parent while maintaining them as separate, individually downloadable catalog entries.

### Problem Statement

Users encounter designs that are variations of the same base design:
- **RoboTortoise_2Color_Multicolor**
- **RoboTortoise_3Color_Multicolor**
- **RoboTortoise_4Color_Multicolor**

Currently, these appear as completely separate catalog entries with no indication of their relationship. Users want:
1. Visual grouping in the UI to see related variants together
2. Ability to download specific variants independently
3. Metadata inheritance (designer, tags) from the family
4. Easy navigation between variants

### Non-Goals

- Automatically merging variants into a single Design (that's deduplication)
- Replacing the existing Design entity
- Breaking existing API contracts

---

## Data Model

### New Entity: DesignFamily

```python
class DesignFamily(Base):
    """Groups related design variants under a common name."""

    __tablename__ = "design_families"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Family identity
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_designer: Mapped[str] = mapped_column(String(255), default="Unknown")

    # Optional user overrides
    name_override: Mapped[str | None] = mapped_column(String(512), nullable=True)
    designer_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Detection metadata
    detection_method: Mapped[str] = mapped_column(
        Enum("NAME_PATTERN", "FILE_HASH_OVERLAP", "AI_DETECTED", "MANUAL"),
        default="MANUAL"
    )
    detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relationships
    designs: Mapped[list[Design]] = relationship("Design", back_populates="family")
    tags: Mapped[list[FamilyTag]] = relationship("FamilyTag", back_populates="family")
```

### Design Entity Updates

```python
class Design(Base):
    # ... existing fields ...

    # New family relationship
    family_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("design_families.id", ondelete="SET NULL"), nullable=True
    )

    # Variant-specific info (what makes this variant different)
    variant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Examples: "2Color", "4Color", "Remix v2", "With Supports"

    # Relationships
    family: Mapped[DesignFamily | None] = relationship(
        "DesignFamily", back_populates="designs"
    )
```

### Family Tags (optional)

Tags can be applied at family level and inherited by all variants:

```python
class FamilyTag(Base):
    __tablename__ = "family_tags"

    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("design_families.id"))
    tag_id: Mapped[str] = mapped_column(String(36), ForeignKey("tags.id"))
    source: Mapped[TagSource] = mapped_column(Enum(TagSource))
```

---

## Detection Strategies

### Strategy 1: Name Pattern Matching

Extract base name and variant suffix from design titles:

```python
VARIANT_PATTERNS = [
    # Color variants
    re.compile(r"^(.+?)_(\d+color).*$", re.IGNORECASE),
    re.compile(r"^(.+?)_(multicolor|single|dual).*$", re.IGNORECASE),

    # Version variants
    re.compile(r"^(.+?)_(v\d+|version\s*\d+)$", re.IGNORECASE),
    re.compile(r"^(.+?)_(remix|remixed).*$", re.IGNORECASE),

    # Size variants
    re.compile(r"^(.+?)_(small|medium|large|xl|xxl)$", re.IGNORECASE),
    re.compile(r"^(.+?)_(\d+mm|\d+cm|\d+%)$", re.IGNORECASE),

    # Support variants
    re.compile(r"^(.+?)_(supported|nosupport|presupported)$", re.IGNORECASE),
]

def extract_family_info(title: str) -> tuple[str, str | None]:
    """Extract family base name and variant name from title.

    Returns:
        (base_name, variant_name) or (title, None) if no pattern matches
    """
    for pattern in VARIANT_PATTERNS:
        match = pattern.match(title)
        if match:
            return match.group(1), match.group(2)
    return title, None
```

**Example:**
| Input Title | Base Name | Variant Name |
|-------------|-----------|--------------|
| RoboTortoise_4Color_Multicolor | RoboTortoise | 4Color_Multicolor |
| Dragon_v2 | Dragon | v2 |
| Benchy_supported | Benchy | supported |

### Strategy 2: File Hash Overlap Detection

After download/extraction, compare file hashes between designs:

```python
async def detect_family_by_file_overlap(
    design: Design,
    min_overlap_ratio: float = 0.3,
    max_overlap_ratio: float = 0.9,  # >90% = duplicate, not variant
) -> list[tuple[Design, float]]:
    """Find designs with partial file overlap (variants, not duplicates).

    Returns designs that share 30-90% of files by hash.
    """
    design_hashes = {f.sha256 for f in design.files if f.sha256}

    # Query other designs with overlapping hashes
    candidates = await db.execute(
        select(Design, func.count(DesignFile.id).label("overlap_count"))
        .join(DesignFile)
        .where(
            DesignFile.sha256.in_(design_hashes),
            Design.id != design.id,
        )
        .group_by(Design.id)
    )

    results = []
    for other_design, overlap_count in candidates:
        other_total = len([f for f in other_design.files if f.sha256])
        overlap_ratio = overlap_count / max(len(design_hashes), other_total)

        if min_overlap_ratio <= overlap_ratio <= max_overlap_ratio:
            results.append((other_design, overlap_ratio))

    return results
```

### Strategy 3: AI-Assisted Detection

Extend the existing Gemini AI service to classify relationships:

```python
FAMILY_DETECTION_PROMPT = """
Analyze these design names and determine if they are variants of the same base design:

Design A: "{title_a}" by {designer_a}
Design B: "{title_b}" by {designer_b}

Consider:
- Do they share a base name with different suffixes?
- Are suffixes typical variant indicators (colors, versions, sizes, support options)?
- Could they be the same model with modifications?

Respond with JSON:
{
    "relationship": "VARIANT" | "DUPLICATE" | "UNRELATED",
    "base_name": "extracted base name if VARIANT",
    "variant_a": "variant suffix for A",
    "variant_b": "variant suffix for B",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}
"""
```

---

## API Endpoints

### Family Management

```
GET    /api/v1/families                  # List all families
GET    /api/v1/families/{id}             # Get family with variants
POST   /api/v1/families                  # Create family manually
PATCH  /api/v1/families/{id}             # Update family metadata
DELETE /api/v1/families/{id}             # Delete family (orphans designs)

# Family-design relationships
POST   /api/v1/families/{id}/designs     # Add design to family
DELETE /api/v1/families/{id}/designs/{design_id}  # Remove from family
```

### Design Endpoint Updates

```python
class DesignResponse(BaseModel):
    # ... existing fields ...

    # New family fields
    family_id: str | None
    family_name: str | None  # Computed from family if present
    variant_name: str | None
    sibling_count: int  # Number of other variants in same family
```

### Detection Endpoints

```
POST /api/v1/families/detect             # Run family detection on all designs
POST /api/v1/designs/{id}/detect-family  # Detect family for specific design
```

### Manual Grouping Endpoints

```
POST /api/v1/families/group              # Group designs into new/existing family
     Body: { design_ids: [...], family_name?: string, family_id?: string }

POST /api/v1/families/{id}/ungroup       # Remove design from family
     Body: { design_id: string }

DELETE /api/v1/families/{id}/dissolve    # Dissolve entire family (ungroup all)
```

---

## UI Changes

### Designs List View

Families display collapsed by default with expand/collapse toggle:

**Collapsed (default):**
```
┌────────────────────────────────────────────────────────┐
│ ▶ RoboTortoise (4 variants)              [Organized]  │
│   by MatMine Makes                                    │
└────────────────────────────────────────────────────────┘
```

**Expanded (on click):**
```
┌────────────────────────────────────────────────────────┐
│ ▼ RoboTortoise (4 variants)                           │
│   ├─ RoboTortoise_4Color_Multicolor    [Organized]   │
│   ├─ RoboTortoise_3Color_Multicolor    [Organized]   │
│   ├─ RoboTortoise_2Color_Multicolor    [Discovered]  │
│   └─ RoboTortoise_R                    [Discovered]  │
└────────────────────────────────────────────────────────┘
```

### Multi-Select Actions

When multiple designs are selected, show grouping actions:

```
┌─ 3 designs selected ───────────────────────────────────┐
│  [Group as Family]  [Add to Existing Family ▼]  [✕]   │
└────────────────────────────────────────────────────────┘
```

### Design Detail View

Add "Variants" section showing siblings with ungroup option:

```
┌─ RoboTortoise Family ──────────────────────────────────┐
│  ○ RoboTortoise_2Color_Multicolor                     │
│  ● RoboTortoise_4Color_Multicolor  (viewing)          │
│  ○ RoboTortoise_3Color_Multicolor                     │
│                                                        │
│  [Remove from Family]  [View All Variants ▸]          │
└────────────────────────────────────────────────────────┘
```

### Family Detail View (new page)

Accessed via "View All Variants" or from family row in list:

```
┌─ RoboTortoise Family ──────────────────────────────────┐
│  Designer: MatMine Makes                               │
│  Variants: 4                                           │
│  Tags: robotortoise, 4color, +18                       │
│                                                        │
│  ┌─ Variants ────────────────────────────────────────┐ │
│  │ [✓] RoboTortoise_4Color_Multicolor  [Organized]   │ │
│  │ [✓] RoboTortoise_3Color_Multicolor  [Organized]   │ │
│  │ [ ] RoboTortoise_2Color_Multicolor  [Discovered]  │ │
│  │ [ ] RoboTortoise_R                  [Discovered]  │ │
│  └───────────────────────────────────────────────────┘ │
│                                                        │
│  [Edit Family]  [Add Designs]  [Dissolve Family]      │
└────────────────────────────────────────────────────────┘
```

---

## Detection Workflow

### On Ingest (New Designs)

```python
async def process_new_design_family(design: Design):
    """Check if new design should join an existing family."""

    # 1. Try name pattern matching
    base_name, variant = extract_family_info(design.canonical_title)

    if variant:
        # Look for existing family with same base name
        family = await find_family_by_base_name(base_name, design.canonical_designer)

        if family:
            design.family_id = family.id
            design.variant_name = variant
            return

        # Look for existing designs that could form a family
        siblings = await find_designs_by_base_name(base_name, design.canonical_designer)

        if siblings:
            # Create new family
            family = await create_family_from_designs([design] + siblings)
            return

    # 2. File hash overlap (post-download only)
    # Handled in separate background job
```

### Background Detection Job

```python
class FamilyDetectionWorker(BaseWorker):
    """Background worker for detecting design families."""

    async def process(self, job: Job, payload: dict):
        """Run family detection on designs without families."""

        # Get designs without families
        orphans = await get_designs_without_family()

        for design in orphans:
            # Try name pattern
            candidates = await find_family_candidates_by_name(design)

            if not candidates and design.status in [ORGANIZED, DOWNLOADED]:
                # Try file hash overlap
                candidates = await detect_family_by_file_overlap(design)

            if candidates:
                # Create suggestion for user review
                await create_family_suggestion(design, candidates)
```

---

## Migration Plan

### Phase 1: Schema Addition
- Add `design_families` table
- Add `family_id` and `variant_name` to `designs`
- No existing functionality changes

### Phase 2: Detection Implementation
- Implement name pattern matching
- Add family detection to ingest pipeline
- Create suggestions table for user review

### Phase 3: API & UI
- Add family endpoints
- Update design responses with family info
- Build family management UI

### Phase 4: Advanced Detection
- File hash overlap detection (post-download)
- AI-assisted detection (optional)
- Batch processing for existing catalog

---

## Design Decisions

### 1. Tag Inheritance Strategy
**Decision**: Collect manual + Telegram tags from all variants; regenerate AI tags at family level.

- When designs are grouped into a family, all `MANUAL` and `AUTO` (from Telegram hashtags) tags are collected and applied to the family
- AI-generated tags are regenerated for the family using the best preview images from all variants
- This ensures no user-created tags are lost while keeping AI analysis coherent

### 2. Designer Matching Rule
**Decision**: Designers must match for variants to be grouped, with one exception.

- `"Unknown"` designer can match with any known designer (takes the known one)
- Different known designers = NOT variants, even if names match
- Example: "RoboTortoise by DesignerA" and "RoboTortoise by DesignerB" stay separate

```python
def designers_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if a == "Unknown" or b == "Unknown":
        return True
    return False
```

### 3. UI Grouping Behavior
**Decision**: Collapsed by default, click to expand.

- Families show as a single row with variant count badge
- Click expands to show all variants inline
- Reduces visual clutter for large libraries

### 4. Detection Strategy
**Decision**: Name patterns on ingest + file hash overlap as background job.

- **On ingest**: Run name pattern matching immediately (fast, catches "_2Color" style)
- **Post-download**: Background job for file hash overlap detection (catches non-obvious variants)
- **AI**: Optional future enhancement, not required for initial implementation

### 5. Migration Strategy
**Decision**: Auto-detect for existing catalog.

- Run family detection on all existing designs when feature is enabled
- Automatically create families where patterns match
- No manual confirmation required (user can ungroup if incorrect)

### 6. Manual Grouping/Ungrouping
**Decision**: Required feature - users must be able to manually manage families.

**Manual Group:**
- Select multiple designs in UI → "Group as Family"
- System prompts for family name (suggests extracted base name)
- Creates family, assigns selected designs as variants

**Manual Ungroup:**
- From family view → "Remove from Family" on individual variant
- Or "Dissolve Family" to ungroup all variants
- Ungrouped designs become standalone again (family_id = NULL)

---

## Related Work

- **DEC-041**: Deduplication Strategy - Handles true duplicates, this handles variants
- **Auto-tagging (v0.7)**: Family tags could feed into auto-tagging
- **AI Service**: Extend for relationship detection

---

## Next Steps

1. Review this proposal with stakeholders
2. Decide on open questions
3. Create GitHub issues for implementation
4. Add to roadmap (suggest: v1.1 or v1.2)
