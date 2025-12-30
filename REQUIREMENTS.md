# Telegram 3D Design Catalog – Requirements

## 1. Overview

This project is a **self-hosted, web-based application** that monitors Telegram channels for 3D-printable designs, catalogs them, and allows browsing, filtering, and controlled downloading into a structured local library.

The application is inspired by the **Radarr/Sonarr UX paradigm**, adapted for 3D printing workflows.

**Primary goals:**
- Monitor Telegram channels (public and private) for 3D design files
- Backfill historical content and ingest new content continuously
- Build a searchable, deduplicated catalog
- Download designs into a structured local library on demand or automatically
- Preserve source attribution and metadata
- Support preview images and optional rendered previews

**Non-goals:**
- No public sharing or redistribution features
- No multi-user access control
- No DRM, legality enforcement, or rights verification

---

## 2. Target Environment

- **Deployment**: Docker container
- **Host platform**: Unraid
- **User model**: Single user
- **Authentication**: None (LAN-only usage assumed)

All storage paths must be configurable via Docker environment variables or volume mappings.

---

## 3. Telegram Integration Requirements

### 3.1 Connection Model
- The application **must use a Telegram user session (MTProto)**, not Bot API.
- Requires a **one-time login** using phone number and verification code.
- Must support Telegram accounts with **2FA passwords**.
- Session data must be persisted across container restarts via a Docker volume.

### 3.2 Channel Support
- Support **public channels** via `https://t.me/<channel>` links.
- Support **private/invite-only channels** if the Telegram account is a member.
- Users must be able to add/remove monitored channels at runtime.

### 3.3 Backfill & Monitoring
- Each channel must support:
  - Configurable historical backfill:
    - All history
    - Last N messages
    - Last N days
  - Continuous monitoring for new posts
- Backfill and monitoring must scale to **hundreds of channels** efficiently.

### 3.4 Source Suggestions (Future-Facing)
- The system should be designed to optionally:
  - Detect mentions/links to other Telegram channels
  - Suggest those channels for monitoring (manual approval required)

---

## 4. File & Content Support

### 4.1 File Types
The system must support (directly or within archives):

- `.stl`
- `.3mf`
- `.obj`
- `.step`
- `.zip`
- `.rar`
- `.7z`

### 4.2 Archives
- Archives must be downloaded, extracted, and indexed.
- Archive contents must be visible in the catalog **before and after download**.
- Archive extraction must support common folder structures and preserve filenames.
- Nested archives should be supported where practical.

### 4.3 Large File Handling
- Must support files ranging from small STLs to **multi-GB archives**.
- Downloads must be resumable and fault-tolerant.
- Downloads should be handled via a background job queue.

---

## 5. Catalog & Data Model Requirements

### 5.1 Design Identity
- A **Design** is a logical entity that may appear in multiple Telegram sources.
- Deduplication must:
  - Prefer file hashes when available
  - Fall back to filename + size + metadata heuristics
- A single catalog item may have **multiple sources**.

### 5.2 Metadata Fields
Each design must support:

- Design title
- Designer (optional / unknown supported)
- Source channel(s)
- Original Telegram message(s)
- File types present (STL, 3MF, etc.)
- Multicolor vs single-color classification
- Tags / keywords
- Post captions (raw + parsed)
- Download status
- Preview images

### 5.3 Tagging
- Automatic tagging from:
  - Captions
  - Filenames
  - File types
- Manual tag editing and overrides must be supported.

---

## 6. Multicolor Detection

### 6.1 Pre-Download
- Classification based on:
  - Presence of `.3mf`
  - Caption keywords (e.g., “AMS”, “multicolor”, “4 color”)

### 6.2 Post-Download
- `.3mf` files must be parsed to detect:
  - Multiple plates
  - Multiple materials/colors
- Post-download analysis may update classification automatically.

---

## 7. Preview & Media Handling

### 7.1 Telegram Images
- All images attached to a post must be captured.
- Up to **10 images per design** may be stored and displayed.

### 7.2 Embedded File Previews
- Extract embedded previews from `.3mf` files when present.

### 7.3 Rendered Previews
- For downloaded designs:
  - Preview renders should be generated automatically.
- For undownloaded designs:
  - Rendering must be user-initiated via a button.
- Rendering must be asynchronous and non-blocking.

---

## 8. Download & Library Management

### 8.1 Download Modes (Configurable Per Channel)
- Download all (immediate)
- Download all new
- Manual (“Wanted” workflow)

### 8.2 Workflow States
Designs should support the following lifecycle:

- Discovered
- Wanted
- Downloading
- Downloaded
- Organized

### 8.3 Storage Model
- Downloads must go to a **staging directory** first.
- After processing, files must be imported into the library.

### 8.4 Library Structure
Default structure:

```
<Library Root>/
  <Designer or Unknown>/
    <Channel>/
      <Design Title>/
        <files>
```

- Library structure must be **globally configurable**
- Channel-specific overrides must be supported
- Designs with unknown designers must be handled cleanly

---

## 9. Web UI Requirements

### 9.1 UX Principles
- Visual and interaction style inspired by **Radarr**
- Responsive, fast, filter-driven browsing
- Grid and list views

### 9.2 Core Screens
- Dashboard
- Channel management
- Design browser
- Undownloaded designs view
- Design detail page
- Activity / download queue
- Settings

### 9.3 Filters & Sorting
Must support filtering by:
- Download state
- Channel
- Designer
- File type
- Multicolor vs single-color
- Tags
- File size
- Date added

---

## 10. Configuration

All configuration must be possible via:
- Environment variables
- Config files mounted via Docker volumes
- UI-based settings (persisted)

Key configurable paths:
- Library root
- Download staging directory
- Preview/render cache

---

## 11. Performance & Scalability

- Must support:
  - Hundreds of channels
  - Tens of thousands of catalog items
  - Large concurrent downloads
- UI operations must not block ingestion or downloads.
- Background jobs must be queue-based and resumable.

---

## 12. Security & Safety

- No authentication required
- No resharing or public links
- Telegram session data must be stored securely
- System must not expose Telegram credentials via UI or logs

---

## 13. External Metadata Enrichment (Thangs)

### 13.1 Core Principles
- **Telegram = file source of truth**: All files come from Telegram channels
- **Printarr owns Design identity**: Canonical design records are maintained locally
- **Thangs = read-only metadata authority**: Enriches designs with authoritative metadata (IMDB/TMDB equivalent for 3D models)
- **User overrides always win**: Manual edits take precedence over all automated data
- **No automatic destructive merges**: System never silently overwrites user data

### 13.2 Supported Metadata Authorities
- **Primary**: Thangs (thangs.com)
- **Secondary (future)**: Printables, Thingiverse
- **Non-authoritative**: Patreon (designer attribution only)

### 13.3 Thangs Capabilities
Required metadata from Thangs:
- Designer name
- Canonical model title
- Preview images
- Tags/categories
- Canonical model URL

Explicitly excluded:
- Downloading files from Thangs
- File hash comparison
- Acting as binary/file authority

### 13.4 Matching Strategies
1. **Explicit Thangs link in Telegram** (auto-link, confidence=1.0)
   - Detect `thangs.com` URLs in captions during ingestion
   - Automatically link and fetch metadata
2. **Text search** (manual confirmation required)
   - User searches Thangs by title/designer
   - Must confirm match before linking
3. **Geometry match** (future, manual confirmation only)
   - Upload model to Thangs geometric search
   - Present candidates for user selection

### 13.5 Metadata Precedence
1. User overrides (highest priority)
2. Confirmed Thangs data
3. Auto-imported Thangs data (high confidence)
4. Telegram heuristics (lowest priority)

### 13.6 UI Requirements
- "Link to Thangs" action on design detail
- Thangs search modal with preview cards
- Confidence score indicators
- Ability to unlink/relink
- Clear provenance display (where metadata came from)

### 13.7 Non-Goals
- No public sharing or redistribution
- No authenticated Thangs scraping
- No background auto-merging without user visibility

---

## 14. Future Considerations (Non-Blocking)
- Channel suggestion system
- Printer profile awareness
- Slicer metadata extraction
- Export to slicer-friendly libraries
- Integration with NAS-based backup strategies
