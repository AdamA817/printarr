# HINTS - Development Commands & Debug Tips

This file contains useful commands, debug tips, and common patterns to help agents work efficiently on Printarr.

## Table of Contents

| Section | Relevant For | Description |
|---------|--------------|-------------|
| [Project Structure](#project-structure) | All | Directory layout overview |
| [Backend (Python/FastAPI)](#backend-pythonfastapi) | Backend Dev | Setup, running, testing, debugging |
| [Frontend (React/TypeScript)](#frontend-reacttypescript) | Web Dev | Setup, running, testing, linting |
| [Docker](#docker) | DevOps, QA | Building, running, debugging containers |
| [Telegram Integration](#telegram-integration) | Backend Dev | Testing connection, common issues |
| [Git Workflow](#git-workflow) | All | Branch naming, commit messages |
| [Troubleshooting](#troubleshooting) | All | Common issues and solutions |
| [QA Testing Tips](#qa-testing-tips) | QA, Web Dev | Browser caching, React gotchas, Vitest config |
| [MCP_DOCKER Browser Testing](#mcp_docker-browser-testing) | QA | Using Playwright browser tools with host IP |
| [STL Preview Rendering](#stl-preview-rendering-v07) | DevOps, Backend | stl-thumb setup, testing, and debugging |
| [Channel Profiling](#channel-profiling) | QA, Architect | Profile test channels for feature coverage |
| [Bulk Folder Import](#bulk-folder-import-v08) | DevOps, QA | Watch folder configuration and troubleshooting |

**Tip**: Use `grep -n "## Section Name" HINTS.md` to find a section quickly.

---

## Project Structure

```
Printarr/
├── .claude/
│   └── agents/           # Agent-specific prompts
├── backend/              # FastAPI Python backend
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── core/         # Config, security, settings
│   │   ├── db/           # Database models & migrations
│   │   ├── services/     # Business logic
│   │   ├── workers/      # Background job workers
│   │   └── telegram/     # Telegram client integration
│   ├── tests/
│   └── requirements.txt
├── frontend/             # React TypeScript frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/     # API client
│   │   └── types/
│   └── package.json
├── docker/               # Docker configuration
└── docs/                 # Documentation
```

---

## Backend (Python/FastAPI)

### Environment Setup
```bash
# Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Running the Backend
```bash
# Development server with hot reload (port 3333 per DEC-006)
cd backend
uvicorn app.main:app --reload --port 3333

# Run with specific log level
uvicorn app.main:app --reload --port 3333 --log-level debug

# Run workers separately (in production)
python -m app.workers.ingestion
python -m app.workers.download
python -m app.workers.preview
```

### Database Commands
```bash
# Run migrations (uses PRINTARR_CONFIG_PATH env var, defaults to /config)
cd backend
alembic upgrade head

# For local development, set the config path first:
PRINTARR_CONFIG_PATH=./config alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1

# Reset database (CAUTION: destroys data)
alembic downgrade base && alembic upgrade head
```

**Important**: Alembic uses `PRINTARR_CONFIG_PATH` to find the database. In Docker this defaults to `/config`. For local development, set it to `./config` or the path where you want your database.

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_channels.py

# Run tests matching pattern
pytest -k "test_download"

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Debugging Tips
```python
# Quick debug logging
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Pretty print Telegram objects
from pprint import pprint
pprint(message.to_dict())

# Check SQLAlchemy queries
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Inspect job queue
from app.db import get_db
db = next(get_db())
pending = db.query(Job).filter(Job.status == 'QUEUED').all()
```

### Common Patterns

#### Creating a new API endpoint
```python
# In app/api/routes/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/")
async def list_items(db: Session = Depends(get_db)):
    return {"items": []}
```

#### Creating a background job
```python
# Enqueue a job
from app.services.job_queue import enqueue_job

await enqueue_job(
    job_type="DOWNLOAD_DESIGN",
    payload={"design_id": design.id},
    priority=5
)
```

---

## Frontend (React/TypeScript)

### Environment Setup
```bash
cd frontend
npm install
```

### Running the Frontend
```bash
# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run typecheck
```

### Testing
```bash
# Run tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch

# Run E2E tests (if configured)
npm run test:e2e
```

### Linting & Formatting
```bash
# Lint
npm run lint

# Fix lint issues
npm run lint:fix

# Format with Prettier
npm run format
```

### Debugging Tips
```typescript
// React Query devtools (already included in dev)
// Open with: Ctrl+Shift+D or floating icon

// Log API responses
console.log(JSON.stringify(data, null, 2));

// Check component renders
import { useRenderCount } from '@uidotdev/usehooks';
const renderCount = useRenderCount();
```

### Common Patterns

#### Creating a new page
1. Add component in `src/pages/NewPage.tsx`
2. Add route in `src/App.tsx`
3. Add navigation link in `src/components/Sidebar.tsx`

#### API Hooks Pattern
```typescript
// src/hooks/useDesigns.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { designsApi } from '../services/api';

export function useDesigns(filters: DesignFilters) {
  return useQuery({
    queryKey: ['designs', filters],
    queryFn: () => designsApi.list(filters),
  });
}

export function useMarkWanted() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: designsApi.markWanted,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['designs'] });
    },
  });
}
```

---

## Docker

### Building
```bash
# Build image
docker build -t printarr:dev .

# Build with no cache
docker build --no-cache -t printarr:dev .
```

### Running with docker-compose
```bash
# Start the container (recommended for local testing)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop and remove
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

### Running Standalone Container
```bash
# Create data directories first
mkdir -p data/{config,data,staging,library,cache}

# Run container with volume mounts
docker run -d --name printarr \
  -p 3333:3333 \
  -v $(pwd)/data/config:/config \
  -v $(pwd)/data/data:/data \
  -v $(pwd)/data/staging:/staging \
  -v $(pwd)/data/library:/library \
  -v $(pwd)/data/cache:/cache \
  printarr:dev

# Shell into container
docker exec -it printarr /bin/bash
```

### Testing Endpoints
```bash
# Health check
curl http://localhost:3333/api/health

# List channels
curl http://localhost:3333/api/v1/channels/

# Create a channel
curl -X POST http://localhost:3333/api/v1/channels/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "username": "test"}'

# Frontend (should return HTML)
curl http://localhost:3333/
```

### Debugging Container Issues
```bash
# Check container status
docker ps -a

# View container logs
docker logs printarr --tail 100

# Follow logs in real-time
docker logs -f printarr

# Inspect container
docker inspect printarr

# Check resource usage
docker stats printarr

# Check if migrations ran (look for "Running upgrade")
docker logs printarr 2>&1 | grep -i migration
```

### Common Docker Issues

| Issue | Solution |
|-------|----------|
| `no such table: channels` | Database path mismatch. Ensure PRINTARR_CONFIG_PATH=/config is set |
| API returns HTML instead of JSON | Static file catch-all intercepting routes. Check main.py routing |
| Container starts but health check fails | Wait for startup (5-10s) or check logs for errors |
| Migration runs but no tables created | Check database path in alembic/env.py matches app config |
| Permission denied on volumes | Check host directory permissions, may need `chmod 777` on data dirs |

### Volume Mounts (Critical!)
All persistent data must be in mounted volumes:
- `/config` - Database, Telegram session, app config
- `/data` - Internal state
- `/staging` - Temporary downloads
- `/library` - Organized 3D model files
- `/cache` - Thumbnails and previews

### Deploy Script (deploy.sh)

The `deploy.sh` script handles local development and GHCR publishing:

```bash
# Local development
./deploy.sh              # Full rebuild and deploy
./deploy.sh --fast       # Quick rebuild (uses cache)
./deploy.sh --pull       # Git pull first, then deploy
./deploy.sh --logs       # Follow container logs

# GHCR publishing (for Unraid)
./deploy.sh --unraid --push                # Build and push as :latest
./deploy.sh --unraid --push --tag=v1.0.0   # Push with version tag
./deploy.sh --reset                        # Wipe DB and restart
```

### GHCR (GitHub Container Registry)

GHCR is GitHub's Docker image hosting. Images live alongside your code at `ghcr.io`.

| | GitHub | GHCR |
|---|--------|------|
| **Stores** | Source code | Docker images |
| **URL** | github.com | ghcr.io |
| **Auth** | SSH key or PAT | PAT with `packages` scope |

#### First-Time GHCR Setup (Dev Machine)

1. Create a GitHub Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Generate new token (classic)
   - Select scopes: `write:packages`, `read:packages`
   - Copy the token

2. Login to GHCR:
   ```bash
   docker login ghcr.io -u YOUR_GITHUB_USERNAME
   # Paste token when prompted
   ```

3. Set up multi-platform builder (for Unraid amd64 + Mac arm64):
   ```bash
   docker buildx create --name multiplatform --use
   ```

#### Building Multi-Platform Images

Mac builds ARM images by default, but Unraid needs AMD64. Use buildx:

```bash
# Build for both platforms and push
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/adama817/printarr:v1.0.0 \
  -t ghcr.io/adama817/printarr:latest \
  --push .

# Or use the deploy script (does this automatically)
./deploy.sh --unraid --push --tag=v1.0.0
```

**Common error**: `no matching manifest for linux/amd64`
- This means the image was built only for ARM (Mac). Rebuild with buildx.

#### First-Time GHCR Setup (Unraid)

1. SSH into Unraid and login to GHCR:
   ```bash
   docker login ghcr.io -u YOUR_GITHUB_USERNAME
   # Paste your PAT (needs read:packages scope)
   ```

2. Pull the image:
   ```bash
   docker pull ghcr.io/adama817/printarr:latest
   ```

3. The login persists across reboots.

**Alternative**: Make the package public while keeping code private:
- Go to https://github.com/YOUR_USERNAME?tab=packages
- Click the package → Settings → Change visibility → Public

### Unraid Template

Copy `unraid/printarr.xml` to your Unraid server:

```bash
# From Unraid terminal
mkdir -p /boot/config/plugins/dockerMan/templates-user
# Then paste the template content into:
nano /boot/config/plugins/dockerMan/templates-user/printarr.xml
```

Or run the container directly:

```bash
docker run -d \
  --name Printarr \
  -p 3333:3333 \
  -e PUID=99 -e PGID=100 \
  -e PRINTARR_TELEGRAM_API_ID=your_api_id \
  -e PRINTARR_TELEGRAM_API_HASH=your_api_hash \
  -v /mnt/user/appdata/printarr/config:/config \
  -v /mnt/user/appdata/printarr/data:/data \
  -v /mnt/user/appdata/printarr/cache:/cache \
  -v /mnt/user/downloads/printarr-staging:/staging \
  -v /mnt/user/3d-library:/library \
  ghcr.io/adama817/printarr:latest
```

### Updating Unraid After New Release

```bash
# From Unraid terminal
docker pull ghcr.io/adama817/printarr:latest
docker stop Printarr && docker rm Printarr
# Recreate from template or docker run command
```

Or in Unraid UI: Docker → Printarr icon → Force Update

---

## Telegram Integration

### Testing Telegram Connection
```python
# Quick test script
from telethon import TelegramClient
import asyncio

async def test():
    client = TelegramClient('test_session', API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"Logged in as: {me.username}")

asyncio.run(test())
```

### Common Issues

| Issue | Solution |
|-------|----------|
| `FloodWaitError` | Wait the specified seconds, implement exponential backoff |
| `SessionPasswordNeeded` | Account has 2FA, need to provide password |
| `ChannelPrivateError` | Account not member of channel, or channel deleted |
| `UsernameNotOccupied` | Channel username doesn't exist |

### Rate Limiting
- Telegram has aggressive rate limits
- Use `asyncio.sleep()` between bulk operations
- Implement exponential backoff on FloodWait
- Max ~30 messages/second for reads
- Max ~20 requests/second for API calls

---

## Git Workflow

### Branch Naming
```
feature/ISSUE-123-add-channel-management
bugfix/ISSUE-456-fix-download-queue
hotfix/ISSUE-789-critical-security-fix
```

### Commit Messages
```
feat(channels): add channel management UI (#123)
fix(download): handle large file resume (#456)
docs(api): update endpoint documentation
refactor(workers): extract job processing logic
test(designs): add filter unit tests
```

### Before Pushing
```bash
# Run tests
pytest  # backend
npm test  # frontend

# Check types
npm run typecheck

# Lint
npm run lint
```

---

## Troubleshooting

### Backend Won't Start
1. Check virtual environment is activated
2. Verify all dependencies installed: `pip install -r requirements.txt`
3. Check database connection: `PRINTARR_CONFIG_PATH=./config alembic upgrade head`
4. Look for port conflicts: `lsof -i :3333`

### Frontend Won't Start
1. Clear node_modules: `rm -rf node_modules && npm install`
2. Clear Vite cache: `rm -rf node_modules/.vite`
3. Check Node version: should be 18+

### Database Issues
1. Reset database: `alembic downgrade base && alembic upgrade head`
2. Check SQLite file permissions
3. For locked database, ensure no other process is using it

### Telegram Session Issues
1. Delete session file and re-authenticate
2. Check API_ID and API_HASH are correct
3. Ensure phone number format is correct (+1234567890)

---

## QA Testing Tips

### Browser Caching Issues
When testing Docker containers, browsers may cache old JS/CSS bundles:
```bash
# Verify what the server is actually serving
curl -s http://localhost:3333/ | grep 'index-'

# Compare with what's in the container
docker exec printarr ls /app/frontend/dist/assets/

# Force cache bust by adding query param
http://localhost:3333/?v=2
```

**Symptoms**: UI shows old version number, features missing, stale behavior
**Solution**: Close browser tab completely or add cache-busting query param

### Docker Rebuild After Code Changes
When testing code changes, ensure the container has the latest:
```bash
# Quick rebuild (uses cache)
docker-compose up -d --build

# Full rebuild (no cache - use when having issues)
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Verify code is current
docker exec printarr cat /app/backend/app/api/router.py | head -10
docker exec printarr bash -c 'grep -o "someString" /app/frontend/dist/assets/*.js'
```

### Environment Variable Naming
The backend uses pydantic-settings with `env_prefix="PRINTARR_"`:
```python
# In Settings class
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRINTARR_")
    telegram_api_id: int | None = None  # Expects: PRINTARR_TELEGRAM_API_ID
```

**Common mistake**: Using `TELEGRAM_API_ID` instead of `PRINTARR_TELEGRAM_API_ID`

```yaml
# docker-compose.yml - CORRECT
environment:
  - PRINTARR_TELEGRAM_API_ID=${TELEGRAM_API_ID}

# docker-compose.yml - WRONG (won't work!)
environment:
  - TELEGRAM_API_ID=${TELEGRAM_API_ID}
```

### React Rendering Gotchas
React renders some falsy values as visible text:
```tsx
// PROBLEM: NaN renders as the string "NaN"
const id = parseInt("not-a-number", 10)  // Returns NaN
{id && <Component />}  // Renders "NaN" instead of nothing!

// SOLUTION: Explicitly check for valid values
const parsedId = parseInt(value ?? '', 10)
const id = isNaN(parsedId) ? null : parsedId
{id !== null && <Component />}
```

**Values React renders as nothing**: `false`, `null`, `undefined`, `""` (empty string)
**Values React renders visibly**: `0`, `NaN`, empty arrays `[]`

### Vitest Configuration
When using vitest with vite, import `defineConfig` from the correct package:
```typescript
// CORRECT - for projects using vitest
import { defineConfig } from 'vitest/config'

// WRONG - causes "test does not exist" TypeScript error
import { defineConfig } from 'vite'
```

### Testing API Endpoints
```bash
# Check Telegram auth status
curl -s http://localhost:3333/api/v1/telegram/auth/status | jq .

# Expected response when configured but not authenticated:
# {"authenticated": false, "configured": true, "connected": true, "user": null}

# Check if API routes are registered
docker logs printarr 2>&1 | grep -i "telegram\|route"
```

### Checking for Missing Code in Docker Build
If features are missing in the Docker container:
```bash
# 1. Check if route file exists
docker exec printarr ls /app/backend/app/api/routes/

# 2. Check if router includes the route
docker exec printarr cat /app/backend/app/api/router.py

# 3. Check if frontend component is bundled
docker exec printarr bash -c 'grep -c "ComponentName" /app/frontend/dist/assets/*.js'

# 4. Rebuild if code is stale
docker-compose build --no-cache && docker-compose up -d
```

### MCP_DOCKER Browser Testing

When using the MCP_DOCKER browser tools (Playwright) for UI testing, the browser runs inside a Docker container and **cannot access `localhost`**. You must use the host machine's IP address.

#### Getting the Host IP Address
```bash
# macOS - get IP from en0 (usually WiFi) or en1 (Ethernet)
ifconfig en0 | grep "inet " | awk '{print $2}'

# Linux
hostname -I | awk '{print $1}'

# Alternative: check what IP your machine has
ip route get 1 | awk '{print $7}'
```

#### Using the Browser Tools
```javascript
// WRONG - browser can't reach localhost from inside Docker
await page.goto('http://localhost:3333/');  // Will fail with ERR_CONNECTION_REFUSED

// CORRECT - use the host machine's IP
await page.goto('http://10.0.0.27:3333/');  // Replace with your actual IP
```

#### Typical Browser Testing Workflow
1. **Get your host IP first**:
   ```bash
   ifconfig en0 | grep "inet " | awk '{print $2}'
   # Example output: 10.0.0.27
   ```

2. **Navigate using the IP**:
   ```javascript
   // Use browser_navigate with host IP
   mcp__MCP_DOCKER__browser_navigate({ url: "http://10.0.0.27:3333/channels" })
   ```

3. **Wait for content to load**:
   ```javascript
   mcp__MCP_DOCKER__browser_wait_for({ time: 2 })
   ```

4. **Take snapshots to see page state**:
   ```javascript
   mcp__MCP_DOCKER__browser_snapshot()
   ```

5. **Interact with elements using refs from snapshot**:
   ```javascript
   mcp__MCP_DOCKER__browser_click({ element: "Add Channel button", ref: "e50" })
   ```

#### Common Issues

| Issue | Solution |
|-------|----------|
| `ERR_CONNECTION_REFUSED` | Using localhost instead of host IP |
| Element outside viewport | Use `browser_run_code` with `scrollIntoViewIfNeeded()` |
| Button click timeout | Try `element.evaluate(el => el.click())` via `browser_run_code` |
| IP changed | Re-run `ifconfig en0` to get current IP |

#### Pro Tips
- Your IP may change (DHCP). Always verify it before starting a browser session.
- Use `browser_snapshot()` instead of `browser_take_screenshot()` for element refs.
- Close browser when done: `mcp__MCP_DOCKER__browser_close()`

---

### Download & Library Debugging (v0.5)

#### Checking Download Status
```bash
# View active jobs in queue
curl -s http://localhost:3333/api/v1/queue/ | jq '.items[:5]'

# View job history (completed/failed)
curl -s http://localhost:3333/api/v1/activity/ | jq '.items[:5]'

# Check specific design status
curl -s http://localhost:3333/api/v1/designs/{design_id} | jq '{status, title}'
```

#### Common Download Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Download stuck at 0% | Telegram rate limiting | Wait and retry; downloads auto-retry with backoff |
| `FloodWaitError` | Too many Telegram requests | Automatic retry after wait period; reduce concurrent downloads |
| Extraction fails | Missing system packages | Verify `unrar` and `7z` installed: `docker exec printarr unrar --version` |
| Password protected archive | Archive requires password | Non-retryable; need manual intervention |
| Missing archive parts | Multi-part RAR incomplete | Ensure all `.partN.rar` files are available in the same design |
| Library import fails | Permission denied | Check volume mount permissions; may need `chmod 777` on host dirs |

#### Manually Queue a Download
```bash
# Queue a specific design for download
curl -X POST http://localhost:3333/api/v1/designs/{design_id}/download

# Queue with high priority
curl -X POST "http://localhost:3333/api/v1/designs/{design_id}/download?priority=10"
```

#### Inspecting Staging/Library Directories
```bash
# Check what's in staging
docker exec printarr ls -la /staging/

# Check a specific design's staging folder
docker exec printarr ls -la /staging/{design_id}/

# Check library structure
docker exec printarr find /library -type f -name "*.stl" | head -10
```

#### Retrying Failed Jobs
```bash
# Get failed job IDs
curl -s "http://localhost:3333/api/v1/activity/?status=FAILED" | jq '.items[].id'

# Retry via UI: Activity page → Failed tab → Retry button
# Or re-queue the design:
curl -X POST http://localhost:3333/api/v1/designs/{design_id}/download
```

#### Archive Extraction Issues
```bash
# Test unrar works
docker exec printarr unrar --version

# Test 7z works
docker exec printarr 7z --help | head -5

# Check Python packages
docker exec printarr python -c "import rarfile, py7zr; print('OK')"
```

---

### STL Preview Rendering (v0.7)

The Docker image includes `stl-thumb` for generating preview images from STL files.

#### Testing stl-thumb
```bash
# Verify stl-thumb is installed
docker exec printarr stl-thumb --version
# Expected: stl-thumb 0.5.0

# Test rendering an STL file
docker exec printarr stl-thumb -s 400 /path/to/model.stl /cache/previews/rendered/output.png
```

#### stl-thumb Options
| Option | Description |
|--------|-------------|
| `-s SIZE` | Output image size in pixels (default 1024, we use 400) |
| `-m MATERIAL` | Material type (default metallic) |
| `-b R,G,B` | Background color (default white) |

#### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Panic about "Failed to initialize any backend" | Normal in headless Docker | Ignore - rendering still works, exit code is 0 |
| Black/empty image | STL file may be malformed | Try with `--recalc-normals` flag |
| Missing dependencies | libosmesa6-dev not installed | Rebuild Docker image |

#### Preview Directory Structure (DEC-027)
Previews are stored in `/cache/previews/` with subdirectories by source:
```
/cache/previews/
├── telegram/    # Images from Telegram posts
├── archive/     # Images extracted from archives
├── thangs/      # Cached Thangs preview images
├── embedded/    # 3MF embedded thumbnails
└── rendered/    # stl-thumb generated previews
```

---

### Channel Profiling

The `scripts/profile_channels.py` script analyzes Telegram channels from `TEST_CHANNELS.md` and generates profiles showing what features each channel has.

#### Prerequisites
- Telegram session must be authenticated (run the app first)
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in environment or `.env`

#### Basic Usage
```bash
# Profile all channels in TEST_CHANNELS.md (100 messages each)
python scripts/profile_channels.py

# Profile specific channels
python scripts/profile_channels.py --channels wickedstl,gambody

# Sample more messages for better accuracy
python scripts/profile_channels.py --messages 500

# Skip channels already profiled
python scripts/profile_channels.py --skip-existing
```

#### Output Files
- `channel_profiles/<channel>.json` - Individual channel profiles
- `channel_profiles/SUMMARY.md` - Markdown summary with suitability matrix
- `channel_profiles/all_profiles.json` - All profiles in one file

#### What It Detects

| Category | Details |
|----------|---------|
| **File Types** | STL, 3MF, OBJ, STEP, ZIP, RAR, 7Z, images |
| **External Links** | Thangs, Printables, Thingiverse URLs |
| **Channel Discovery** | Forwarded messages, @mentions, t.me links |
| **Multi-part Files** | Split RAR archives (.part1, .part2) |
| **Image/File Pairs** | Posts with "(Images)" / "(Non Supported)" patterns |
| **Activity** | Last post date, posts per week |
| **Captions** | Hashtags, average length |

#### Suitability Flags
Each profile includes suitability flags for testing:
- `v0.3_ingestion` - Has design files (STL, 3MF, archives)
- `v0.3_thangs` - Has Thangs URLs in captions
- `v0.4_multipart` - Has split archives or image/file pairs
- `v0.6_active` - Posted in last 30 days
- `v0.6_discovery` - Has channel references (forwards, mentions)
- `v0.7_previews` - Has images in posts
- `v0.7_3mf` - Has 3MF files (for embedded thumbnails)

---

### Bulk Folder Import (v0.8+)

Printarr can monitor local folders for 3D designs to import into the library.

#### Configuring Watch Folders

In docker-compose.yml:
```yaml
volumes:
  # Standard volumes
  - ./data/config:/config
  - ./data/library:/library

  # Bulk import watch folders (v0.8+)
  - /mnt/user/downloads/3d-models:/watch/downloads:ro
  - /mnt/user/patreon:/watch/patreon:ro
```

In Unraid template:
- "Watch Folder 1" → First monitored path
- "Watch Folder 2" → Second monitored path (optional)
- "Watch Folder 3" → Third monitored path (optional)

#### Read-Only vs Read-Write Mounts

| Mode | Use Case | Pros | Cons |
|------|----------|------|------|
| Read-only (`:ro`) | When copying files to library | Safer, source unchanged | Uses more disk space |
| Read-write (`:rw`) | When moving files to library | Saves disk space | Source files deleted |

**Recommendation**: Use read-only mounts unless disk space is critical.

#### Permission Requirements

The container runs as root by default. For mounted folders:
```bash
# On Unraid, ensure the folder is accessible
# Usually no changes needed for shares

# On Linux with PUID/PGID set
chown -R $PUID:$PGID /path/to/watch/folder
chmod 755 /path/to/watch/folder
```

#### Common Watch Folder Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Permission denied" | Container can't read host folder | Check folder permissions |
| Folder not detected | Path not mounted in container | Verify volume mapping in docker-compose.yml |
| Files not importing | Path inside container wrong | Check target path (e.g., `/watch/downloads`) |
| "Folder not accessible" in UI | Mount is broken or path doesn't exist | Verify host path exists and is mounted |

#### Verifying Watch Folder Access

```bash
# Check if folder is mounted correctly
docker exec printarr ls -la /watch/

# Check specific watch folder contents
docker exec printarr ls -la /watch/downloads/

# Test read access
docker exec printarr head -c 100 /watch/downloads/some-file.stl
```

#### Supported Folder Structures

Printarr detects designs using Import Profiles. Common patterns:

1. **Flat structure** - STL files at root:
   ```
   /watch/downloads/
   ├── dragon.stl
   ├── sword.stl
   └── shield.stl
   ```

2. **One folder per design**:
   ```
   /watch/downloads/
   ├── Dragon Model/
   │   ├── dragon.stl
   │   └── dragon_base.stl
   └── Medieval Weapons/
       ├── sword.stl
       └── shield.stl
   ```

3. **Creator/Design hierarchy** (Yosh Studios style):
   ```
   /watch/patreon/
   └── YoshStudios/
       └── 2024-01/
           └── Dragon/
               ├── Supported/
               │   └── dragon_supported.stl
               └── Unsupported/
                   └── dragon.stl
   ```

See Import Profiles in Settings to configure detection rules.
