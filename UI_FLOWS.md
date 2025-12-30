# UI_FLOWS (Radarr-like)

## 1. Navigation (Primary)

- Dashboard
- Designs
- Undownloaded
- Activity
- Channels
- Settings

---

## 2. Dashboard

**Purpose:** Quick status + recent activity.

Widgets:
- Telegram connection status (Connected / Needs login)
- Channels monitored (enabled/disabled)
- Designs discovered (total + last 24h)
- Download queue status (running, queued, failed)
- Recent additions (last 20 designs)

Actions:
- “Connect Telegram” (if not connected)
- “Add Channel”
- “View Activity”

---

## 3. Channels

### 3.1 Channel List
Columns:
- Name / Title
- Type (public/private)
- Enabled toggle
- Download mode (All / All New / Manual)
- Backfill mode summary
- Last sync time
- Errors indicator

Actions:
- Add channel (paste `t.me/...` link)
- Edit channel settings
- Trigger backfill now
- Disable monitoring
- Remove channel

### 3.2 Add Channel Flow
Steps:
1) Paste link (public username link or invite link)
2) Resolve and preview channel metadata (title, type)
3) Choose per-channel settings:
   - Enabled
   - Backfill mode/value
   - Download mode
   - Optional library template override
4) Save → enqueue backfill (if configured)

---

## 4. Designs (Main Browser)

### 4.1 Views
- Grid view (poster-like cards)
- List view (dense table)

### 4.2 Faceted Filters (left sidebar, Radarr style)
- Status:
  - Discovered
  - Wanted
  - Downloading
  - Downloaded
  - Organized
- Channels (multi-select)
- Designer (searchable dropdown)
- File types:
  - STL / 3MF / OBJ / STEP / ARCHIVE
- Multicolor:
  - Unknown / Single / Multi
- Tags (multi-select + search)
- Has previews (yes/no)
- Size range (optional)
- Date added range (optional)

Sorting:
- Date added (desc/asc)
- Title
- Designer
- File size
- Channel

Bulk actions:
- Mark Wanted
- Unmark Wanted
- Download (if manual)
- Generate preview (for selected, if eligible)
- Add/remove tags
- Change designer/title (bulk override; optional)

---

## 5. Undownloaded (Special View)

**Purpose:** Your “hunt list” + easy triage.

Default filter:
- Status in {Discovered, Wanted} AND not Downloaded/Organized

Extra quick filters:
- “Only with images”
- “Only multicolor”
- “Only 3MF”
- “Only from channel X”
- “Only > 200MB”
- “Only tagged (or untagged)”

Actions:
- Mark Wanted
- Download now
- Ignore (optional status: hidden/ignored; if implemented)

---

## 6. Design Detail Page

Header:
- Title (editable override)
- Designer (editable override; default Unknown)
- Status pill
- Multicolor pill (auto + override)
- Source count (how many channels/messages)

Tabs/Sections:

### 6.1 Overview
- Preview gallery (Telegram images + embedded + rendered)
- Key metadata:
  - Channels
  - Tags
  - File types
  - Total size (best source)
  - Date discovered
- Primary actions:
  - Mark Wanted / Unwanted
  - Download
  - Open in Telegram (if feasible)
  - Generate preview (if undownloaded)
  - Re-run analysis (post-download)

### 6.2 Sources
List of source messages:
- Channel name
- Post date
- Caption excerpt
- Attachments list
- “Preferred source” toggle
- Status per source (available, missing, failed, etc.)

### 6.3 Files
Shows:
- Staging files (if downloading)
- Extracted contents
- Library path (if imported)
- Hashes (if computed)
Actions:
- Re-extract archive
- Re-import to library
- Delete local copy (optional; may be dangerous)

### 6.4 Activity
- Job history scoped to this design (downloads, extracts, renders)
- Errors and retries

---

## 7. Activity (Queue)

Two panels:
- **Queue** (Running + Queued)
- **History** (Completed + Failed)

Columns:
- Job type
- Target (channel/design)
- Status
- Progress (bytes/%)
- Started/ended
- Retry count
- Error message (if failed)

Actions:
- Cancel job
- Retry failed
- Pause downloads globally (optional)

---

## 8. Settings

### 8.1 Telegram
- Session status
- Login/logout
- Device/session info (minimal)
- (If required) Telegram App ID/HASH configuration

### 8.2 Storage
- Staging path
- Library path
- Cache path
- Library template global
- Unknown designer label

### 8.3 Defaults
- Default backfill mode/value
- Default download mode for new channels
- Preview settings (max telegram images = 10)

### 8.4 Performance
- Max concurrent downloads
- Max concurrent extracts
- Max concurrent renders
- Retry policy knobs

---

## 9. UX Conventions (Radarr-Inspired)

- Sticky filter sidebar on browse pages
- Instant search box (title/designer/tags)
- Status icons/pills on cards/rows
- Bulk select + bulk actions toolbar
- Consistent “Wanted” toggle behavior across list/grid/detail views
