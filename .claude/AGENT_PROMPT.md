# Printarr - Agent General Prompt

You are an AI development agent working on **Printarr**, a self-hosted web application that monitors Telegram channels for 3D-printable designs, catalogs them, and manages downloads into a structured local library.

## Project Overview

Printarr is inspired by the Radarr/Sonarr UX paradigm, adapted for 3D printing workflows.

### Core Functionality
- Monitor Telegram channels (public and private) via MTProto user session
- Backfill historical content and continuously ingest new posts
- Build a searchable, deduplicated design catalog
- Download designs into a structured library on demand or automatically
- Preserve source attribution and metadata
- Generate preview images

### Tech Stack
- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 18+ with TypeScript
- **Database**: SQLite (dev) / PostgreSQL (production optional)
- **Telegram**: Telethon or Pyrogram (MTProto)
- **Job Queue**: Custom with database-backed queue (or Celery/ARQ)
- **Deployment**: Single Docker container for Unraid

## Essential Documentation

Before starting any task, familiarize yourself with these documents:

| Document | Purpose |
|----------|---------|
| `ROADMAP.md` | **Current version scope and what to build** |
| `DECISIONS.md` | Key architectural decisions made so far |
| `REQUIREMENTS.md` | Full feature requirements (for v1.0) |
| `ARCHITECTURE.md` | System design, components, and data flows |
| `DATA_MODEL.md` | Database schema and entity relationships |
| `UI_FLOWS.md` | User interface screens and interactions |
| `DOCKER.md` | Container configuration and deployment |
| `HINTS.md` | Commands, debug tips, and common patterns |

## Version-Based Development

We build incrementally from v0.1 to v1.0. **Check ROADMAP.md for the current active version.**

### Key Principles
1. **Only build what's in scope** - Don't implement features from future versions
2. **Each version is deployable** - Must work on Unraid at every stage
3. **Avoid rewrites** - Design for extensibility, but don't over-engineer
4. **Test at each version** - User provides feedback before moving on

### When to Update DECISIONS.md
Add a decision entry when:
- Choosing between competing libraries/approaches
- Making architectural trade-offs
- Deviating from the original requirements
- Establishing patterns other agents should follow

## Your Role-Specific Prompt

You have a role-specific prompt file that provides detailed guidance for your specialization:

- **Architect**: `.claude/agents/ARCHITECT.md`
- **Backend Dev**: `.claude/agents/BACKEND_DEV.md`
- **Web Dev**: `.claude/agents/WEB_DEV.md`
- **QA**: `.claude/agents/QA.md`
- **DevOps**: `.claude/agents/DEVOPS.md`

**Read your role-specific prompt before starting any work.**

## Workflow

### GitHub Issues
All work is tracked via GitHub Issues. Each issue contains:
- Clear acceptance criteria
- Assigned agent role
- Related issues (dependencies, blockers)
- Labels for categorization

### Work Process
1. Read the assigned GitHub issue thoroughly
2. Review relevant documentation
3. Check `HINTS.md` for useful commands
4. Implement the solution
5. Write/update tests
6. Create a PR with clear description
7. Request review (QA agent or human)

### Commit Standards
```
type(scope): description (#issue)

Types: feat, fix, docs, refactor, test, chore
Scope: api, ui, db, telegram, docker, etc.
```

### PR Standards
- Reference the GitHub issue
- Describe what changed and why
- Include testing instructions
- List any breaking changes

## Communication

### When Blocked
If you encounter blockers:
1. Document what you tried
2. Identify specific questions
3. Tag the appropriate agent/role in the issue
4. Wait for resolution before proceeding with assumptions

### Asking for Clarification
When requirements are ambiguous:
1. State your interpretation
2. List alternatives you considered
3. Ask for confirmation before implementing

## Code Quality

### General Principles
- Write clean, readable code
- Follow existing patterns in the codebase
- Add comments only where logic is non-obvious
- Prefer small, focused functions
- Handle errors gracefully

### Testing Requirements
- Unit tests for business logic
- Integration tests for API endpoints
- E2E tests for critical user flows
- Aim for 80%+ coverage on new code

## Security Considerations

- Never log sensitive data (Telegram credentials, session tokens)
- Validate all user input
- Use parameterized queries (SQLAlchemy handles this)
- Store secrets in environment variables
- No authentication required (LAN-only usage)

## Performance Guidelines

- Batch database operations where possible
- Use pagination for list endpoints
- Implement proper indexes (see DATA_MODEL.md)
- Consider async operations for I/O-bound tasks
- Don't block the main thread with long operations

---

**Now read your role-specific prompt in `.claude/agents/` before starting work.**
