# HINTS - Development Commands & Debug Tips

This file contains useful commands, debug tips, and common patterns to help agents work efficiently on Printarr.

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

### Unraid Deployment
```bash
# On Unraid server, clone repo and set up deploy script
git clone https://github.com/AdamA817/printarr.git
cd printarr
cp scripts/deploy.conf.example scripts/deploy.conf

# Edit deploy.conf with your paths
nano scripts/deploy.conf

# Run deploy script
./scripts/deploy.sh

# Build only (don't restart container)
./scripts/deploy.sh --build
```

The deploy script will:
1. Pull latest code from git
2. Build Docker image
3. Stop/remove existing container
4. Start new container with configured volumes

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
