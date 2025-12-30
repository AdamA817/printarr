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

## Pending Decisions

### To Decide: Telegram Client Library
**Context**: Need to choose between Telethon and Pyrogram for MTProto client.
**Status**: Research needed during v0.2

### To Decide: Job Queue Implementation
**Context**: Custom database-backed queue vs Celery/ARQ
**Status**: Decide during v0.5

### To Decide: Preview Rendering Engine
**Context**: How to render STL/3MF to images
**Status**: Research needed during v0.7

---

## Decision Review Schedule

Revisit decisions at these milestones:
- After v0.2: Telegram library choice
- After v0.5: Job queue performance
- After v0.7: Preview rendering approach
- Before v1.0: Overall architecture review
