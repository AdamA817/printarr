# Printarr

A self-hosted web application that monitors Telegram channels for 3D-printable designs, catalogs them, and manages downloads into a structured local library.

Inspired by the Radarr/Sonarr UX paradigm, adapted for 3D printing workflows.

## Features

### Channel Monitoring
- Monitor Telegram channels (public and private) via MTProto
- Backfill historical content from channels
- Automatic design detection from posts containing 3D files

### Design Catalog (v0.4)
- Radarr-style grid and list views for browsing designs
- Filter by status, channel, file type
- Thangs integration for metadata enrichment
- Manual and automatic Thangs linking
- Multi-message design merging for split archives

### Downloads & Library (v0.5)
- One-click download with "Want" / "Download" buttons
- Archive extraction (ZIP, RAR, 7z, TAR)
- Configurable library folder structure with template variables
- Activity page with real-time queue and history views
- Priority-based job queue with retry support

### Coming Soon
- Live channel monitoring with auto-download (v0.6)
- Preview image generation (v0.7)
- Deduplication (v0.8)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Telegram API credentials ([setup guide](TELEGRAM_SETUP.md))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/AdamA817/printarr.git
   cd printarr
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your Telegram API credentials
   ```

3. Start Printarr:
   ```bash
   docker compose up -d
   ```

4. Open http://localhost:3333 in your browser

5. Complete the Telegram authentication wizard

## Documentation

| Document | Description |
|----------|-------------|
| [Telegram Setup](TELEGRAM_SETUP.md) | How to obtain and configure Telegram API credentials |
| [Docker Configuration](DOCKER.md) | Container setup, volumes, and environment variables |
| [Architecture](ARCHITECTURE.md) | System design, components, and data flows |
| [Data Model](DATA_MODEL.md) | Database schema and entity relationships |
| [UI Flows](UI_FLOWS.md) | User interface screens and interactions |
| [Requirements](REQUIREMENTS.md) | Full feature requirements |
| [Roadmap](ROADMAP.md) | Development milestones and current version scope |

## Deployment

### Docker Compose

See [docker-compose.yml](docker-compose.yml) for the default configuration.

### Unraid

An Unraid template is available at [unraid/printarr.xml](unraid/printarr.xml).

### Manual Deploy Script

For manual deployments on Unraid or other systems:

```bash
cp scripts/deploy.conf.example scripts/deploy.conf
# Edit deploy.conf with your settings
./scripts/deploy.sh
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_API_ID` | Yes | - | Telegram API ID from my.telegram.org |
| `TELEGRAM_API_HASH` | Yes | - | Telegram API Hash |
| `PRINTARR_PORT` | No | 3333 | Web UI port |
| `PRINTARR_LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PRINTARR_MAX_CONCURRENT_DOWNLOADS` | No | 3 | Maximum simultaneous Telegram downloads (1-10) |
| `PRINTARR_LIBRARY_TEMPLATE` | No | `{designer}/{channel}/{title}` | Library folder structure template |
| `PRINTARR_FLARESOLVERR_URL` | No | - | FlareSolverr URL for Thangs integration |

### Volume Mounts

| Path | Purpose |
|------|---------|
| `/config` | Application config and Telegram session |
| `/data` | Database and internal state |
| `/staging` | Temporary download/extraction workspace |
| `/library` | Final organized 3D model library |
| `/cache` | Thumbnails and preview cache |

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 18+ with TypeScript
- **Database**: SQLite (dev) / PostgreSQL (production optional)
- **Telegram**: Telethon (MTProto)
- **Deployment**: Docker

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

## License

MIT

## Contributing

Contributions are welcome! Please read the documentation and check the [Roadmap](ROADMAP.md) for current development priorities.
