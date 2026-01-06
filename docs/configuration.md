# Configuration Reference

Complete reference for all Printarr configuration options.

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `PRINTARR_TELEGRAM_API_ID` | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `PRINTARR_TELEGRAM_API_HASH` | Telegram API Hash |

### Server

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_PORT` | 3333 | Web UI port |
| `PRINTARR_HOST` | 0.0.0.0 | Bind address |
| `PRINTARR_LOG_LEVEL` | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `PRINTARR_DEBUG` | false | Enable debug mode |

### Telegram

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_TELEGRAM_RATE_LIMIT_RPM` | 30 | Max API requests per minute (10-100) |
| `PRINTARR_TELEGRAM_CHANNEL_SPACING` | 2.0 | Seconds between same-channel requests |
| `PRINTARR_SYNC_ENABLED` | true | Enable live monitoring |
| `PRINTARR_SYNC_POLL_INTERVAL` | 300 | Catch-up sync interval in seconds |
| `PRINTARR_SYNC_BATCH_SIZE` | 100 | Messages per sync batch |

### Downloads

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_MAX_CONCURRENT_DOWNLOADS` | 2 | Simultaneous downloads (1-10) |
| `PRINTARR_LIBRARY_TEMPLATE` | `{designer}/{title}` | Library folder structure |

### Google Drive

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_GOOGLE_CLIENT_ID` | - | OAuth Client ID |
| `PRINTARR_GOOGLE_CLIENT_SECRET` | - | OAuth Client Secret |
| `PRINTARR_GOOGLE_API_KEY` | - | API key (public folders only) |
| `PRINTARR_GOOGLE_REDIRECT_URI` | - | Custom OAuth redirect URI |
| `PRINTARR_GOOGLE_REQUEST_DELAY` | 0.5 | Seconds between API requests |
| `PRINTARR_GOOGLE_REQUESTS_PER_MINUTE` | 60 | Rate limit for Google API |

### Uploads

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_UPLOAD_MAX_SIZE_MB` | 500 | Maximum upload file size |
| `PRINTARR_UPLOAD_RETENTION_HOURS` | 24 | Hours to keep unprocessed uploads |

### Rendering

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_AUTO_QUEUE_RENDER_AFTER_IMPORT` | true | Auto-queue STL preview renders |
| `PRINTARR_AUTO_QUEUE_RENDER_PRIORITY` | -1 | Priority for auto-renders (-10 to 10) |

### Integrations

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTARR_FLARESOLVERR_URL` | - | FlareSolverr URL for Thangs |

## Library Template Variables

Use these variables in `PRINTARR_LIBRARY_TEMPLATE`:

| Variable | Description | Example |
|----------|-------------|---------|
| `{designer}` | Designer/creator name | `FlexiFactory` |
| `{channel}` | Source channel name | `FlexiFactorySTL` |
| `{title}` | Design title | `Flexi Dragon` |
| `{date}` | Post date (YYYY-MM-DD) | `2024-01-15` |
| `{year}` | Post year | `2024` |
| `{month}` | Post month | `01` |

### Example Templates

```bash
# By designer and title (default)
PRINTARR_LIBRARY_TEMPLATE="{designer}/{title}"
# Result: /library/FlexiFactory/Flexi Dragon/

# By channel with date
PRINTARR_LIBRARY_TEMPLATE="{channel}/{date}-{title}"
# Result: /library/FlexiFactorySTL/2024-01-15-Flexi Dragon/

# Organized by year
PRINTARR_LIBRARY_TEMPLATE="{year}/{designer}/{title}"
# Result: /library/2024/FlexiFactory/Flexi Dragon/
```

## Volume Mounts

| Container Path | Purpose | Notes |
|----------------|---------|-------|
| `/config` | Database, Telegram session, settings | Persistent, backup recommended |
| `/data` | Uploads, internal state | Persistent |
| `/staging` | Download/extraction workspace | Can be tmpfs for speed |
| `/library` | Organized 3D model library | Your main storage |
| `/cache` | Thumbnails and previews | Regeneratable |
| `/watch/*` | Bulk import folders | Read-only recommended |

## Settings UI

Many settings can also be configured via **Settings** in the web UI:

- Telegram connection status and rate limiting
- Download concurrency and library template
- Google Drive OAuth connection
- Auto-render preferences
- Sync/monitoring settings

Settings configured in the UI are stored in the database and override environment variable defaults.

## Example Configurations

### Minimal Setup

```yaml
environment:
  - PRINTARR_TELEGRAM_API_ID=12345678
  - PRINTARR_TELEGRAM_API_HASH=abcdef1234567890
```

### Full Featured

```yaml
environment:
  - PRINTARR_TELEGRAM_API_ID=12345678
  - PRINTARR_TELEGRAM_API_HASH=abcdef1234567890
  - PRINTARR_LOG_LEVEL=INFO
  - PRINTARR_MAX_CONCURRENT_DOWNLOADS=3
  - PRINTARR_LIBRARY_TEMPLATE={designer}/{title}
  - PRINTARR_FLARESOLVERR_URL=http://flaresolverr:8191/v1
  - PRINTARR_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
  - PRINTARR_GOOGLE_CLIENT_SECRET=xxx
  - PRINTARR_SYNC_ENABLED=true
  - PRINTARR_SYNC_POLL_INTERVAL=300
  - PRINTARR_AUTO_QUEUE_RENDER_AFTER_IMPORT=true
```

### High-Volume Setup

```yaml
environment:
  - PRINTARR_TELEGRAM_API_ID=12345678
  - PRINTARR_TELEGRAM_API_HASH=abcdef1234567890
  - PRINTARR_MAX_CONCURRENT_DOWNLOADS=5
  - PRINTARR_TELEGRAM_RATE_LIMIT_RPM=20  # Lower to avoid rate limits
  - PRINTARR_TELEGRAM_CHANNEL_SPACING=3.0
  - PRINTARR_SYNC_BATCH_SIZE=50  # Smaller batches
```
