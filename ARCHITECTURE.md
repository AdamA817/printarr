# ARCHITECTURE

## 1. High-Level Goals

- **Radarr-like UX** backed by reliable ingestion, cataloging, and download/import workflows.
- **Scales to hundreds of channels** and large files (100MB → multi-GB).
- **Resilient**: resumable jobs, safe retries, idempotent processing.
- **Self-hosted**: runs as a single Docker container on Unraid, with persistent volumes.

---

## 2. Proposed System Topology

A pragmatic approach is a **single deployable container** that runs multiple internal processes:

- **Web App (API + UI)**
- **Ingestion Worker** (Telegram monitoring + backfill)
- **Download/Import Worker** (download queue, extraction, library import)
- **Preview Worker** (3MF thumbnails, render tasks)

All workers share:
- a common **database**
- a common **job queue**
- a common **filesystem layout** (staging, library, cache)

This can be implemented as:
- a monorepo with a single backend service + worker processes, or
- separate internal services launched via a process supervisor (recommended for Docker simplicity).

---

## 3. Core Components

### 3.1 Web UI (Radarr-like)
Responsibilities:
- Browse/search designs (list + grid)
- Filter/sort views (especially “Undownloaded”)
- Channel management (add/remove channels, per-channel mode)
- Design details page (sources, images, file list, actions)
- Activity/queue (downloads, ingestion, renders)
- Settings (paths, modes, backfill rules)

### 3.2 API Server
Responsibilities:
- CRUD for channels, tags, design overrides
- Search endpoints (faceted search)
- Job submission endpoints (download, render, backfill)
- Status endpoints (queue, worker health)
- Webhook/stream updates to UI (SSE/WebSocket optional)

### 3.3 Telegram Client Adapter (MTProto)
Responsibilities:
- One-time interactive login (incl. 2FA)
- Persist session to volume
- Resolve channel from `t.me/<name>` or invite link
- Fetch history for backfill
- Subscribe to updates for new messages
- Normalize message + attachments into internal model

### 3.4 Ingestion Pipeline
Stages:
1) **Fetch** messages (historical or live)
2) **Extract** metadata:
   - caption, author (when available), channel, post date
   - attachments (documents/photos/videos)
3) **Identify** candidate “design posts”
4) **Upsert**:
   - message record
   - attachments record
   - design record (create or merge)
5) **Schedule** follow-up jobs:
   - attachment metadata fetch
   - preview import (Telegram images)
   - optional “suggested channels” scan

### 3.5 Job Queue + Workers
Required job types:
- `BACKFILL_CHANNEL` (paged history ingest)
- `SYNC_CHANNEL_LIVE` (subscription / polling)
- `DOWNLOAD_DESIGN` (download best source attachments)
- `EXTRACT_ARCHIVE` (zip/rar/7z extraction)
- `ANALYZE_3MF` (read plates/materials + extract thumbnails)
- `GENERATE_RENDER` (STL/3MF → preview images)
- `IMPORT_TO_LIBRARY` (move/rename into final structure)
- `DEDUPE_RECONCILE` (merge duplicates as new evidence arrives)

Queue requirements:
- Concurrency limits per worker type (e.g., download workers)
- Retry with backoff and max attempts
- Idempotent execution (safe to rerun)
- Progress reporting (bytes downloaded, %)
- Cancellation support (nice-to-have)

### 3.6 Storage Layout (inside container)
All are mapped to host volumes:

- `/config`  
  - app config, Telegram session, secrets
- `/data`  
  - database (if using SQLite) or local state
- `/staging`  
  - temp download location, extraction work area
- `/library`  
  - final organized library
- `/cache`  
  - thumbnails, renders, derived artifacts

All paths must be configurable via env or UI settings.

---

## 4. Data Flow

### 4.1 Channel Backfill
1. User adds channel link
2. API resolves link → Telegram peer
3. Create channel record + backfill config
4. Enqueue `BACKFILL_CHANNEL`
5. Worker fetches messages in pages and ingests
6. UI shows progress + “Discovered” count

### 4.2 Live Monitoring
1. Worker maintains subscriptions/polling
2. New message arrives → ingestion pipeline
3. Dedupe + catalog upsert
4. If channel mode is “download all new” or “download all”, enqueue downloads

### 4.3 Download + Import
1. User marks “Wanted” or channel policy triggers auto-download
2. Enqueue `DOWNLOAD_DESIGN`
3. Download attachments to `/staging/<designId>/raw`
4. If archives present, enqueue `EXTRACT_ARCHIVE`
5. Index extracted contents
6. Analyze 3MF + extract embedded previews
7. Import to `/library/<Designer>/<Channel>/<Title>/...`
8. Update status to Downloaded/Organized

### 4.4 Previews
- Telegram images are saved as “original previews”
- After download/import:
  - auto-generate renders for downloaded models
- For undownloaded:
  - user clicks “Generate preview” → job enqueued

---

## 5. Performance Strategy

- **Incremental backfill** with checkpointing (last message id, offsets)
- **Indexing-first**: ingest metadata without downloading large files until requested
- **Batch DB writes** for message ingestion
- **Queue throttling**:
  - per-channel ingest rate limits
  - max concurrent downloads
- **Lazy hashing**:
  - compute hashes after download, not at ingest time
- **Faceted search** backed by DB indexes:
  - (download_state, channel_id, designer, file_types, multicolor, tags, created_at)

---

## 6. Observability

Minimum:
- Structured logs for all job types (job id, design id, channel id)
- UI “Activity” page powered by job table
- Metrics (optional):
  - ingest throughput
  - download speed
  - queue depth
  - failures by type

---

## 7. External Metadata Enrichment

### 7.1 Thangs Adapter
A read-only enrichment service, fully decoupled from Telegram ingestion and download workflows.

Responsibilities:
- URL normalization (extract model ID from thangs.com URLs)
- Public metadata fetch via Thangs API
- Text search for manual linking
- Payload normalization to internal schema

API Endpoints (via Thangs public API):
- `api/models/v3/search-by-text` - Text search
- `api/search/v1/mesh-search` - Geometry search (future)
- Model detail pages - Metadata fetch

### 7.2 Metadata Enrichment Pipeline
Triggered by:
- Telegram link detection during ingestion (auto-link)
- User search/link action (manual)

Requirements:
- Non-blocking (failures don't stop ingestion)
- Retryable (transient failures can be retried)
- Reversible (links can be removed)

### 7.3 Data Flows

**Explicit Link (Auto-detect)**:
```
Telegram post → detect thangs.com URL → fetch metadata → auto-link → mark confirmed
```

**Manual Search**:
```
User search → candidate list → confirm → persist link
```

### 7.4 Failure Isolation
Thangs failures must not block:
- Telegram ingestion
- Downloads
- Library import

The system must continue operating normally if Thangs is unreachable.

### 7.5 Extensibility
Supports future metadata sources via adapter pattern:
- Printables adapter (future)
- Thingiverse adapter (future)

---

## 8. Extensibility Considerations

- "Suggested channels" feature should be implemented as a separate job scanning captions for `t.me/` links.
- Rendering should be pluggable (support different render engines).
- Library path templating should be configurable globally and per-channel.
- Metadata adapters follow a common interface for easy addition of new sources.
