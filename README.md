# Printarr

A self-hosted web application that monitors Telegram channels for 3D-printable designs, catalogs them, and manages downloads into a structured local library.

Inspired by the Radarr/Sonarr UX paradigm, adapted for 3D printing workflows.

## Features

- Monitor Telegram channels (public and private) via MTProto
- Backfill historical content and continuously ingest new posts
- Build a searchable, deduplicated design catalog
- Download designs into a structured library on demand or automatically
- Preserve source attribution and metadata
- Generate preview images

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
