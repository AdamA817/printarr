# Printarr

[![CI](https://github.com/AdamA817/printarr/actions/workflows/ci.yml/badge.svg)](https://github.com/AdamA817/printarr/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ghcr.io%2Fadama817%2Fprintarr-blue)](https://ghcr.io/adama817/printarr)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/AdamA817/printarr/releases)

A self-hosted web application that monitors Telegram channels for 3D-printable designs, catalogs them, and manages downloads into a structured local library.

Inspired by the Radarr/Sonarr UX paradigm, adapted for 3D printing workflows.

## Features

- **Channel Monitoring** - Monitor Telegram channels (public and private) with live sync
- **Design Catalog** - Radarr-style grid/list views with filtering and search
- **Smart Downloads** - Priority queue with archive extraction (ZIP, RAR, 7z)
- **Library Organization** - Configurable folder templates with designer/channel metadata
- **Preview Generation** - Automatic STL thumbnail rendering with stl-thumb
- **Thangs Integration** - Metadata enrichment and duplicate detection
- **Google Drive Import** - OAuth integration for cloud file imports
- **Bulk Folder Import** - Monitor local folders for existing collections
- **Real-time Updates** - Live UI updates via Server-Sent Events
- **AI Auto-Tagging** - Optional Google Gemini integration for automatic design categorization

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)

### 1. Create directories

```bash
mkdir -p printarr/{config,data,staging,library,cache}
cd printarr
```

### 2. Start container

```bash
docker run -d \
  --name printarr \
  -p 3333:3333 \
  -v ./config:/config \
  -v ./data:/data \
  -v ./staging:/staging \
  -v ./library:/library \
  -v ./cache:/cache \
  -e PRINTARR_TELEGRAM_API_ID=your_api_id \
  -e PRINTARR_TELEGRAM_API_HASH=your_api_hash \
  ghcr.io/adama817/printarr:latest
```

### 3. Access the web UI

Open http://localhost:3333 and complete the Telegram authentication wizard.

## Installation Options

### Docker Compose (Recommended)

```yaml
services:
  printarr:
    image: ghcr.io/adama817/printarr:latest
    container_name: printarr
    ports:
      - "3333:3333"
    volumes:
      - ./config:/config
      - ./data:/data
      - ./staging:/staging
      - ./library:/library
      - ./cache:/cache
    environment:
      - PRINTARR_TELEGRAM_API_ID=${TELEGRAM_API_ID}
      - PRINTARR_TELEGRAM_API_HASH=${TELEGRAM_API_HASH}
    restart: unless-stopped
```

### Unraid

Install via Community Apps by searching for "Printarr", or manually add the template from:
`https://raw.githubusercontent.com/AdamA817/printarr/main/unraid/printarr.xml`

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `PRINTARR_TELEGRAM_API_ID` | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `PRINTARR_TELEGRAM_API_HASH` | Telegram API Hash |

### Optional Environment Variables

<details>
<summary>Click to expand all options</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_PORT` | 3333 | Web UI port |
| `PRINTARR_LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PRINTARR_MAX_CONCURRENT_DOWNLOADS` | 2 | Maximum simultaneous downloads |
| `PRINTARR_LIBRARY_TEMPLATE` | `{designer}/{title}` | Library folder structure template |
| `PRINTARR_FLARESOLVERR_URL` | - | FlareSolverr URL for Thangs (Cloudflare bypass) |
| `PRINTARR_SYNC_ENABLED` | true | Enable live Telegram monitoring |
| `PRINTARR_SYNC_POLL_INTERVAL` | 300 | Catch-up sync interval in seconds |
| `PRINTARR_SYNC_BATCH_SIZE` | 100 | Messages per sync batch |
| `PRINTARR_TELEGRAM_RATE_LIMIT_RPM` | 30 | Max Telegram API requests/minute |
| `PRINTARR_TELEGRAM_CHANNEL_SPACING` | 2.0 | Seconds between channel requests |
| `PRINTARR_GOOGLE_CLIENT_ID` | - | Google OAuth Client ID for Drive |
| `PRINTARR_GOOGLE_CLIENT_SECRET` | - | Google OAuth Client Secret |
| `PRINTARR_AUTO_QUEUE_RENDER_AFTER_IMPORT` | true | Auto-queue STL preview renders |
| `PRINTARR_AI_ENABLED` | false | Enable AI-powered tagging (requires API key) |
| `PRINTARR_AI_API_KEY` | - | Google Gemini API key |
| `PRINTARR_AI_MODEL` | gemini-1.5-flash | AI model (gemini-1.5-flash, gemini-1.5-pro) |
| `PRINTARR_AI_AUTO_ANALYZE_ON_IMPORT` | true | Auto-analyze new designs |
| `PRINTARR_AI_RATE_LIMIT_RPM` | 15 | AI API requests per minute (5-60) |

</details>

### Volume Mounts

| Path | Purpose | Size Estimate |
|------|---------|---------------|
| `/config` | App config, database, Telegram session | ~50MB |
| `/data` | Internal state, uploads | ~500MB |
| `/staging` | Download/extraction workspace | 2-5GB |
| `/library` | Organized 3D model library | Varies |
| `/cache` | Thumbnails and preview images | ~1GB |

## First-Time Setup

### Getting Telegram API Credentials

1. Go to [my.telegram.org](https://my.telegram.org) and log in
2. Click "API development tools"
3. Create a new application (any name/description)
4. Copy the `api_id` and `api_hash`

See [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) for detailed instructions.

### Adding Your First Channel

1. Navigate to **Channels** in the sidebar
2. Click **Add Channel**
3. Enter a Telegram channel username (e.g., `@FlexiFactorySTL`) or invite link
4. Choose download mode:
   - **Manual** - Only download explicitly requested designs
   - **Auto (New Only)** - Automatically download new posts
   - **Auto (All)** - Download everything including backfill
5. Click **Add** and optionally start a backfill

## FAQ

<details>
<summary>How do I get Telegram API credentials?</summary>

Visit [my.telegram.org](https://my.telegram.org), log in, and create an application under "API development tools".
</details>

<details>
<summary>Why do I need FlareSolverr for Thangs?</summary>

Thangs uses Cloudflare protection. FlareSolverr acts as a proxy to bypass this for metadata lookups.
</details>

<details>
<summary>How do I add a private channel?</summary>

For private channels, use the invite link (e.g., `https://t.me/+abc123`). Your Telegram account must be a member of the channel.
</details>

<details>
<summary>Where are my downloads stored?</summary>

Downloads are organized in `/library` using the template defined in `PRINTARR_LIBRARY_TEMPLATE`. Default: `{designer}/{title}`.
</details>

<details>
<summary>How do I enable AI auto-tagging?</summary>

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set `PRINTARR_AI_ENABLED=true` and `PRINTARR_AI_API_KEY=your_key`
3. The free tier allows 15 requests/minute, which is sufficient for most personal use
</details>

## Documentation

| Document | Description |
|----------|-------------|
| [Telegram Setup](TELEGRAM_SETUP.md) | Telegram API credentials guide |
| [Google Drive Setup](docs/GOOGLE_DRIVE_SETUP.md) | OAuth configuration for Drive imports |
| [Docker Configuration](DOCKER.md) | Container setup and volumes |
| [Architecture](ARCHITECTURE.md) | System design and components |

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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

## Contributing

Contributions are welcome! Please:

1. Check the [Roadmap](ROADMAP.md) for current priorities
2. Open an issue to discuss significant changes
3. Follow the existing code style
4. Include tests for new features

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Inspired by [Radarr](https://radarr.video/) and [Sonarr](https://sonarr.tv/)
- STL rendering by [stl-thumb](https://github.com/unlimitedbacon/stl-thumb)
- Telegram integration via [Telethon](https://github.com/LonamiWebs/Telethon)
