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

### DEC-019: SQLite Concurrency Limitations
**Date**: 2025-12-31
**Status**: Issue Identified - Needs Resolution

**Context**
During v0.5 E2E testing, critical database locking issues were discovered when using SQLite with async workers. When the download worker performs long-running file downloads from Telegram, it holds a database connection open, blocking:
- Other workers from picking up jobs
- API requests to update/cancel jobs
- Maintenance tasks like requeuing stale jobs

Despite WAL mode and busy_timeout settings, SQLite's write lock architecture fundamentally conflicts with long-running async operations.

**Options to Consider**
1. **Refactor to release connection during I/O** - Download files outside of database session, only use DB briefly for status updates
2. **Switch to PostgreSQL** - Better concurrent write support, more complexity
3. **Serialize workers** - Only run one worker at a time, simplest but slowest
4. **Use connection pooling differently** - Separate pools for workers vs API

**Immediate Mitigation Applied**
- Reduced download workers to 1
- Added commit after job claim to release lock before processing
- Added WAL mode and 30-second busy_timeout

**Resolution Needed**
The download service needs refactoring to not hold database connections during file downloads. This is a priority bug for v0.5 stabilization.

**Consequences**
- Queue management (priority, cancel) may fail during active downloads
- Other workers blocked until download completes
- System appears unresponsive during large file downloads

---

## Pending Decisions

### To Decide: Preview Rendering Engine
**Context**: How to render STL/3MF to images
**Status**: Research needed during v0.7

---

## Decision Review Schedule

Revisit decisions at these milestones:
- After v0.2: Evaluate Telethon performance (DEC-013)
- After v0.5: Job queue performance
- After v0.7: Preview rendering approach
- Before v1.0: Overall architecture review
