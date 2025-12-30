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
# Development server with hot reload
uvicorn app.main:app --reload --port 7878

# Run with specific log level
uvicorn app.main:app --reload --log-level debug

# Run workers separately (in production)
python -m app.workers.ingestion
python -m app.workers.download
python -m app.workers.preview
```

### Database Commands
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1

# Reset database (CAUTION: destroys data)
alembic downgrade base && alembic upgrade head
```

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

### Running
```bash
# Run with docker-compose (recommended for dev)
docker-compose up -d

# View logs
docker-compose logs -f

# Restart specific service
docker-compose restart backend

# Shell into container
docker exec -it printarr-backend /bin/bash
```

### Debugging Container Issues
```bash
# Check container status
docker ps -a

# View container logs
docker logs printarr --tail 100

# Inspect container
docker inspect printarr

# Check resource usage
docker stats printarr
```

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
3. Check database connection: `alembic upgrade head`
4. Look for port conflicts: `lsof -i :7878`

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
