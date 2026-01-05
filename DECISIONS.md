# Decisions Log

This document tracks key architectural and implementation decisions made during Printarr development.

Each decision is numbered and dated. Decisions can be revisited and superseded as the project evolves.

---

## Template

```markdown
### DEC-XXX: [Title]
**Date**: YYYY-MM-DD
**Status**: Accepted | Superseded by DEC-YYY | Reconsidering

**Context**
[What situation prompted this decision?]

**Options Considered**
1. Option A - [pros/cons]
2. Option B - [pros/cons]

**Decision**
[What we decided and why]

**Consequences**
[What this enables or constrains going forward]
```

---

## Decisions

### DEC-001: Backend Technology Stack
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need to choose a backend framework and language for the API server and workers.

**Options Considered**
1. Python/FastAPI - Excellent Telegram libraries (Telethon, Pyrogram), rapid development, good async support
2. TypeScript/Node - Same language as frontend, decent Telegram support (GramJS)
3. Go - High performance, but less mature Telegram libraries
4. Rust - Maximum performance, but slower development velocity

**Decision**
Python with FastAPI. The mature Telegram MTProto libraries (Telethon) are a significant advantage. FastAPI provides excellent async support and automatic API documentation.

**Consequences**
- Can use Telethon for reliable Telegram integration
- Team needs Python expertise
- Good ecosystem for file processing and background workers

---

### DEC-002: Frontend Technology Stack
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need to choose a frontend framework for the Radarr-style UI.

**Options Considered**
1. React + TypeScript - Most common, large ecosystem, similar to Radarr
2. Vue 3 + TypeScript - Simpler learning curve
3. Svelte/SvelteKit - Minimal bundle size
4. Next.js - Full-stack React with SSR

**Decision**
React with TypeScript. Matches the Radarr UX paradigm we're emulating, has the largest ecosystem for components we'll need (data grids, virtualized lists).

**Consequences**
- Rich component library ecosystem
- React Query for server state management
- TypeScript for type safety

---

### DEC-003: Development Workflow
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need to establish how agents coordinate work and track progress.

**Options Considered**
1. Linear flow - Architect creates issues → agent works → QA reviews → merge
2. Parallel sprints - Multiple agents work simultaneously
3. Kanban - Agents pull from backlog

**Decision**
Linear flow with GitHub Issues and Milestones. Architect creates issues with clear acceptance criteria, assigns to appropriate agent. QA reviews before merge.

**Consequences**
- Clear ownership of tasks
- Predictable workflow
- May be slower than parallel work, but more controlled

---

### DEC-004: Iterative Release Strategy
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need to decide between big-bang v1.0 release vs incremental versions.

**Options Considered**
1. Plan everything upfront → build → release v1.0
2. Incremental v0.x releases with feedback loops

**Decision**
Incremental v0.x releases (v0.1 through v0.9) building toward v1.0. Each version is deployable and testable, allowing course correction based on real usage.

**Consequences**
- Can test and adjust as we go
- Need to maintain deployability at each version
- More flexibility in feature prioritization
- ROADMAP.md tracks version scope

---

### DEC-005: Database Strategy
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need to choose database for development and production.

**Options Considered**
1. SQLite only - Simple, file-based, good for single-user
2. PostgreSQL only - More features, but heavier
3. SQLite for dev, PostgreSQL optional - Flexibility

**Decision**
SQLite as primary database. For a single-user self-hosted app on Unraid, SQLite is sufficient and simpler. SQLAlchemy ORM allows PostgreSQL upgrade path if ever needed.

**Consequences**
- Simple deployment (no separate DB container)
- File-based backup
- Some query limitations vs PostgreSQL
- Must use SQLAlchemy-compatible patterns

---

### DEC-006: Application Port
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need a default port for the web UI.

**Options Considered**
1. 7878 - Radarr-style (*arr convention)
2. 8080 - Common web app default
3. 3333 - Thematic (3D printing)

**Decision**
Port 3333. Memorable and thematic for a 3D printing application.

**Consequences**
- Easy to remember
- Unlikely to conflict with other services
- All documentation uses 3333

---

### DEC-007: Full Schema from Start
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Should we implement minimal database models and add fields later, or implement the full schema from DATA_MODEL.md upfront?

**Decision**
Implement full schema from DATA_MODEL.md even in v0.1. While the UI won't use all fields immediately, this avoids database migrations and rewrites as we add features.

**Consequences**
- More upfront work in v0.1
- No schema migrations needed in later versions
- Consistent data model throughout development
- UI can progressively use more fields

---

### DEC-008: Frontend Styling Setup
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Should we set up full styling (Tailwind, dark theme, Radarr colors) in v0.1, or keep it minimal and style properly later?

**Decision**
Full Tailwind + dark theme setup from v0.1. Establish the Radarr-inspired visual language early so all components follow it.

**Consequences**
- Consistent look from the start
- Component patterns established early
- More upfront work in v0.1
- Avoids restyling later

---

### DEC-009: Development Environment
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Should we have separate dev configurations with hot-reload, or use production-like single container for development?

**Decision**
Production-like single container. Rebuild to test changes. Keeps dev/prod parity high and simplifies the setup.

**Consequences**
- Slower iteration (rebuild required)
- Higher confidence that dev matches prod
- Simpler Docker configuration
- May revisit if rebuild times become painful

---

### DEC-010: Unraid Deployment Approach
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need a way to build and deploy during development on Unraid.

**Options Considered**
1. Build locally, push to container registry, pull on Unraid
2. Build locally, docker save/scp/load to Unraid
3. Clone repo on Unraid, build directly there

**Decision**
Clone repo on Unraid and build directly. A deploy script on the Unraid server will:
- `git pull` to get latest code
- `docker build` to build the image
- Deploy/restart the container with config from a local config file

**Consequences**
- Simple workflow: push to GitHub, SSH to Unraid, run deploy script
- No container registry needed
- Unraid needs git installed (usually available)
- Build happens on Unraid (may be slower than Mac, but avoids transfer)

---

### DEC-011: API Trailing Slash Convention
**Date**: 2024-12-29
**Status**: Accepted

**Context**
A bug occurred where backend routes used `/channels/` but frontend called `/channels`, causing 404 errors. Need a consistent convention.

**Decision**
Always use trailing slashes for collection endpoints:
- `GET /api/v1/channels/` (list)
- `POST /api/v1/channels/` (create)
- `GET /api/v1/channels/{id}` (no trailing slash for single resource)
- `PUT /api/v1/channels/{id}` (no trailing slash for single resource)
- `DELETE /api/v1/channels/{id}` (no trailing slash for single resource)

Additionally, FastAPI should be configured with `redirect_slashes=True` as a safety net.

**Consequences**
- Consistent URL patterns across frontend and backend
- Less debugging of routing issues
- Documentation must reflect this convention

---

### DEC-012: Integration Testing Before Issue Closure
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Agents were testing in isolation (frontend with mocks, backend with curl). Bugs only appeared when components were integrated.

**Decision**
Before closing any issue that involves API endpoints:
- Backend Dev: Verify endpoints work via OpenAPI docs or curl
- Web Dev: Test against running backend, not just TypeScript compilation
- QA: Run integration checks across frontend and backend
- DevOps: Verify deployment with browser console check

**Consequences**
- Catches integration bugs before issues are closed
- Slightly slower issue completion
- Higher quality at each handoff

---

### DEC-013: Telegram Client Library
**Date**: 2024-12-29
**Status**: Accepted

**Context**
Need to choose a Python MTProto client library for Telegram integration. The library will handle user authentication, channel resolution, message retrieval, and file downloads.

**Options Considered**
1. **Telethon** - 11.6k stars, 27 open issues, created 2016
   - Pros: Most popular, mature, excellent documentation, large community, very few open issues
   - Cons: None significant

2. **Pyrogram** - 4.6k stars, 283 open issues, created 2017
   - Pros: Modern "Pythonic" API, good documentation
   - Cons: 10x more open issues, smaller community

**Decision**
Telethon. The maturity, community size, and low issue count indicate better stability and support. Both libraries have similar async capabilities, but Telethon's battle-tested nature makes it the safer choice for production use.

**Consequences**
- Use `telethon` package for all Telegram interactions
- Session files stored in /config volume
- Async integration with FastAPI via shared event loop
- Documentation at docs.telethon.dev for implementation reference

---

### DEC-014: External Metadata Integration Strategy
**Date**: 2025-12-30
**Status**: Accepted

**Context**
v0.3 introduces external metadata enrichment (starting with Thangs). Need to decide how to integrate external metadata sources with the Telegram ingestion pipeline.

**Options Considered**
1. Synchronous fetch - Block ingestion until external metadata retrieved
2. Async fetch - Ingest immediately, fetch metadata in background
3. Detect only - Store URLs, no automatic fetch

**Decision**
Async fetch with graceful degradation:
- Detect external URLs (thangs.com, printables.com, thingiverse.com) during ingestion
- For Thangs: Async fetch metadata, don't block ingestion
- For Printables/Thingiverse: Store URL only (fetch in future version)
- On API failure: Store URL, queue retry job
- External metadata never overwrites user overrides

**Consequences**
- Ingestion pipeline remains fast and resilient
- Thangs failures don't block catalog growth
- Phased rollout: Thangs first, other sources later
- Need retry mechanism for failed fetches

---

### DEC-015: Design-to-Message Relationship
**Date**: 2025-12-30
**Status**: Accepted

**Context**
Need to define how Telegram messages map to Design catalog entries.

**Options Considered**
1. One Design per message (all attachments grouped)
2. One Design per attachment (split files)
3. User-configurable per channel

**Decision**
One Design per Telegram message (default). All attachments from a single message belong to one Design. This matches how creators typically post - multiple STL files for one model in a single message.

Future consideration: Allow splitting/merging when needed, but start simple.

**Consequences**
- Simpler initial implementation
- Matches typical posting patterns
- May need merge/split features later for edge cases
- DesignSource provides 1:1 link between Design and TelegramMessage

---

### DEC-016: FlareSolverr for Cloudflare Bypass
**Date**: 2025-12-30
**Status**: Accepted

**Context**
Thangs API (thangs.com) uses Cloudflare protection that blocks server-side HTTP requests. Direct API calls return a JavaScript challenge page instead of JSON data, causing 502 errors in our Thangs integration.

**Options Considered**
1. **Accept limitation** - Disable search, only support manual URL pasting
   - Pros: No additional dependencies
   - Cons: Poor UX, no search functionality

2. **FlareSolverr proxy** - Route requests through FlareSolverr (headless browser)
   - Pros: Works with existing Unraid *arr stack, solves Cloudflare challenges
   - Cons: Additional container, ~200MB RAM per request

3. **Official API access** - Contact Thangs/Physna for API keys
   - Pros: Proper solution, no workarounds
   - Cons: Unknown availability, timeline

**Decision**
Use FlareSolverr as an optional proxy for Thangs API requests:
- Add `FLARESOLVERR_URL` environment variable (optional)
- If configured, route Thangs requests through FlareSolverr
- If not configured, fall back to direct requests (may fail with Cloudflare)
- Graceful degradation: URL detection always works, only API calls need proxy

**Implementation Notes**
- Correct Thangs search endpoint: `https://thangs.com/api/models/v3/search-by-text`
- FlareSolverr API: `POST http://{host}:8191/v1` with `{"cmd":"request.get","url":"..."}`
- Response contains solved HTML/JSON in `solution.response`
- Parse JSON from response body for API data

**Consequences**
- Thangs search and metadata fetch will work when FlareSolverr is configured
- Users on Unraid likely already have FlareSolverr for Prowlarr/Jackett
- No hard dependency - feature degrades gracefully without it
- Documentation must explain FlareSolverr setup

---

### DEC-017: Job Queue Implementation
**Date**: 2025-12-30
**Status**: Accepted

**Context**
v0.5 introduces the download workflow, requiring a robust job queue for background tasks (downloads, extraction, library import). Need to choose between custom database-backed queue vs external solutions.

**Options Considered**
1. **Database-backed queue (custom)** - Simple, no external deps, SQLite storage, matches Radarr pattern
2. **ARQ (Redis)** - Proven async library, requires adding Redis container
3. **Celery** - Enterprise-grade, heavy, requires Redis or RabbitMQ

**Decision**
Database-backed queue. Rationale:
- No additional containers/dependencies
- SQLite storage keeps deployment simple (Unraid-friendly)
- Matches the *arr ecosystem pattern users expect
- Job model already exists with all needed fields
- Can implement priority-based scheduling (user preference)

**Implementation Notes**
- Use existing Job model with `status`, `priority`, `attempts` fields
- Worker process polls for QUEUED jobs ordered by priority, created_at
- Support exponential backoff on retry
- Separate worker pools for different job types (downloads, extraction)

**Consequences**
- Simpler deployment (no Redis/RabbitMQ)
- Must implement polling logic manually
- Performance sufficient for single-user self-hosted use case
- May need optimization if scaling beyond expected load

---

### DEC-018: Download Workflow Configuration
**Date**: 2025-12-30
**Status**: Accepted

**Context**
v0.5 needs decisions on download priority model, library folder structure, and archive handling.

**Decisions Made**

1. **Download Priority**: Priority-based from the start
   - Jobs have integer `priority` field (higher = more urgent)
   - Default priority: 0
   - User can adjust priority per design
   - Queue ordered by: priority DESC, created_at ASC

2. **Library Folder Structure**: Configurable templates
   - Global default: `/<DesignerOrUnknown>/<Channel>/<DesignTitle>/`
   - Per-channel override via `library_template_override` field (already in Channel model)
   - Template variables: `{designer}`, `{channel}`, `{title}`, `{date}`, `{status}`
   - Settings UI to modify global template

3. **Archive Cleanup**: Delete after extraction
   - Default behavior: Remove original archives after successful extraction
   - Saves disk space (archives can be re-downloaded)
   - Future consideration: Make this configurable if users request it

**Consequences**
- Priority system adds complexity but improves UX
- Template configuration requires settings storage/UI
- Archive deletion may frustrate some users (document clearly)

---

### DEC-019: SQLite Concurrency - Session-Per-Operation Pattern
**Date**: 2025-12-31
**Status**: Resolved

**Context**
During v0.5 E2E testing, critical database locking issues were discovered when using SQLite with async workers. When the download worker performs long-running file downloads from Telegram, it holds a database connection open, blocking:
- Other workers from picking up jobs
- API requests to update/cancel jobs
- Maintenance tasks like requeuing stale jobs

Despite WAL mode and busy_timeout settings, SQLite's write lock architecture fundamentally conflicts with long-running async operations.

**Options Considered**
1. **Refactor to release connection during I/O** - Download files outside of database session, only use DB briefly for status updates
2. **Switch to PostgreSQL** - Better concurrent write support, more complexity
3. **Serialize workers** - Only run one worker at a time, simplest but slowest
4. **Use connection pooling differently** - Separate pools for workers vs API

**Decision**
Option 1: Session-per-operation pattern. The download service was refactored to:
1. Open brief session to read design/attachment info, commit, close
2. Download files with NO database session held
3. Open brief session to record success/failure, commit, close

This pattern applies to all long-running I/O operations.

**Implementation**
- `DownloadService.download_design()` uses `async_session_maker()` for brief operations only
- `AttachmentDownloadInfo` dataclass holds plain data (not ORM objects) for use outside sessions
- Each phase (read, download, write) uses independent sessions
- `BaseWorker` commits after claiming job before calling `process()`

**Verification**
E2E testing confirmed:
- Priority updates work during active downloads
- Job cancellation works during active downloads
- Multiple workers can process jobs concurrently
- API remains responsive during large file downloads

**Consequences**
- SQLite remains viable for single-user self-hosted use case
- Pattern must be followed for any future long-running operations
- Slightly more complex code, but clear phase separation

---

### DEC-020: Live Monitoring Strategy
**Date**: 2025-12-30
**Status**: Accepted

**Context**
v0.6 introduces live channel monitoring - automatically detecting new posts in Telegram channels. Need to decide between polling (check periodically), real-time (Telethon event handlers), or hybrid approach.

**Options Considered**
1. **Polling only** - Periodically check each channel for new messages (every N minutes)
   - Pros: Simple, works reliably, no persistent connection needed
   - Cons: Delay between post and detection, more API calls

2. **Real-time only** - Use Telethon's event handlers to receive updates instantly
   - Pros: Near-instant detection, fewer API calls
   - Cons: Requires persistent connection, reconnection handling

3. **Hybrid** - Real-time when connected, poll on reconnect to catch missed messages
   - Pros: Best of both worlds - instant when connected, catch-up on reconnect
   - Cons: More complex implementation

**Decision**
Hybrid approach with fixed-interval polling:
- Use Telethon event handlers for real-time new message detection
- On reconnection, poll all channels to catch messages missed during disconnect
- Fixed polling interval (configurable, default 5 minutes) for all channels
- Poll interval applies to catch-up sync, not continuous monitoring

**Implementation Notes**
- `SyncService` handles real-time subscriptions via `@client.on(events.NewMessage)`
- On client disconnect/reconnect, query `last_ingested_message_id` to fetch missed messages
- Environment variable `PRINTARR_SYNC_POLL_INTERVAL` for configurable interval
- Consider rate limiting to avoid Telegram flood wait

**Consequences**
- Near-instant design detection during normal operation
- Resilient to connection drops
- Must handle Telethon reconnection events properly
- Worker process must maintain long-running connection

---

### DEC-021: Channel Discovery Data Model
**Date**: 2025-12-30
**Status**: Accepted

**Context**
v0.6 introduces channel discovery - tracking channels referenced in monitored content (forwards, mentions, links) so users can easily find and add related channels.

**Options Considered**
1. **Dedicated table** - New `DiscoveredChannel` table with reference_count, last_seen, etc.
   - Pros: Clean separation, queryable fields, flexible schema
   - Cons: More tables to maintain

2. **Extend Channel model** - Add `is_discovered` flag to existing Channel model
   - Pros: Single model for all channels
   - Cons: Mixes monitored/discovered concepts, clutters model

3. **Lightweight JSON** - Store references in a JSON field
   - Pros: Minimal schema change
   - Cons: Hard to query, no relationships

**Decision**
Dedicated `DiscoveredChannel` table with the following design:
- Separate from `Channel` model (discovered channels are NOT monitored)
- Store: `telegram_peer_id`, `title`, `username`, `reference_count`, `last_seen_at`, `first_seen_at`
- Track sources: forwarded messages, @mentions, t.me/ links in captions, links in message text
- When user adds a discovered channel, create proper `Channel` record and optionally delete discovered entry

**Detection Sources** (all enabled for v0.6):
1. Forwarded messages (`message.fwd_from.chat`)
2. t.me/ links in captions
3. @mentions in captions
4. t.me/ links in message text

**UI Location**
Tab on Channels page: "Monitored" (existing) and "Discovered" (new) tabs.

**Consequences**
- Clean data model separation
- Easy to show reference counts and discovery metadata
- One-click "Add Channel" converts discovered to monitored
- Need to handle deduplication (same channel discovered multiple ways)

---

### DEC-022: Auto-Download Mode Behavior
**Date**: 2025-12-30
**Status**: Accepted

**Context**
The `DownloadMode` enum has three values: `MANUAL`, `DOWNLOAD_ALL_NEW`, `DOWNLOAD_ALL`. Need to clarify exact behavior for each mode.

**Decision**
- **MANUAL**: No automatic downloads. User must explicitly trigger download for each design.
- **DOWNLOAD_ALL_NEW**: Only auto-download designs detected AFTER the mode is enabled. Existing DISCOVERED designs remain in DISCOVERED status until manually downloaded.
- **DOWNLOAD_ALL**: One-time bulk queue of all existing DISCOVERED designs, PLUS auto-download all future designs. Acts like DOWNLOAD_ALL_NEW after initial queue.

**Rationale**
- DOWNLOAD_ALL_NEW is "prospective" - users enable it when they want new content going forward
- DOWNLOAD_ALL is "retroactive + prospective" - users want everything from this channel
- This prevents surprise bulk downloads when enabling DOWNLOAD_ALL_NEW

**Consequences**
- Clear user expectations for each mode
- DOWNLOAD_ALL needs confirmation dialog (may queue many downloads)
- UI should show counts (e.g., "This will queue 47 existing designs")

---

### DEC-023: Dashboard Design for v0.6
**Date**: 2025-12-30
**Status**: Accepted

**Context**
v0.6 includes a dashboard. Need to decide scope for initial implementation.

**Options Considered**
1. **Minimal** - Total designs, downloads today, active channels count
2. **Radarr-style** - Calendar view, storage stats, queue summary
3. **Analytics-focused** - Graphs over time, per-channel stats

**Decision**
Radarr-style dashboard with:
- **Calendar view**: Recent additions by date (last 7-14 days)
- **Storage stats**: Library size, staging size, total designs count
- **Queue summary**: Active downloads, queued count, recent completions
- **Quick actions**: Resume paused, clear completed

This provides visual overview similar to Radarr/Sonarr dashboards without complex analytics.

**Consequences**
- More UI work than minimal approach
- Need API endpoints for aggregated stats
- Calendar component required (use existing React calendar library)
- Storage calculation needs efficient implementation (cache results)

---

### DEC-024: Telethon SQLite Session Concurrency
**Date**: 2025-12-31
**Status**: Resolved

**Context**
During v0.6 implementation, Telethon's SQLite session file (`telegram.session`) experienced "database is locked" errors. This occurred because multiple async operations accessed the session file concurrently (auth check, channel resolution, message retrieval). Unlike the application database (DEC-019), Telethon manages its own session storage internally.

**Root Cause**
Telethon's `SQLiteSession` uses default SQLite settings that don't handle concurrent access well:
- No WAL mode (uses default journal mode)
- No busy_timeout (fails immediately on lock)
- Multiple coroutines calling client methods simultaneously

**Options Considered**
1. **External lock** - Add asyncio.Lock to serialize all Telethon operations
   - Pros: Simple, prevents all concurrent access
   - Cons: Performance bottleneck, doesn't fix underlying session issue

2. **WAL mode + busy_timeout** - Configure SQLite for better concurrency
   - Pros: Allows concurrent readers, handles lock contention gracefully
   - Cons: Requires subclassing Telethon's session class

3. **Combined approach** - Both external lock AND improved session configuration
   - Pros: Defense in depth, handles edge cases
   - Cons: More code, may be overkill

**Decision**
Combined approach with:
1. **`WalSqliteSession`** - Custom subclass of `SQLiteSession` that applies:
   - `PRAGMA busy_timeout = 30000` (30s wait on lock)
   - `PRAGMA journal_mode = WAL` (better concurrent access)

2. **Asyncio Lock** - Added `self._lock` to `TelegramService`, applied to ALL client methods:
   - `is_authenticated()`
   - `get_current_user()`
   - `start_auth()`
   - `complete_auth()`
   - `logout()`
   - `resolve_channel()`
   - `get_messages()`

**Implementation Notes**
- If session file becomes corrupted, delete `telegram.session*` files and re-authenticate
- Channel resolution after session reset requires username fallback (see DEC-025)

**Consequences**
- Telethon operations are now serialized but resilient
- Slight performance impact from locking, acceptable for single-user app
- Session file survives concurrent access without corruption

---

### DEC-025: Channel Resolution After Session Reset
**Date**: 2025-12-31
**Status**: Resolved

**Context**
After fixing Telethon session locking (DEC-024), deleting the corrupted session file caused a new issue: channels could no longer be resolved by numeric peer ID. Telethon's `get_entity()` requires the entity to be in its local cache when using numeric IDs.

**Root Cause**
Telethon caches entity metadata (username, access_hash) in the session file. After session reset:
- Numeric IDs like `1234567890` can't be resolved (no cached access_hash)
- Usernames like `@channelname` CAN be resolved (public lookup)

**Decision**
Modified `get_channel_messages` endpoint to look up channel username from the Printarr database:
1. If channel has a stored `username`, use that for resolution
2. Fall back to numeric peer ID if no username available
3. Original numeric ID preserved for database queries

**Implementation**
```python
# Look up channel in database to get username
db_channel = await db.scalar(
    select(Channel).where(Channel.telegram_peer_id == str(channel_id))
)
if db_channel and db_channel.username:
    channel_identifier = db_channel.username  # Use username instead
```

**Consequences**
- Channels with stored usernames work after session reset
- Channels without usernames (private/invite-only) may fail until re-cached
- Encourages storing username during channel addition

---

### DEC-026: Preview Rendering Engine
**Date**: 2025-12-31
**Status**: Accepted

**Context**
v0.7 introduces preview image generation for downloaded STL/3MF files. Need to choose a rendering approach that balances quality, performance, and deployment simplicity.

**Options Considered**
1. **stl-thumb** - Rust CLI tool, fast, simple, basic renders
2. **OpenSCAD** - Mature, headless rendering, more control
3. **Three.js server-side** - Node process, high quality, more complex
4. **Blender headless** - Best quality, heaviest resource usage
5. **Skip for v0.7** - Only use Telegram/Thangs images, defer rendering

**Decision**
stl-thumb. Rationale:
- Single binary, easy to add to Docker image
- Fast rendering (< 1s per model)
- Sufficient quality for catalog thumbnails
- No additional runtime dependencies (Node, Python, etc.)
- Can upgrade to better renderer later if needed

**Implementation**
- Render resolution: 400×400px
- Output format: PNG
- Trigger: POST_DOWNLOAD_ANALYSIS job

**Consequences**
- Simple deployment
- May need upgrade for complex models with materials/colors
- Can be replaced with better renderer in future version

---

### DEC-027: Preview Image Storage Strategy
**Date**: 2025-12-31
**Status**: Accepted

**Context**
Need to decide where to store preview images (Telegram, Thangs, archive, rendered).

**Options Considered**
1. **Filesystem** - `/cache/previews/` directory, served via static route
2. **Database BLOBs** - Simpler backup, slower for large images
3. **Object storage** - S3-compatible, overkill for single-user

**Decision**
Filesystem storage at `/cache/previews/` with subdirectories by source:
```
/cache/previews/
├── telegram/{design_id}/
├── archive/{design_id}/
├── thangs/{thangs_model_id}/
├── embedded/{design_id}/
└── rendered/{design_id}/
```

**Consequences**
- Matches existing volume mount pattern (/cache is already mounted)
- Easy to browse/debug
- Requires static file serving route in FastAPI
- Backup requires including /cache volume

---

### DEC-028: Tag Taxonomy
**Date**: 2025-12-31
**Status**: Accepted

**Context**
Need to decide how tags should be organized - free-form vs structured categories.

**Options Considered**
1. **Free-form** - Any string, user creates tags as needed
2. **Hierarchical categories** - Predefined categories only
3. **Hybrid** - Predefined categories + free-form custom tags

**Decision**
Hybrid approach:
- Predefined categories with suggested values: Type, Theme, Scale, Complexity, Print Type
- Free-form tags without category for custom organization
- Tags normalized to lowercase for deduplication
- Max 20 tags per design

**Predefined Categories**
```python
TAG_CATEGORIES = {
    "Type": ["Figure", "Bust", "Diorama", "Miniature", "Cosplay", "Prop", "Tool", "Art"],
    "Theme": ["Sci-Fi", "Fantasy", "Horror", "Anime", "Gaming", "Movie", "Comic"],
    "Scale": ["28mm", "32mm", "75mm", "1:6", "1:10", "Life Size"],
    "Complexity": ["Simple", "Moderate", "Complex", "Expert"],
    "Print Type": ["FDM", "Resin", "Both"],
}
```

**Consequences**
- Flexible for users while providing structure
- Autocomplete can suggest predefined tags
- Category filtering possible in future
- May need tag cleanup/merge features later

---

### DEC-029: Multicolor Detection Strategy
**Date**: 2025-12-31
**Status**: Accepted

**Context**
Need to detect whether designs are multicolor (MMU/AMS compatible) for filtering.

**Options Considered**
1. **Filename only** - Keywords in filenames/captions
2. **3MF inspection** - Parse 3MF for multiple materials
3. **Both** - Combine heuristics + 3MF parsing

**Decision**
Both approaches, applied at different stages:

**Heuristic Detection (during ingestion)**
Keywords: "multicolor", "multi-color", "MMU", "AMS", "IDEX", "dual color", "multi material", "[N] color"

**3MF Analysis (post-download)**
Parse 3MF XML for multiple `<basematerials>` entries or different `materialid` references.

**Data Model**
- `is_multicolor`: Boolean on Design
- `multicolor_source`: HEURISTIC | 3MF_ANALYSIS | USER_OVERRIDE

**Consequences**
- Early detection for filtering before download
- Accurate confirmation after download
- User can override if detection is wrong

---

### DEC-030: Telegram Image Download Strategy
**Date**: 2025-12-31
**Status**: Accepted

**Context**
When should Telegram preview images (photos attached to posts) be downloaded?

**Options Considered**
1. **During ingestion** - Download immediately when design created
2. **On-demand** - Download when user views design detail
3. **Background job** - Queue separate job for image downloads

**Decision**
Background job approach:
- During ingestion, detect if message has photos
- Create `DOWNLOAD_TELEGRAM_IMAGES` job
- ImageWorker processes jobs asynchronously
- Keeps ingestion fast and decoupled

**Consequences**
- Ingestion remains fast even with many photos
- Images may not be immediately available
- Need new worker/job type
- Better resilience to Telegram rate limits

---

### DEC-031: Archive Preview Extraction
**Date**: 2025-12-31
**Status**: Accepted

**Context**
Many archives contain preview images (preview.jpg, images/ folder, etc.) that should be extracted and displayed.

**Decision**
During archive extraction (download phase), scan for preview images:

**Detection Patterns** (priority order)
1. Explicit files: `preview.*`, `thumbnail.*`, `cover.*`, `render.*`
2. Preview folders: `images/`, `previews/`, `renders/`, `photos/`
3. Root-level images: `*.jpg`, `*.png`, `*.gif`, `*.webp`

**Limits**
- Max 10 preview images per archive
- Skip images < 10KB (likely icons)
- Skip images > 10MB (likely source renders)

**Storage**
- Extract to `/cache/previews/archive/{design_id}/`
- Create DesignPreview records with `source=ARCHIVE`

**Consequences**
- Designer-provided previews available without manual upload
- May extract irrelevant images (logos, instructions)
- Adds processing time to extraction phase

---

### DEC-032: Primary Preview Selection
**Date**: 2025-12-31
**Status**: Accepted

**Context**
Designs may have multiple preview images from different sources. Need to determine which is shown as the primary/card image.

**Decision**
Auto-select based on source priority, with manual override:

**Priority Order** (highest to lowest)
1. RENDERED - We generated it, best quality
2. EMBEDDED_3MF - Designer's intended preview
3. ARCHIVE - Designer included it
4. THANGS - Authoritative external source
5. TELEGRAM - Channel post image (may be unrelated)

**Implementation**
- Auto-select runs when previews are added
- User can manually set any preview as primary via UI
- Manual selection persists (not overwritten by auto)

**Consequences**
- Reasonable defaults without user intervention
- User has full control when needed
- May need "reset to auto" option

---

### DEC-033: Manual Import Source Types
**Date**: 2026-01-02
**Status**: Accepted

**Context**
v0.8 introduces importing designs from sources beyond Telegram. Need to define the supported import source types and their capabilities.

**Options Considered**
1. **Google Drive only** - Most common for Patreon creators
2. **File upload only** - Simplest, no API dependencies
3. **Multiple sources** - Google Drive + Upload + Bulk folders

**Decision**
Support three import source types:

1. **Google Drive** - For Patreon/creator shared folders
   - Public links (no auth required)
   - Authenticated access (OAuth flow for private folders)
   - Periodic sync to detect new files
   - Support both folder and file links

2. **Direct Upload** - For one-off files
   - Single file or archive upload
   - Drag-and-drop in UI
   - Extract archives and detect designs

3. **Bulk Folder** - For existing local collections
   - Monitor configured directories
   - Multiple paths supported
   - Import on startup + watch for changes

**Data Model**
```python
class ImportSourceType(Enum):
    GOOGLE_DRIVE = "google_drive"
    UPLOAD = "upload"
    BULK_FOLDER = "bulk_folder"

class ImportSource(Base):
    id: UUID
    name: str
    source_type: ImportSourceType
    google_drive_url: str | None
    google_credentials_id: UUID | None
    folder_path: str | None
    import_profile_id: UUID | None
    default_designer: str | None
    default_tags: list[str]
    sync_enabled: bool
    sync_interval_hours: int
    last_synced_at: datetime | None
```

**Consequences**
- Covers main use cases (Patreon, manual imports, existing libraries)
- Google Drive requires API credentials configuration
- Bulk folder needs file system watcher
- Each source type has different sync behavior

---

### DEC-034: Google Drive Integration Strategy
**Date**: 2026-01-02
**Status**: Accepted

**Context**
Google Drive is the primary distribution method for Patreon creators. Need to decide authentication approach and folder traversal strategy.

**Options Considered**
1. **Public links only** - Use web scraping or direct download URLs
2. **OAuth only** - Full API access, requires user authentication
3. **Both** - Public links when possible, OAuth for restricted folders

**Decision**
Support both public and authenticated access:

**Public Links**
- Parse shared folder links (`drive.google.com/drive/folders/...`)
- Use Google Drive API with API key (no user auth)
- Works for "Anyone with link" shares

**Authenticated Access**
- OAuth 2.0 flow for user's Google account
- Store refresh tokens securely in database
- Required for private/restricted folders
- One-time setup per Google account

**Token Storage**
```python
class GoogleCredentials(Base):
    id: UUID
    email: str  # Google account email
    access_token: str  # Encrypted
    refresh_token: str  # Encrypted
    token_expiry: datetime
    created_at: datetime
```

**Sync Behavior**
- Configurable interval (default: 1 hour)
- Full folder traversal on each sync
- Track last sync time and file modification dates
- Skip already-imported files (by path + size)

**Consequences**
- Public links work out of the box
- OAuth requires app credentials in Google Cloud Console
- Must handle token refresh and expiration
- Documentation needed for OAuth setup

---

### DEC-035: Import Profile System
**Date**: 2026-01-02
**Status**: Accepted

**Context**
Different creators organize their files differently. Need a flexible system to detect designs within various folder structures.

**Known Folder Patterns**
1. **Yosh Studios**: `Tier Folder/Design Name/STLs/*.stl` + `*.3mf` at root
2. **Generic Supported/Unsupported**: `Design/Supported/*.stl` + `Design/Unsupported/*.stl`
3. **Flat structure**: All model files directly in folder
4. **Nested with renders**: `Design/Models/*.stl` + `Design/Renders/*.png`

**Decision**
Configurable Import Profiles with:

**Profile Scope**
- Universal default profile (applies to all sources)
- Override per import source (channel-level)
- Override per link (specific folder)

**Profile Configuration**
```yaml
name: "Yosh Studios"
design_detection:
  rules:
    - has_extension: [".3mf"]
    - has_subfolder: ["STLs", "stls", "Models"]
  mode: "any"  # any rule matches = design

title:
  source: "folder_name"  # Use folder name as design title

model_subfolders:
  - "STLs"
  - "stls"
  - "Models"
  - "Supported"
  - "Unsupported"

preview_subfolders:
  - "Renders"
  - "*Renders"  # Wildcard: "4K Renders", "Preview Renders"
  - "Images"
  - "Photos"

ignore_folders:
  - "Lychee"
  - "Chitubox"
  - "Project Files"
  - "Source"

ignore_extensions:
  - ".lys"
  - ".ctb"
  - ".gcode"
  - ".blend"

auto_tags:
  - level: 1
    pattern: "^(.+?)\\s*Tier$"
    # "Dec25 Yosher Tier" → tag "Yosher Tier"
```

**UI Approach**
- Simple mode: Pick from presets, override designer/tags
- Advanced mode: Full YAML/JSON editor for custom profiles

**Consequences**
- Flexible enough for any folder structure
- Presets reduce setup friction
- May need community-contributed profiles
- Profile validation required (prevent invalid configs)

---

### DEC-036: Design Detection Algorithm
**Date**: 2026-01-02
**Status**: Accepted

**Context**
When traversing a folder structure, need to determine which folders represent individual designs vs organizational hierarchy.

**Decision**
A folder is considered a **Design** if ANY of these conditions are met:

1. **Model files at root**: Folder contains `.stl`, `.3mf`, `.obj`, `.step` directly
2. **Model subfolder exists**: Folder has a child matching `model_subfolders` pattern that contains model files
3. **Archive at root**: Folder contains `.zip`, `.rar`, `.7z` (assumed to contain models)

**Algorithm**
```python
def is_design_folder(folder_path: Path, profile: ImportProfile) -> bool:
    # Check for model files at root
    model_extensions = {".stl", ".3mf", ".obj", ".step"}
    root_files = [f for f in folder_path.iterdir() if f.is_file()]
    if any(f.suffix.lower() in model_extensions for f in root_files):
        return True

    # Check for model subfolders
    for subfolder in profile.model_subfolders:
        subfolder_path = folder_path / subfolder
        if subfolder_path.exists():
            if any(f.suffix.lower() in model_extensions
                   for f in subfolder_path.rglob("*")):
                return True

    # Check for archives
    archive_extensions = {".zip", ".rar", ".7z"}
    if any(f.suffix.lower() in archive_extensions for f in root_files):
        return True

    return False
```

**Traversal Strategy**
1. Start at root folder
2. For each subfolder, check if it's a design
3. If yes: import as design, don't recurse deeper
4. If no: recurse into children
5. Skip folders matching `ignore_folders` pattern

**Consequences**
- Handles both flat and nested structures
- Stops recursion at design level (avoids importing subcomponents)
- Archives treated as single-design containers
- May need tuning for edge cases

---

### DEC-037: Import Conflict Handling
**Date**: 2026-01-02
**Status**: Accepted

**Context**
When re-importing or syncing, may encounter designs that already exist in the catalog. Need to decide how to handle conflicts.

**Options Considered**
1. **Always skip** - Never update existing designs
2. **Always overwrite** - Replace with new import
3. **Ask user** - Prompt for each conflict
4. **Smart merge** - Compare and merge changes

**Decision**
Configurable per import source with default of "skip existing":

**Conflict Detection**
Match by:
1. Same import source + source path (exact match)
2. Same title + designer (fuzzy match for cross-source dedup in v0.9)

**Resolution Modes**
```python
class ConflictResolution(Enum):
    SKIP = "skip"  # Keep existing, ignore new (default)
    REPLACE = "replace"  # Delete existing, import new
    ASK = "ask"  # Prompt user for each conflict
```

**Re-import Behavior**
- Skip already-imported files based on source path
- Don't re-download unchanged files
- Update metadata if file content changed (by size/date)

**Consequences**
- Safe default prevents accidental data loss
- "Ask" mode may be tedious for large imports
- Need UI for conflict resolution queue
- Deduplication (v0.9) will add cross-source matching

---

### DEC-038: Multi-Folder Import Sources
**Date**: 2026-01-02
**Status**: Accepted (updates DEC-033)

**Context**
Patreon creators often have multiple Google Drive folders (e.g., one per month, one per release tier). The original DEC-033 design had a 1:1 relationship between ImportSource and folder. Users requested the ability to group multiple folders under a single source for better organization.

**Example Use Case**
```
"Wicked STL Patreon" (Import Source)
  ├── Dec 2025 Release (folder)
  ├── Nov 2025 Release (folder)
  ├── Oct 2025 Release (folder)
  └── Bonus Pack (folder)
```

**Decision**
Split into two tables:
- **ImportSource**: Parent container with shared settings (designer, tags, profile)
- **ImportSourceFolder**: Individual folders/paths belonging to a source

**Updated Data Model**
```python
class ImportSource(Base):
    """Parent container for import folders."""
    id: UUID
    name: str  # "Wicked STL Patreon"
    source_type: ImportSourceType  # GOOGLE_DRIVE, BULK_FOLDER

    # Shared settings
    import_profile_id: UUID | None
    default_designer: str | None
    default_tags: list[str]
    sync_enabled: bool
    sync_interval_hours: int

    # Google OAuth (shared across folders)
    google_credentials_id: UUID | None

    # Relationships
    folders: list[ImportSourceFolder]


class ImportSourceFolder(Base):
    """Individual folder within an import source."""
    id: UUID
    import_source_id: UUID  # FK to ImportSource
    name: str | None  # Optional display name ("Dec 2025 Release")

    # Location (one of these set based on parent source_type)
    google_drive_url: str | None
    folder_path: str | None  # For BULK_FOLDER type

    # Per-folder overrides (optional)
    import_profile_id: UUID | None  # Override source's profile
    default_designer: str | None  # Override source's designer
    default_tags: list[str] | None  # Override source's tags

    # Sync state
    enabled: bool = True
    last_synced_at: datetime | None
    sync_cursor: str | None  # For incremental sync

    created_at: datetime
```

**Direct Upload Handling**
For `UPLOAD` type sources, we don't need folders - uploads create designs directly. The ImportSource with `source_type=UPLOAD` is a system singleton representing "Direct Uploads".

**UI Changes**
- Add folder management within source settings
- "Add Folder" button to add new folders to existing source
- Per-folder enable/disable toggle
- Optional per-folder setting overrides

**Consequences**
- Better organization for multi-folder Patreons
- Shared OAuth credentials across folders from same account
- More complex data model but cleaner UX
- Migration needed from original single-folder design

---

### DEC-039: Replace SQLite with PostgreSQL
**Date**: 2026-01-04
**Status**: Accepted (supersedes DEC-005)

**Context**
SQLite with WAL mode, busy_timeout, non-blocking progress updates, and session-per-operation pattern (DEC-019) still exhibits locking issues during heavy concurrent operations:
- Multiple workers updating job progress
- Import sync scanning large folders while API serves requests
- "database is locked" errors causing transaction rollbacks

These are fundamental SQLite limitations - single-writer architecture cannot be fully worked around.

**Decision**
Replace SQLite with PostgreSQL as the only supported database, running inside the same container.

- PostgreSQL runs inside Printarr container (supervisord manages both)
- `DATABASE_URL` points to local PostgreSQL socket
- Remove SQLite-specific code (pragmas, workarounds)
- MVCC provides true concurrent writes - no more locking issues
- Single container deployment preserved (Unraid-friendly)

**Implementation**
- Issue #168: Backend database configuration
- Issue #169: Docker container with embedded PostgreSQL

**Consequences**
- No more "database is locked" errors
- Simpler codebase (remove SQLite workarounds)
- Single container maintained (no separate postgres container)
- Slightly larger container image (~50MB for PostgreSQL)
- Existing SQLite databases need migration path

---

### DEC-040: Per-Design Download Jobs
**Date**: 2026-01-05
**Status**: Accepted

**Context**
Current import sync flow is monolithic:
1. `SYNC_IMPORT_SOURCE` job scans folder, finds 50 designs
2. Same job downloads all 50 designs sequentially
3. Queue shows generic "Syncing..." with no visibility into individual designs
4. Cannot cancel individual downloads
5. One failure can affect the entire batch

This makes it hard for users to understand what's happening or control the import process.

**Decision**
Split import into scan + individual download jobs:

1. `SYNC_IMPORT_SOURCE` job:
   - Scans source folder/Google Drive
   - Creates `ImportRecord` entries (status=PENDING)
   - Queues `DOWNLOAD_IMPORT_RECORD` job for each design
   - Completes quickly (scan only, no downloads)

2. `DOWNLOAD_IMPORT_RECORD` job (new):
   - Named: "Download: {design_title} from {source_name}"
   - Downloads files for one ImportRecord
   - Creates Design record
   - Queues `IMPORT_TO_LIBRARY` job
   - Updates ImportRecord status

**Benefits**
- Queue shows meaningful job names ("Download: Dragon Bust from Wicked STL")
- Users can cancel individual downloads
- Parallel downloads possible (configurable concurrency)
- One failure doesn't block other downloads
- Better progress tracking per design
- Cleaner separation of concerns

**Trade-offs**
- More jobs in queue (N designs = N+1 jobs instead of 1)
- Slightly more database overhead
- Need to handle job dependencies (sync must complete before downloads start)

**Implementation**
- Add `JobType.DOWNLOAD_IMPORT_RECORD`
- Create `DownloadImportRecordWorker`
- Refactor `SyncImportSourceWorker` to only scan
- Add `display_name` field to Job model for custom job names

---

## Pending Decisions

*No pending decisions at this time.*

---

## Decision Review Schedule

Revisit decisions at these milestones:
- After v0.2: Evaluate Telethon performance (DEC-013)
- After v0.5: Job queue performance
- After v0.7: Preview rendering approach
- Before v1.0: Overall architecture review
