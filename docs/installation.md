# Installation Guide

This guide covers all installation methods for Printarr.

## Prerequisites

Before installing Printarr, you'll need:

1. **Docker** - Printarr runs as a Docker container
2. **Telegram API Credentials** - See [Telegram Setup](telegram-setup.md)
3. **Storage Space** - At least 10GB for staging and cache

## Installation Methods

### Docker Compose (Recommended)

1. Create a directory for Printarr:

```bash
mkdir -p ~/printarr && cd ~/printarr
```

2. Create a `docker-compose.yml` file:

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

  # Optional: FlareSolverr for Thangs integration
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    environment:
      - LOG_LEVEL=info
    restart: unless-stopped
```

3. Create a `.env` file with your credentials:

```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

4. Start Printarr:

```bash
docker compose up -d
```

5. Access the web UI at http://localhost:3333

### Docker CLI

For a quick single-command install:

```bash
docker run -d \
  --name printarr \
  -p 3333:3333 \
  -v /path/to/config:/config \
  -v /path/to/data:/data \
  -v /path/to/staging:/staging \
  -v /path/to/library:/library \
  -v /path/to/cache:/cache \
  -e PRINTARR_TELEGRAM_API_ID=your_api_id \
  -e PRINTARR_TELEGRAM_API_HASH=your_api_hash \
  ghcr.io/adama817/printarr:latest
```

### Unraid

1. Go to **Apps** in the Unraid web UI
2. Search for "Printarr"
3. Click **Install**
4. Configure the paths and Telegram credentials
5. Click **Apply**

If Printarr isn't in Community Apps yet, add the template manually:

1. Go to **Docker** > **Add Container**
2. Click **Template URL**
3. Enter: `https://raw.githubusercontent.com/AdamA817/printarr/main/unraid/printarr.xml`
4. Click **Load** and configure

## Post-Installation

### First-Time Setup

1. Open http://localhost:3333 (or your server's IP)
2. You'll be prompted to authenticate with Telegram
3. Enter your phone number and the verification code sent to Telegram
4. Add your first channel to start monitoring

### Verify Installation

Check that Printarr is running correctly:

```bash
# Check container status
docker ps | grep printarr

# Check logs
docker logs printarr

# Test health endpoint
curl http://localhost:3333/api/health
```

Expected health response:
```json
{"status":"ok","version":"1.0.0","database":"connected"}
```

## Upgrading

### Docker Compose

```bash
docker compose pull
docker compose up -d
```

### Docker CLI

```bash
docker pull ghcr.io/adama817/printarr:latest
docker stop printarr
docker rm printarr
# Re-run your docker run command
```

### Unraid

1. Go to **Docker**
2. Click the Printarr icon
3. Select **Check for Updates**
4. Click **Apply Update** if available

## Volume Layout

| Mount Point | Purpose | Recommended Location |
|-------------|---------|---------------------|
| `/config` | Database, Telegram session | Fast storage (SSD) |
| `/data` | Uploads, internal state | Fast storage |
| `/staging` | Download workspace | Fast storage, 5-10GB |
| `/library` | Final organized files | Large storage (NAS) |
| `/cache` | Thumbnails, previews | Fast storage, 1-2GB |

## Next Steps

- [Configure settings](configuration.md)
- [Set up Telegram](telegram-setup.md)
- [Add your first channel](channels.md)
